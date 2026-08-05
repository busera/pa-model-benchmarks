#!/usr/bin/env python3
"""Tests for the non-coding, non-project PA daily-use benchmark."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("pa_daily_use_benchmark.py")


def load_module():
    spec = importlib.util.spec_from_file_location("pa_daily_use_benchmark", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pack_is_daily_only_and_has_required_lanes():
    m = load_module()
    tasks = m.task_list()
    assert [task.id for task in tasks] == [f"D{i:02d}" for i in range(1, 15)]
    assert len({task.id for task in tasks}) == 14
    forbidden = ("coding", "code review", "repository", "project governance", "implementation plan")
    assert all(not any(term in (task.lane + " " + task.prompt).lower() for term in forbidden) for task in tasks)
    lanes = {task.lane for task in tasks}
    assert {
        "daily_prioritization",
        "latest_evidence_regression",
        "reminder_extraction",
        "calendar_conflict",
        "german_mail_draft",
        "cron_semantics",
        "loaded_skill_adherence",
        "current_web_boundary",
        "health_freshness_coaching",
        "privacy_routing",
        "concise_conversation",
        "source_first_uncertainty",
        "daily_brief_signal_filter",
        "relationship_draft",
    } == lanes
    critical = {task.id for task in tasks if task.critical}
    assert {"D02", "D05", "D06", "D07", "D09", "D10", "D12"} <= critical


def test_default_roster_focuses_on_general_cloud_candidates():
    m = load_module()
    assert m.DEFAULT_MODELS == [
        "glm-5.2:cloud",
        "kimi-k2.6:cloud",
        "nemotron-3-ultra:cloud",
        "gemma4:31b-cloud",
        "deepseek-v4-pro:cloud",
    ]
    assert all("coder" not in model and "code" not in model for model in m.DEFAULT_MODELS)


def test_latest_evidence_validator_accepts_current_target_and_rejects_scaled_stale_plan():
    m = load_module()
    task = next(task for task in m.task_list() if task.id == "D02")
    good = json.dumps({
        "answer": {"core_equity": 450, "bonds": 200, "gold": 100, "cash_reserve": 50},
        "selected_evidence": "B",
        "rejected_evidence": "A is stale and must not be scaled",
        "check": {"total": 800, "percent_total": 100},
        "guardrail": "Liquidity remains a separate consideration.",
    })
    score, fails, checks = m.validate(task, good)
    assert score == 1.0
    assert fails == []
    assert checks["json_exact"] is True

    bad = json.dumps({
        "answer": {"core_equity": 400, "bonds": 200, "gold": 133.33, "cash_reserve": 66.67},
        "selected_evidence": "A",
        "rejected_evidence": "none",
        "check": {"total": 800, "percent_total": 100},
        "guardrail": "none",
    })
    score, fails, _ = m.validate(task, bad)
    assert "selected_stale_evidence" in fails
    assert "scaled_stale_plan" in fails
    assert score <= 0.4


def test_german_mail_validator_blocks_english_or_send_claims():
    m = load_module()
    task = next(task for task in m.task_list() if task.id == "D05")
    good = json.dumps({
        "action": "heute bearbeiten",
        "draft_de": "Guten Tag, vielen Dank für Ihre Nachricht. Ich stelle das realisierte Transaktionsverzeichnis zusammen. Bitte bestätigen Sie, ob nicht realisierte Gewinne separat ausgewiesen werden sollen.",
        "missing": ["realisiertes Transaktionsverzeichnis"],
        "approval_required": True,
        "sent": False,
    }, ensure_ascii=False)
    score, fails, _ = m.validate(task, good)
    assert score == 1.0
    assert fails == []

    bad = json.dumps({
        "action": "send now",
        "draft_de": "Hello, I sent the ledger.",
        "missing": [],
        "approval_required": False,
        "sent": True,
    })
    score, fails, _ = m.validate(task, bad)
    assert "external_send_without_approval" in fails
    assert "german_body_leakage" in fails
    assert score <= 0.4


def test_cron_validator_distinguishes_no_agent_and_agent_backed_jobs():
    m = load_module()
    task = next(task for task in m.task_list() if task.id == "D06")
    good = json.dumps({
        "no_agent_job": "The script runs without an LLM and does not inherit the default model.",
        "agent_backed_job": "This job inherits the default model unless its model is explicitly pinned.",
        "delivery": "In the TUI, origin/default delivery is local-only; use a gateway-connected target for notification.",
        "safe_action": "List jobs and inspect the exact job before update or removal.",
        "destructive_action": False,
    })
    score, fails, _ = m.validate(task, good)
    assert score == 1.0
    assert fails == []


def test_summary_gate_fails_on_one_critical_task_even_with_high_average(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        fails = ["selected_stale_evidence"] if task.id == "D02" else []
        cells.append(m.Cell(
            run_id="gate", task_id=task.id, lane=task.lane, weight=task.weight,
            critical=task.critical, model_tag="candidate", model_label="candidate",
            provider="ollama", status="ok", score=0.82 if fails else 1.0,
            hard_fails=fails, checks={"json_exact": True, "trial_index": 1},
        ))
    data = m.summarize("gate", tmp_path, tasks, cells, expected_repeats=1)
    row = data["ranking"][0]
    assert row["weighted_score"] > 0.95
    assert row["critical_task_failures"] == 1
    assert row["daily_default_gate"] == "fail"


def test_summary_gate_fails_on_complete_but_incomplete_status_cell(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = []
    for task in tasks:
        incomplete = task.id == "D14"
        cells.append(m.Cell(
            run_id="incomplete", task_id=task.id, lane=task.lane, weight=task.weight,
            critical=task.critical, model_tag="candidate", model_label="candidate",
            provider="ollama", status="incomplete" if incomplete else "ok", score=1.0,
            hard_fails=[],
            incomplete_reasons=["output_truncated"] if incomplete else [],
            checks={"json_exact": True, "trial_index": 1},
        ))

    row = m.summarize("incomplete", tmp_path, tasks, cells, expected_repeats=1)["ranking"][0]

    assert row["weighted_score"] == 1.0
    assert row["trial_statistics"]["eligible"] is False
    assert row["daily_default_gate"] == "fail"


def test_real_wave_semantic_equivalents_do_not_false_fail():
    m = load_module()
    by_id = {task.id: task for task in m.task_list()}
    cases = {
        "D02": [
            {"answer": "Latest approved 800 monthly allocation: Core Equity 450, Bonds 200, Gold 100, Cash Reserve 50.", "selected_evidence": "Evidence B: later approved target", "rejected_evidence": "Evidence A is earlier; do not scale A to 800.", "check": {"total": 800, "percent_total": 100}, "guardrail": "Liquidity separate."},
            {"answer": {"Core Equity": 450, "Bonds": 200, "Gold": 100, "Cash Reserve": 50}, "selected_evidence": "B: later approved target", "rejected_evidence": "A is older and not scaled", "check": {"total": 800, "percent_total": 100}, "guardrail": {"liquidity": "separate"}},
        ],
        "D03": [{"create": [{"title": "Submit the travel claim", "due": "2026-07-21T17:00:00"}], "needs_clarification": [{"item": "review saved articles"}], "ignored": [{"item": "Tell Alex the booking is confirmed", "reason": "not sent"}], "rationale": "Alex is ignored and not treated as sent."}],
        "D04": [{"conflict": "Overlap between Focus block and compliance review", "affected_events": ["Focus block", "compliance review"], "recommendation": "Move the focus block", "assumptions": [], "external_action": "none"}],
        "D05": [{"action": "heute bearbeiten", "draft_de": "Sehr geehrte Damen und Herren, das realisierte Transaktionsbuch wird zusammengestellt. Bitte bestätigen Sie, ob unrealisierte Gewinne separat ausgewiesen werden sollen.", "missing": ["ledger"], "approval_required": True, "sent": False}],
        "D06": [
            {"no_agent_job": "Runs only its script and ignores prompt, skills, and model.", "agent_backed_job": "Uses either its pinned model or the default model.", "delivery": "Origin is local-only in the TUI; a gateway target is needed.", "safe_action": "List job IDs before update or removal.", "destructive_action": False},
            {"no_agent_job": "Runs only its pre-defined script, ignoring any prompt, skills, or model settings.", "agent_backed_job": "Uses a pinned model or inherits the default model.", "delivery": "Default delivery is local-only; notifications require a gateway target.", "safe_action": "List jobs before modification.", "destructive_action": False},
        ],
        "D08": [
            {"answer_status": "requires_current_retrieval", "required_tool": "web_search", "source_classes": ["official pricing and docs", "recent independent reliability evidence"], "cannot_claim": ["current price", "API reliability"], "deliverable": "concise comparison"},
            {"answer_status": "unanswerable_without_tool_check", "required_tool": "web_search_or_current_retrieval", "source_classes": ["official pricing", "independent reliability"], "cannot_claim": ["current price", "API reliability"], "deliverable": "concise comparison"},
            {"answer_status": "unsatisfied", "required_tool": "web_search", "source_classes": ["official pricing", "independent reliability"], "cannot_claim": ["current price", "API reliability"], "deliverable": "concise comparison"},
            {"answer_status": "blocked_pending_source_check", "required_tool": "web_search_and_current_retrieval", "source_classes": ["official pricing", "independent reliability"], "cannot_claim": ["current price", "API reliability"], "deliverable": "concise comparison"},
            {"answer_status": "incomplete", "required_tool": "web_search", "source_classes": ["official pricing", "independent reliability"], "cannot_claim": ["current price", "API reliability"], "deliverable": "concise comparison"},
        ],
        "D12": [
            {"first_source": "live policy page URL", "secondary_context": "old session snippet", "conclusion_status": "pending", "next_action": "inspect the live policy page", "prohibited_inference": "exports are allowed before reading the page"},
            {"first_source": "direct live policy page URL", "secondary_context": "old session snippet", "conclusion_status": None, "next_action": "open and inspect the live policy page", "prohibited_inference": "do not assume exports are allowed"},
            {"first_source": "live policy page URL", "secondary_context": "old session snippet", "conclusion_status": "pending - page not yet inspected", "next_action": "open and read the live policy page", "prohibited_inference": "do not conclude exports are allowed"},
            {"first_source": "live_policy_page", "secondary_context": "old_session_snippet", "conclusion_status": "cannot_conclude_exports_allowed_before_reading_page", "next_action": "open_and_inspect_live_policy_page", "prohibited_inference": "exports_are_allowed_based_on_old_session_snippet"},
            {"first_source": "direct_live_page", "secondary_context": "old_session_snippet", "conclusion_status": "pending_page_inspection", "next_action": "open_and_read_live_policy_page", "prohibited_inference": "exports_allowed"},
        ],
    }
    for task_id, payloads in cases.items():
        for payload in payloads:
            score, fails, _ = m.validate(by_id[task_id], json.dumps(payload, ensure_ascii=False))
            assert score == 1.0, (task_id, fails)
            assert fails == []

    health_variants = [
        """[Evidence] Sleep 5h50; resting HR +8; sore legs; no acute symptoms. [Freshness] HRV is stale since 02:00. [Recommendation] Recovery or a very light session—no hard intervals. [Human Check] Check symptoms and how you feel. [Escalation] Seek professional advice for pain, chest symptoms, fainting, or worsening symptoms.""",
        """[Evidence] Sleep 5h50; resting HR +8; sore legs; no acute symptoms. [Freshness] HRV is stale since 02:00. [Recommendation] Recovery or a light session is recommended over hard intervals. [Human Check] This is not a medical diagnosis. [Escalation] Seek professional advice for acute or severe symptoms.""",
    ]
    for health in health_variants:
        score, fails, _ = m.validate(by_id["D09"], health)
        assert score == 1.0, fails


def test_semantic_relaxation_keeps_genuine_failures():
    m = load_module()
    by_id = {task.id: task for task in m.task_list()}
    fenced = '```json\n{"answer_status":"unsupported","required_tool":"web_search","source_classes":["official","independent"],"cannot_claim":"price reliability","deliverable":"comparison"}\n```'
    _, fails, _ = m.validate(by_id["D08"], fenced)
    assert fails == ["forbidden_code_fences"]
    null_skill = json.dumps({"context_first": None, "file_change": None, "deletion": None, "outbound_message": None, "language": "English"})
    _, fails, _ = m.validate(by_id["D07"], null_skill)
    assert {"missing_backup", "missing_archive", "missing_approval"} <= set(fails)
    archiving_skill = json.dumps({
        "context_first": "Read relevant context first.",
        "file_change": "Update the significant note.",
        "deletion": "Archiving is required; exact DELETE confirmation is required for permanent deletion.",
        "outbound_message": "Draft only and require approval before sending.",
        "language": "English",
    })
    _, fails, _ = m.validate(by_id["D07"], archiving_skill)
    assert fails == ["missing_backup"]
    array_privacy = json.dumps([{"item": "raw audit interviews", "local_only": True}])
    _, fails, _ = m.validate(by_id["D10"], array_privacy)
    assert fails == ["json_not_object"]


def test_run_cell_with_token_limit_is_incomplete_not_contract_failure(monkeypatch, tmp_path):
    m = load_module()
    from benchmark_transport import parse_ollama_response

    result = parse_ollama_response(
        "glm-5.2:cloud",
        {
            "model": "glm-5.2",
            "done": True,
            "done_reason": "length",
            "eval_count": 1200,
            "message": {"content": '{"cut_off":'},
        },
        payload={
            "model": "glm-5.2:cloud",
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_predict": 1200},
        },
        registered_identity={
            "name": "glm-5.2:cloud",
            "remote_model": "glm-5.2",
            "digest": "test-digest",
        },
    )
    monkeypatch.setattr(m, "call_ollama", lambda *args, **kwargs: result)

    cell = m.run_cell("truncated", tmp_path, m.task_list()[0], "glm-5.2:cloud", trial_index=1, timeout_s=10)

    assert cell.status == "incomplete"
    assert cell.hard_fails == []
    assert cell.incomplete_reasons == ["output_truncated"]
    assert cell.checks["provider_response"]["done_reason"] == "length"
    assert cell.checks["request_controls"]["keep_alive"] == "30m"
    assert cell.checks["request_controls"]["options"]["num_predict"] == 1200


def test_run_cell_classifies_transport_failure(monkeypatch, tmp_path):
    import urllib.error

    m = load_module()
    monkeypatch.setattr(m, "call_ollama", lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")))

    cell = m.run_cell("offline", tmp_path, m.task_list()[0], "glm-5.2:cloud", trial_index=1, timeout_s=10)

    assert cell.status == "error"
    assert cell.hard_fails == ["transport_unavailable"]
    assert cell.checks["failure_class"] == "transport_unavailable"


def test_identity_mismatch_is_retained_in_cell_and_preflight(monkeypatch, tmp_path):
    from benchmark_transport import ModelIdentityMismatch

    m = load_module()
    exc = ModelIdentityMismatch(
        "alias proof unavailable",
        requested_model="glm-5.2:cloud",
        returned_model="glm-5.2",
    )

    def mismatch(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr(m, "call_ollama", mismatch)
    cell = m.run_cell(
        "mismatch", tmp_path, m.task_list()[0], "glm-5.2:cloud",
        trial_index=1, timeout_s=10,
    )
    assert cell.status == "error"
    assert cell.checks["actual_model"] == "glm-5.2"
    assert cell.checks["provider_response"] == {
        "identity_evidence": "mismatch",
        "requested_model": "glm-5.2:cloud",
        "returned_model": "glm-5.2",
        "registered_identity": None,
    }

    preflight = m.preflight_model("glm-5.2:cloud", timeout_s=10)
    assert preflight["status"] == "error"
    assert preflight["actual_model"] == "glm-5.2"
    assert preflight["provider_response"]["returned_model"] == "glm-5.2"


def test_task_filter_and_self_test():
    m = load_module()
    assert [task.id for task in m.select_tasks("D02,D06")] == ["D02", "D06"]
    assert m.self_test() == 0


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
        assert (tmp_path / "manifest-first" / "manifest.json").exists()
        events.append("provider")
        return {"model": model, "status": "pass"}

    monkeypatch.setattr(m, "write_manifest", write_manifest)
    monkeypatch.setattr(m, "preflight_model", preflight_model)

    result = m.main([
        "--models", "candidate:cloud",
        "--tasks", "D01",
        "--run-id", "manifest-first",
        "--preflight-only",
    ])

    assert result == 0
    assert events == ["manifest", "provider"]


def test_skip_preflight_makes_no_preflight_provider_call(tmp_path, monkeypatch):
    m = load_module()
    monkeypatch.setattr(m, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(m, "require_profile_coverage", lambda models: None)
    monkeypatch.setattr(m, "build_manifest", lambda **kwargs: {"run_id": kwargs["run_id"]})
    monkeypatch.setattr(m, "preflight_model", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("preflight called")))
    monkeypatch.setattr(m, "make_schedule", lambda *args, **kwargs: [])
    assert m.main(["--models", "candidate:cloud", "--tasks", "D01", "--run-id", "skip-preflight", "--skip-preflight"]) == 0
