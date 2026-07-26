#!/usr/bin/env python3
"""Regression tests for the PA Real-Life Pack promotion runner."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).with_name("pa_real_life_pack_benchmark.py")


def load_module():
    spec = importlib.util.spec_from_file_location("pa_real_life_pack_benchmark_tested", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hermes_route_applies_recorded_openai_profile(monkeypatch):
    m = load_module()
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    result = m.call_hermes("gpt-5.5", "Return JSON.")
    effective_prompt = captured["cmd"][captured["cmd"].index("-q") + 1]
    assert m.profile_for_model("gpt-5.5").system_prompt() in effective_prompt
    assert m.SYSTEM in effective_prompt
    assert captured["cmd"][captured["cmd"].index("--max-turns") + 1] == "3"
    assert result.evidence_failure == "route_identity_unverified"


def test_complete_hermes_response_is_diagnostic_but_not_promotion_eligible(monkeypatch, tmp_path):
    m = load_module()
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="valid response", stderr=""))
    monkeypatch.setattr(m, "validate", lambda *a, **k: (1.0, [], {"semantic": True}))

    cell = m.run_cell("hermes-unverified", tmp_path, m.task_list()[0], "gpt-5.5")

    assert cell.status == "unverified"
    assert cell.score == 1.0
    assert cell.hard_fails == ["route_identity_unverified"]


def test_hermes_max_iterations_is_incomplete_before_semantic_validation(monkeypatch, tmp_path):
    m = load_module()

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout='{"looks": "valid"}\n⚠️ Reached maximum iterations (3)', stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    cell = m.run_cell("hermes-incomplete", tmp_path, m.task_list()[0], "gpt-5.5")

    assert cell.status == "incomplete"
    assert cell.score == 0.0
    assert cell.hard_fails == ["max_iterations_reached"]
    assert cell.checks["actual_model"] is None
    assert cell.checks["provider_response"]["identity_evidence"] == "request_only"


def test_promotion_gate_fails_on_incomplete_coverage(tmp_path):
    m = load_module()
    tasks = m.task_list()
    task = tasks[0]
    cell = m.Cell(
        run_id="partial",
        task_id=task.id,
        lane=task.lane,
        weight=task.weight,
        model_tag="gpt-5.5",
        model_label="gpt55",
        provider="hermes",
        status="ok",
        score=1.0,
    )
    data = m.summarize("partial", tmp_path, tasks, [cell], expected_repeats=2)
    row = data["ranking"][0]
    assert row["coverage"] == f"1/{len(tasks) * 2}"
    assert row["coverage_complete"] is False
    assert row["promotion_gate"] == "fail"


def test_promotion_gate_requires_at_least_three_repeats(tmp_path):
    m = load_module()
    tasks = m.task_list()
    cells = [
        m.Cell(
            run_id="single-observation",
            task_id=task.id,
            lane=task.lane,
            weight=task.weight,
            model_tag="candidate",
            model_label="candidate",
            provider="ollama",
            status="ok",
            score=1.0,
            checks={"trial_index": 1},
        )
        for task in tasks
    ]

    row = m.summarize("single-observation", tmp_path, tasks, cells, expected_repeats=1)["ranking"][0]

    assert row["coverage_complete"] is True
    assert row["repeat_evidence_sufficient"] is False
    assert row["promotion_gate"] == "fail"


def test_section_contract_rejects_wrong_order_and_duplicates():
    m = load_module()
    expected = ['[Prior Decision]', '[New Evidence]', '[Recommendation]', '[Risks]', '[Next Actions]']
    bad = '[New Evidence]\nx\n[Prior Decision]\ny\n[Recommendation]\nz\n[Risks]\nr\n[Next Actions]\nn\n[Next Actions]\nduplicate'
    ok, problems = m.has_sections(bad, expected)
    assert ok is False
    assert 'wrong_order_duplicates_or_extra_sections' in problems


def test_self_test_passes():
    m = load_module()
    assert m.self_test() == 0
