#!/usr/bin/env python3
"""Run one-pass T01-T12 PA benchmark matrix for all current routing candidates.

This fills missing cells in the HTML report. It uses judge-free validators from the
existing wave1/wave2 runners and writes JSONL + per-cell artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
RUN_ID = os.environ.get('BENCH_RUN_ID') or datetime.now().strftime('%Y%m%d-%H%M%S-t01-t12-full-matrix')
ARTIFACT_ROOT = SCRIPTS_DIR.parent / 'artifacts' / RUN_ID
RESULTS = ARTIFACT_ROOT / 'results.jsonl'
SUMMARY = ARTIFACT_ROOT / 'summary.json'
BASE = 'http://localhost:11434/api/chat'
sys.path.append(str(SCRIPTS_DIR))
from model_prompt_profiles import profile_for_model
from benchmark_manifest import build_manifest, claim_run_root, write_manifest
from benchmark_transport import ProviderProcessError, ProviderResult, classify_exception, parse_hermes_response, parse_ollama_response, result_checks
from benchmark_trials import complete_trial_coverage, make_schedule, progress_snapshot, summarize_trials
from legacy_t_matrix import wave1 as w1
from legacy_t_matrix import wave2 as w2

MODELS = [
    {'tag': 'gpt-5.5', 'label': 'gpt55', 'provider': 'hermes', 'tier': 'primary'},
    {'tag': 'kimi-k2.6:cloud', 'label': 'kimi26', 'provider': 'ollama', 'tier': 'cloud'},
    {'tag': 'deepseek-v4-pro:cloud', 'label': 'v4pro', 'provider': 'ollama', 'tier': 'cloud'},
    {'tag': 'nemotron-3-ultra:cloud', 'label': 'nemotron', 'provider': 'ollama', 'tier': 'cloud'},
    {'tag': 'qwen3.5:35b-a3b-coding-nvfp4', 'label': 'qwen35_coding', 'provider': 'ollama', 'tier': 'local'},
    {'tag': 'qwen3-coder:480b-cloud', 'label': 'qwen3_coder_480b', 'provider': 'ollama', 'tier': 'cloud_coding'},
    {'tag': 'kimi-k2.7-code:cloud', 'label': 'kimi_k27_code', 'provider': 'ollama', 'tier': 'cloud_coding'},
    {'tag': 'gemma4:31b-cloud', 'label': 'gemma4', 'provider': 'ollama', 'tier': 'cloud'},
    {'tag': 'glm-5.2:cloud', 'label': 'glm52', 'provider': 'ollama', 'tier': 'cloud_candidate'},
    {'tag': 'mistral-large-3:675b-cloud', 'label': 'mistral_large3', 'provider': 'ollama', 'tier': 'heavy_cloud'},
    {'tag': 'mistral-small3.2:24b', 'label': 'mistral_local24', 'provider': 'ollama', 'tier': 'local'},
]
TASKS = [
    {'id': 'T01', 'key': 't1_brief', 'parts': ['t1_brief']},
    {'id': 'T02', 'key': 't2_longctx', 'parts': ['t2_longctx']},
    {'id': 'T03', 'key': 't3_coding', 'parts': ['t3_coding']},
    {'id': 'T04', 'key': 't4_email_de', 'parts': ['t4_email_de']},
    {'id': 'T05', 'key': 't5_triage', 'parts': ['t5_triage']},
    {'id': 'T06', 'key': 'synthetic_fixture_smoke', 'parts': ['t1_real', 't4_real']},
    {'id': 'T07', 'key': 't7_multiturn', 'parts': ['t7_multiturn']},
    {'id': 'T08', 'key': 't8_reasoning', 'parts': ['t8_reasoning']},
    {'id': 'T09', 'key': 't9_coding_complex', 'parts': ['t9_coding_complex_turn1', 't9_coding_complex_turn2', 't9_coding_complex_turn3']},
    {'id': 'T10', 'key': 't10_skill_instruction_adherence', 'parts': ['t10_skill_instruction_adherence']},
    {'id': 'T11', 'key': 't11_health_architecture_bugfix', 'parts': ['t11_health_architecture_bugfix']},
    {'id': 'T12', 'key': 't12_domain_import_skill_routing', 'parts': ['t12_domain_import_skill_routing']},
]



@dataclass
class Cell:
    run_id: str
    canonical_id: str
    task: str
    part: str
    model_tag: str
    model_label: str
    status: str
    started_at: str
    finished_at: str
    elapsed_s: float = 0.0
    error: str = ''
    response_text: str = ''
    validators: dict[str, Any] = field(default_factory=dict)
    weighted_score: float = 0.0
    hard_fails: list[str] = field(default_factory=list)
    dims: dict[str, float] = field(default_factory=dict)
    artifact_path: str = ''


def ts() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def call_ollama(model: str, messages: list[dict[str, str]], num_predict: int = 1200, timeout_s: int = 600) -> ProviderResult:
    profile = profile_for_model(model)
    msgs = list(messages)
    if not msgs or msgs[0].get('role') != 'system':
        msgs = [{'role': 'system', 'content': profile.system_prompt()}] + msgs
    payload = {
        'model': model,
        'messages': msgs,
        'stream': False,
        'keep_alive': '30m',
        'options': {'num_predict': num_predict, **profile.options},
    }
    payload.update(profile.top_level)
    req = urllib.request.Request(BASE, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode())
    return parse_ollama_response(model, data, payload=payload)


def call_hermes(model: str, prompt: str, timeout_s: int = 420) -> ProviderResult:
    profile = profile_for_model(model)
    effective_prompt = profile.system_prompt() + '\n\nTASK:\n' + prompt
    cmd = ['hermes', 'chat', '-Q', '--max-turns', '3', '--provider', 'openai-codex', '-m', model, '-t', '', '-q', effective_prompt]
    r = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_s)
    if r.returncode != 0:
        raise ProviderProcessError((r.stderr or r.stdout or '').strip()[-1000:])
    return parse_hermes_response(model, r.stdout or '', provider='openai-codex', max_turns=3)


def prompt_for(part: str) -> str:
    if part == 't1_brief':
        return w2.FIXTURE_T1
    if part == 't2_longctx':
        return w1.fixture_t2_longctx()
    if part == 't3_coding':
        return w2.FIXTURE_T3
    if part == 't4_email_de':
        return w2.FIXTURE_T4
    if part == 't5_triage':
        return w1.fixture_t5_triage()
    if part == 't1_real':
        return w2.FIXTURE_T1
    if part == 't4_real':
        return w2.FIXTURE_T4
    if part == 't8_reasoning':
        return w2.FIXTURE_T8
    if part == 't9_coding_complex_turn1':
        return w2.FIXTURE_T9_TURN1
    if part == 't9_coding_complex_turn2':
        return w2.FIXTURE_T9_TURN2
    if part == 't9_coding_complex_turn3':
        return w2.FIXTURE_T9_TURN3
    if part == 't10_skill_instruction_adherence':
        return w2.FIXTURE_T10
    if part == 't11_health_architecture_bugfix':
        return w2.FIXTURE_T11
    if part == 't12_domain_import_skill_routing':
        return w2.FIXTURE_T12
    raise KeyError(part)


def validate_and_score(part: str, text: str) -> tuple[dict[str, Any], float, list[str], dict[str, float]]:
    if part == 't2_longctx':
        v = w1.validate_t2_longctx(text)
        score, fails, dims = w1.score_cell('t2_longctx', v, text)
        return v, score, fails, dims
    if part == 't5_triage':
        v = w1.validate_t5_triage(text)
        score, fails, dims = w1.score_cell('t5_triage', v, text)
        return v, score, fails, dims
    scorer_part = part
    validator_part = part
    if part == 't7_multiturn':
        validator_part = 't1_brief'
    elif part == 't1_real':
        validator_part = 't1_brief'
    elif part == 't4_real':
        validator_part = 't4_email_de'
    v = w2.VALIDATORS[validator_part](text)
    score, fails, dims = w2.score_cell(scorer_part, v, text)
    return v, score, fails, dims


def run_part(model: dict[str, Any], canonical_id: str, task_key: str, part: str, context_messages: list[dict[str, str]] | None = None, trial_index: int = 1) -> tuple[Cell, list[dict[str, str]] | None]:
    start = time.time()
    started = ts()
    response = ''
    status = 'ok'
    error = ''
    new_context = context_messages
    provider_result: ProviderResult | None = None
    try:
        if part == 't7_multiturn':
            if model['provider'] == 'ollama':
                r1 = call_ollama(model['tag'], [{'role': 'user', 'content': w2.FIXTURE_T7_TURN1}], num_predict=80, timeout_s=300)
                if r1.incomplete_reason:
                    provider_result = r1
                    response = r1.content
                else:
                    msgs = [{'role': 'user', 'content': w2.FIXTURE_T7_TURN1}, {'role': 'assistant', 'content': r1.content}, {'role': 'user', 'content': w2.FIXTURE_T7_TURN2}]
                    provider_result = call_ollama(model['tag'], msgs, num_predict=500, timeout_s=420)
                    response = provider_result.content
            else:
                # Hermes one-shot cannot safely reuse a temp session without polluting current routing;
                # use an explicit transcript prompt and mark as hermes-simulated multiturn in validators artifact.
                provider_result = call_hermes(model['tag'], w2.FIXTURE_T7_TURN1 + "\n\nASSISTANT: VERSTANDEN\n\nUSER: " + w2.FIXTURE_T7_TURN2, timeout_s=420)
                response = provider_result.content
        else:
            p = prompt_for(part)
            if model['provider'] == 'ollama':
                # For t9 parts, carry prior turns for actual multi-turn coherence.
                msgs = list(context_messages or [])
                msgs.append({'role': 'user', 'content': p})
                provider_result = call_ollama(model['tag'], msgs, num_predict=w2.TASK_CONFIG.get(part, {}).get('num_predict', 1200), timeout_s=600)
                response = provider_result.content
                new_context = msgs + [{'role': 'assistant', 'content': response}]
            else:
                if part.startswith('t9_coding_complex') and context_messages:
                    transcript = '\n\n'.join(f"{m['role'].upper()}: {m['content']}" for m in context_messages)
                    p = transcript + '\n\nUSER: ' + p
                provider_result = call_hermes(model['tag'], p, timeout_s=600)
                response = provider_result.content
                new_context = (context_messages or []) + [{'role': 'user', 'content': p}, {'role': 'assistant', 'content': response}]
        if provider_result and provider_result.incomplete_reason:
            status = 'incomplete'
            validators = result_checks(provider_result)
            score, fails, dims = 0.0, [provider_result.incomplete_reason], {}
        else:
            validators, score, fails, dims = validate_and_score(part, response)
            if provider_result:
                validators.update(result_checks(provider_result))
                if provider_result.evidence_failure:
                    status = 'unverified'
                    fails = sorted(set([*fails, provider_result.evidence_failure]))
    except Exception as e:
        failure = classify_exception(e)
        status = 'error'
        error = str(e)[-1000:]
        validators, score, fails, dims = {'failure_class': failure}, 0.0, [failure], {}
    finished = ts()
    elapsed = time.time() - start
    cell = Cell(
        run_id=RUN_ID, canonical_id=canonical_id, task=task_key, part=part,
        model_tag=model['tag'], model_label=model['label'], status=status,
        started_at=started, finished_at=finished, elapsed_s=round(elapsed, 3),
        error=error, response_text=response, validators=validators,
        weighted_score=round(score, 4), hard_fails=fails, dims=dims,
    )
    profile = profile_for_model(model['tag']) if model['provider'] == 'ollama' else profile_for_model(model['tag'])
    cell.validators = {**cell.validators, 'prompt_profile': profile.name, 'prompt_guide': profile.guide, 'runtime_options': profile.options, 'runtime_top_level': profile.top_level, 'trial_index': trial_index}
    outdir = ARTIFACT_ROOT / canonical_id / model['label'] / f'trial-{trial_index:03d}' / part
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / 'cell.json'
    cell.artifact_path = str(path)
    path.write_text(json.dumps(asdict(cell), indent=2, ensure_ascii=False))
    with RESULTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(asdict(cell), ensure_ascii=False) + '\n')
    print(f"{canonical_id} {part} {model['label']} {status} score={cell.weighted_score} fails={fails} elapsed={elapsed:.1f}s", flush=True)
    return cell, new_context


def aggregate(cells: list[Cell], *, expected_repeats: int = 1) -> dict[str, Any]:
    by_model: dict[str, list[Cell]] = {}
    by_task: dict[str, list[Cell]] = {}
    for c in cells:
        by_model.setdefault(c.model_tag, []).append(c)
        by_task.setdefault(c.canonical_id, []).append(c)
    def summarize(items: list[Cell], *, expected: int, coverage_complete: bool) -> dict[str, Any]:
        ok = [c for c in items if c.status == 'ok']
        fails = sorted({f for c in items for f in c.hard_fails})
        stats = summarize_trials([c.weighted_score for c in items], passed=[c.status == 'ok' and not c.hard_fails for c in items], expected_trials=expected)
        return {
            'parts': len(items), 'ok': len(ok),
            'status_counts': {status: sum(c.status == status for c in items) for status in sorted({c.status for c in items})},
            'avg_score': round(sum(c.weighted_score for c in ok) / len(ok), 4) if ok else 0.0,
            'hard_fails': sum(len(c.hard_fails) for c in items),
            'fail_types': fails,
            'coverage_complete': coverage_complete,
            'trial_statistics': stats,
            'lane_eligible': coverage_complete and bool(stats['eligible']) and not fails,
        }
    model_summaries = {}
    for model, items in by_model.items():
        coverage = complete_trial_coverage(
            ((c.canonical_id, int(c.validators.get('trial_index', 1))) for c in items),
            task_ids=(task['id'] for task in TASKS), repeats=expected_repeats,
        )
        model_summaries[model] = summarize(items, expected=len(TASKS) * expected_repeats, coverage_complete=coverage)
    task_summaries = {}
    for task_id, items in by_task.items():
        actual = [(c.model_tag, int(c.validators.get('trial_index', 1))) for c in items]
        expected_pairs = {(model['tag'], trial) for model in MODELS for trial in range(1, expected_repeats + 1)}
        coverage = len(actual) == len(set(actual)) and set(actual) == expected_pairs
        task_summaries[task_id] = summarize(items, expected=len(MODELS) * expected_repeats, coverage_complete=coverage)
    return {
        'run_id': RUN_ID,
        'created_at': ts(),
        'models': MODELS,
        'tasks': TASKS,
        'by_model': model_summaries,
        'by_task': task_summaries,
    }


def self_test() -> int:
    assert prompt_for('t1_brief') == w2.FIXTURE_T1
    assert prompt_for('t2_longctx') == w1.fixture_t2_longctx()
    validators = w2.VALIDATORS['t1_brief']('{}')
    assert isinstance(validators, dict)
    print(json.dumps({'self_test': 'pass', 'fixture_source': 'scripts/legacy_t_matrix', 'model_calls': 0}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--run-order', choices=['balanced', 'random', 'fixed'], default='balanced')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    claim_run_root(ARTIFACT_ROOT)
    write_manifest(ARTIFACT_ROOT, build_manifest(run_id=RUN_ID, models=[m['tag'] for m in MODELS], task_payload=TASKS, source_paths=[Path(__file__), SCRIPTS_DIR / 'legacy_t_matrix' / 'wave1.py', SCRIPTS_DIR / 'legacy_t_matrix' / 'wave2.py'], repeats=args.repeats, seed=args.seed, run_order=args.run_order, privacy_class='synthetic', argv=sys.argv, model_routes={model['tag']: model['provider'] for model in MODELS}))
    cells: list[Cell] = []
    model_by_tag = {model['tag']: model for model in MODELS}
    task_by_id = {task['id']: task for task in TASKS}
    schedule = make_schedule(list(model_by_tag), list(task_by_id), repeats=args.repeats, seed=args.seed, order=args.run_order)
    for trial in schedule:
        model = model_by_tag[trial.model]
        task = task_by_id[trial.task_id]
        print(f"\n=== {task['id']} MODEL {model['label']} / {model['tag']} TRIAL {trial.trial_index} ===", flush=True)
        ctx: list[dict[str, str]] | None = []
        part_cells: list[Cell] = []
        for part in task['parts']:
            cell, ctx = run_part(model, task['id'], task['key'], part, context_messages=ctx, trial_index=trial.trial_index)
            part_cells.append(cell)
        if len(part_cells) > 1:
            ok = [c for c in part_cells if c.status == 'ok']
            agg = Cell(
                run_id=RUN_ID, canonical_id=task['id'], task=task['key'], part='aggregate',
                model_tag=model['tag'], model_label=model['label'], status='ok' if len(ok) == len(part_cells) else 'partial',
                started_at=part_cells[0].started_at, finished_at=part_cells[-1].finished_at,
                elapsed_s=round(sum(c.elapsed_s for c in part_cells), 3),
                response_text='', validators={'parts': [c.part for c in part_cells], 'trial_index': trial.trial_index},
                weighted_score=round(sum(c.weighted_score for c in ok) / len(ok), 4) if ok else 0.0,
                hard_fails=sorted({failure for c in part_cells for failure in c.hard_fails}), dims={},
            )
            outdir = ARTIFACT_ROOT / task['id'] / model['label'] / f'trial-{trial.trial_index:03d}' / 'aggregate'
            outdir.mkdir(parents=True, exist_ok=True)
            path = outdir / 'cell.json'
            agg.artifact_path = str(path)
            path.write_text(json.dumps(asdict(agg), indent=2, ensure_ascii=False))
            with RESULTS.open('a', encoding='utf-8') as result_file:
                result_file.write(json.dumps(asdict(agg), ensure_ascii=False) + '\n')
            cells.append(agg)
        else:
            cells.extend(part_cells)
        progress = progress_snapshot(schedule, [(cell.model_tag, cell.status == 'ok' and not cell.hard_fails) for cell in cells])
        print(f"progress={json.dumps(progress, separators=(',', ':'))}", flush=True)
    summary = aggregate(cells, expected_repeats=args.repeats)
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print('\nSUMMARY', json.dumps({'run_id': RUN_ID, 'artifact_root': str(ARTIFACT_ROOT)}, indent=2), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
