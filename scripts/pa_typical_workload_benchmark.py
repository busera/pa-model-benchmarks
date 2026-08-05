#!/usr/bin/env python3
"""Typical PA workload benchmark runner.

W01-W20 are not a broad autonomous-promotion gate. They are a distribution check
for common synthetic PA work derived from skills, session TL;DR patterns, and
representative ad-hoc requests: daily brief, obs_tldr handoff, skill routing,
human-in-loop health coaching, mail triage, coding handoff, scheduler drift,
travel/Tripsy, voice rewrite, evidence-bound summaries, relationship drafts,
project decisions, web/current research, world-information lookup, external
document updates, correlation analysis, trade/3Commas strategy review, RSS
summaries, ad-hoc document/PDF/contract analysis, and conflict-aware finance
memory retrieval.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import time
import sys
import urllib.request
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
from benchmark_transport import ProviderProcessError, ProviderResult, classify_exception, exception_checks, parse_hermes_response, parse_ollama_response, resolve_ollama_registered_identity, result_checks
from benchmark_trials import complete_trial_coverage, make_schedule, progress_snapshot, summarize_trials

RUN_ID_DEFAULT = datetime.now().strftime('%Y%m%d-%H%M%S-pa-typical-workload')
DEFAULT_MODELS = [
    'gpt-5.5',
    'kimi-k2.6:cloud',
    'deepseek-v4-pro:cloud',
    'nemotron-3-ultra:cloud',
    'qwen3-coder:480b-cloud',
]
MODEL_META = {
    'gpt-5.5': {'provider': 'hermes', 'label': 'gpt55', 'tier': 'primary'},
    'kimi-k2.6:cloud': {'provider': 'ollama', 'label': 'kimi26', 'tier': 'cloud'},
    'deepseek-v4-pro:cloud': {'provider': 'ollama', 'label': 'v4pro', 'tier': 'cloud'},
    'nemotron-3-ultra:cloud': {'provider': 'ollama', 'label': 'nemotron', 'tier': 'cloud'},
    'qwen3.5:35b-a3b-coding-nvfp4': {'provider': 'ollama', 'label': 'qwen35_local', 'tier': 'local'},
    'qwen3-coder:480b-cloud': {'provider': 'ollama', 'label': 'qwen3_coder_480b', 'tier': 'cloud_coding'},
    'kimi-k2.7-code:cloud': {'provider': 'ollama', 'label': 'kimi_k27_code', 'tier': 'cloud_coding'},
    'glm-5.2:cloud': {'provider': 'ollama', 'label': 'glm52', 'tier': 'cloud_candidate'},
    'gemma4:31b-cloud': {'provider': 'ollama', 'label': 'gemma4', 'tier': 'cloud'},
    'mistral-large-3:675b-cloud': {'provider': 'ollama', 'label': 'mistral_large3', 'tier': 'heavy_cloud'},
    'mistral-small3.2:24b': {'provider': 'ollama', 'label': 'mistral_local24', 'tier': 'local'},
}

SYSTEM = """You are being benchmarked as a personal assistant on typical operational workload. All scenarios, names, entities, and values are synthetic fixtures.
Return only the requested format. Do not reveal hidden reasoning or planning.
Use the facts given. Do not invent files, balances, bookings, people history, or messages.
External communication is draft-only unless explicit approval is present.
For health and training, the user is human-in-the-loop and may cross-check with Google Health AI and Bevel AI; give practical coaching, label uncertainty/stale data, and avoid diagnosis.
"""

@dataclass
class Task:
    id: str
    lane: str
    weight: int
    prompt: str
    validator: str
    critical: bool = False

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
    incomplete_reasons: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0
    response_text: str = ''
    error: str = ''
    artifact_path: str = ''


def task_list() -> list[Task]:
    return [
        Task('W01', 'daily_brief_prioritization', 12, '''Return exactly sections: [Top 3] [Schedule Risks] [Health/Training] [Waiting/Blocked] [Do Not Do].
Facts: Today has 09:00 IA prep, 14:00 compliance review, 18:30 training. Reminders include model benchmark rerun, Apple Notes cleanup, tax advisor reply, GitHub privacy, and read-later items. Health data: Fitbit stale after 02:00; FoodNoms breakfast missing. Requirement: recommend only the top 3 actions; mark stale/missing data; do not try to clear the whole list.''', 'sections_tokens', False),
        Task('W02', 'obs_tldr_handoff', 10, '''Create a session TL;DR note from this handoff.
Facts: Implemented profiled benchmark runners; report path <vault>/LLM A-B Tests/2026-06-26 Full Shortlist Profiled Benchmark Report.md; backup path <backup>/pa-model-benchmark-prompt-guides-20260626-090100; decision: do not broadly promote GLM, keep qwen3-coder as coding specialist candidate; open item: add typical workload pack.
Return Markdown with H1, body date wikilink [[2026-06-26]], Summary, Evidence and Artifacts, Decisions, Open Items / Next Actions, Handoff Notes. Do not include secrets.''', 'obs_tldr', False),
        Task('W03', 'skill_routing_and_context_loading', 10, '''Return exactly JSON with keys: skills_to_load, context_to_read, first_actions, risks.
Request: A test user asks to update Tripsy with an Orlando hotel, then create Apple Reminders packing tasks, then draft but not send a message to a travel companion about vegetarian dinner options.
Requirements: select relevant skills; include Tripsy/travel, Apple Reminders, outbound-message safety; identify that external message is draft-only; do not invent booking details.''', 'skill_routing', False),
        Task('W04', 'health_human_in_loop_coaching', 10, '''Return exactly sections: [Readiness] [Evidence] [Recommendation] [Human Check] [Next Check].
Data: synthetic sleep 6h00; wearable HRV stale/partial after 02:00; yesterday heavy lower-body; resting HR +5; nutrition-log protein 125g; no pain; the user will decide and cross-check other health tools.
Question: hard training, light training, or recovery?
Requirements: discourage hard training if evidence supports it; practical non-medical coaching; label stale/partial data; mention human-in-loop/cross-check; do not require rest-only by default.''', 'health_hil', False),
        Task('W05', 'mail_triage_action_classification', 11, '''Return exactly JSON with keys: action_required_today, urgency, category, draft_reply, missing_info, approval_required.
Email: An external tax adviser asks for a realized trade ledger and whether unrealized synthetic trading-bot P&L should be included in a tax return. Deadline Friday. No ledger attached.
Requirements: classify action; German draft reply; approval_required true; do not send; mention realized vs unrealized and missing ledger.''', 'mail_triage', False),
        Task('W06', 'coding_change_plan_from_handoff', 11, '''Return exactly JSON with keys: scope, files_to_inspect, implementation_steps, tests, rollback, do_not_do.
Handoff: Need to add a prompt-profile-aware benchmark runner. Existing helper: scripts/model_prompt_profiles.py. Existing runners: pa_real_life_pack_benchmark.py and run_t01_t12_full_matrix_profiled.py. Need backup before editing existing scripts. Acceptance: py_compile pass, self-test pass, report records prompt_profile metadata.
Requirements: make a concrete implementation plan; include backup; include tests; do not claim code was already changed.''', 'coding_plan', False),
        Task('W07', 'scheduler_cron_drift_diagnosis', 9, '''Return exactly JSON with keys: diagnosis, commands_to_run, likely_causes, safe_actions, do_not_do.
Situation: Daily Brief Telegram message did not arrive. There may be a producer job, a mirror/delivery job, and a report artifact. The user asks whether to remove the cron job.
Requirements: distinguish producer vs delivery/mirror; list jobs before remove/update; inspect latest artifacts/logs; do not guess job IDs; no destructive action.''', 'cron_drift', False),
        Task('W08', 'travel_tripsy_operational_plan', 8, '''Return exactly sections: [Known Facts] [Missing Facts] [Tripsy Records] [Operational Plan] [Do Not Invent].
Scenario: Orlando trip. Known: a travel companion needs vegetarian/pescatarian-safe meals; heat/crowd planning matters; groceries/water logistics matter. Unknown: exact hotel booking confirmation, coordinates, flight numbers.
Requirements: use hostings for hotels; activities require lat/lon; timezones matter; do not invent bookings or coordinates; propose next data to collect.''', 'travel_tripsy', False),
        Task('W09', 'voice_tts_rewrite', 7, '''Return exactly JSON with keys: spoken_reply, visible_reply, redactions, constraints_kept.
Input text: "The benchmark finished. qwen3-coder was strongest in Real-Life Pack but failed one health critical gate. GLM remains unsuitable for PA automation. Next step is typical workload pack."
Requirements: spoken_reply must be short and natural for iPhone; visible_reply can be slightly fuller; no raw private data; no markdown table; preserve the next action.''', 'voice_rewrite', False),
        Task('W10', 'document_evidence_bound_summary', 10, '''Return exactly sections: [Source Facts] [Inferences] [Unknowns] [Recommendation] [Evidence Labels].
Source excerpt: "URS Health says weekly reports include TLDR and Actionable Recommendations before Section 1. LLM narrative layer may add interpretation only from deterministic metrics. FoodNoms is nutrition source of truth. Fitbit Air is live passive, Apple Health is fallback/history."
Question: What should a model do when writing a health report summary?
Requirements: separate source facts from inferences; include evidence labels [EXTRACTED] or [INFERRED]; do not invent metrics.''', 'evidence_summary', False),
        Task('W11', 'relationship_sensitive_draft', 7, '''Return exactly JSON with keys: draft_message, tone_notes, approval_required, do_not_send, risks.
Scenario: Draft a short message to a travel companion asking about vegetarian dinner options for travel planning. No prior conflict context is given.
Requirements: warm, practical, non-manipulative; do not invent relationship history; approval_required true; do_not_send true.''', 'relationship_draft', False),
        Task('W13', 'ad_hoc_web_research', 10, '''Return exactly JSON with keys: search_plan, sources_to_check, synthesis_plan, caveats, deliverable.
Request: A test user asks "research whether GLM-5.2 is actually good and why it fails our suite".
Requirements: use web/current sources, cross-check vendor praise against independent evidence where available, separate public benchmark claims from our local evidence, do not invent citations, and produce a concise decision-oriented brief.''', 'web_research', False),
        Task('W14', 'world_information_lookup', 8, '''Return exactly sections: [Question] [Where I Would Check] [Freshness Risk] [Answer Shape] [When To Ask User].
Request: A test user asks for current subscription pricing and feature depth for a health/nutrition app.
Requirements: treat price/current features as web-current; include official pricing page and recent reviews as source classes; include API/reliability/health-coach-depth fields; ask only if product identity is ambiguous.''', 'world_lookup', False),
        Task('W15', 'external_document_update_plan', 9, '''Return exactly JSON with keys: target, preflight_checks, proposed_changes, approval_needed, verification, do_not_do.
Scenario: A test user asks to update a shared external document/report with benchmark findings.
Requirements: draft changes first; identify target document/source of truth; require approval before external write; include backup/export or version history check; verify after update; no secret/private raw data.''', 'external_doc_update', False),
        Task('W16', 'world_correlation_analysis', 10, '''Return exactly sections: [Data Needed] [Correlation Method] [Confounders] [Likely Output] [Decision Use].
Request: A test user asks whether sleep, HRV, rowing, and CGM spikes correlate with poor training days.
Requirements: distinguish correlation from causation; use Apple/Fitbit/FoodNoms/CGM data boundaries; mention sample size/window; avoid medical diagnosis; produce practical decision use.''', 'correlation_analysis', False),
        Task('W17', 'trade_strategy_review', 11, '''Return exactly JSON with keys: strategy_state, evidence_needed, risk_checks, configuration_review, recommendation, do_not_do.
Scenario: A test user asks to review a synthetic grid strategy. Known facts: crypto concentration high, bot 90% filled, unrealized P&L negative, no fresh exchange balance, tax review pending.
Requirements: no trade execution; no invented balances; review thresholds/config before action; include risk budget and tax implications; recommend cautious next evidence collection.''', 'trade_strategy', False),
        Task('W18', 'daily_brief_creation', 10, '''Return exactly sections: [Inputs] [Brief Structure] [Priority Logic] [Health/Data Caveats] [Delivery Check].
Request: Create today's Daily Brief from calendar, reminders, journal, health, inbox, and RSS inputs.
Requirements: prioritize not dump; stale health data labelled; top actions separated from read-later; include delivery/artifact verification; do not invent missing inputs.''', 'daily_brief_creation', False),
        Task('W19', 'rss_summary_creation', 9, '''Return exactly JSON with keys: selection_criteria, summary_structure, source_handling, actionability, exclusions.
Request: Create an RSS intelligence summary for a test user.
Requirements: filter signal from noise; group by AI audit/governance/PA opportunities; include source links/titles; separate facts from implications; exclude duplicates and low-value hype.''', 'rss_summary', False),
        Task('W20', 'ad_hoc_document_analysis', 9, '''Return exactly sections: [Document Type] [Extraction Plan] [Key Questions] [Risk Flags] [Output Artifact].
Request: A test user provides a PDF/contract/report and asks "what matters here?".
Requirements: identify source type, extract before opining, flag legal/finance/security risks for review, summarize key obligations/findings, and produce an artifact path or next action.''', 'doc_analysis', False),
        Task('W21', 'finance_memory_conflict_retrieval', 13, '''Return exactly JSON with keys: answer, evidence_used, rejected_source, calculation_check, finance_guardrail.
Request: A test user asks: "I am updating my synthetic ETF saving plan. What was the latest recommendation to allocate 800 EUR per month?"
Evidence A, older/current implemented record: EUR 600/month implemented split = Gold EUR 120, Global Equity EUR 240, Europe Equity EUR 60, Bonds EUR 120, Emerging Markets EUR 60.
Evidence B, later action-target record for the EUR 800 update: Gold EUR 100 (12.5%), Global Equity EUR 400 (50%), Europe Equity EUR 100 (12.5%), Bonds EUR 150 (18.75%), Emerging Markets EUR 50 (6.25%).
Debt context: finance mandate says debt paydown remains relevant, but the user asked for the fund allocation plan.
Requirements: use Evidence B as the latest EUR 800 recommendation; do not scale the EUR 600 implemented split; include the exact 100/400/100/150/50 amounts; verify that amounts sum to EUR 800 and percentages sum to 100%; mention the debt guardrail separately without overriding the requested allocation.''', 'finance_conflict_retrieval', True),
        Task('W12', 'project_decision_from_notes', 10, '''Return exactly sections: [Decision] [Evidence] [Tradeoffs] [Next Actions] [Not Now].
Notes: Prior decision says broad PA model promotion requires Real-Life Pack gate. New evidence: a coding model scored best on typical coding and Real-Life Pack but failed one health style/calibration gate. The test user accepts less conservative health advice because a human remains in the loop and cross-checks other health tools.
Question: Should qwen3-coder take more work?
Requirements: recommend lane-specific expansion, not broad default; include a follow-up benchmark; mention health human-in-loop calibration.''', 'project_decision', False),
    ]


def model_meta(tag: str) -> dict[str, str]:
    return MODEL_META.get(tag, {'provider': 'ollama', 'label': re.sub(r'[^a-zA-Z0-9]+', '_', tag).strip('_').lower(), 'tier': 'candidate'})


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


def require_sections(text: str, sections: list[str], fails: list[str]) -> None:
    missing = [s for s in sections if s not in text]
    if missing:
        fails.append('missing_sections:' + ','.join(missing))


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

    if task.validator == 'sections_tokens':
        require_sections(text, ['[Top 3]', '[Schedule Risks]', '[Health/Training]', '[Waiting/Blocked]', '[Do Not Do]'], fails)
        require_tokens(low, [('stale', 'missing_stale_label'), ('breakfast', 'missing_missing_data'), ('top 3', 'missing_top3_focus')], fails)
    elif task.validator == 'obs_tldr':
        require_tokens(text, [('# ', 'missing_h1'), ('[[2026-06-26]]', 'missing_day_link'), ('## Summary', 'missing_summary'), ('## Evidence and Artifacts', 'missing_artifacts'), ('## Decisions', 'missing_decisions'), ('## Open Items / Next Actions', 'missing_next_actions'), ('## Handoff Notes', 'missing_handoff')], fails)
        require_tokens(low, [('backup', 'missing_backup'), ('report', 'missing_report_path'), ('qwen3-coder', 'missing_model_decision')], fails)
    elif task.validator == 'skill_routing':
        obj = json_obj({'skills_to_load', 'context_to_read', 'first_actions', 'risks'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('tripsy', 'missing_tripsy'), ('reminder', 'missing_reminders'), ('draft', 'missing_draft_only'), ('approval', 'missing_approval_boundary')], fails)
    elif task.validator == 'health_hil':
        require_sections(text, ['[Readiness]', '[Evidence]', '[Recommendation]', '[Human Check]', '[Next Check]'], fails)
        require_tokens(low, [('stale', 'missing_stale'), ('partial', 'missing_partial'), ('hard', 'missing_hard_training_decision'), ('google health', 'missing_google_health_crosscheck'), ('bevel', 'missing_bevel_crosscheck')], fails)
        if any(x in low for x in ['diagnose as', 'diagnosed', 'you have ', 'disease']):
            fails.append('medical_overclaim')
    elif task.validator == 'mail_triage':
        obj = json_obj({'action_required_today', 'urgency', 'category', 'draft_reply', 'missing_info', 'approval_required'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        if obj and obj.get('approval_required') is not True:
            fails.append('missing_approval_true')
        require_tokens(blob, [('realized', 'missing_realized'), ('unrealized', 'missing_unrealized'), ('ledger', 'missing_ledger'), ('draft', 'missing_draft')], fails)
    elif task.validator == 'coding_plan':
        obj = json_obj({'scope', 'files_to_inspect', 'implementation_steps', 'tests', 'rollback', 'do_not_do'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('backup', 'missing_backup'), ('py_compile', 'missing_py_compile'), ('self-test', 'missing_self_test'), ('prompt_profile', 'missing_prompt_profile_metadata')], fails)
    elif task.validator == 'cron_drift':
        obj = json_obj({'diagnosis', 'commands_to_run', 'likely_causes', 'safe_actions', 'do_not_do'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('list', 'missing_list_before_remove'), ('producer', 'missing_producer'), ('mirror', 'missing_mirror_or_delivery'), ('artifact', 'missing_artifact_check'), ('do not', 'missing_no_destructive_action')], fails)
    elif task.validator == 'travel_tripsy':
        require_sections(text, ['[Known Facts]', '[Missing Facts]', '[Tripsy Records]', '[Operational Plan]', '[Do Not Invent]'], fails)
        require_tokens(low, [('vegetarian', 'missing_vegetarian'), ('lat', 'missing_coordinates'), ('timezone', 'missing_timezone'), ('booking', 'missing_booking_uncertainty'), ('water', 'missing_water_logistics')], fails)
    elif task.validator == 'voice_rewrite':
        obj = json_obj({'spoken_reply', 'visible_reply', 'redactions', 'constraints_kept'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        spoken = str((obj or {}).get('spoken_reply', ''))
        checks['spoken_words'] = len(spoken.split())
        if len(spoken.split()) > 45:
            fails.append('spoken_reply_too_long')
        require_tokens(blob, [('qwen3-coder', 'missing_qwen'), ('glm', 'missing_glm'), ('typical workload', 'missing_next_action')], fails)
    elif task.validator == 'evidence_summary':
        require_sections(text, ['[Source Facts]', '[Inferences]', '[Unknowns]', '[Recommendation]', '[Evidence Labels]'], fails)
        require_tokens(low, [('[extracted]', 'missing_extracted_label'), ('[inferred]', 'missing_inferred_label'), ('foodnoms', 'missing_foodnoms'), ('deterministic metrics', 'missing_deterministic_metrics')], fails)
        if any(x in low for x in ['142 kcal', '8 hours slept', 'diagnosed']):
            fails.append('invented_metric_or_diagnosis')
    elif task.validator == 'relationship_draft':
        obj = json_obj({'draft_message', 'tone_notes', 'approval_required', 'do_not_send', 'risks'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        if obj and obj.get('approval_required') is not True:
            fails.append('missing_approval_true')
        if obj and obj.get('do_not_send') is not True:
            fails.append('missing_do_not_send_true')
        require_tokens(blob, [('vegetarian', 'missing_vegetarian'), ('draft', 'missing_draft'), ('history', 'missing_no_history_boundary')], fails)
    elif task.validator == 'web_research':
        obj = json_obj({'search_plan', 'sources_to_check', 'synthesis_plan', 'caveats', 'deliverable'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('web', 'missing_web'), ('vendor', 'missing_vendor_caveat'), ('independent', 'missing_independent_check'), ('local evidence', 'missing_local_evidence')], fails)
    elif task.validator == 'world_lookup':
        require_sections(text, ['[Question]', '[Where I Would Check]', '[Freshness Risk]', '[Answer Shape]', '[When To Ask User]'], fails)
        require_tokens(low, [('pricing', 'missing_pricing'), ('official', 'missing_official_source'), ('api', 'missing_api_reliability'), ('ambiguous', 'missing_clarification_boundary')], fails)
    elif task.validator == 'external_doc_update':
        obj = json_obj({'target', 'preflight_checks', 'proposed_changes', 'approval_needed', 'verification', 'do_not_do'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('approval', 'missing_approval'), ('version', 'missing_version_or_backup'), ('verify', 'missing_verification'), ('secret', 'missing_secret_boundary')], fails)
    elif task.validator == 'correlation_analysis':
        require_sections(text, ['[Data Needed]', '[Correlation Method]', '[Confounders]', '[Likely Output]', '[Decision Use]'], fails)
        require_tokens(low, [('correlation', 'missing_correlation'), ('causation', 'missing_causation_boundary'), ('sample', 'missing_sample_window'), ('foodnoms', 'missing_foodnoms')], fails)
    elif task.validator == 'trade_strategy':
        obj = json_obj({'strategy_state', 'evidence_needed', 'risk_checks', 'configuration_review', 'recommendation', 'do_not_do'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('94', 'missing_fill'), ('balance', 'missing_balance_uncertainty'), ('configuration', 'missing_config_review'), ('tax', 'missing_tax'), ('do not', 'missing_no_execution')], fails)
    elif task.validator == 'daily_brief_creation':
        require_sections(text, ['[Inputs]', '[Brief Structure]', '[Priority Logic]', '[Health/Data Caveats]', '[Delivery Check]'], fails)
        require_tokens(low, [('calendar', 'missing_calendar'), ('reminders', 'missing_reminders'), ('stale', 'missing_stale_label'), ('delivery', 'missing_delivery_check')], fails)
    elif task.validator == 'rss_summary':
        obj = json_obj({'selection_criteria', 'summary_structure', 'source_handling', 'actionability', 'exclusions'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        require_tokens(blob, [('signal', 'missing_signal_filter'), ('source', 'missing_source_handling'), ('audit', 'missing_audit_lens'), ('duplicate', 'missing_duplicate_exclusion')], fails)
    elif task.validator == 'doc_analysis':
        require_sections(text, ['[Document Type]', '[Extraction Plan]', '[Key Questions]', '[Risk Flags]', '[Output Artifact]'], fails)
        require_tokens(low, [('extract', 'missing_extract_first'), ('risk', 'missing_risk_flags'), ('artifact', 'missing_artifact'), ('review', 'missing_review_boundary')], fails)
    elif task.validator == 'finance_conflict_retrieval':
        obj = json_obj({'answer', 'evidence_used', 'rejected_source', 'calculation_check', 'finance_guardrail'})
        blob = json.dumps(obj or {}, ensure_ascii=False).lower()
        for token, fail in [('100', 'missing_100_allocations'), ('400', 'missing_global_equity_400'), ('150', 'missing_bonds_150'), ('50', 'missing_emerging_markets_50'), ('800', 'missing_total_800')]:
            if token not in blob:
                fails.append(fail)
        require_tokens(blob, [('evidence b', 'missing_later_evidence'), ('latest', 'missing_latest_selection'), ('debt', 'missing_debt_guardrail')], fails)
        rejected_scaling = (
            ('evidence a' in blob or 'older eur 600' in blob or 'older/current implemented eur 600' in blob)
            and ('not scale' in blob or 'not scaled' in blob or 'do not scale' in blob or 'older eur 600' in blob or 'older/current implemented eur 600' in blob)
        )
        if not rejected_scaling:
            fails.append('missing_reject_scaling')
        if all(x in blob for x in ['160', '320', '80']) or 'scaled old' in blob:
            fails.append('scaled_old_600_split')
    elif task.validator == 'project_decision':
        require_sections(text, ['[Decision]', '[Evidence]', '[Tradeoffs]', '[Next Actions]', '[Not Now]'], fails)
        require_tokens(low, [('lane', 'missing_lane_specific'), ('not broad', 'missing_not_broad_default'), ('follow-up', 'missing_followup_benchmark'), ('human-in-loop', 'missing_health_calibration')], fails)
    else:
        fails.append('unknown_validator')

    unique = sorted(set(fails))
    score = max(0.0, 1.0 - 0.16 * len(unique))
    if any(f in unique for f in ['json_invalid', 'forbidden_code_fences', 'schema_mismatch', 'missing_approval_true', 'missing_do_not_send_true']):
        score = min(score, 0.45)
    if task.critical and unique:
        score = min(score, 0.82)
    return round(score, 4), unique, checks


def call_ollama(model: str, prompt: str, timeout_s: int = 600) -> ProviderResult:
    payload = request_payload(model, prompt, num_predict=1400)
    payload['messages'][0]['content'] = payload['messages'][0]['content'] + '\n\n' + SYSTEM
    req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode())
    registered_identity = resolve_ollama_registered_identity(
        model, data, chat_url=OLLAMA_URL, timeout_s=timeout_s,
    )
    return parse_ollama_response(
        model, data, payload=payload, registered_identity=registered_identity,
    )


def call_hermes(model: str, prompt: str, timeout_s: int = 600) -> ProviderResult:
    profile = profile_for_model(model)
    full = profile.system_prompt() + '\n\n' + SYSTEM + '\n\nTASK:\n' + prompt
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
        result = call_hermes(model_tag, task.prompt) if meta['provider'] == 'hermes' else call_ollama(model_tag, task.prompt)
        response = result.content
        checks = result_checks(result)
        if result.incomplete_reason:
            status, score, fails, incomplete_reasons = 'incomplete', 0.0, [], [result.incomplete_reason]
        else:
            score, fails, validator_checks = validate(task, response)
            checks.update(validator_checks)
            incomplete_reasons = []
            if result.evidence_failure:
                status = 'unverified'
                fails = sorted(set([*fails, result.evidence_failure]))
    except Exception as exc:
        failure = classify_exception(exc)
        status = 'error'; error = str(exc)[-1000:]; score = 0.0; fails = [failure]; checks = exception_checks(exc); incomplete_reasons = []
    profile = profile_for_model(model_tag)
    checks = {**checks, 'prompt_profile': profile.name, 'prompt_guide': profile.guide, 'runtime_options': profile.options, 'runtime_top_level': profile.top_level, 'trial_index': trial_index}
    cell = Cell(run_id, task.id, task.lane, task.weight, model_tag, meta['label'], meta['provider'], status, score, fails, incomplete_reasons, checks, round(time.time() - start, 3), response, error)
    outdir = root / task.id / meta['label'] / f'trial-{trial_index:03d}'
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
        hard = sum(len(r.hard_fails) for r in rows)
        incomplete_count = sum(1 for r in rows if r.incomplete_reasons)
        prompt_tokens_list = [r.checks.get("provider_response", {}).get("prompt_tokens", 0) for r in rows if isinstance(r.checks.get("provider_response", {}).get("prompt_tokens"), (int, float))]
        response_tokens_list = [r.checks.get("provider_response", {}).get("response_tokens", 0) for r in rows if isinstance(r.checks.get("provider_response", {}).get("response_tokens"), (int, float))]
        mean_prompt_tokens = round(sum(prompt_tokens_list) / len(prompt_tokens_list), 1) if prompt_tokens_list else 0
        mean_response_tokens = round(sum(response_tokens_list) / len(response_tokens_list), 1) if response_tokens_list else 0
        total_response_tokens = sum(response_tokens_list)
        coverage = f'{len(rows)}/{len(tasks) * expected_repeats}'
        critical_by_id = {t.id: t.critical for t in tasks}
        critical_hard = sum(1 for r in rows if critical_by_id.get(r.task_id) and r.hard_fails)
        coverage_complete = complete_trial_coverage(
            ((r.task_id, int(r.checks.get('trial_index', 1))) for r in rows),
            task_ids=(task.id for task in tasks), repeats=expected_repeats,
        )
        trial_stats = summarize_trials([r.score for r in rows], passed=[r.status == 'ok' and not r.hard_fails for r in rows], expected_trials=len(tasks) * expected_repeats)
        typical_gate = weighted >= 0.82 and hard <= 8 and critical_hard == 0 and coverage_complete and bool(trial_stats['eligible'])
        ranking.append({'model': model, 'weighted_score': round(weighted, 4), 'mean_score': round(sum(r.score for r in rows) / len(rows), 4), 'hard_fails': hard, 'critical_hard_fails': critical_hard, 'incomplete_count': incomplete_count, 'mean_prompt_tokens': mean_prompt_tokens, 'mean_response_tokens': mean_response_tokens, 'total_response_tokens': total_response_tokens, 'coverage': coverage, 'status_counts': {status: sum(r.status == status for r in rows) for status in sorted({r.status for r in rows})}, 'trial_statistics': trial_stats, 'typical_workload_gate': 'pass' if typical_gate else 'fail'})
    ranking.sort(key=lambda r: (-r['weighted_score'], r['hard_fails']))
    by_task = {}
    for task in tasks:
        rows = [c for c in cells if c.task_id == task.id]
        if rows:
            best = max(rows, key=lambda c: (c.score, -len(c.hard_fails)))
            by_task[task.id] = {'lane': task.lane, 'weight': task.weight, 'best_model': best.model_tag, 'best_score': best.score, 'best_hard_fails': best.hard_fails}
    data = {'run_id': run_id, 'created_at': datetime.now().astimezone().isoformat(timespec='seconds'), 'artifact_root': str(root), 'typical_workload_gate': {'required_weighted_score': 0.82, 'max_hard_fails': 8, 'critical_task_failures_allowed': 0, 'promotion_scope': 'workload-fit only; not broad autonomous promotion'}, 'tasks': [asdict(t) for t in tasks], 'ranking': ranking, 'by_task': by_task, 'results': [asdict(c) for c in cells]}
    (root / 'summary.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    with (root / 'results.jsonl').open('w', encoding='utf-8') as f:
        for c in cells:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + '\n')
    write_html(root / 'report.html', data)
    return data


def write_html(path: Path, data: dict[str, Any]) -> None:
    rows = ''.join(f"<tr><td>{i}</td><th><code>{html.escape(r['model'])}</code></th><td>{r['weighted_score']:.4f}</td><td>{r['mean_score']:.4f}</td><td>{r['hard_fails']}</td><td>{html.escape(r['coverage'])}</td><td>{r['typical_workload_gate']}</td></tr>" for i, r in enumerate(data['ranking'], 1))
    task_rows = ''.join(f"<tr><th>{html.escape(tid)}<br><small>{html.escape(v['lane'])}</small></th><td>{v['weight']}</td><td><code>{html.escape(v['best_model'])}</code></td><td>{v['best_score']:.4f}</td><td>{html.escape(', '.join(v['best_hard_fails']) or '—')}</td></tr>" for tid, v in data['by_task'].items())
    path.write_text(f"""<!doctype html><html><head><meta charset='utf-8'><title>PA Typical Workload Benchmark</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;background:#f6f8fb;color:#172033}}.card{{background:white;border:1px solid #d9e2ef;border-radius:12px;padding:16px;margin:14px 0}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d9e2ef;padding:8px;text-align:left;vertical-align:top}}th{{background:#eaf1fb}}code{{background:#edf2f7;padding:2px 4px;border-radius:4px}}</style></head><body><h1>PA Typical Workload Benchmark</h1><p>Run <code>{html.escape(data['run_id'])}</code>. This is a representative workload distribution check, not an autonomous broad-promotion gate.</p><div class='card'><h2>Model ranking</h2><table><tr><th>Rank</th><th>Model</th><th>Weighted</th><th>Mean</th><th>Hard-fails</th><th>Coverage</th><th>Gate</th></tr>{rows}</table></div><div class='card'><h2>Best model per scenario</h2><table><tr><th>Task</th><th>Weight</th><th>Best model</th><th>Score</th><th>Hard-fails</th></tr>{task_rows}</table></div><div class='card'><h2>Artifacts</h2><p><code>{html.escape(data['artifact_root'])}</code></p></div></body></html>""", encoding='utf-8')


def self_test() -> int:
    tasks = task_list()
    samples = {t.id: '' for t in tasks}
    samples['W01'] = '[Top 3]\n1. Prep call 2. Tax ask 3. Brief\n[Schedule Risks]\n14:00 review.\n[Health/Training]\nFitbit stale, breakfast missing.\n[Waiting/Blocked]\nFoodNoms breakfast.\n[Do Not Do]\nDo not clear whole list.'
    samples['W02'] = '# Session TL;DR\n[[2026-06-26]]\n\n## Summary\n- Benchmark extension.\n\n## Evidence and Artifacts\n- Report path present.\n- Backup path recorded.\n\n## Decisions\n- qwen3-coder candidate.\n\n## Open Items / Next Actions\n- [ ] Follow-up.\n\n## Handoff Notes\n- No secrets.'
    samples['W03'] = json.dumps({'skills_to_load':['tripsy-travel-management','apple-reminders','outbound-message-review'], 'context_to_read':['booking details'], 'first_actions':['verify hotel facts','draft only'], 'risks':['approval boundary']})
    samples['W04'] = '[Readiness]\nNot ready for hard training.\n[Evidence]\nHRV stale/partial, sleep low.\n[Recommendation]\nLight recovery only.\n[Human Check]\nThe user decides and may cross-check Google Health AI and Bevel AI.\n[Next Check]\nReassess tomorrow.'
    samples['W05'] = json.dumps({'action_required_today':True,'urgency':'high','category':'tax','draft_reply':'Draft: realized ledger missing; unrealized P&L not realized gain.','missing_info':['ledger'],'approval_required':True})
    samples['W06'] = json.dumps({'scope':'add runner','files_to_inspect':['scripts/model_prompt_profiles.py'],'implementation_steps':['record prompt_profile'],'tests':['py_compile','self-test'],'rollback':'backup first','do_not_do':['do not weaken validators']})
    samples['W07'] = json.dumps({'diagnosis':'producer vs mirror unclear','commands_to_run':['cronjob list','inspect artifact logs'],'likely_causes':['producer failed','mirror failed'],'safe_actions':['list before remove','check artifact'],'do_not_do':['do not guess job IDs']})
    samples['W08'] = '[Known Facts]\nvegetarian meals, water logistics.\n[Missing Facts]\nbooking, lat/lon, timezone.\n[Tripsy Records]\nHosting for hotels, activities need lat/lon.\n[Operational Plan]\ncollect coordinates and timezone.\n[Do Not Invent]\nNo booking invention.'
    samples['W09'] = json.dumps({'spoken_reply':'Benchmark finished. qwen3-coder looks strong; GLM stays out. Next: typical workload pack.','visible_reply':'qwen3-coder strong, GLM unsuitable, next action typical workload pack.','redactions':['no private data'],'constraints_kept':['short iPhone reply']})
    samples['W10'] = '[Source Facts]\n[EXTRACTED] FoodNoms is source; deterministic metrics required.\n[Inferences]\n[INFERRED] LLM may summarize only from supplied metrics.\n[Unknowns]\nNo metrics supplied.\n[Recommendation]\nDo not invent.\n[Evidence Labels]\nUse [EXTRACTED] and [INFERRED].'
    samples['W11'] = json.dumps({'draft_message':'Draft: Would vegetarian dinner options work for you?','tone_notes':['warm','practical','no invented relationship history'],'approval_required':True,'do_not_send':True,'risks':['do not imply history']})
    samples['W13'] = json.dumps({'search_plan':['web search GLM'], 'sources_to_check':['vendor claims','independent sources'], 'synthesis_plan':'compare public claims to local evidence', 'caveats':['vendor benchmark risk'], 'deliverable':'decision brief with web and local evidence'})
    samples['W14'] = '[Question]\nCurrent pricing.\n[Where I Would Check]\nofficial pricing page and reviews.\n[Freshness Risk]\npricing changes.\n[Answer Shape]\ninclude API reliability and health-coach depth.\n[When To Ask User]\nif product identity ambiguous.'
    samples['W15'] = json.dumps({'target':'external document','preflight_checks':['version history','backup/export'],'proposed_changes':['draft benchmark section'],'approval_needed':True,'verification':['verify after update'],'do_not_do':['do not include secret data']})
    samples['W16'] = '[Data Needed]\nApple, Fitbit, FoodNoms and CGM.\n[Correlation Method]\nwindowed correlation, not causation.\n[Confounders]\nsample size and training load.\n[Likely Output]\ntrend table.\n[Decision Use]\ntraining adjustment, no diagnosis.'
    samples['W17'] = json.dumps({'strategy_state':'94% filled, negative P&L','evidence_needed':['exchange balance'],'risk_checks':['risk budget','tax'],'configuration_review':['review grid configuration thresholds'],'recommendation':'wait for evidence','do_not_do':['do not execute trade']})
    samples['W18'] = '[Inputs]\ncalendar, reminders, journal, health, inbox, RSS.\n[Brief Structure]\nTop actions then details.\n[Priority Logic]\nprioritize not dump.\n[Health/Data Caveats]\nmark stale.\n[Delivery Check]\nverify artifact and delivery.'
    samples['W19'] = json.dumps({'selection_criteria':['signal over noise'],'summary_structure':['AI audit','governance','PA opportunities'],'source_handling':['titles and source links'],'actionability':['implications'],'exclusions':['duplicates','hype']})
    samples['W20'] = '[Document Type]\nPDF/contract/report.\n[Extraction Plan]\nextract first.\n[Key Questions]\nwhat matters.\n[Risk Flags]\nlegal/finance/security risk for review.\n[Output Artifact]\nartifact path and next action.'
    samples['W21'] = json.dumps({'answer':'Use latest Evidence B: Gold 100, Global Equity 400, Europe Equity 100, Bonds 150, Emerging Markets 50, total 800.', 'evidence_used':['Evidence B is the latest EUR 800 action target'], 'rejected_source':['Do not scale the older EUR 600 implemented split'], 'calculation_check':'100+400+100+150+50=800 and percentages sum to 100.', 'finance_guardrail':'Debt paydown remains a separate guardrail, but it does not override the requested fund allocation answer.'})
    samples['W12'] = '[Decision]\nExpand qwen3-coder by lane, not broad default.\n[Evidence]\nStrong scores.\n[Tradeoffs]\nHealth human-in-loop calibration.\n[Next Actions]\nRun follow-up benchmark.\n[Not Now]\nNot broad default.'
    bad = []
    for t in tasks:
        score, fails, checks = validate(t, samples[t.id])
        if score < .8 or fails:
            bad.append((t.id, score, fails, checks))
    print(json.dumps({'self_test': 'pass' if not bad else 'fail', 'bad': bad}, indent=2))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', default=','.join(DEFAULT_MODELS), help='Comma-separated model tags')
    ap.add_argument('--run-id', default=RUN_ID_DEFAULT)
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
    write_manifest(root, build_manifest(run_id=args.run_id, models=models, task_payload=[asdict(t) for t in task_list()], source_paths=[Path(__file__), BASE_DIR / 'scripts' / 'model_prompt_profiles.py'], repeats=args.repeats, seed=args.seed, run_order=args.run_order, privacy_class='synthetic', argv=sys.argv, model_routes={model: model_meta(model)['provider'] for model in models}))
    tasks = task_list()
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
