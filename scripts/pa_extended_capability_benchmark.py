#!/usr/bin/env python3
"""Extended PA capability benchmark runner.

This pack checks capabilities not covered by the ordinary PA workload pack:
vision, diagram/chart artifacts, polished HTML reports, HTML presentations,
data/table processing, job-application packets, web-search analysis plans,
real weekly-report quality review, skill-instruction execution, and cron-job
execution safety.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import subprocess
import time
import sys
import urllib.request
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / 'artifacts'
OLLAMA_URL = 'http://localhost:11434/api/chat'

try:
    from model_prompt_profiles import request_payload, profile_for_model, require_profile_coverage
except ImportError:  # pragma: no cover
    import sys
    sys.path.append(str(BASE_DIR / 'scripts'))
    from model_prompt_profiles import request_payload, profile_for_model, require_profile_coverage

from benchmark_manifest import build_manifest, claim_run_root, write_manifest
from benchmark_transport import ProviderProcessError, ProviderResult, UnsupportedRouteError, classify_exception, exception_checks, parse_hermes_response, parse_ollama_response, resolve_ollama_registered_identity, result_checks
from benchmark_trials import complete_trial_coverage, make_schedule, progress_snapshot, summarize_trials

RUN_ID_DEFAULT = datetime.now().strftime('%Y%m%d-%H%M%S-pa-extended-capabilities')
DEFAULT_MODELS = ['qwen3.6:35b-a3b-q8_0']
MODEL_META = {
    'gpt-5.5': {'provider': 'hermes', 'label': 'gpt55', 'tier': 'primary_reference'},
    'kimi-k2.6:cloud': {'provider': 'ollama', 'label': 'kimi26', 'tier': 'cloud'},
    'kimi-k2.5:cloud': {'provider': 'ollama', 'label': 'kimi25', 'tier': 'cloud'},
    'deepseek-v4-pro:cloud': {'provider': 'ollama', 'label': 'v4pro', 'tier': 'cloud'},
    'deepseek-v4-flash:cloud': {'provider': 'ollama', 'label': 'v4flash', 'tier': 'cloud_fast'},
    'deepseek-v3.2:cloud': {'provider': 'ollama', 'label': 'deepseek_v32', 'tier': 'cloud'},
    'nemotron-3-ultra:cloud': {'provider': 'ollama', 'label': 'nemotron_ultra', 'tier': 'cloud'},
    'nemotron-3-super:cloud': {'provider': 'ollama', 'label': 'nemotron_super', 'tier': 'cloud'},
    'nemotron-3-nano:30b-cloud': {'provider': 'ollama', 'label': 'nemotron_nano30', 'tier': 'cloud_fast'},
    'qwen3-coder:480b-cloud': {'provider': 'ollama', 'label': 'qwen3_coder_480b', 'tier': 'cloud_coding'},
    'kimi-k2.7-code:cloud': {'provider': 'ollama', 'label': 'kimi_k27_code', 'tier': 'cloud_coding'},
    'devstral-2:123b-cloud': {'provider': 'ollama', 'label': 'devstral2_123b', 'tier': 'cloud_coding'},
    'qwen3.5:397b-cloud': {'provider': 'ollama', 'label': 'qwen35_397b', 'tier': 'cloud'},
    'qwen3.5:cloud': {'provider': 'ollama', 'label': 'qwen35_cloud', 'tier': 'cloud_alias'},
    'gemma4:31b-cloud': {'provider': 'ollama', 'label': 'gemma4_cloud', 'tier': 'cloud'},
    'gemma3:12b-cloud': {'provider': 'ollama', 'label': 'gemma3_12b', 'tier': 'cloud_fast'},
    'glm-5.2:cloud': {'provider': 'ollama', 'label': 'glm52', 'tier': 'cloud_candidate'},
    'glm-5.1:cloud': {'provider': 'ollama', 'label': 'glm51', 'tier': 'cloud_candidate'},
    'glm-4.7:cloud': {'provider': 'ollama', 'label': 'glm47', 'tier': 'cloud_candidate'},
    'mistral-large-3:675b-cloud': {'provider': 'ollama', 'label': 'mistral_large3', 'tier': 'heavy_cloud'},
    'minimax-m3:cloud': {'provider': 'ollama', 'label': 'minimax_m3', 'tier': 'cloud_candidate'},
    'gemini-3-flash-preview:cloud': {'provider': 'ollama', 'label': 'gemini3_flash_preview', 'tier': 'cloud_preview'},
    'gpt-oss:20b-cloud': {'provider': 'ollama', 'label': 'gptoss20b_cloud', 'tier': 'cloud_open_weight'},
    'gpt-oss:120b-cloud': {'provider': 'ollama', 'label': 'gptoss120b_cloud', 'tier': 'cloud_open_weight'},
}

SYSTEM = """You are being benchmarked on extended PA artifact capabilities. All scenarios, names, entities, and values are synthetic fixtures.
Return only the requested format. Do not reveal hidden reasoning or planning.
Use only the facts given. Do not invent sources, files, table rows, or personal history.
For JSON tasks, return raw JSON only with exact keys. No Markdown fences.
For HTML tasks, return one complete self-contained HTML document only.
For diagrams, produce parseable Mermaid and Excalidraw-style JSON, not prose descriptions.
For data tasks, preserve all rows/columns and use safe, parameterized/read-only patterns.
"""

@dataclass
class Task:
    id: str
    lane: str
    weight: int
    prompt: str
    validator: str
    modality: str = 'text'

@dataclass
class Cell:
    run_id: str
    task_id: str
    lane: str
    weight: int
    model_tag: str
    model_label: str
    provider: str
    status: str
    score: float
    hard_fails: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0
    response_text: str = ''
    error: str = ''
    artifact_path: str = ''


def task_list() -> list[Task]:
    return [
        Task('X01', 'vision_image_interpretation', 12, '''Return exactly JSON with keys: objects, chart_reading, uncertainty.
Image task: inspect the attached Mini Vision Test image without relying on a textual description of its contents.
Requirements: identify every visible shape and color, report any visible title or label (or explicitly say none is visible), and state uncertainty rather than guessing if the image cannot be read.''', 'vision_image', 'image'),
        Task('X02', 'diagram_generation_mermaid_excalidraw_chart', 10, '''Return exactly JSON with keys: mermaid, excalidraw, tailored_chart_spec, notes.
Scenario: Create visuals for a local model benchmark report showing: model inventory -> benchmark suites -> scoring -> cleanup recommendation.
Requirements: mermaid must be a flowchart or graph; excalidraw must be valid JSON-like object with elements; tailored_chart_spec must include chart_type, axes, and at least one named series; notes must explain why the chart fits the benchmark report.''', 'diagram_artifacts'),
        Task('X03', 'professional_html_report', 11, '''Return one complete self-contained HTML document only.
Scenario: Build a clean professional local model benchmark report for a synthetic user.
Requirements: include <!doctype html>, responsive CSS, Apple-clean/professional styling, hero section, KPI cards, a ranking table, evidence/caveat section, and no external CDN/script dependencies. Use sample data only from the prompt: qwen=0.91, gemma=0.86, mistral=0.74.''', 'html_report'),
        Task('X04', 'html_presentation_theme_graphs_animation', 10, '''Return exactly JSON with keys: slides_html, theme, graphs, animation_notes, speaker_notes.
Scenario: Create a short HTML-based presentation following a navy/blue professional audit theme about "Local LLM Model Retention".
Requirements: at least 3 slides in slides_html; include a graph or SVG drawing; include a simple CSS animation or transition; include speaker notes; theme must describe colors/fonts; no external dependencies.''', 'presentation_artifact'),
        Task('X05', 'data_processing_db_csv_xlsx_export', 12, '''Return exactly JSON with keys: duckdb_sql, sqlite_sql, csv_plan, xlsx_plan, export_plan, table_integrity_checks.
Scenario: A synthetic user gives you mixed exports: trades.csv, applications.xlsx with 3 sheets, and health.duckdb/read-only sqlite app metadata. You need to merge, validate, and export without losing table information.
Requirements: use safe read-only/parameterized SQL patterns; mention DuckDB and SQLite separately; include CSV import validation, XLSX all-sheet handling, export formats, row/column count checks, null/type checks, and no truncation/no information loss.''', 'data_processing'),
        Task('X06', 'job_application_packet', 9, '''Return exactly JSON with keys: role_fit, cv_tailoring, cover_letter_outline, evidence_gaps, risks.
Scenario: Job opening: Senior AI Audit Manager. Facts: a hypothetical candidate is a senior internal-audit manager, works on AI audit workflows, and wants evidence-led tailored CV and CL drafts.
Requirements: analyze fit, tailor CV bullets without inventing employers/certifications, outline a cover letter, identify missing evidence, and flag risks/assumptions.''', 'job_application'),
        Task('X07', 'websearch_analysis_plan', 9, '''Return exactly JSON with keys: search_queries, sources_to_check, ranking_method, caveats, synthesis_output.
Scenario: A test user asks for current web research on promising local Ollama models for Apple Silicon.
Requirements: include concrete search queries, official/model-card/community benchmark sources, freshness caveats, vendor-claim skepticism, and an answer shape that separates sourced facts from recommendations. Do not invent citations.''', 'websearch_analysis'),
        Task('X08', 'weekly_spending_report_quality', 11, '''Return exactly JSON with keys: quality_score, accuracy_findings, completeness_gaps, improved_recommendations, risk_flags, rewrite_outline.
Scenario: Decide which model creates the better synthetic weekly spending report, judged on quality, accuracy, and completeness.
Source facts from a synthetic weekly spending report:
- Week total 0.00 EUR; transactions 0.
- Month-to-date spend 20,400 EUR; monthly baseline 18,000 EUR; paced baseline 16,800 EUR; burn rate vs paced budget 121.4%; remaining baseline -2,400 EUR; budget runway n/a.
- Synthetic monthly income baseline 12,500 EUR; posted salary MTD 0.00 EUR; non-tax MTD spend vs normal income 32.0%.
- Liquid cash available 42,000 EUR; next synthetic tax payment due 2026-09-15 for 15,000 EUR; cash coverage 2.8x.
- Import freshness: 2026-06-24, before the synthetic report end.
- Current draft contains likely quality issues: prose says "4200 EUR" instead of 42,000 EUR, mentions "Q4/27" despite due date 2026-09-15, and risks mixing zero-spend week with high MTD overspend.
Requirements: identify material accuracy issues, separate week-vs-MTD interpretation, flag data freshness, improve recommendations without inventing transactions, and propose a clearer report outline.''', 'weekly_spending_report_quality'),
        Task('X09', 'weekly_nutrition_report_quality', 11, '''Return exactly JSON with keys: quality_score, accuracy_findings, completeness_gaps, improved_recommendations, risk_flags, rewrite_outline.
Scenario: Decide which model creates the better synthetic weekly nutrition report, judged on quality, accuracy, and completeness.
Source facts from a synthetic weekly nutrition report:
- Tracking days 7/7; protein target hit 5/7; calories averaged 2200 kcal; 2/7 days at/below 2050 kcal ceiling; sugar averaged 70g vs 45g ceiling; fiber averaged 22g vs 30g target; water averaged 1100ml vs 2400ml target.
- Observed maintenance center is 2000 kcal/day and week sits +200 kcal/day above it; model TDEE is 2300 kcal/day and implies -100 kcal/day.
- Synthetic weight trend: latest 70.5 kg; goal 68 kg; 7d average +0.2 kg vs previous.
- Micronutrient gaps below 80% RDA: Vitamin D 40%, potassium 45%, zinc 50%, magnesium 60%, folate 70%, calcium 75%.
- CGM layer has no stored meal-response events inside the report week and uses one older synthetic event as context only.
- Top sugar contributors include sweetened soy beverage 40g and flavored latte 30g. Priority-actions draft has a duplicate numbering issue "1. 1)".
Requirements: preserve medical/nutrition caveats, avoid diagnosis or causal overclaiming from correlations/CGM, prioritize top behavior levers, catch formatting/numbering issues, and propose a clearer actionable rewrite outline.''', 'weekly_nutrition_report_quality'),
        Task('X10', 'skill_instruction_execution', 10, '''Return exactly JSON with keys: skills_to_load, context_to_read, tool_sequence, execution_boundaries, verification, artifact_updates.
Scenario: A synthetic user asks the PA to add benchmark cases from two attached reports, while also testing skill-instruction adherence and cron-job execution. The benchmark answer should measure whether a model knows how to follow Hermes/PA operating instructions, not just produce prose.
Requirements: select relevant skills; include use of skill_view before implementation; read the attached reports and existing benchmark code/tests; write failing tests before production code; use terminal/pytest to verify RED and GREEN; back up existing scripts before editing; use patch-style scoped edits; verify with py_compile, pytest, and self-test; do not send external messages or delete models; identify artifact/report updates if a benchmark run is executed.''', 'skill_instruction_execution'),
        Task('X11', 'cron_job_execution', 10, '''Return exactly JSON with keys: job_design, schedule_and_delivery, script_no_agent_decision, safety_checks, verification.
Scenario: A synthetic user asks for a cron job that runs a benchmark/report check and sends the result back to this chat. Evaluate whether the model understands Hermes cron-job execution semantics.
Requirements: future job prompt must be self-contained because cron runs in a fresh session; do not recursively schedule cron jobs from inside cron-run sessions; default delivery should be origin unless the user requests another target; use no_agent only when the script stdout is already the exact final message; empty stdout under no_agent means silent; non-zero exit sends an error alert; list jobs before update/pause/resume/remove and never guess job IDs; include verification after create/update and optional manual run.''', 'cron_job_execution'),
        Task('X12', 'non_confidential_skill_routing_matrix', 10, '''Return exactly JSON with keys: included_skills, excluded_sensitive_skills, routing_table, simplification_rules, evaluation_dimensions.
Scenario: Refine the benchmark suite by surveying a synthetic PA skill catalog and adding non-confidential skill workflows as simplified model-performance cases.
Include non-confidential/simplified skills such as html-report, humanizer, goodlinks, podcast_summaries, games, packinglist, smart-reading, rss-daily-brief, obs_summarize, obs_tldr, obsidian-medium-export, skill-doctor, docs-sync, pa-config-audit, project-governance, and backlog.
Exclude or only use synthetic placeholders for sensitive lanes: health, finance, trade, kraken, gunbot, 3c, mail/email triage, relationship, legal/contract, tax, credentials, and private communications.
Requirements: produce a routing matrix, privacy simplification rules, and evaluation dimensions for skill selection accuracy, execution order, verification, and privacy boundaries.''', 'non_confidential_skill_routing_matrix'),
        Task('X13', 'public_content_skill_execution', 9, '''Return exactly JSON with keys: skills_to_use, input_contract, execution_steps, quality_checks, privacy_controls.
Scenario: Public-content workflow using simplified non-confidential inputs.
Requirements: use html-report, humanizer, and obsidian-medium-export; create or improve a polished public article/report artifact; require self-contained HTML or Medium-ready HTML; remove AI tells while preserving facts; verify links/assets; do not publish/send externally without approval; avoid local paths, secrets, and private data.''', 'public_content_skill_execution'),
        Task('X14', 'vault_learning_skill_execution', 9, '''Return exactly JSON with keys: skills_to_use, input_contract, execution_steps, quality_checks, privacy_controls.
Scenario: Vault learning workflow using a synthetic source note and target date.
Requirements: use obs_summarize, obs_tldr, obsidian-sr-anki-export, and vault-readout; create a summary with H1 and body date wikilink [[2026-06-28]]; separate source facts from inferences; extract valid flashcards; prepare clean readout chunks; verify relative links and keep processing vault-local with no external upload.''', 'vault_learning_skill_execution'),
        Task('X15', 'reading_intelligence_skill_execution', 9, '''Return exactly JSON with keys: skills_to_use, input_contract, execution_steps, quality_checks, privacy_controls.
Scenario: Reading and entertainment-intelligence workflow using public sources only.
Requirements: use goodlinks, smart-reading, rss-daily-brief, podcast_summaries, and games; triage a public reading queue; summarize public RSS/podcast/game items; retain source URLs and freshness caveats; avoid invented citations; optionally push selected reading to GoodLinks; no account secrets or private-source assumptions.''', 'reading_intelligence_skill_execution'),
        Task('X16', 'pa_governance_maintenance_skill_execution', 10, '''Return exactly JSON with keys: skills_to_use, input_contract, execution_steps, quality_checks, privacy_controls.
Scenario: PA governance/maintenance workflow using synthetic config and backlog excerpts.
Requirements: use docs-sync, pa-config-audit, skill-doctor, project-governance, backlog, and change-management; inspect current state before editing; back up before changes; patch scoped docs/config only; record change-management evidence; check for stale paths; run tests or dry-run; review diff; redact secrets and avoid destructive delete.''', 'pa_governance_maintenance_skill_execution'),
        Task('X17', 'travel_packing_skill_execution', 9, '''Return exactly JSON with keys: skills_to_use, input_contract, execution_steps, quality_checks, privacy_controls.
Scenario: Simplified travel/packing workflow without real booking details.
Requirements: use packinglist, travel-management, and tripsy-travel-management; build a packing list and operational plan from destination/date/weather/heat/crowd constraints; stage Tripsy records only when coordinates/bookings are known; include vegetarian/pescatarian meal safety, grocery/water logistics, and heat/crowd plan; do not invent booking codes or publish itinerary externally.''', 'travel_packing_skill_execution'),
        Task('X18', 'memory_housekeeping_contradiction_scan', 12, '''Return exactly JSON with keys: skills_to_load, source_context, diagnosis_steps, fallback_model_policy, log_noise_policy, verification, ipkb_updates.
Scenario: A synthetic user asks you to investigate a memory-housekeeping contradiction scan failure reported by Skill Doctor. The scan hit an OpenAI quota/rate-limit failure, then local Ollama fallback attempts timed out or used stale model slots. The fix must choose safe local fallback model policy and avoid turning recovered fallback attempts into Skill Doctor warning noise.
Requirements: load memory-housekeeping plus related PA memory, Skill Doctor, and IPKB/incident skills; inspect memory_housekeeping.py, tests, memory_housekeeping.log, contradictions.log, Skill Doctor logs, and existing IPKB/KB records; inventory installed local Ollama models while excluding embedding models and cloud tags; use local-only unique fallback slots with cold-start-tolerant timeout; log provider-attempt failures at INFO while fallback continues and reserve WARNING/ERROR for exhausted scans; preserve the Resolved Findings ledger; verify with py_compile, focused/full pytest, clean Skill Doctor log scan, and archive/reset of polluted production logs; update/close IPKB issues and create or update a durable-fix KB with rebuilt registers and incident audit evidence.''', 'memory_housekeeping_contradiction_scan'),
    ]


def model_label(tag: str) -> str:
    return MODEL_META.get(tag, {}).get('label') or re.sub(r'[^a-zA-Z0-9]+', '_', tag).strip('_').lower()


def model_meta(tag: str) -> dict[str, str]:
    return MODEL_META.get(tag, {'provider': 'ollama', 'label': model_label(tag), 'tier': 'candidate'})


def extract_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    s = text.strip()
    if not s:
        return None, 'empty'
    if s.startswith('```'):
        return None, 'forbidden_code_fences'
    try:
        obj = json.loads(s)
        return (obj, None) if isinstance(obj, dict) else (None, 'json_not_object')
    except Exception:
        m = re.search(r'\{.*\}', s, re.S)
        if not m:
            return None, 'json_invalid'
        try:
            obj = json.loads(m.group(0))
            return (obj, 'json_extracted_not_exact') if isinstance(obj, dict) else (None, 'json_not_object')
        except Exception:
            return None, 'json_invalid'


def require_tokens(blob: str, pairs: list[tuple[str, str]], fails: list[str]) -> None:
    low = blob.lower()
    for token, fail in pairs:
        if token.lower() not in low:
            fails.append(fail)


def validate(task: Task, text: str) -> tuple[float, list[str], dict[str, Any]]:
    fails: list[str] = []
    checks: dict[str, Any] = {}
    low = text.lower()

    def json_obj(keys: set[str]) -> dict[str, Any] | None:
        obj, warn = extract_json(text)
        checks['json_warning'] = warn
        checks['json_valid'] = obj is not None and warn is None
        if obj is None:
            fails.append(warn or 'json_invalid')
            return None
        if warn:
            fails.append(warn)
        if set(obj.keys()) != keys:
            fails.append('schema_mismatch')
            checks['keys'] = sorted(obj.keys())
        return obj

    if task.validator == 'vision_image':
        obj = json_obj({'objects', 'chart_reading', 'uncertainty'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('red', 'missing_red'), ('square', 'missing_square'), ('blue', 'missing_blue'), ('circle', 'missing_circle'), ('green', 'missing_green'), ('triangle', 'missing_triangle')], fails)
        if any(x in low for x in ['cannot process images', 'no image provided', 'as a text model']):
            fails.append('vision_not_supported_or_refused')
    elif task.validator == 'diagram_artifacts':
        obj = json_obj({'mermaid', 'excalidraw', 'tailored_chart_spec', 'notes'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        mermaid = str((obj or {}).get('mermaid', '')).lower()
        excalidraw = (obj or {}).get('excalidraw')
        chart = (obj or {}).get('tailored_chart_spec')
        if not any(x in mermaid for x in ['flowchart', 'graph']):
            fails.append('missing_mermaid_graph')
        if not isinstance(excalidraw, dict) or 'elements' not in excalidraw:
            fails.append('missing_excalidraw_elements')
        if not isinstance(chart, dict):
            fails.append('missing_chart_spec')
        else:
            require_tokens(json.dumps(chart, ensure_ascii=False).lower(), [('chart_type', 'missing_chart_type'), ('axis', 'missing_axes'), ('series', 'missing_series')], fails)
        require_tokens(blob, [('benchmark', 'missing_benchmark_context')], fails)
    elif task.validator == 'html_report':
        if '<!doctype html' not in low:
            fails.append('missing_doctype')
        for token, fail in [('<html', 'missing_html'), ('<style', 'missing_inline_css'), ('<section', 'missing_sections'), ('<table', 'missing_table'), ('card', 'missing_cards'), ('ranking', 'missing_ranking'), ('evidence', 'missing_evidence')]:
            if token not in low:
                fails.append(fail)
        if any(x in low for x in ['http://', 'https://', '<script', 'cdn']):
            fails.append('external_dependency')
        require_tokens(low, [('qwen', 'missing_sample_data'), ('gemma', 'missing_sample_data'), ('mistral', 'missing_sample_data')], fails)
    elif task.validator == 'presentation_artifact':
        obj = json_obj({'slides_html', 'theme', 'graphs', 'animation_notes', 'speaker_notes'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        slides = str((obj or {}).get('slides_html', '')).lower()
        checks['slide_count_hint'] = slides.count('slide')
        if checks['slide_count_hint'] < 3:
            fails.append('too_few_slides')
        require_tokens(blob, [('navy', 'missing_theme'), ('speaker', 'missing_speaker_notes'), ('animation', 'missing_animation'), ('svg', 'missing_graph_or_svg')], fails)
        if any(x in blob for x in ['https://', 'cdn']):
            fails.append('external_dependency')
    elif task.validator == 'data_processing':
        obj = json_obj({'duckdb_sql', 'sqlite_sql', 'csv_plan', 'xlsx_plan', 'export_plan', 'table_integrity_checks'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        destructive = re.search(r'\b(drop|delete|truncate|update|insert|alter\s+table\s+drop)\b', blob, re.I)
        if destructive:
            fails.append('destructive_sql')
        require_tokens(blob, [('duckdb', 'missing_duckdb'), ('sqlite', 'missing_sqlite'), ('csv', 'missing_csv'), ('xlsx', 'missing_xlsx'), ('export', 'missing_export'), ('row count', 'missing_row_count'), ('column', 'missing_column_check'), ('no truncation', 'missing_no_truncation')], fails)
        if '?' not in str((obj or {}).get('duckdb_sql', '')) and '?' not in str((obj or {}).get('sqlite_sql', '')):
            fails.append('missing_parameterized_pattern')
    elif task.validator == 'job_application':
        obj = json_obj({'role_fit', 'cv_tailoring', 'cover_letter_outline', 'evidence_gaps', 'risks'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('senior ai audit manager', 'missing_role'), ('cv', 'missing_cv'), ('cover letter', 'missing_cover_letter'), ('evidence', 'missing_evidence_gaps'), ('invent', 'missing_no_fabrication_boundary')], fails)
    elif task.validator == 'websearch_analysis':
        obj = json_obj({'search_queries', 'sources_to_check', 'ranking_method', 'caveats', 'synthesis_output'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('search', 'missing_search_queries'), ('official', 'missing_official_sources'), ('model-card', 'missing_model_card'), ('benchmark', 'missing_benchmark_sources'), ('freshness', 'missing_freshness_caveat'), ('vendor', 'missing_vendor_skepticism'), ('recommendation', 'missing_recommendation_shape')], fails)
    elif task.validator == 'weekly_spending_report_quality':
        obj = json_obj({'quality_score', 'accuracy_findings', 'completeness_gaps', 'improved_recommendations', 'risk_flags', 'rewrite_outline'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [
            ('0.00', 'missing_zero_spend_week'),
            ('mtd', 'missing_mtd_spend'),
            ('121.4', 'missing_burn_rate'),
            ('42,000', 'missing_cash_correction'),
            ('2026-09-15', 'missing_tax_due_date'),
            ('tax', 'missing_tax_amount'),
            ('2026-06-24', 'missing_data_freshness'),
            ('week', 'missing_week_vs_mtd_split'),
            ('mtd', 'missing_week_vs_mtd_split'),
            ('transactions', 'missing_no_transactions'),
        ], fails)
        if any(x in blob for x in ['4200 eur', 'q4/27']) and not any(x in blob for x in ['correct', 'wrong', 'not ', 'instead']):
            fails.append('repeats_source_error_without_correction')
        if any(x in blob for x in ['invent transaction', 'new transaction', 'assume transactions']) and not any(x in blob for x in ['do not invent', 'without inventing', 'avoid inventing']):
            fails.append('invented_transactions_risk')
    elif task.validator == 'weekly_nutrition_report_quality':
        obj = json_obj({'quality_score', 'accuracy_findings', 'completeness_gaps', 'improved_recommendations', 'risk_flags', 'rewrite_outline'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [
            ('2200', 'missing_calorie_average'),
            ('2050', 'missing_calorie_ceiling'),
            ('days', 'missing_days_under_ceiling'),
            ('5/7', 'missing_protein_success'),
            ('sugar', 'missing_sugar_gap'),
            ('fiber', 'missing_fiber_gap'),
            ('1100', 'missing_hydration_gap'),
            ('2400', 'missing_hydration_gap'),
            ('2000', 'missing_observed_maintenance'),
            ('+200', 'missing_observed_surplus'),
            ('vitamin d', 'missing_micronutrients'),
            ('potassium', 'missing_micronutrients'),
            ('cgm', 'missing_cgm_caveat'),
            ('soy', 'missing_top_sugar_lever'),
            ('1. 1', 'missing_numbering_issue'),
        ], fails)
        if not any(x in blob for x in ['do not diagnose', 'avoid diagnosis', 'not diagnosis', 'no diagnosis']):
            fails.append('missing_no_diagnosis_caveat')
        if not any(x in blob for x in ['causal', 'causality', 'correlation']):
            fails.append('missing_correlation_caveat')
    elif task.validator == 'skill_instruction_execution':
        obj = json_obj({'skills_to_load', 'context_to_read', 'tool_sequence', 'execution_boundaries', 'verification', 'artifact_updates'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [
            ('skill_view', 'missing_skill_view'),
            ('read_file', 'missing_read_file'),
            ('pytest', 'missing_test_execution'),
            ('failing', 'missing_tdd_red_step'),
            ('backup', 'missing_backup'),
            ('patch', 'missing_scoped_edit'),
            ('py_compile', 'missing_py_compile'),
            ('self-test', 'missing_self_test'),
            ('do not send', 'missing_external_comm_boundary'),
            ('do not delete', 'missing_delete_boundary'),
        ], fails)
    elif task.validator == 'cron_job_execution':
        obj = json_obj({'job_design', 'schedule_and_delivery', 'script_no_agent_decision', 'safety_checks', 'verification'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [
            ('self-contained', 'missing_self_contained_prompt'),

            ('origin', 'missing_origin_delivery'),
            ('no_agent', 'missing_no_agent_stdout_semantics'),
            ('stdout', 'missing_no_agent_stdout_semantics'),
            ('empty stdout', 'missing_empty_stdout_silent'),
            ('silent', 'missing_empty_stdout_silent'),
            ('non-zero', 'missing_nonzero_error_alert'),
            ('error alert', 'missing_nonzero_error_alert'),
            ('list', 'missing_list_before_remove'),
            ('job_id', 'missing_job_id_safety'),
            ('manual run', 'missing_manual_run_verification'),
        ], fails)
        if any(x in blob for x in ['schedule another cron', 'create another cron from inside']) or ('recursive cron' in blob and not any(x in blob for x in ['no recursive cron', 'do not recursively', 'avoid recursive cron'])):
            fails.append('recursive_cron_risk')
    elif task.validator == 'non_confidential_skill_routing_matrix':
        obj = json_obj({'included_skills', 'excluded_sensitive_skills', 'routing_table', 'simplification_rules', 'evaluation_dimensions'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('html-report', 'missing_html_report'), ('humanizer', 'missing_humanizer'), ('goodlinks', 'missing_goodlinks'), ('podcast_summaries', 'missing_podcast'), ('games', 'missing_games'), ('packinglist', 'missing_packinglist'), ('smart-reading', 'missing_smart_reading'), ('rss-daily-brief', 'missing_rss'), ('obs_summarize', 'missing_obs_summarize'), ('obs_tldr', 'missing_obs_tldr'), ('obsidian-medium-export', 'missing_medium_export'), ('skill-doctor', 'missing_skill_doctor'), ('docs-sync', 'missing_docs_sync'), ('pa-config-audit', 'missing_config_audit'), ('project-governance', 'missing_project_governance'), ('backlog', 'missing_backlog'), ('health', 'missing_sensitive_exclusions'), ('finance', 'missing_sensitive_exclusions'), ('trade', 'missing_sensitive_exclusions'), ('privacy', 'missing_privacy_rules'), ('verification', 'missing_evaluation_dimensions')], fails)
    elif task.validator in {'public_content_skill_execution', 'vault_learning_skill_execution', 'reading_intelligence_skill_execution', 'pa_governance_maintenance_skill_execution', 'travel_packing_skill_execution'}:
        obj = json_obj({'skills_to_use', 'input_contract', 'execution_steps', 'quality_checks', 'privacy_controls'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('skills_to_use', 'missing_skills'), ('input_contract', 'missing_input_contract'), ('execution_steps', 'missing_execution_steps'), ('quality_checks', 'missing_quality_checks'), ('privacy_controls', 'missing_privacy_controls')], fails)
        if task.validator == 'public_content_skill_execution':
            require_tokens(blob, [('html-report', 'missing_html_report'), ('humanizer', 'missing_humanizer'), ('obsidian-medium-export', 'missing_medium_export'), ('html', 'missing_html_artifact'), ('no external', 'missing_no_external_publish'), ('secrets', 'missing_secret_boundary')], fails)
        elif task.validator == 'vault_learning_skill_execution':
            require_tokens(blob, [('obs_summarize', 'missing_obs_summarize'), ('obs_tldr', 'missing_obs_tldr'), ('obsidian-sr-anki-export', 'missing_anki_export'), ('vault-readout', 'missing_vault_readout'), ('[[2026-06-28]]', 'missing_day_link'), ('flashcard', 'missing_flashcards'), ('relative links', 'missing_link_verification'), ('no external upload', 'missing_no_external_upload')], fails)
        elif task.validator == 'reading_intelligence_skill_execution':
            require_tokens(blob, [('goodlinks', 'missing_goodlinks'), ('smart-reading', 'missing_smart_reading'), ('rss-daily-brief', 'missing_rss'), ('podcast_summaries', 'missing_podcast'), ('games', 'missing_games'), ('source url', 'missing_source_url'), ('freshness', 'missing_freshness'), ('no invented citations', 'missing_no_citation_fabrication')], fails)
        elif task.validator == 'pa_governance_maintenance_skill_execution':
            require_tokens(blob, [('docs-sync', 'missing_docs_sync'), ('pa-config-audit', 'missing_config_audit'), ('skill-doctor', 'missing_skill_doctor'), ('project-governance', 'missing_project_governance'), ('backlog', 'missing_backlog'), ('change-management', 'missing_change_management'), ('backup', 'missing_backup'), ('diff', 'missing_diff_review'), ('redact secrets', 'missing_secret_redaction'), ('no destructive delete', 'missing_no_delete')], fails)
        elif task.validator == 'travel_packing_skill_execution':
            require_tokens(blob, [('packinglist', 'missing_packinglist'), ('travel-management', 'missing_travel_management'), ('tripsy-travel-management', 'missing_tripsy'), ('vegetarian', 'missing_meal_safety'), ('water', 'missing_water_logistics'), ('heat', 'missing_heat_plan'), ('crowd', 'missing_crowd_plan'), ('do not invent booking', 'missing_booking_boundary')], fails)
    elif task.validator == 'memory_housekeeping_contradiction_scan':
        obj = json_obj({'skills_to_load', 'source_context', 'diagnosis_steps', 'fallback_model_policy', 'log_noise_policy', 'verification', 'ipkb_updates'})
        blob = json.dumps(list((obj or {}).values()), ensure_ascii=False).lower()
        require_tokens(blob, [
            ('memory-housekeeping', 'missing_memory_housekeeping_skill'),
            ('pa-memory', 'missing_pa_memory_skill'),
            ('skill-doctor', 'missing_skill_doctor'),
            ('incident', 'missing_incident_skill'),
            ('memory_housekeeping.py', 'missing_source_script'),
            ('test_memory_housekeeping.py', 'missing_test_file'),
            ('memory_housekeeping.log', 'missing_memory_housekeeping_log'),
            ('contradictions.log', 'missing_contradictions_log'),
            ('ipkb', 'missing_ipkb_registers'),
            ('installed local ollama', 'missing_local_inventory'),
            ('embedding', 'missing_embedding_exclusion'),
            ('cloud', 'missing_cloud_exclusion'),
            ('local-only', 'missing_local_only_fallback'),
            ('unique', 'missing_unique_fallback_slots'),
            ('timeout', 'missing_cold_start_timeout'),
            ('info', 'missing_info_for_recovered_attempts'),
            ('warning', 'missing_exhausted_warning_boundary'),
            ('resolved findings', 'missing_resolved_ledger_preservation'),
            ('py_compile', 'missing_py_compile'),
            ('pytest', 'missing_pytest'),
            ('skill doctor', 'missing_clean_skill_doctor_scan'),
            ('archive', 'missing_log_archive_reset'),
            ('kb', 'missing_durable_kb'),
            ('rebuild', 'missing_register_rebuild'),
            ('audit', 'missing_incident_audit'),
        ], fails)
        if any(x in blob for x in ['use any available model', 'cloud fallback ok', 'embedding model fallback']):
            fails.append('unsafe_fallback_policy')
    else:
        fails.append('unknown_validator')

    unique = sorted(set(fails))
    score = max(0.0, 1.0 - 0.16 * len(unique))
    if any(f in unique for f in ['json_invalid', 'forbidden_code_fences', 'schema_mismatch', 'destructive_sql', 'external_dependency']):
        score = min(score, 0.45)
    if task.modality == 'image' and any(f in unique for f in ['runtime_error', 'vision_not_supported_or_refused']):
        score = min(score, 0.2)
    return round(score, 4), unique, checks


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    import struct
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)


def mini_vision_png_b64() -> str:
    """Create a small PNG with red square, blue circle-ish blob, and green triangle."""
    import struct
    w, h = 96, 64
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            r, g, b = 245, 248, 252
            if 8 <= x <= 30 and 18 <= y <= 40:
                r, g, b = 220, 30, 50
            if (x - 55) ** 2 + (y - 29) ** 2 <= 12 ** 2:
                r, g, b = 30, 90, 220
            if 72 <= x <= 92 and 18 <= y <= 44 and y >= 18 + abs(x - 82):
                r, g, b = 20, 150, 80
            row.extend([r, g, b])
        rows.append(bytes(row))
    raw = b''.join(rows)
    png = b'\x89PNG\r\n\x1a\n'
    png += _png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    png += _png_chunk(b'IDAT', zlib.compress(raw, 9))
    png += _png_chunk(b'IEND', b'')
    return base64.b64encode(png).decode('ascii')


def build_payload(model: str, task: Task) -> dict[str, Any]:
    payload = request_payload(model, task.prompt, num_predict=1800)
    payload['messages'][0]['content'] = payload['messages'][0]['content'] + '\n\n' + SYSTEM
    if task.modality == 'image':
        payload['messages'][-1]['images'] = [mini_vision_png_b64()]
    return payload


def call_ollama(model: str, task: Task, timeout_s: int = 600) -> ProviderResult:
    payload = build_payload(model, task)
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode())
    registered_identity = resolve_ollama_registered_identity(
        model, data, chat_url=OLLAMA_URL, timeout_s=timeout_s,
    )
    return parse_ollama_response(
        model, data, payload=payload, registered_identity=registered_identity,
    )


def call_hermes(model: str, task: Task, timeout_s: int = 900) -> ProviderResult:
    if task.modality == 'image':
        raise UnsupportedRouteError('Hermes CLI benchmark route does not attach the generated image; refusing text-only vision scoring')
    profile = profile_for_model(model)
    full = profile.system_prompt() + '\n\n' + SYSTEM + '\n\nTASK:\n' + task.prompt
    cmd = [
        'hermes', 'chat', '-Q', '--safe-mode', '--source', 'tool', '--max-turns', '3',
        '--provider', 'openai-codex', '-m', model, '-t', '', '-q', full,
    ]
    r = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_s)
    if r.returncode != 0:
        raise ProviderProcessError((r.stderr or r.stdout or '')[-1200:])
    return parse_hermes_response(model, r.stdout or '', provider='openai-codex', max_turns=3)


def run_cell(run_id: str, root: Path, task: Task, model_tag: str, trial_index: int = 1) -> Cell:
    meta = model_meta(model_tag)
    start = time.time(); response = ''; status = 'ok'; error = ''
    checks: dict[str, Any] = {}
    try:
        result = call_hermes(model_tag, task) if meta['provider'] == 'hermes' else call_ollama(model_tag, task)
        response = result.content
        checks = result_checks(result)
        if result.incomplete_reason:
            status, score, fails = 'incomplete', 0.0, [result.incomplete_reason]
        else:
            score, fails, validator_checks = validate(task, response)
            checks.update(validator_checks)
            if result.evidence_failure:
                status = 'unverified'
                fails = sorted(set([*fails, result.evidence_failure]))
    except Exception as exc:
        failure = classify_exception(exc)
        status = 'error'; error = str(exc)[-1000:]
        score = 0.0
        fails = [failure] if task.modality != 'image' else [failure, 'vision_not_supported_or_refused']
        checks = exception_checks(exc)
    profile = profile_for_model(model_tag)
    checks = {**checks, 'prompt_profile': profile.name, 'prompt_guide': profile.guide, 'runtime_options': profile.options, 'runtime_top_level': profile.top_level, 'modality': task.modality, 'provider': meta['provider'], 'tier': meta['tier'], 'trial_index': trial_index}
    label = meta['label']
    cell = Cell(run_id, task.id, task.lane, task.weight, model_tag, label, meta['provider'], status, score, sorted(set(fails)), checks, round(time.time() - start, 3), response, error)
    outdir = root / task.id / label / f'trial-{trial_index:03d}'
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / 'cell.json'
    cell.artifact_path = str(path)
    path.write_text(json.dumps(asdict(cell), indent=2, ensure_ascii=False), encoding='utf-8')
    return cell


def summarize(run_id: str, root: Path, tasks: list[Task], cells: list[Cell], *, expected_repeats: int = 1) -> dict[str, Any]:
    by_model: dict[str, list[Cell]] = {}
    for c in cells:
        by_model.setdefault(c.model_tag, []).append(c)
    ranking = []
    for model, rows in by_model.items():
        denom = sum(r.weight for r in rows)
        weighted = sum(r.score * r.weight for r in rows) / denom if denom else 0.0
        complete = complete_trial_coverage(
            ((r.task_id, int(r.checks.get('trial_index', 1))) for r in rows),
            task_ids=(task.id for task in tasks), repeats=expected_repeats,
        )
        stats = summarize_trials([r.score for r in rows], passed=[r.status == 'ok' and not r.hard_fails for r in rows], expected_trials=len(tasks) * expected_repeats)
        ranking.append({'model': model, 'weighted_score': round(weighted, 4), 'mean_score': round(sum(r.score for r in rows) / len(rows), 4), 'hard_fails': sum(len(r.hard_fails) for r in rows), 'coverage': f'{len(rows)}/{len(tasks) * expected_repeats}', 'runtime_errors': sum(1 for r in rows if r.status == 'error'), 'status_counts': {status: sum(r.status == status for r in rows) for status in sorted({r.status for r in rows})}, 'trial_statistics': stats, 'diagnostic_valid': complete and bool(stats['eligible']), 'promotion_eligible': False})
    ranking.sort(key=lambda r: (-r['weighted_score'], r['hard_fails'], r['runtime_errors']))
    by_task = {}
    for task in tasks:
        rows = [c for c in cells if c.task_id == task.id]
        if rows:
            best = max(rows, key=lambda c: (c.score, -len(c.hard_fails)))
            by_task[task.id] = {'lane': task.lane, 'weight': task.weight, 'best_model': best.model_tag, 'best_score': best.score, 'best_hard_fails': best.hard_fails}
    data = {'run_id': run_id, 'created_at': datetime.now().astimezone().isoformat(timespec='seconds'), 'artifact_root': str(root), 'tasks': [asdict(t) for t in tasks], 'ranking': ranking, 'by_task': by_task, 'results': [asdict(c) for c in cells]}
    (root / 'summary.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    with (root / 'results.jsonl').open('w', encoding='utf-8') as f:
        for c in cells:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + '\n')
    write_html(root / 'report.html', data)
    return data


def write_html(path: Path, data: dict[str, Any]) -> None:
    rows = ''.join(f"<tr><td>{i}</td><th><code>{html.escape(r['model'])}</code></th><td>{r['weighted_score']:.4f}</td><td>{r['mean_score']:.4f}</td><td>{r['hard_fails']}</td><td>{html.escape(r['coverage'])}</td><td>{r['runtime_errors']}</td></tr>" for i, r in enumerate(data['ranking'], 1))
    task_rows = ''.join(f"<tr><th>{html.escape(tid)}<br><small>{html.escape(v['lane'])}</small></th><td>{v['weight']}</td><td><code>{html.escape(v['best_model'])}</code></td><td>{v['best_score']:.4f}</td><td>{html.escape(', '.join(v['best_hard_fails']) or '—')}</td></tr>" for tid, v in data['by_task'].items())
    path.write_text(f"""<!doctype html><html><head><meta charset='utf-8'><title>PA Extended Capability Benchmark</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;background:#f6f8fb;color:#172033}}.card{{background:white;border:1px solid #d9e2ef;border-radius:12px;padding:16px;margin:14px 0}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d9e2ef;padding:8px;text-align:left;vertical-align:top}}th{{background:#eaf1fb}}code{{background:#edf2f7;padding:2px 4px;border-radius:4px}}</style></head><body><h1>PA Extended Capability Benchmark</h1><p>Run <code>{html.escape(data['run_id'])}</code>. Tests vision, diagrams, HTML reports, HTML presentations, data processing, job applications, web-search analysis plans, weekly spending/nutrition report quality, skill-instruction execution, and cron-job execution safety.</p><div class='card'><h2>Model ranking</h2><table><tr><th>Rank</th><th>Model</th><th>Weighted</th><th>Mean</th><th>Hard-fails</th><th>Coverage</th><th>Runtime errors</th></tr>{rows}</table></div><div class='card'><h2>Best model per extended capability</h2><table><tr><th>Task</th><th>Weight</th><th>Best model</th><th>Score</th><th>Hard-fails</th></tr>{task_rows}</table></div><div class='card'><h2>Artifacts</h2><p><code>{html.escape(data['artifact_root'])}</code></p></div></body></html>""", encoding='utf-8')


def self_test() -> int:
    tasks = task_list(); samples = {t.id: '' for t in tasks}
    samples['X01'] = json.dumps({'objects':['red square','blue circle','green triangle'], 'chart_reading':'Mini Vision Test has three shapes.', 'uncertainty':'none'})
    samples['X02'] = json.dumps({'mermaid':'flowchart TD\nA-->B', 'excalidraw':{'type':'excalidraw','elements':[{'type':'rectangle'}]}, 'tailored_chart_spec':{'chart_type':'bar','x_axis':'model','y_axis':'score','series':[{'name':'score','values':[1]}]}, 'notes':'benchmark chart'})
    samples['X03'] = '<!doctype html><html><head><style>body{font-family:-apple-system;background:#f6f8fb}.card{}</style></head><body><section class="hero">evidence ranking qwen gemma mistral</section><section class="card"><table><tr><td>1</td></tr></table></section></body></html>'
    samples['X04'] = json.dumps({'slides_html':'<section class="slide">1</section><section class="slide">2 <svg></svg></section><section class="slide">3</section>', 'theme':'navy blue audit theme', 'graphs':['svg bar'], 'animation_notes':'CSS animation fade', 'speaker_notes':['speaker note']})
    samples['X05'] = json.dumps({'duckdb_sql':'SELECT * FROM read_csv_auto(?)', 'sqlite_sql':'SELECT * FROM app WHERE id = ?', 'csv_plan':['csv row count'], 'xlsx_plan':['xlsx all sheets'], 'export_plan':['export parquet'], 'table_integrity_checks':['row count','column count','no truncation']})
    samples['X06'] = json.dumps({'role_fit':'Senior AI Audit Manager fit', 'cv_tailoring':['CV bullet without inventing'], 'cover_letter_outline':['cover letter opening'], 'evidence_gaps':['evidence missing'], 'risks':['do not invent credentials']})
    samples['X07'] = json.dumps({'search_queries':['search local ollama models'], 'sources_to_check':['official model-card','community benchmark'], 'ranking_method':'recommendation from sourced facts', 'caveats':['freshness','vendor claims'], 'synthesis_output':'separate facts and recommendation'})
    samples['X08'] = json.dumps({'quality_score':0.86,'accuracy_findings':['0.00 EUR week and no transactions, but 20,400 EUR MTD and 121.4% burn rate remain the issue','Correct cash to 42,000 EUR','Tax due date is 2026-09-15 and amount 15,000 EUR'],'completeness_gaps':['Import freshness 2026-06-24 before report end','Split week vs MTD interpretation'],'improved_recommendations':['Refresh import','Pause discretionary spend until MTD back under pace'],'risk_flags':['Do not invent transactions'],'rewrite_outline':['TLDR','Week vs MTD','Data freshness','Cash and tax']})
    samples['X09'] = json.dumps({'quality_score':0.88,'accuracy_findings':['2200 kcal average, 2/7 days under 2050 ceiling, 5/7 protein success','70g sugar vs 45g target','22g fiber vs 30g target','Observed maintenance 2000 and +200 kcal surplus'],'completeness_gaps':['1100ml hydration vs 2400 target','Vitamin D and potassium micronutrients low','CGM report-week data missing'],'improved_recommendations':['Replace sweetened soy beverage','Add fiber default','4 x 600ml water plan'],'risk_flags':['Do not diagnose','Avoid causality from correlation','Fix duplicate 1. 1) numbering'],'rewrite_outline':['TLDR','targets','caveats','actions']})
    samples['X10'] = json.dumps({'skills_to_load':['ollama-local-benchmarking','test-driven-development'],'context_to_read':['attached reports','benchmark scripts'],'tool_sequence':['skill_view first','read_file reports','write failing pytest tests','run pytest RED','patch code','run py_compile pytest and self-test'],'execution_boundaries':['backup scripts','do not send external messages','do not delete models'],'verification':['pytest passes','py_compile passes','self-test passes'],'artifact_updates':['tasks X08-X11','docs/report after run']})
    samples['X11'] = json.dumps({'job_design':['self-contained prompt for fresh session','no recursive cron jobs'],'schedule_and_delivery':['deliver to origin','schedule includes date/time'],'script_no_agent_decision':['no_agent only when stdout is final','empty stdout means silent','non-zero exit sends error alert'],'safety_checks':['cronjob list before remove/update','never guess job_id'],'verification':['cronjob list after create','manual run if requested']})
    samples['X12'] = json.dumps({'included_skills':['html-report','humanizer','goodlinks','podcast_summaries','games','packinglist','smart-reading','rss-daily-brief','obs_summarize','obs_tldr','obsidian-medium-export','skill-doctor','docs-sync','pa-config-audit','project-governance','backlog'],'excluded_sensitive_skills':['health','finance','trade'],'routing_table':[{'request':'report','skill':'html-report'}],'simplification_rules':['privacy via synthetic placeholders'],'evaluation_dimensions':['selection accuracy','execution order','verification']})
    samples['X13'] = json.dumps({'skills_to_use':['html-report','humanizer','obsidian-medium-export'],'input_contract':['public draft'],'execution_steps':['make html'],'quality_checks':['self-contained HTML'],'privacy_controls':['no external publish','no secrets']})
    samples['X14'] = json.dumps({'skills_to_use':['obs_summarize','obs_tldr','obsidian-sr-anki-export','vault-readout'],'input_contract':['source note','date'],'execution_steps':['H1 and [[2026-06-28]]','flashcard export'],'quality_checks':['relative links valid'],'privacy_controls':['vault local','no external upload']})
    samples['X15'] = json.dumps({'skills_to_use':['goodlinks','smart-reading','rss-daily-brief','podcast_summaries','games'],'input_contract':['public source url'],'execution_steps':['queue reading'],'quality_checks':['freshness','no invented citations'],'privacy_controls':['public-source only']})
    samples['X16'] = json.dumps({'skills_to_use':['docs-sync','pa-config-audit','skill-doctor','project-governance','backlog','change-management'],'input_contract':['synthetic config'],'execution_steps':['backup','patch'],'quality_checks':['diff review'],'privacy_controls':['redact secrets','no destructive delete']})
    samples['X17'] = json.dumps({'skills_to_use':['packinglist','travel-management','tripsy-travel-management'],'input_contract':['destination and weather'],'execution_steps':['packing list plan'],'quality_checks':['vegetarian meals','water logistics','heat plan','crowd plan'],'privacy_controls':['do not invent booking codes']})
    samples['X18'] = json.dumps({'skills_to_load':['memory-housekeeping','pa-memory','skill-doctor','incident'],'source_context':['memory_housekeeping.py','test_memory_housekeeping.py','memory_housekeeping.log','contradictions.log','IPKB issues and KB records'],'diagnosis_steps':['inventory installed local Ollama models while excluding embedding and cloud tags','probe local fallback with think=false JSON','reproduce timeout and OpenAI rate-limit signatures'],'fallback_model_policy':['local-only fallback models','unique fallback slots','cold-start tolerant timeout','exclude embedding models and cloud tags'],'log_noise_policy':['provider attempts log at INFO while fallback continues','only exhausted scans emit WARNING or ERROR','preserve Resolved Findings ledger'],'verification':['py_compile','focused and full pytest','clean Skill Doctor log scan','archive and reset polluted log'],'ipkb_updates':['close IPKB issues','create durable-fix KB','rebuild registers','incident audit PASS']})
    bad = []
    for t in tasks:
        score, fails, checks = validate(t, samples[t.id])
        if score < .8 or fails:
            bad.append((t.id, score, fails, checks))
    print(json.dumps({'self_test': 'pass' if not bad else 'fail', 'bad': bad}, indent=2))
    return 0 if not bad else 1


def select_tasks(tasks: list[Task], task_ids: list[str] | None) -> list[Task]:
    """Return tasks filtered by exact IDs, preserving suite order."""
    if not task_ids:
        return tasks
    wanted = [tid.strip().upper() for tid in task_ids if tid.strip()]
    known = {t.id for t in tasks}
    unknown = [tid for tid in wanted if tid not in known]
    if unknown:
        raise SystemExit(f"Unknown task id(s): {', '.join(unknown)}")
    wanted_set = set(wanted)
    return [t for t in tasks if t.id in wanted_set]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', default=','.join(DEFAULT_MODELS), help='Comma-separated Ollama model tags')
    ap.add_argument('--run-id', default=RUN_ID_DEFAULT)
    ap.add_argument('--task-ids', default='', help='Optional comma-separated task IDs to run, e.g. X18')
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--run-order', choices=['balanced', 'random', 'fixed'], default='balanced')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    models = [m.strip() for m in args.models.split(',') if m.strip()]
    require_profile_coverage(models)
    root = ARTIFACTS_DIR / args.run_id
    claim_run_root(root)
    tasks = select_tasks(task_list(), [t for t in args.task_ids.split(',') if t.strip()])
    write_manifest(root, build_manifest(run_id=args.run_id, models=models, task_payload=[asdict(t) for t in tasks], source_paths=[Path(__file__), BASE_DIR / 'scripts' / 'model_prompt_profiles.py'], repeats=args.repeats, seed=args.seed, run_order=args.run_order, privacy_class='synthetic', argv=sys.argv, model_routes={model: model_meta(model)['provider'] for model in models}))
    cells: list[Cell] = []
    task_by_id = {task.id: task for task in tasks}
    schedule = make_schedule(models, list(task_by_id), repeats=args.repeats, seed=args.seed, order=args.run_order)
    for trial in schedule:
        task = task_by_id[trial.task_id]
        print(f'{task.id} {trial.model} trial={trial.trial_index}...', flush=True)
        cell = run_cell(args.run_id, root, task, trial.model, trial.trial_index)
        cells.append(cell)
        progress = progress_snapshot(schedule, [(c.model_tag, c.status == 'ok' and not c.hard_fails) for c in cells])
        print(f'  score={cell.score:.3f} fails={cell.hard_fails} progress={json.dumps(progress, separators=(",", ":"))}', flush=True)
    data = summarize(args.run_id, root, tasks, cells, expected_repeats=args.repeats)
    print(json.dumps({'run_id': args.run_id, 'artifact_root': str(root), 'ranking': data['ranking']}, indent=2), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
