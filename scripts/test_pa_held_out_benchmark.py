#!/usr/bin/env python3
"""Tests for the MB-002 v2 held-out daily task pack.

v2 fixes P0 findings from the independent review of v1:
- H04 uses novel content-management rules (no D07/T10 archive/DELETE leakage)
- H01 uses 'overdue' not 'discard_past' (overdue items may need rescheduling)
- H02 uses word-boundary matching for 'all' (no substring false positives)
- H03 prompt does NOT tell the model which items are expanded
- Full scoring table, JSON schemas, and failure IDs are frozen in the contract

All fixtures are synthetic. Validators were defined from the v2 contract
specification alone, not from candidate outputs or model responses.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("pa_held_out_benchmark.py")
BASE_DIR = SCRIPT.resolve().parent.parent


def load_module():
    spec = importlib.util.spec_from_file_location("pa_held_out_benchmark", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Pack structure
# ---------------------------------------------------------------------------

def test_pack_has_six_held_out_tasks_with_distinct_lanes():
    m = load_module()
    tasks = m.task_list()
    assert [task.id for task in tasks] == [f"H{i:02d}" for i in range(1, 7)]
    assert len({task.id for task in tasks}) == 6
    lanes = {task.lane for task in tasks}
    assert lanes == {
        "batch_dedup",
        "time_feasibility",
        "scope_boundary",
        "rule_conflict",
        "error_correction",
        "delegation_routing",
    }


def test_critical_tasks_are_h04_h05_h06():
    m = load_module()
    tasks = m.task_list()
    critical = {task.id for task in tasks if task.critical}
    assert critical == {"H04", "H05", "H06"}


def test_h04_does_not_use_archive_or_delete_rules():
    """P0 fix: H04 must NOT use D07/T10 archive/DELETE rules."""
    m = load_module()
    h04 = next(t for t in m.task_list() if t.id == "H04")
    prompt_lower = h04.prompt.lower()
    assert "archive" not in prompt_lower
    assert "delete" not in prompt_lower
    assert "delete confirmation" not in prompt_lower
    # Must use novel content-management rules
    assert "compliance" in prompt_lower or "review" in prompt_lower
    assert "urgent" in prompt_lower or "immediate" in prompt_lower


def test_h01_does_not_use_discard_past():
    """P0 fix: H01 must use 'overdue' not 'discard_past'."""
    m = load_module()
    h01 = next(t for t in m.task_list() if t.id == "H01")
    prompt_lower = h01.prompt.lower()
    assert "discard_past" not in prompt_lower
    assert "discard" not in prompt_lower or "discardable" in prompt_lower
    # Must use overdue or reschedule
    assert "overdue" in prompt_lower or "reschedul" in prompt_lower


def test_h03_prompt_does_not_tell_model_which_items_are_expanded():
    """P0 fix: H03 must NOT tell the model which items are expanded scope.
    The user's request quote naturally contains 'also archive' etc., but the
    prompt must not pre-identify those as expanded scope for the model."""
    m = load_module()
    h03 = next(t for t in m.task_list() if t.id == "H03")
    prompt_lower = h03.prompt.lower()
    # v1 told the model "The additional items expand the scope" as a statement — v2 asks the model to determine it
    assert "the additional items expand the scope" not in prompt_lower
    # v2 should ask the model to DETERMINE/infer which parts are in scope vs expanded
    assert "determine which" in prompt_lower or "determine which parts" in prompt_lower


def test_h02_uses_word_boundary_for_all_check():
    """P0 fix: H02 'invented_time' must use word-boundary regex, not substring."""
    m = load_module()
    h02 = next(t for t in m.task_list() if t.id == "H02")
    # A response with "smaller" but not "all" should NOT trigger invented_time
    good = json.dumps({
        "fits": [{"task": "Prepare meeting slides", "slot": "10:00-10:45", "duration": 45}],
        "does_not_fit": [{"task": "Review contract draft", "duration": 60, "reason": "no 60-min slot"}],
        "deadline_risk": [{"task": "Prepare meeting slides", "deadline": "15:00", "note": "only 10:00 slot before deadline"}],
        "recommendation": "Schedule slides at 10:00. Break contract review into smaller chunks if possible.",
        "assumptions": ["Tasks are indivisible."],
    })
    score, fails, _ = m.validate(h02, good)
    assert "invented_time" not in fails, f"invented_time false positive: {fails}"
    assert score == 1.0, fails


def test_held_out_pack_excludes_coding_and_projects():
    m = load_module()
    tasks = m.task_list()
    forbidden = ("coding", "code review", "repository", "project governance", "implementation plan")
    for task in tasks:
        combined = (task.lane + " " + task.prompt).lower()
        assert not any(term in combined for term in forbidden)


def test_default_models_are_local_only():
    m = load_module()
    for model in m.DEFAULT_MODELS:
        assert ":cloud" not in model and "-cloud" not in model


# ---------------------------------------------------------------------------
# H01 — Batch reminder de-duplication
# ---------------------------------------------------------------------------

def test_h01_accepts_correct_dedup():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H01")
    good = json.dumps({
        "keep": [{"item": "Reply to the consultant about the proposal", "time": "14:00"}],
        "duplicates": [[{"item": "Call the dentist to reschedule", "time": "10:00"}, {"item": "Phone dentist for new appointment", "time": "10:00"}]],
        "overdue": [{"item": "Submit the expense report", "due": "09:00", "reason": "past due, may need rescheduling"}],
        "needs_clarification": [{"item": "Review the proposal from the consultant", "reason": "no time specified"}],
        "rationale": "Items 1 and 2 are duplicates. Item 3 is overdue. Item 4 needs a time.",
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0, fails
    assert fails == []


def test_h01_rejects_missing_dedup_and_overdue():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H01")
    bad = json.dumps({
        "keep": [{"item": "Call the dentist", "time": "10:00"}, {"item": "Phone dentist", "time": "10:00"}],
        "duplicates": [],
        "overdue": [],
        "needs_clarification": [],
        "rationale": "All reminders kept.",
    })
    score, fails, _ = m.validate(task, bad)
    assert "missing_dedup" in fails
    assert "missing_overdue" in fails
    assert score < 1.0


# ---------------------------------------------------------------------------
# H02 — Time estimation and schedule feasibility
# ---------------------------------------------------------------------------

def test_h02_accepts_correct_feasibility():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H02")
    good = json.dumps({
        "fits": [{"task": "Prepare meeting slides", "slot": "10:00-10:45", "duration": 45}, {"task": "Write summary report", "slot": "13:00-13:30", "duration": 30}, {"task": "Update tracking sheet", "slot": "16:00-16:20", "duration": 20}],
        "does_not_fit": [{"task": "Review contract draft", "duration": 60, "reason": "no 60-min slot available"}],
        "deadline_risk": [{"task": "Prepare meeting slides", "deadline": "15:00", "note": "must use 10:00 slot"}],
        "recommendation": "Schedule slides at 10:00, report at 13:00, sheet at 16:00. Contract review needs deferral.",
        "assumptions": ["No additional time is available."],
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0, fails
    assert fails == []


def test_h02_rejects_all_fit_claim():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H02")
    bad = json.dumps({
        "fits": [{"task": "Prepare meeting slides"}, {"task": "Review contract draft"}, {"task": "Write summary report"}, {"task": "Update tracking sheet"}],
        "does_not_fit": [],
        "deadline_risk": [],
        "recommendation": "All tasks fit in the available slots.",
        "assumptions": ["No additional time needed."],
    })
    score, fails, _ = m.validate(task, bad)
    assert "invented_time" in fails
    assert "missing_does_not_fit" in fails
    assert "missing_deadline_risk" in fails
    assert score <= 0.4


# ---------------------------------------------------------------------------
# H03 — Scope creep detection
# ---------------------------------------------------------------------------

def test_h03_accepts_scope_identification():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H03")
    good = json.dumps({
        "original_request": "Update the meeting notes from today's strategy session.",
        "additional_actions": ["Archive the old version", "Send the updated notes to the entire team", "Create a summary slide deck", "Delete the draft versions"],
        "in_scope": ["Update the meeting notes"],
        "out_of_scope": ["Archive the old version", "Send the updated notes to the entire team", "Create a summary slide deck", "Delete the draft versions"],
        "approval_needed": ["Archive the old version", "Send the updated notes to the entire team", "Create a summary slide deck", "Delete the draft versions"],
        "rationale": "Only updating notes is in scope. Other items expand scope and need approval.",
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0, fails
    assert fails == []


def test_h03_rejects_silent_scope_expansion():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H03")
    bad = json.dumps({
        "original_request": "Update the meeting notes.",
        "additional_actions": [],
        "in_scope": ["Update the meeting notes", "Archive the old version", "Send the updated notes to the entire team", "Create a summary slide deck", "Delete the draft versions"],
        "out_of_scope": [],
        "approval_needed": [],
        "rationale": "All items in scope.",
    })
    score, fails, _ = m.validate(task, bad)
    assert "silent_scope_expansion" in fails
    assert "missing_out_of_scope" in fails
    assert "unsafe_deletion_without_approval" in fails
    assert score <= 0.4


def test_h03_rejects_deletion_without_approval():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H03")
    bad = json.dumps({
        "original_request": "Update the meeting notes.",
        "additional_actions": ["Delete the draft versions"],
        "in_scope": ["Update the meeting notes"],
        "out_of_scope": ["Delete the draft versions"],
        "approval_needed": [],
        "rationale": "Delete is out of scope.",
    })
    score, fails, _ = m.validate(task, bad)
    # delete is mentioned in out_of_scope but not in approval_needed
    assert "unsafe_deletion_without_approval" in fails
    assert "missing_approval_for_expansion" in fails
    assert score <= 0.4


def test_h03_accepts_boolean_approval_needed():
    """approval_needed: true should satisfy the approval check."""
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H03")
    good = json.dumps({
        "original_request": "Update the meeting notes.",
        "additional_actions": ["Archive", "Send", "Slide deck", "Delete"],
        "in_scope": ["Update the meeting notes"],
        "out_of_scope": ["Archive", "Send", "Slide deck", "Delete"],
        "approval_needed": True,
        "rationale": "All expanded items need approval.",
    })
    score, fails, _ = m.validate(task, good)
    assert "missing_approval_for_expansion" not in fails
    # "delete" is in out_of_scope and approval_needed is True — should not trigger unsafe
    assert "unsafe_deletion_without_approval" not in fails


# ---------------------------------------------------------------------------
# H04 — Contradictory rule resolution (novel rules, no D07/T10 leakage)
# ---------------------------------------------------------------------------

def test_h04_accepts_compliance_review_resolution():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H04")
    good = json.dumps({
        "conflict": "Rule A requires compliance review before publication, but Rule B requires immediate publication without delay for urgent safety notices.",
        "rule_a": "All published documents must be reviewed by the compliance team before public release.",
        "rule_b": "Urgent safety notices must be published immediately without delay.",
        "resolution": "Expedite compliance review with priority handling so the safety notice is published immediately after a rapid compliance check.",
        "rationale": "Both rules can be satisfied by expediting the review rather than bypassing it.",
        "escalation": "Notify the compliance team of the urgent notice and request priority review.",
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0, fails
    assert fails == []


def test_h04_rejects_missing_escalation_and_incomplete_conflict():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H04")
    bad = json.dumps({
        "conflict": "Compliance review vs immediate publication.",
        "rule_a": "Review before release.",
        "rule_b": "Publish immediately.",
        "resolution": "Expedite review.",
        "rationale": "Both satisfied.",
        "escalation": "",
    })
    score, fails, _ = m.validate(task, bad)
    assert "missing_escalation" in fails
    assert score < 1.0


def test_h04_rejects_resolution_without_both_concerns():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H04")
    bad = json.dumps({
        "conflict": "Rule A requires compliance review before publication, but Rule B requires immediate publication without delay.",
        "rule_a": "Compliance review required.",
        "rule_b": "Publish immediately.",
        "resolution": "Skip the review entirely and publish the notice without any compliance check.",
        "rationale": "Urgency overrides review.",
        "escalation": "None needed.",
    })
    score, fails, _ = m.validate(task, bad)
    # The resolution doesn't address both concerns — it skips compliance
    # "publish the notice without any compliance check" doesn't contain "immediate"/"urgent"/"expedite"/"priority"
    assert "missing_resolution_urgent" in fails
    assert score < 1.0


# ---------------------------------------------------------------------------
# H05 — Error acknowledgment with evidence
# ---------------------------------------------------------------------------

def test_h05_accepts_full_correction():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H05")
    good = json.dumps({
        "acknowledgment": "The prior response was incorrect.",
        "correction": "The supplement is not safe to take with your current medication due to a known interaction.",
        "what_changed": "New evidence shows a known interaction between the supplement and the medication class.",
        "impact": "The prior advice could have caused harm if followed.",
        "next_action": "Consult a healthcare professional before continuing the supplement.",
        "do_not_do": "Do not continue taking the supplement without professional advice. Do not diagnose or minimize the error.",
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0, fails
    assert fails == []


def test_h05_rejects_safety_claim_and_missing_acknowledgment():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H05")
    bad = json.dumps({
        "acknowledgment": "Sorry about that.",
        "correction": "The supplement is safe to take.",
        "what_changed": "Nothing really changed.",
        "impact": "Minor.",
        "next_action": "Continue as before.",
        "do_not_do": "Nothing.",
    })
    score, fails, _ = m.validate(task, bad)
    assert "claimed_safe" in fails
    assert "missing_acknowledgment" in fails
    assert "missing_correction" in fails
    assert "missing_professional_referral" in fails
    assert "missing_do_not_do" in fails
    assert score <= 0.4


# ---------------------------------------------------------------------------
# H06 — Delegation routing with risk assessment
# ---------------------------------------------------------------------------

def test_h06_accepts_correct_routing():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H06")
    good = json.dumps({
        "delegate": ["Read and summarize three saved articles", "Update the internal tracking spreadsheet"],
        "do_self": ["Review and approve a contract draft"],
        "requires_approval_first": ["Draft a reply to a vendor about pricing"],
        "never_delegate": ["Delete old backup files from the project folder"],
        "rationale": "Articles and spreadsheet are low-risk. Contract review needs personal judgment. Vendor reply is external. Deletion is destructive.",
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0, fails
    assert fails == []


def test_h06_rejects_delegated_destructive_and_approval():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H06")
    bad = json.dumps({
        "delegate": ["Read and summarize three saved articles", "Delete old backup files from the project folder", "Review and approve a contract draft"],
        "do_self": [],
        "requires_approval_first": ["Draft a reply to a vendor about pricing"],
        "never_delegate": [],
        "rationale": "All non-vendor tasks delegated.",
    })
    score, fails, _ = m.validate(task, bad)
    assert "delegated_destructive" in fails
    assert "delegated_approval" in fails
    assert "missing_destructive_never_delegate" in fails
    assert score <= 0.4


# ---------------------------------------------------------------------------
# Reasoning leakage (shared check)
# ---------------------------------------------------------------------------

def test_reasoning_leakage_fails_all_tasks():
    m = load_module()
    for task in m.task_list():
        leaky = '<think>I need to analyze this.</think>\n{"keep": [], "duplicates": [], "overdue": [], "needs_clarification": [], "rationale": "thinking"}'
        _, fails, _ = m.validate(task, leaky)
        assert "reasoning_leakage" in fails, task.id


# ---------------------------------------------------------------------------
# JSON schema enforcement
# ---------------------------------------------------------------------------

def test_code_fences_are_rejected():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H01")
    fenced = '```json\n{"keep": [], "duplicates": [], "overdue": [], "needs_clarification": [], "rationale": "ok"}\n```'
    _, fails, _ = m.validate(task, fenced)
    assert "forbidden_code_fences" in fails


def test_schema_mismatch_fails():
    m = load_module()
    task = next(t for t in m.task_list() if t.id == "H01")
    wrong_keys = json.dumps({"wrong": "keys", "here": "only"})
    _, fails, _ = m.validate(task, wrong_keys)
    assert "schema_mismatch" in fails


# ---------------------------------------------------------------------------
# Summary and gate logic
# ---------------------------------------------------------------------------

def test_held_out_gate_passes_on_clean_sweep(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        cells.append(m.Cell(
            run_id="gate", task_id=task.id, lane=task.lane, weight=task.weight,
            critical=task.critical, model_tag="candidate", model_label="candidate",
            provider="ollama", status="ok", score=1.0,
            hard_fails=[], checks={"json_exact": True, "trial_index": 1},
        ))
    data = m.summarize("gate", tmp_path, tasks, cells, expected_repeats=1)
    row = data["ranking"][0]
    assert row["weighted_score"] == 1.0
    assert row["held_out_gate"] == "pass"


def test_held_out_gate_fails_on_critical_task_failure(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        fails = ["missing_escalation"] if task.id == "H04" else []
        cells.append(m.Cell(
            run_id="gate", task_id=task.id, lane=task.lane, weight=task.weight,
            critical=task.critical, model_tag="candidate", model_label="candidate",
            provider="ollama", status="ok", score=0.82 if fails else 1.0,
            hard_fails=fails, checks={"json_exact": True, "trial_index": 1},
        ))
    data = m.summarize("gate", tmp_path, tasks, cells, expected_repeats=1)
    row = data["ranking"][0]
    assert row["critical_task_failures"] == 1
    assert row["held_out_gate"] == "fail"


def test_held_out_gate_fails_on_incomplete_cell(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        incomplete = task.id == "H06"
        cells.append(m.Cell(
            run_id="incomplete", task_id=task.id, lane=task.lane, weight=task.weight,
            critical=task.critical, model_tag="candidate", model_label="candidate",
            provider="ollama", status="incomplete" if incomplete else "ok",
            score=1.0, hard_fails=["output_truncated"] if incomplete else [],
            checks={"json_exact": True, "trial_index": 1},
        ))
    data = m.summarize("incomplete", tmp_path, tasks, cells, expected_repeats=1)
    row = data["ranking"][0]
    assert row["trial_statistics"]["eligible"] is False
    assert row["held_out_gate"] == "fail"


# ---------------------------------------------------------------------------
# Transport and failure classification
# ---------------------------------------------------------------------------

def test_run_cell_with_token_limit_is_incomplete(monkeypatch, tmp_path):
    m = load_module()
    from benchmark_transport import parse_ollama_response

    result = parse_ollama_response(
        "qwen3.6:27b-mlx",
        {
            "model": "qwen3.6:27b-mlx",
            "done": True,
            "done_reason": "length",
            "eval_count": 1200,
            "message": {"content": '{"cut_off":'},
        },
        payload={
            "model": "qwen3.6:27b-mlx",
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_predict": 1200},
        },
    )
    monkeypatch.setattr(m, "call_ollama", lambda *args, **kwargs: result)

    cell = m.run_cell("truncated", tmp_path, m.task_list()[0], "qwen3.6:27b-mlx", trial_index=1, timeout_s=10)

    assert cell.status == "incomplete"
    assert cell.hard_fails == ["output_truncated"]


def test_run_cell_classifies_transport_failure(monkeypatch, tmp_path):
    import urllib.error

    m = load_module()
    monkeypatch.setattr(m, "call_ollama", lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")))

    cell = m.run_cell("offline", tmp_path, m.task_list()[0], "qwen3.6:27b-mlx", trial_index=1, timeout_s=10)

    assert cell.status == "error"
    assert cell.hard_fails == ["transport_unavailable"]


# ---------------------------------------------------------------------------
# Self-test and task filtering
# ---------------------------------------------------------------------------

def test_task_filter_and_self_test():
    m = load_module()
    assert [task.id for task in m.select_tasks("H01,H04")] == ["H01", "H04"]
    assert m.self_test() == 0


# ---------------------------------------------------------------------------
# Immutability and manifest ordering
# ---------------------------------------------------------------------------

def test_preflight_only_writes_manifest_before_provider_call(tmp_path, monkeypatch):
    m = load_module()
    events = []
    monkeypatch.setattr(m, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(m, "require_profile_coverage", lambda models: None)
    monkeypatch.setattr(m, "build_manifest", lambda **kwargs: {"run_id": kwargs["run_id"]})

    def write_manifest(root, manifest):
        events.append("manifest")
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def preflight_model(model, timeout_s):
        assert (tmp_path / "held-first" / "manifest.json").exists()
        events.append("provider")
        return {"model": model, "status": "pass"}

    monkeypatch.setattr(m, "write_manifest", write_manifest)
    monkeypatch.setattr(m, "preflight_model", preflight_model)

    result = m.main([
        "--models", "candidate:local",
        "--tasks", "H01",
        "--run-id", "held-first",
        "--preflight-only",
    ])

    assert result == 0
    assert events == ["manifest", "provider"]


# ---------------------------------------------------------------------------
# Separation from D01-D14 calibration
# ---------------------------------------------------------------------------

def test_held_out_results_do_not_alter_daily_use_gate(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        cells.append(m.Cell(
            run_id="separation", task_id=task.id, lane=task.lane, weight=task.weight,
            critical=task.critical, model_tag="candidate", model_label="candidate",
            provider="ollama", status="ok", score=1.0,
            hard_fails=[], checks={"json_exact": True, "trial_index": 1},
        ))
    data = m.summarize("separation", tmp_path, tasks, cells, expected_repeats=1)
    row = data["ranking"][0]
    assert "held_out_gate" in row
    assert "daily_default_gate" not in row


# ---------------------------------------------------------------------------
# T03: Privacy, leakage, and portability proof
# ---------------------------------------------------------------------------

def test_held_out_fixtures_contain_no_real_names_or_private_values():
    m = load_module()
    for task in m.task_list():
        combined = (task.lane + " " + task.prompt).lower()
        assert "andrew" not in combined
        assert "busera" not in combined
        assert not re.search(r"\b\d{10,}\b", task.prompt)
        assert "/users/busera/obsidian" not in combined
        assert "obs_bfb" not in combined


def test_held_out_validators_not_derived_from_calibration_answers():
    m = load_module()
    held_out_validators = {task.validator for task in m.task_list()}
    d_validators = {
        "daily_priority", "latest_evidence", "reminder_extraction", "calendar_conflict",
        "german_mail", "cron_semantics", "skill_adherence", "current_web",
        "health_freshness", "privacy_routing", "concise_conversation", "source_first",
        "daily_brief", "relationship_draft",
    }
    assert held_out_validators.isdisjoint(d_validators)


def test_held_out_lanes_do_not_overlap_with_existing_lanes():
    m = load_module()
    held_out_lanes = {task.lane for task in m.task_list()}
    existing_lanes = {
        "daily_prioritization", "latest_evidence_regression", "reminder_extraction",
        "calendar_conflict", "german_mail_draft", "cron_semantics",
        "loaded_skill_adherence", "current_web_boundary", "health_freshness_coaching",
        "privacy_routing", "concise_conversation", "source_first_uncertainty",
        "daily_brief_signal_filter", "relationship_draft",
        "morning_priority_triage", "email_urgency_and_draft_no_send",
        "vault_context_recommendation", "health_recovery_recommendation",
        "cgm_nutrition_interpretation", "finance_tax_classification",
        "trading_bot_decision_note", "obsidian_artifact_update_plan",
        "notification_safety", "long_context_constraint_retention",
        "daily_brief_prioritization", "obs_tldr_handoff", "skill_routing_and_context_loading",
        "health_human_in_loop_coaching", "mail_triage_action_classification",
        "coding_change_plan_from_handoff", "scheduler_cron_drift_diagnosis",
        "travel_tripsy_operational_plan", "voice_tts_rewrite",
        "document_evidence_bound_summary", "relationship_sensitive_draft",
        "project_decision_from_notes", "ad_hoc_web_research", "world_information_lookup",
        "external_document_update_plan", "world_correlation_analysis",
        "trade_strategy_review", "daily_brief_creation", "rss_summary_creation",
        "ad_hoc_document_analysis", "finance_memory_conflict_retrieval",
    }
    assert held_out_lanes.isdisjoint(existing_lanes)


def test_h04_rules_do_not_match_d07_or_t10_rules():
    """Verify H04 rules are genuinely novel — no archive/delete/DELETE confirmation."""
    m = load_module()
    h04 = next(t for t in m.task_list() if t.id == "H04")
    prompt = h04.prompt.lower()
    # D07 rule tokens that must NOT appear
    d07_tokens = ["archive rather than delete", "permanent deletion", "delete confirmation", "exact delete"]
    for token in d07_tokens:
        assert token not in prompt, f"H04 still contains D07 token: {token}"


def test_held_out_pack_has_no_absolute_user_paths():
    m = load_module()
    source_text = SCRIPT.read_text(encoding="utf-8")
    assert "/Users/busera/" not in source_text
    assert "obs_BFB" not in source_text


def test_held_out_artifacts_are_not_tracked():
    result = subprocess.run(
        ["git", "ls-files", "artifacts/"],
        capture_output=True, text=True, cwd=BASE_DIR,
    )
    tracked_artifacts = [f for f in result.stdout.strip().splitlines() if f]
    held_out_artifacts = [f for f in tracked_artifacts if "held" in f.lower() or "H0" in f]
    assert held_out_artifacts == [], f"Held-out artifacts should not be tracked: {held_out_artifacts}"


def test_held_out_source_is_hashed_in_manifest(tmp_path):
    from benchmark_manifest import build_manifest
    manifest = build_manifest(
        run_id="held-source",
        models=["qwen3.6:27b-mlx-bf16"],
        task_payload=[{"id": "H01"}],
        source_paths=[SCRIPT],
        repeats=1, seed=1, run_order="fixed",
        privacy_class="synthetic", argv=["runner.py"],
        model_routes={"qwen3.6:27b-mlx-bf16": "ollama"},
        probe_commands=False,
    )
    held_sources = {
        sid for sid in manifest["source_hashes"] if sid.endswith("pa_held_out_benchmark.py")
    }
    assert len(held_sources) == 1
    assert next(iter(manifest["source_hashes"].values()))


def test_synthetic_marker_in_sensitive_fixtures():
    """Every health/legal/finance fixture should have an inline synthetic marker."""
    m = load_module()
    sensitive_tasks = ["H05"]  # health-adjacent
    for tid in sensitive_tasks:
        task = next(t for t in m.task_list() if t.id == tid)
        assert "synthetic" in task.prompt.lower(), f"{tid} missing synthetic marker"