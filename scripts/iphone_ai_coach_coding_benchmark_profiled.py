#!/usr/bin/env python3
"""Dedicated coding benchmark for future iPhone app and AI Coach work.

Runs repo-shaped coding tasks against candidate models, reconstructs returned files in
isolated workspaces, executes Swift/Python validation, writes JSONL artifacts, and
updates a standalone HTML report.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUN_ID = datetime.now().strftime('%Y%m%d-%H%M%S-iphone-ai-coach-coding')
ARTIFACT_ROOT = BASE_DIR / 'artifacts' / RUN_ID
RESULTS = ARTIFACT_ROOT / 'results.jsonl'
SUMMARY = ARTIFACT_ROOT / 'summary.json'
HTML_REPORT = ARTIFACT_ROOT / 'report.html'
PYTHON = sys.executable
OLLAMA_URL = 'http://localhost:11434/api/chat'
SCRIPTS_DIR = BASE_DIR / 'scripts'
sys.path.append(str(SCRIPTS_DIR))
from model_prompt_profiles import profile_for_model

MODELS = [
    {'key': 'gpt55', 'label': 'gpt-5.5', 'provider': 'hermes', 'tag': 'gpt-5.5', 'role': 'frontier lead/reviewer'},
    {'key': 'kimi26', 'label': 'kimi-k2.6:cloud', 'provider': 'ollama', 'tag': 'kimi-k2.6:cloud', 'role': 'current PA fallback'},
    {'key': 'v4pro', 'label': 'deepseek-v4-pro:cloud', 'provider': 'ollama', 'tag': 'deepseek-v4-pro:cloud', 'role': 'cloud fallback'},
    {'key': 'nemotron', 'label': 'nemotron-3-ultra:cloud', 'provider': 'ollama', 'tag': 'nemotron-3-ultra:cloud', 'role': 'German/long-context specialist'},
    {'key': 'qwen35_local', 'label': 'qwen3.5:35b-a3b-coding-nvfp4', 'provider': 'ollama', 'tag': 'qwen3.5:35b-a3b-coding-nvfp4', 'role': 'local/private executor'},
    {'key': 'qwen3_coder_480b', 'label': 'qwen3-coder:480b-cloud', 'provider': 'ollama', 'tag': 'qwen3-coder:480b-cloud', 'role': 'coding specialist challenger'},
    {'key': 'kimi_k27_code', 'label': 'kimi-k2.7-code:cloud', 'provider': 'ollama', 'tag': 'kimi-k2.7-code:cloud', 'role': 'coding specialist challenger'},
    {'key': 'gemma4', 'label': 'gemma4:31b-cloud', 'provider': 'ollama', 'tag': 'gemma4:31b-cloud', 'role': 'multimodal/coding challenger'},
    {'key': 'glm52', 'label': 'glm-5.2:cloud', 'provider': 'ollama', 'tag': 'glm-5.2:cloud', 'role': 'long-horizon coding watchlist'},
    {'key': 'mistral_large3', 'label': 'mistral-large-3:675b-cloud', 'provider': 'ollama', 'tag': 'mistral-large-3:675b-cloud', 'role': 'heavy cloud challenger'},
    {'key': 'mistral_local24', 'label': 'mistral-small3.2:24b', 'provider': 'ollama', 'tag': 'mistral-small3.2:24b', 'role': 'local control'},
]
SYSTEM = """You are in a strict coding benchmark. Return exactly one JSON object, no markdown, no code fences.
Schema: {"files": {"path.ext": "complete file content"}, "notes": "brief implementation notes"}.
Do not include explanations outside JSON. Implement production-quality, testable code with safety boundaries."""

TASKS = [
    {
        'id': 'C01',
        'name': 'SwiftUI health coach card',
        'criticality': 'high',
        'language': 'Swift',
        'expected': ['HealthCoachCard.swift'],
        'prompt': """Implement HealthCoachCard.swift for an iPhone AI Coach app.
Requirements:
- Use Swift and SwiftUI.
- Define HealthCoachMetric: Identifiable, Equatable with id, name, value, unit, source, measuredAtISO, freshnessLabel, isStale.
- Define HealthCoachCardViewModel: ObservableObject with @Published metrics and headline.
- Include a static previewSample() with at least Apple Watch activity, FoodNoms protein, Withings weight, and Google Health/Fitbit fallback steps.
- Add source/freshness labeling in the UI so stale or fallback data is visible.
- Define HealthCoachCard: View that renders headline plus metric rows.
- No networking, no HealthKit writes, no hardcoded secrets.
Return JSON with files only.""",
    },
    {
        'id': 'C02',
        'name': 'iPhone foreground TCP export parser',
        'criticality': 'high',
        'language': 'Swift',
        'expected': ['HealthAutoExportParser.swift'],
        'prompt': """Implement HealthAutoExportParser.swift for a synthetic user's iPhone Health Auto Export foreground TCP flow.
Requirements:
- Pure Swift standard library/Foundation only; no networking required.
- Define ParsedHealthExport: Equatable with metric, value: Double, unit, source, measuredAtISO, receivedAtISO, freshnessLabel.
- Implement parseHealthAutoExportLine(_ line: String, receivedAtISO: String) throws -> ParsedHealthExport.
- Input line format: metric|value|unit|source|measuredAtISO . Trim whitespace.
- Reject malformed lines, empty fields, and non-numeric values with clear thrown errors.
- Freshness labels: same date as receivedAtISO => fresh; older date => stale; invalid date string => unknown.
- Preserve source exactly; do not relabel Google Health/Fitbit as Apple Health.
Return JSON with files only.""",
    },
    {
        'id': 'C03',
        'name': 'AI Coach source priority resolver',
        'criticality': 'critical',
        'language': 'Python',
        'expected': ['health_source_resolver.py'],
        'prompt': """Implement health_source_resolver.py for the AI Coach.
Requirements:
- Python stdlib only.
- Define choose_metric(candidates: list[dict], metric: str, current_date: str) -> dict.
- Candidates contain metric, value, unit, source, measured_date.
- Source priority for activity/workout: Apple Watch/Apple Health first, then Withings where relevant, then Google Health/Fitbit as additive fallback only.
- Nutrition source of truth is FoodNoms; Google Health must not override nutrition.
- Return a copy of the selected candidate with added fields freshness_label and reason.
- freshness_label is fresh if measured_date == current_date, stale if older, unknown if missing/invalid.
- If only fallback source exists, return it with reason containing "fallback".
- If no candidates for the metric, raise ValueError.
Return JSON with files only.""",
    },
    {
        'id': 'C04',
        'name': 'Health DuckDB migration safety planner',
        'criticality': 'critical',
        'language': 'Python',
        'expected': ['health_migration_plan.py'],
        'prompt': """Implement health_migration_plan.py for safe AI Coach database changes.
Requirements:
- Python stdlib only.
- Define build_migration_plan(db_path: str, target_table: str, columns: dict[str, str], write_allowed: bool) -> dict.
- Refuse writes to health.duckdb unless write_allowed is true and target_table starts with pa_ or bridge_.
- Always include backup_path ending with .bak-YYYYMMDD-HHMMSS.
- SQL may CREATE TABLE IF NOT EXISTS or ALTER TABLE ADD COLUMN IF NOT EXISTS only.
- Never emit DROP, DELETE, UPDATE, INSERT, TRUNCATE, or ALTER TABLE DROP.
- Validate column names/types defensively with simple allowlists.
- Return dict with db_path, backup_path, sql_statements, warnings.
Return JSON with files only.""",
    },
    {
        'id': 'C05',
        'name': 'Test failure recovery plan',
        'criticality': 'high',
        'language': 'JSON/patch planning',
        'expected': [],
        'prompt': """A coding agent attempted an AI Coach source resolver and got this pytest failure:

FAILED test_google_health_does_not_override_foodnoms
E AssertionError: assert 'Google Health' == 'FoodNoms'
Input candidates included FoodNoms protein for today's date and Google Health protein for today's date.

Return exactly JSON with this schema:
{"root_cause": str, "fix_strategy": [str], "tests_to_add": [str], "verification_commands": [str], "risk_notes": [str]}
The answer must explicitly protect FoodNoms as nutrition source of truth, label Google Health/Fitbit as fallback/additive, and include pytest verification. No code fences.""",
    },
]

SWIFT_C02_TEST = r'''
import Foundation

let fresh = try parseHealthAutoExportLine("steps|1234|count|Google Health/Fitbit|2026-06-14T08:00:00Z", receivedAtISO: "2026-06-14T09:00:00Z")
assert(fresh.metric == "steps")
assert(fresh.value == 1234)
assert(fresh.source == "Google Health/Fitbit")
assert(fresh.freshnessLabel == "fresh")
let stale = try parseHealthAutoExportLine("protein|150|g|FoodNoms|2026-06-13T20:00:00Z", receivedAtISO: "2026-06-14T09:00:00Z")
assert(stale.freshnessLabel == "stale")
do {
    _ = try parseHealthAutoExportLine("bad|line", receivedAtISO: "2026-06-14T09:00:00Z")
    assertionFailure("Expected malformed input to throw")
} catch { }
'''

PY_C03_TEST = r'''
import pytest
from health_source_resolver import choose_metric


def test_foodnoms_beats_google_health_for_nutrition():
    candidates = [
        {"metric": "protein", "value": 130, "unit": "g", "source": "Google Health/Fitbit", "measured_date": "2026-06-14"},
        {"metric": "protein", "value": 150, "unit": "g", "source": "FoodNoms", "measured_date": "2026-06-14"},
    ]
    selected = choose_metric(candidates, "protein", "2026-06-14")
    assert selected["source"] == "FoodNoms"
    assert selected["freshness_label"] == "fresh"
    assert "FoodNoms" in selected["reason"]


def test_google_health_is_labeled_fallback_for_activity_when_alone():
    selected = choose_metric([
        {"metric": "steps", "value": 9000, "unit": "count", "source": "Google Health/Fitbit", "measured_date": "2026-06-13"}
    ], "steps", "2026-06-14")
    assert selected["source"] == "Google Health/Fitbit"
    assert selected["freshness_label"] == "stale"
    assert "fallback" in selected["reason"].lower()


def test_apple_watch_beats_google_health_for_activity():
    selected = choose_metric([
        {"metric": "steps", "value": 9000, "unit": "count", "source": "Google Health/Fitbit", "measured_date": "2026-06-14"},
        {"metric": "steps", "value": 8700, "unit": "count", "source": "Apple Watch", "measured_date": "2026-06-14"},
    ], "steps", "2026-06-14")
    assert selected["source"] == "Apple Watch"


def test_missing_metric_raises():
    with pytest.raises(ValueError):
        choose_metric([], "steps", "2026-06-14")
'''

PY_C04_TEST = r'''
import re
import pytest
from health_migration_plan import build_migration_plan


def test_refuses_health_duckdb_without_write_flag():
    with pytest.raises(PermissionError):
        build_migration_plan("/tmp/health.duckdb", "pa_health_scores", {"score": "DOUBLE"}, False)


def test_builds_safe_bridge_plan():
    plan = build_migration_plan("/tmp/health_bridge.duckdb", "pa_health_scores", {"score": "DOUBLE", "source": "TEXT"}, True)
    assert plan["backup_path"].startswith("/tmp/health_bridge.duckdb.bak-")
    joined = "\n".join(plan["sql_statements"]).upper()
    assert "CREATE TABLE IF NOT EXISTS" in joined
    assert "ALTER TABLE" in joined
    assert not re.search(r"\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE)\b", joined)


def test_rejects_unsafe_table_and_column_names():
    with pytest.raises(ValueError):
        build_migration_plan("/tmp/health_bridge.duckdb", "records_clean", {"score": "DOUBLE"}, True)
    with pytest.raises(ValueError):
        build_migration_plan("/tmp/health_bridge.duckdb", "pa_scores", {"bad-name": "DOUBLE"}, True)
    with pytest.raises(ValueError):
        build_migration_plan("/tmp/health_bridge.duckdb", "pa_scores", {"score": "DROP TABLE"}, True)
'''

@dataclass
class Result:
    run_id: str
    task_id: str
    task_name: str
    criticality: str
    model_key: str
    model_label: str
    status: str
    score: float
    hard_fails: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0
    response_text: str = ''
    workspace: str = ''
    error: str = ''


def call_ollama(model: str, prompt: str, timeout: int = 900) -> str:
    profile = profile_for_model(model)
    system = profile.system_prompt() + '\n\n' + SYSTEM
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
        'stream': False,
        'options': {'num_predict': 2200, **profile.options},
    }
    payload.update(profile.top_level)
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return data.get('message', {}).get('content', '') or data.get('response', '') or ''


def call_hermes(model: str, prompt: str, timeout: int = 900) -> str:
    full_prompt = SYSTEM + '\n\nUSER TASK:\n' + prompt
    cmd = ['hermes', 'chat', '-Q', '--provider', 'openai-codex', '-m', model, '-t', '', '-q', full_prompt]
    r = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or '')[-1200:])
    out = (r.stdout or '').strip()
    # Hermes may prepend session_id; strip it if present.
    lines = out.splitlines()
    if lines and lines[0].startswith('session_id:'):
        out = '\n'.join(lines[1:]).strip()
    return out


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    s = text.strip()
    if s.startswith('```'):
        return None, 'forbidden_code_fences'
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            return None, 'json_not_object'
        return obj, None
    except Exception:
        m = re.search(r'\{.*\}', s, re.S)
        if not m:
            return None, 'json_invalid'
        try:
            return json.loads(m.group(0)), 'json_extracted_not_exact'
        except Exception:
            return None, 'json_invalid'


def write_workspace(task: dict[str, Any], model: dict[str, str], obj: dict[str, Any]) -> Path:
    ws = ARTIFACT_ROOT / 'workspaces' / task['id'] / model['key']
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    files = obj.get('files') if isinstance(obj, dict) else None
    if not isinstance(files, dict):
        return ws
    for rel, content in files.items():
        if '..' in rel or rel.startswith('/'):
            continue
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding='utf-8')
    return ws


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout[-3000:], r.stderr[-3000:]


def validate(task: dict[str, Any], obj: dict[str, Any] | None, parse_warning: str | None, ws: Path) -> tuple[float, list[str], dict[str, Any]]:
    fails: list[str] = []
    checks: dict[str, Any] = {}
    if obj is None:
        return 0.0, [parse_warning or 'json_invalid'], {}
    if parse_warning:
        fails.append(parse_warning)
    tid = task['id']
    files = obj.get('files')
    if tid != 'C05' and not isinstance(files, dict):
        fails.append('missing_files_object')
        files = {}
    elif tid == 'C05' and not isinstance(files, dict):
        files = {}
    for exp in task['expected']:
        if exp not in files:
            fails.append(f'missing_{exp}')
    tid = task['id']
    if tid == 'C01':
        p = ws / 'HealthCoachCard.swift'
        text = p.read_text() if p.exists() else ''
        checks['has_swiftui'] = 'import SwiftUI' in text
        checks['has_observable'] = 'ObservableObject' in text and '@Published' in text
        checks['has_sources'] = all(x in text for x in ['Apple Watch', 'FoodNoms', 'Withings']) and ('Google Health' in text or 'Fitbit' in text)
        checks['has_freshness'] = 'freshnessLabel' in text and 'isStale' in text
        rc, out, err = run_cmd(['swiftc', '-typecheck', str(p)], ws) if p.exists() else (1, '', 'missing')
        checks['swift_typecheck_rc'] = rc
        if rc != 0: fails.append('swift_typecheck_failed')
        for k in ['has_swiftui','has_observable','has_sources','has_freshness']:
            if not checks[k]: fails.append(k + '_false')
    elif tid == 'C02':
        p = ws / 'HealthAutoExportParser.swift'
        # Swift permits top-level executable assertions only in a file named main.swift
        # when compiling multiple files together.
        test = ws / 'main.swift'
        test.write_text(SWIFT_C02_TEST)
        rc, out, err = run_cmd(['swiftc', str(p), str(test), '-o', str(ws/'parser_test')], ws) if p.exists() else (1, '', 'missing')
        checks['swift_compile_rc'] = rc
        if rc == 0:
            rc2, out2, err2 = run_cmd([str(ws/'parser_test')], ws)
            checks['swift_run_rc'] = rc2
            if rc2 != 0: fails.append('swift_tests_failed')
        else:
            fails.append('swift_compile_failed')
        text = p.read_text() if p.exists() else ''
        checks['preserves_google_source'] = 'Google Health' not in text or 'Apple Health' in text  # weak static only
        checks['has_freshness_logic'] = all(x in text.lower() for x in ['fresh', 'stale', 'unknown'])
        if not checks['has_freshness_logic']: fails.append('missing_freshness_logic')
    elif tid == 'C03':
        (ws/'test_health_source_resolver.py').write_text(PY_C03_TEST)
        rc, out, err = run_cmd([PYTHON, '-m', 'pytest', '-q'], ws)
        checks['pytest_rc'] = rc; checks['pytest_stdout'] = out; checks['pytest_stderr'] = err
        if rc != 0: fails.append('pytest_failed')
        text = (ws/'health_source_resolver.py').read_text() if (ws/'health_source_resolver.py').exists() else ''
        if 'FoodNoms' not in text: fails.append('missing_foodnoms_guardrail')
        if not ('fallback' in text.lower() and ('Google Health' in text or 'Fitbit' in text)): fails.append('missing_google_fallback_label')
    elif tid == 'C04':
        (ws/'test_health_migration_plan.py').write_text(PY_C04_TEST)
        rc, out, err = run_cmd([PYTHON, '-m', 'pytest', '-q'], ws)
        checks['pytest_rc'] = rc; checks['pytest_stdout'] = out; checks['pytest_stderr'] = err
        if rc != 0: fails.append('pytest_failed')
        text = (ws/'health_migration_plan.py').read_text() if (ws/'health_migration_plan.py').exists() else ''
        forbidden = re.search(r'\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE)\b', text, re.I)
        checks['no_forbidden_sql_words_in_source'] = forbidden is None
        if forbidden: fails.append('forbidden_sql_word_in_source')
    elif tid == 'C05':
        req = ['root_cause','fix_strategy','tests_to_add','verification_commands','risk_notes']
        for key in req:
            if key not in obj: fails.append(f'missing_{key}')
        blob = json.dumps(obj).lower()
        if 'foodnoms' not in blob: fails.append('missing_foodnoms')
        if 'fallback' not in blob and 'additive' not in blob: fails.append('missing_fallback_additive')
        if 'pytest' not in blob: fails.append('missing_pytest_verification')
    # Score: contract 0.25, executable/tests 0.45, safety/domain 0.30 approximated by fail count.
    if not fails:
        return 1.0, [], checks
    penalty = min(0.9, 0.18 * len(set(fails)))
    return round(max(0.05, 1.0 - penalty), 4), fails, checks


def run_cell(task: dict[str, Any], model: dict[str, str]) -> Result:
    start = time.time()
    response = ''
    status = 'ok'
    err = ''
    ws = ARTIFACT_ROOT / 'workspaces' / task['id'] / model['key']
    try:
        if model['provider'] == 'hermes':
            response = call_hermes(model['tag'], task['prompt'])
        else:
            response = call_ollama(model['tag'], task['prompt'])
        obj, warning = parse_json_object(response)
        ws = write_workspace(task, model, obj or {})
        score, fails, checks = validate(task, obj, warning, ws)
    except Exception as exc:
        status = 'error'
        err = str(exc)[-1000:]
        score, fails, checks = 0.0, ['runtime_error'], {}
    res = Result(RUN_ID, task['id'], task['name'], task['criticality'], model['key'], model['label'], status, score, fails, checks, round(time.time()-start,3), response, str(ws), err)
    profile = profile_for_model(model['tag'])
    res.checks = {**res.checks, 'prompt_profile': profile.name, 'prompt_guide': profile.guide, 'runtime_options': profile.options, 'runtime_top_level': profile.top_level}
    outdir = ARTIFACT_ROOT / task['id'] / model['key']
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir/'cell.json').write_text(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    with RESULTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(asdict(res), ensure_ascii=False) + '\n')
    print(f"{task['id']} {model['label']}: {score:.3f} fails={len(fails)}", flush=True)
    return res


def summarize(results: list[Result]) -> dict[str, Any]:
    by_model: dict[str, list[Result]] = {}
    for r in results:
        by_model.setdefault(r.model_label, []).append(r)
    ranking = []
    critical_weights = {'critical': 1.4, 'high': 1.1, 'medium': 1.0}
    for label, rows in by_model.items():
        denom = sum(critical_weights.get(r.criticality, 1.0) for r in rows)
        score = sum(r.score * critical_weights.get(r.criticality, 1.0) for r in rows) / denom if denom else 0
        ranking.append({'model': label, 'weighted_score': round(score,4), 'mean_score': round(sum(r.score for r in rows)/len(rows),4), 'hard_fails': sum(len(r.hard_fails) for r in rows), 'runtime_errors': sum(1 for r in rows if r.status == 'error')})
    ranking.sort(key=lambda x: (-x['weighted_score'], x['hard_fails']))
    data = {'run_id': RUN_ID, 'created_at': datetime.now().astimezone().isoformat(timespec='seconds'), 'artifact_root': str(ARTIFACT_ROOT), 'models': MODELS, 'tasks': TASKS, 'ranking': ranking, 'results': [asdict(r) for r in results]}
    SUMMARY.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def write_html(summary: dict[str, Any]) -> None:
    rows = summary['results']
    models = [m['label'] for m in MODELS]
    tasks = TASKS
    cell = {(r['task_id'], r['model_label']): r for r in rows}
    def pill(score: float) -> str:
        cls = 'good' if score >= .85 else 'mid' if score >= .65 else 'bad'
        return f'<span class="pill {cls}">{score:.3f}</span>'
    parts = [f'''<!doctype html><html><head><meta charset="utf-8"><title>iPhone / AI Coach Coding Benchmark</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;background:#f6f8fb;color:#172033}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d9e2ef;padding:8px;vertical-align:top}}th{{background:#eaf1fb}}.card{{background:white;border:1px solid #d9e2ef;border-radius:12px;padding:16px;margin:14px 0}}.pill{{border-radius:999px;padding:3px 8px;font-weight:700}}.good{{background:#d8f5df;color:#145c2a}}.mid{{background:#fff0c2;color:#744d00}}.bad{{background:#ffd9d9;color:#7a1515}}code{{background:#edf2f7;padding:2px 4px;border-radius:4px}}</style></head><body>
<h1>iPhone / AI Coach Dedicated Coding Benchmark</h1><p>Run <code>{html.escape(summary['run_id'])}</code>. Tasks cover Swift/iPhone app code, Health Auto Export parsing, AI Coach source priority, Health DuckDB migration safety, and failure recovery.</p>''']
    parts.append('<div class="card"><h2>Ranking</h2><table><tr><th>Rank</th><th>Model</th><th>Critical-weighted score</th><th>Mean</th><th>Hard-fails</th><th>Runtime errors</th></tr>')
    for i, r in enumerate(summary['ranking'], 1):
        parts.append(f"<tr><td>{i}</td><th>{html.escape(r['model'])}</th><td>{r['weighted_score']:.4f}</td><td>{r['mean_score']:.4f}</td><td>{r['hard_fails']}</td><td>{r['runtime_errors']}</td></tr>")
    parts.append('</table></div>')
    parts.append('<div class="card"><h2>Tasks × Models Matrix</h2><table><tr><th>Task</th>' + ''.join(f'<th>{html.escape(m)}</th>' for m in models) + '</tr>')
    for t in tasks:
        parts.append(f"<tr><th>{t['id']}<br>{html.escape(t['name'])}<br><small>{html.escape(t['criticality'])} · {html.escape(t['language'])}</small></th>")
        for m in models:
            r = cell.get((t['id'], m))
            if not r:
                parts.append('<td>N/R</td>')
            else:
                fails = ', '.join(r['hard_fails'][:4])
                parts.append(f"<td>{pill(float(r['score']))}<br><small>{html.escape(r['status'])}; HF {len(r['hard_fails'])}</small><br><small>{html.escape(fails)}</small></td>")
        parts.append('</tr>')
    parts.append('</table></div>')
    parts.append(f"<div class='card'><h2>Artifacts</h2><p><code>{html.escape(str(ARTIFACT_ROOT))}</code></p><p><code>{html.escape(str(SUMMARY))}</code></p></div></body></html>")
    HTML_REPORT.write_text('\n'.join(parts), encoding='utf-8')


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    for model in MODELS:
        for task in TASKS:
            results.append(run_cell(task, model))
    summary = summarize(results)
    write_html(summary)
    print(json.dumps({'run_id': RUN_ID, 'artifact_root': str(ARTIFACT_ROOT), 'html_report': str(HTML_REPORT), 'ranking': summary['ranking']}, indent=2), flush=True)

if __name__ == '__main__':
    main()
