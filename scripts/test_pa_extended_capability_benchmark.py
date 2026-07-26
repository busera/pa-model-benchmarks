#!/usr/bin/env python3
"""Self-tests for the PA extended capability benchmark runner."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name('pa_extended_capability_benchmark.py')


def load_module():
    spec = importlib.util.spec_from_file_location('pa_extended_capability_benchmark', SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extended_pack_has_expected_capability_lanes():
    m = load_module()
    tasks = m.task_list()
    ids = [t.id for t in tasks]
    assert ids == [f'X{i:02d}' for i in range(1, 19)]
    lanes = {t.lane for t in tasks}
    assert {
        'vision_image_interpretation',
        'diagram_generation_mermaid_excalidraw_chart',
        'professional_html_report',
        'html_presentation_theme_graphs_animation',
        'data_processing_db_csv_xlsx_export',
        'job_application_packet',
        'websearch_analysis_plan',
        'weekly_spending_report_quality',
        'weekly_nutrition_report_quality',
        'skill_instruction_execution',
        'cron_job_execution',
        'non_confidential_skill_routing_matrix',
        'public_content_skill_execution',
        'vault_learning_skill_execution',
        'reading_intelligence_skill_execution',
        'pa_governance_maintenance_skill_execution',
        'travel_packing_skill_execution',
        'memory_housekeeping_contradiction_scan',
    } == lanes


def test_vision_prompt_does_not_leak_expected_objects_and_hermes_route_fails_closed():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X01')
    prompt = task.prompt.lower()
    assert 'red square' not in prompt
    assert 'blue circle' not in prompt
    assert 'green triangle' not in prompt
    try:
        m.call_hermes('gpt-5.5', task)
    except RuntimeError as exc:
        assert 'does not attach the generated image' in str(exc)
    else:
        raise AssertionError('text-only Hermes route must not receive a vision score')


def test_vision_validator_accepts_correct_json_answer():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X01')
    text = json.dumps({
        'objects': ['red square', 'blue circle', 'green triangle'],
        'chart_reading': 'The image contains three labeled shapes and the title Mini Vision Test.',
        'uncertainty': 'No uncertainty.'
    })
    score, fails, checks = m.validate(task, text)
    assert score == 1.0
    assert fails == []


def test_diagram_validator_requires_mermaid_excalidraw_and_chart_spec():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X02')
    good = json.dumps({
        'mermaid': 'flowchart TD\nA[Inbox]-->B[Classifier]\nB-->C[Report]',
        'excalidraw': {'type': 'excalidraw', 'elements': [{'type': 'rectangle'}, {'type': 'arrow'}]},
        'tailored_chart_spec': {'chart_type': 'bar', 'x_axis': 'model', 'y_axis': 'score', 'series': [{'name': 'score', 'values': [1, 2]}]},
        'notes': 'Tailored for model benchmark reporting.'
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({'mermaid': 'flowchart TD; A-->B'})
    score, fails, checks = m.validate(task, bad)
    assert 'schema_mismatch' in fails
    assert score <= 0.45


def test_html_report_validator_requires_self_contained_professional_html():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X03')
    html = '''<!doctype html><html><head><style>
    body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#f6f8fb;color:#172033}
    .card{border:1px solid #d9e2ef;border-radius:12px;padding:16px}
    </style></head><body><main><section class="hero"><h1>Model Report</h1></section><section class="card"><h2>Ranking evidence</h2><table><tr><th>Model</th></tr><tr><td>qwen 0.91</td></tr><tr><td>gemma 0.86</td></tr><tr><td>mistral 0.74</td></tr></table></section></main></body></html>'''
    score, fails, checks = m.validate(task, html)
    assert score == 1.0
    assert fails == []


def test_data_processing_validator_rejects_destructive_or_lossy_sql():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X05')
    good = json.dumps({
        'duckdb_sql': 'SELECT account_id, SUM(amount) AS total FROM read_csv_auto(?) GROUP BY account_id',
        'sqlite_sql': 'SELECT id, name FROM applications WHERE status = ?',
        'csv_plan': ['read with explicit encoding', 'validate delimiter and row count'],
        'xlsx_plan': ['read all sheets', 'preserve formulas as values plus metadata'],
        'export_plan': ['write parquet and csv with manifest'],
        'table_integrity_checks': ['row count before/after', 'column count', 'null audit', 'no truncation']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({
        'duckdb_sql': 'DROP TABLE records',
        'sqlite_sql': 'DELETE FROM applications',
        'csv_plan': [], 'xlsx_plan': [], 'export_plan': [], 'table_integrity_checks': []
    })
    score, fails, checks = m.validate(task, bad)
    assert 'destructive_sql' in fails
    assert score <= 0.45


def test_self_test_passes():
    m = load_module()
    assert m.self_test() == 0



def test_weekly_spending_report_validator_rewards_accuracy_completeness_and_actions():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X08')
    good = json.dumps({
        'quality_score': 0.86,
        'accuracy_findings': [
            'Week total is 0.00 EUR with 0 transactions, so do not imply new weekly spend drove the MTD overspend.',
            'Liquid cash should be 42,000 EUR, not 4200 EUR.',
            'Synthetic tax payment is due 2026-09-15, not Q4/27.'
        ],
        'completeness_gaps': ['Import is stale at 2026-06-24 for the synthetic report.', 'Explain MTD overspend separately from week activity.'],
        'improved_recommendations': ['Keep non-essential spending pause because MTD is 121.4% of paced budget.', 'Refresh transactions before treating the zero-spend week as final.'],
        'risk_flags': ['Do not overstate budget runway because remaining baseline is negative and runway is n/a.'],
        'rewrite_outline': ['Executive TLDR', 'Data freshness caveat', 'Week vs MTD split', 'Cash/tax obligation check', 'Specific next actions']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({'quality_score': 1, 'accuracy_findings': [], 'completeness_gaps': [], 'improved_recommendations': ['looks good'], 'risk_flags': [], 'rewrite_outline': []})
    score, fails, checks = m.validate(task, bad)
    assert 'missing_cash_correction' in fails
    assert 'missing_data_freshness' in fails
    assert score < 0.8


def test_weekly_nutrition_report_validator_rewards_actionable_grounded_health_quality():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X09')
    good = json.dumps({
        'quality_score': 0.88,
        'accuracy_findings': ['Calories averaged 2200 kcal, above the 2050 kcal ceiling on 5/7 days.', 'Observed maintenance center is 2000 kcal, so the safer decision input is +200 kcal/day.', 'Protein target was hit on 5/7 days.'],
        'completeness_gaps': ['Hydration averaged 1100ml vs 2400ml target.', 'Vitamin D, potassium, zinc, magnesium, folate, and calcium are below 80% RDA.', 'CGM coverage is missing for the report week and uses one older event only.'],
        'improved_recommendations': ['Replace the sweetened soy beverage / latte sugar source.', 'Add one repeat fiber default such as beans/green beans/multigrain bread.', 'Use a 4 x 600ml bottle plan.'],
        'risk_flags': ['Do not diagnose from CGM or correlations.', 'Fix duplicate numbering 1. 1) in priority actions.', 'Do not infer causality from Fiber to HRV correlation.'],
        'rewrite_outline': ['TLDR', 'Targets vs actuals', 'Evidence caveats', 'Top three behavior changes', 'Next experiment']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({'quality_score': 1, 'accuracy_findings': ['healthy week'], 'completeness_gaps': [], 'improved_recommendations': [], 'risk_flags': [], 'rewrite_outline': []})
    score, fails, checks = m.validate(task, bad)
    assert 'missing_calorie_ceiling' in fails
    assert 'missing_hydration_gap' in fails
    assert 'missing_no_diagnosis_caveat' in fails
    assert score < 0.8


def test_skill_instruction_execution_validator_requires_real_tool_and_skill_steps():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X10')
    good = json.dumps({
        'skills_to_load': ['ollama-local-benchmarking', 'test-driven-development', 'code-agent'],
        'context_to_read': ['current benchmark script', 'test file', 'attached weekly spending report', 'attached weekly nutrition report'],
        'tool_sequence': ['skill_view for matching skills', 'read_file attached reports', 'write failing pytest tests', 'terminal pytest to verify RED', 'patch implementation', 'terminal py_compile and pytest', 'update manifest/report if a run is executed'],
        'execution_boundaries': ['do not send external messages', 'backup existing scripts before edit', 'do not delete models', 'ask approval before destructive changes'],
        'verification': ['pytest targeted tests pass', 'self-test pass', 'py_compile pass', 'report new task IDs X08-X11'],
        'artifact_updates': ['benchmark runner tasks', 'self-test samples', 'extended suite documentation']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({'skills_to_load': [], 'context_to_read': [], 'tool_sequence': ['I would inspect files later'], 'execution_boundaries': [], 'verification': [], 'artifact_updates': []})
    score, fails, checks = m.validate(task, bad)
    assert 'missing_skill_view' in fails
    assert 'missing_read_file' in fails
    assert 'missing_test_execution' in fails
    assert score < 0.8


def test_cron_job_execution_validator_requires_scheduler_safety_and_delivery_semantics():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X11')
    good = json.dumps({
        'job_design': ['self-contained prompt', 'no recursive cron scheduling', 'origin delivery unless the user asks otherwise'],
        'schedule_and_delivery': ['create with schedule 0 9 * * *', 'deliver origin', 'timezone/date included in prompt'],
        'script_no_agent_decision': ['use no_agent only when script stdout is final message', 'empty stdout means silent', 'non-zero exit sends error alert'],
        'safety_checks': ['cronjob list before remove or update', 'never guess job_id', 'no destructive action without approval'],
        'verification': ['cronjob list after create/update', 'manual run if requested', 'check delivered artifact/log output']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({'job_design': ['schedule another cron from inside the job'], 'schedule_and_delivery': [], 'script_no_agent_decision': [], 'safety_checks': ['remove old job'], 'verification': []})
    score, fails, checks = m.validate(task, bad)
    assert 'missing_list_before_remove' in fails
    assert 'recursive_cron_risk' in fails
    assert 'missing_no_agent_stdout_semantics' in fails
    assert score < 0.8



def test_non_confidential_skill_routing_matrix_validator_covers_selected_custom_skills():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X12')
    good = json.dumps({
        'included_skills': ['html-report', 'humanizer', 'goodlinks', 'podcast_summaries', 'games', 'packinglist', 'smart-reading', 'rss-daily-brief', 'obs_summarize', 'obs_tldr', 'obsidian-medium-export', 'skill-doctor', 'docs-sync', 'pa-config-audit', 'project-governance', 'backlog'],
        'excluded_sensitive_skills': ['health', 'finance', 'trade', 'kraken', 'gunbot', 'mail-triage', 'relationship'],
        'routing_table': [{'request': 'polished report', 'skill': 'html-report'}, {'request': 'reading queue', 'skill': 'goodlinks'}],
        'simplification_rules': ['use synthetic/public placeholders', 'no personal data or secrets'],
        'evaluation_dimensions': ['skill selection accuracy', 'execution order', 'verification', 'privacy boundaries']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_public_content_skill_execution_validator_checks_artifact_quality_and_no_external_send():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X13')
    good = json.dumps({
        'skills_to_use': ['html-report', 'humanizer', 'obsidian-medium-export'],
        'input_contract': ['public draft excerpt only', 'audience and tone constraints'],
        'execution_steps': ['load skill', 'draft polished HTML report', 'humanize copy', 'export Medium-ready HTML'],
        'quality_checks': ['self-contained HTML', 'no AI tells', 'links/assets verified'],
        'privacy_controls': ['no external publish or send without approval', 'no local paths or secrets']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_vault_learning_skill_execution_validator_checks_day_links_and_study_artifacts():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X14')
    good = json.dumps({
        'skills_to_use': ['obs_summarize', 'obs_tldr', 'obsidian-sr-anki-export', 'vault-readout'],
        'input_contract': ['source note excerpt', 'target date 2026-06-28'],
        'execution_steps': ['create summary note with H1', 'add [[2026-06-28]] body wikilink', 'extract flashcards', 'prepare readout chunks'],
        'quality_checks': ['relative links resolve', 'flashcard format valid', 'source facts separated from inferences'],
        'privacy_controls': ['vault-local only', 'no external upload']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_reading_intelligence_skill_execution_validator_checks_source_freshness_and_queueing():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X15')
    good = json.dumps({
        'skills_to_use': ['goodlinks', 'smart-reading', 'rss-daily-brief', 'podcast_summaries', 'games'],
        'input_contract': ['public RSS items', 'public podcast episode', 'public game page'],
        'execution_steps': ['triage reading queue', 'summarize source with freshness', 'push selected item to GoodLinks', 'produce concise recommendation'],
        'quality_checks': ['source URL retained', 'freshness caveat', 'no invented citations'],
        'privacy_controls': ['public-source only', 'no account secrets']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_pa_governance_maintenance_skill_execution_validator_checks_safe_change_control():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X16')
    good = json.dumps({
        'skills_to_use': ['docs-sync', 'pa-config-audit', 'skill-doctor', 'project-governance', 'backlog', 'change-management'],
        'input_contract': ['synthetic config excerpt', 'synthetic backlog card'],
        'execution_steps': ['inspect current state', 'backup before edit', 'patch scoped docs/config', 'record change-management evidence'],
        'quality_checks': ['no stale paths', 'tests or dry-run pass', 'diff reviewed'],
        'privacy_controls': ['redact secrets', 'no destructive delete']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_travel_packing_skill_execution_validator_checks_operational_plan_without_booking_fabrication():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X17')
    good = json.dumps({
        'skills_to_use': ['packinglist', 'travel-management', 'tripsy-travel-management'],
        'input_contract': ['destination, dates, weather/heat, crowd constraints; no booking confirmations provided'],
        'execution_steps': ['build packing list', 'create operational travel plan', 'stage Tripsy records only when coordinates/bookings are known'],
        'quality_checks': ['vegetarian/pescatarian meal safety', 'water/grocery logistics', 'heat/crowd plan'],
        'privacy_controls': ['do not invent booking codes', 'do not publish itinerary externally']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_memory_housekeeping_validator_checks_contradiction_fallback_and_ipkb_closeout():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == 'X18')
    good = json.dumps({
        'skills_to_load': ['memory-housekeeping', 'pa-memory', 'skill-doctor', 'incident'],
        'source_context': ['memory_housekeeping.py', 'test_memory_housekeeping.py', 'memory_housekeeping.log', 'contradictions.log', 'IPKB issues and KB entries'],
        'diagnosis_steps': ['reproduce OpenAI 429 and local Ollama timeout signatures', 'inventory installed local Ollama models excluding embedding and cloud tags', 'probe qwen3.6:27b-mlx-bf16 with think=false JSON'],
        'fallback_model_policy': ['local-only fallback models', 'exclude embedding models and cloud tags', 'unique fallback slots', 'cold-start tolerant timeout'],
        'log_noise_policy': ['provider-attempt failures are INFO while fallback continues', 'only exhausted scans should WARNING or ERROR', 'preserve Resolved Findings ledger'],
        'verification': ['py_compile modified files', 'pytest focused and full memory-housekeeping tests', 'run Skill Doctor log scanner clean', 'archive/reset polluted production log'],
        'ipkb_updates': ['update or close issue records', 'create durable-fix KB', 'rebuild registers', 'incident audit --skip-change-management PASS']
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    bad = json.dumps({'skills_to_load': [], 'source_context': [], 'diagnosis_steps': [], 'fallback_model_policy': ['use any available model'], 'log_noise_policy': [], 'verification': [], 'ipkb_updates': []})
    score, fails, checks = m.validate(task, bad)
    assert 'missing_memory_housekeeping_skill' in fails
    assert 'missing_local_only_fallback' in fails
    assert 'missing_ipkb_registers' in fails
    assert score < 0.8


def test_select_tasks_filters_by_task_ids_and_rejects_unknown_ids():
    m = load_module()
    selected = m.select_tasks(m.task_list(), ['X18'])
    assert [t.id for t in selected] == ['X18']
    try:
        m.select_tasks(m.task_list(), ['X99'])
    except SystemExit as exc:
        assert 'Unknown task id' in str(exc)
    else:
        raise AssertionError('expected SystemExit for unknown task id')
