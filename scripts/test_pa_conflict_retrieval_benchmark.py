#!/usr/bin/env python3
"""Self-tests for the PA generic conflict-retrieval benchmark runner."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name('pa_conflict_retrieval_benchmark.py')


def load_module():
    spec = importlib.util.spec_from_file_location('pa_conflict_retrieval_benchmark', SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_conflict_pack_is_generic_and_has_expected_lanes():
    m = load_module()
    tasks = m.task_list()
    ids = [t.id for t in tasks]
    assert ids == [f'F{i:02d}' for i in range(1, 11)]
    assert len(ids) == len(set(ids))

    assert {t.lane for t in tasks} == {
        'finance_latest_allocation',
        'finance_statement_reconciliation',
        'health_stale_vs_current_readiness',
        'health_source_priority',
        'work_deadline_priority',
        'external_communication_approval',
        'project_decision_supersession',
        'trading_config_vs_intent',
        'document_revision_conflict',
        'retrieval_uncertainty_boundary',
    }
    assert all(t.critical for t in tasks)


def test_finance_latest_allocation_validator_rejects_scaled_stale_plan():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'F01')
    good = json.dumps({
        'answer': 'Use the latest target: Core Equity 450, Bonds 200, Gold 100, Cash Reserve 50.',
        'selected_source': 'Source B latest target from 2026-06-15.',
        'rejected_sources': ['Reject Source A because it is the older 600 plan and should not be scaled.'],
        'calculation_check': '450+200+100+50=800; 56.25+25+12.5+6.25=100.',
        'guardrail': 'Debt/liquidity remains a separate guardrail, not the allocation answer.'
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []

    bad = json.dumps({
        'answer': 'Scale old plan to Core Equity 400, Bonds 200, Gold 133.33, Cash Reserve 66.67.',
        'selected_source': 'Source A older plan.',
        'rejected_sources': [],
        'calculation_check': 'Sums to 800.',
        'guardrail': 'Looks fine.'
    })
    score, fails, checks = m.validate(task, bad)
    assert 'selected_stale_source' in fails
    assert 'scaled_stale_plan' in fails
    assert score <= 0.45


def test_health_readiness_validator_requires_stale_current_distinction():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'F03')
    good = json.dumps({
        'answer': 'Recommend recovery or light training, not hard intervals.',
        'selected_source': 'Source B latest current check-in with sleep 5h50 and elevated resting HR.',
        'rejected_sources': ['Reject Source A yesterday green readiness because it is stale.'],
        'calculation_check': 'Resting HR is +8 vs baseline and sleep 5h50 is below target.',
        'guardrail': 'Non-medical advice; reassess with fresh wearable data.'
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_gate_fails_on_any_critical_hard_fail(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        hard_fails = ['selected_stale_source'] if task.id == 'F01' else []
        score = 0.82 if task.id == 'F01' else 1.0
        cells.append(m.Cell(
            run_id='gate-test', task_id=task.id, lane=task.lane, weight=task.weight,
            model_tag='test-model', model_label='test_model', provider='test',
            status='ok', score=score, hard_fails=hard_fails,
        ))
    data = m.summarize('gate-test', tmp_path, tasks, cells, expected_repeats=2)
    assert data['ranking'][0]['coverage'] == f'{len(tasks)}/{len(tasks) * 2}'
    assert data['ranking'][0]['weighted_score'] > 0.9
    assert data['ranking'][0]['conflict_gate'] == 'fail'
    assert data['ranking'][0]['critical_hard_fails'] == 1


def test_task_filter_selects_requested_cases_only():
    m = load_module()
    selected = m.select_tasks('F01,F03')
    assert [t.id for t in selected] == ['F01', 'F03']


def test_self_test_passes():
    m = load_module()
    assert m.self_test() == 0
