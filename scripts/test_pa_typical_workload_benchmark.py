#!/usr/bin/env python3
"""Self-tests for the PA typical workload benchmark runner."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name('pa_typical_workload_benchmark.py')


def load_module():
    spec = importlib.util.spec_from_file_location('pa_typical_workload_benchmark', SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_task_pack_has_expected_typical_workload_lanes():
    m = load_module()
    tasks = m.task_list()
    ids = [t.id for t in tasks]
    assert sorted(ids) == [f'W{i:02d}' for i in range(1, 22)]
    assert len(ids) == len(set(ids))
    lanes = {t.lane for t in tasks}
    assert {
        'daily_brief_prioritization',
        'obs_tldr_handoff',
        'skill_routing_and_context_loading',
        'health_human_in_loop_coaching',
        'mail_triage_action_classification',
        'coding_change_plan_from_handoff',
        'ad_hoc_web_research',
        'world_information_lookup',
        'external_document_update_plan',
        'world_correlation_analysis',
        'trade_strategy_review',
        'daily_brief_creation',
        'rss_summary_creation',
        'ad_hoc_document_analysis',
        'finance_memory_conflict_retrieval',
    } <= lanes


def test_human_in_loop_health_accepts_light_recovery_without_conservative_keyword():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'W04')
    text = """[Readiness]
Not ready for hard training.
[Evidence]
Sleep is 6h05, HRV is stale/partial after 02:00, resting HR is elevated, and heavy lower-body work was yesterday.
[Recommendation]
Do light recovery: easy walk, mobility, upper-body technique, or Zone 1/2 only. Avoid max efforts and heavy lower-body work.
[Human Check]
The user makes the final decision and may cross-check Google Health AI and Bevel AI.
[Next Check]
Reassess after better sleep and refreshed wearable data."""
    score, fails, checks = m.validate(task, text)
    assert score == 1.0
    assert fails == []


def test_obs_tldr_validator_requires_handoff_artifacts_and_next_actions():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'W02')
    good = """# Session TL;DR
[[2026-06-26]]

## Summary
- Implemented benchmark extension.

## Evidence and Artifacts
- Report: /tmp/report.md
- Tests: py_compile pass

## Decisions
- Keep broad PA routing unchanged.

## Open Items / Next Actions
- [ ] Run qwen3-coder follow-up.

## Handoff Notes
- Backup path recorded."""
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_json_contract_rejects_fenced_output():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'W05')
    text = '```json\n{"items": []}\n```'
    score, fails, checks = m.validate(task, text)
    assert 'forbidden_code_fences' in fails
    assert score <= 0.45


def test_hermes_max_iteration_warning_keeps_content_but_fails_closed():
    m = load_module()
    raw = """⚠️  Reached maximum iterations (3). Requesting summary...
{"ok": true, "value": "kept"}

session_id: 20260626_dummy"""
    result = m.parse_hermes_response('gpt-5.5', raw, provider='openai-codex', max_turns=3)
    assert result.content == '{"ok": true, "value": "kept"}'
    assert result.incomplete_reason == 'max_iterations_reached'


def test_self_test_passes():
    m = load_module()
    assert m.self_test() == 0


def test_finance_conflict_retrieval_prefers_latest_800_plan_over_scaled_600_split():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'W21')
    good = json.dumps({
        'answer': 'Use latest Evidence B: Gold 100, Global Equity 400, Europe Equity 100, Bonds 150, Emerging Markets 50.',
        'evidence_used': ['Evidence B is the latest EUR 800 action target.'],
        'rejected_source': ['Do not scale the older EUR 600 implemented split.'],
        'calculation_check': '100+400+100+150+50=800 and 12.5+50+12.5+18.75+6.25=100.',
        'finance_guardrail': 'Debt paydown remains a separate guardrail, but the requested allocation is the fund plan.'
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []

    bad = json.dumps({
        'answer': 'Scale the old 600 plan: Gold 160, Global Equity 320, Europe Equity 80, bonds 160, Emerging Markets 80.',
        'evidence_used': ['Evidence A'],
        'rejected_source': [],
        'calculation_check': 'Sums to 800.',
        'finance_guardrail': 'Debt paydown reminder.'
    })
    score, fails, checks = m.validate(task, bad)
    assert 'scaled_old_600_split' in fails
    assert 'missing_global_equity_400' in fails
    assert score <= 0.82


def test_typical_gate_fails_when_critical_task_has_hard_fail(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        hard_fails = ['missing_reject_scaling'] if task.id == 'W21' else []
        score = 0.82 if task.id == 'W21' else 1.0
        cells.append(m.Cell(
            run_id='critical-gate-test',
            task_id=task.id,
            lane=task.lane,
            weight=task.weight,
            model_tag='test-model',
            model_label='test_model',
            provider='test',
            status='ok',
            score=score,
            hard_fails=hard_fails,
        ))

    data = m.summarize('critical-gate-test', tmp_path, tasks, cells, expected_repeats=2)

    assert data['ranking'][0]['coverage'] == f'{len(tasks)}/{len(tasks) * 2}'
    assert data['ranking'][0]['weighted_score'] > 0.82
    assert data['ranking'][0]['typical_workload_gate'] == 'fail'
    assert data['ranking'][0]['critical_hard_fails'] == 1
