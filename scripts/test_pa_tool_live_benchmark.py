from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("pa_tool_live_benchmark.py")


def load_module():
    spec = importlib.util.spec_from_file_location("pa_tool_live_benchmark_tested", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fixture_contains_only_synthetic_nonces(tmp_path):
    m = load_module()
    fixture = m.create_fixture(tmp_path, "RUN-NONCE-123")
    content = "\n".join(p.read_text() for p in fixture.glob("*.md"))
    assert "RUN-NONCE-123" in content
    assert "/Users/busera" not in content
    assert "Source B" in content


def test_cloud_route_requires_explicit_approval():
    m = load_module()
    try:
        m.require_route_allowed("qwen3.5:cloud", allow_cloud=False)
    except ValueError as exc:
        assert "--allow-cloud" in str(exc)
    else:
        raise AssertionError("cloud route must fail closed")


def test_validator_requires_tool_evidence_and_exact_nonce():
    m = load_module()
    ok, failures = m.validate_response("FILE_NONCE=ABC123\nTOOL_EVIDENCE=read_file", "ABC123", "read_file")
    assert ok and not failures
    ok, failures = m.validate_response("FILE_NONCE=wrong\nTOOL_EVIDENCE=read_file", "ABC123", "read_file")
    assert not ok and "missing_exact_nonce" in failures


def test_execution_root_rejects_untrusted_existing_and_symlink_paths(tmp_path, monkeypatch):
    m = load_module()
    trusted = (tmp_path / "trusted").resolve()
    trusted.mkdir()
    monkeypatch.setattr(m, "TRUSTED_EXECUTION_PARENT", trusted)
    accepted = m.create_execution_root(trusted / "pa-tool-live-clean")
    assert accepted.parent == trusted
    try:
        m.create_execution_root(Path.home())
        assert False, "home root accepted"
    except ValueError:
        pass
    existing = trusted / "pa-tool-live-existing"
    existing.mkdir()
    try:
        m.create_execution_root(existing)
        assert False, "existing root accepted"
    except ValueError:
        pass
    escape = trusted / "pa-tool-live-escape"
    escape.symlink_to(tmp_path)
    try:
        m.create_execution_root(escape)
        assert False, "symlink escape accepted"
    except ValueError:
        pass


def test_sandbox_profile_denies_user_home_and_wraps_command(tmp_path):
    m = load_module()
    fixture = m.create_fixture(tmp_path / "fixture", "N")
    home = m.create_hermes_home(tmp_path / "home", "model")
    profile = m.create_sandbox_profile(tmp_path, fixture, home)
    text = profile.read_text()
    assert "(deny default)" in text
    assert '(allow network-outbound (remote ip "localhost:*"))' in text
    assert "(allow network-outbound)" not in text
    assert '(allow process-exec (subpath "/usr/bin"))' not in text
    assert '(allow process-exec (subpath "/bin"))' not in text
    cmd = m.build_command("model", "read", "file", fixture, profile)
    assert cmd[:3] == ["sandbox-exec", "-f", str(profile)]
    denied = subprocess.run(["sandbox-exec", "-f", str(profile), "/bin/cat", str(Path.home() / ".zshrc")], check=False, capture_output=True)
    denied_runtime_source = subprocess.run(["sandbox-exec", "-f", str(profile), "/bin/cat", str(Path.home() / ".hermes" / "hermes-agent" / "ui-tui" / "README.md")], check=False, capture_output=True)
    allowed = subprocess.run(["sandbox-exec", "-f", str(profile), "/bin/cat", str(fixture / "current.md")], check=False, capture_output=True)
    hostile = fixture / "hostile"
    hostile.write_text("#!/bin/sh\nexit 0\n")
    hostile.chmod(0o700)
    blocked_exec = subprocess.run(["sandbox-exec", "-f", str(profile), str(hostile)], check=False, capture_output=True)
    assert denied.returncode != 0
    assert denied_runtime_source.returncode != 0
    assert allowed.returncode == 0
    assert blocked_exec.returncode != 0


def test_extract_session_id_reads_stderr_metadata():
    m = load_module()
    assert m.extract_session_id("ACK", "session_id: 20260711_161742_d0ce32") == "20260711_161742_d0ce32"


def test_command_is_isolated_and_tool_bounded(tmp_path):
    m = load_module()
    cmd = m.build_command("qwen3.6:27b", "read file", "file", tmp_path)
    assert "--ignore-rules" in cmd
    assert cmd[cmd.index("-t") + 1] == "file"
    assert cmd[cmd.index("--provider") + 1] == "custom"
    assert "--source" in cmd and "tool" in cmd
    assert cmd[cmd.index("--reasoning") + 1] == "high"


def test_isolated_home_uses_recording_proxy_endpoint(tmp_path):
    m = load_module()
    home = m.create_hermes_home(tmp_path / "hermes-home", "qwen3.6:27b", base_url="http://127.0.0.1:45678/v1")
    config = (home / "config.yaml").read_text()
    assert "http://127.0.0.1:45678/v1" in config
    assert "provider: custom" in config
    assert "api_max_retries: 1" in config


def _calls(count: int, *, model: str = "model:tag"):
    return [
        {
            "request_model": model,
            "response_model": model,
            "status_code": 200,
            "prompt_tokens": 10,
            "response_tokens": 5,
            "total_tokens": 15,
            "usage_present": True,
            "elapsed_s": 0.25,
            "finish_reasons": ["tool_calls" if index == 0 and count > 1 else "stop"],
            "finish_telemetry_present": True,
            "reasoning_control": "high",
        }
        for index in range(count)
    ]


def test_three_true_repeats_plan_complete_cells_and_bounded_agent_calls():
    m = load_module()

    plan = m.plan_cases("N", repeats=3)

    assert len(plan) == 9
    assert {(row["case"].id, row["trial_index"]) for row in plan} == {
        (case_id, trial) for case_id in ("L01", "L02", "L03") for trial in range(1, 4)
    }
    assert m.maximum_provider_calls(repeats=3) == 48


def test_streaming_provider_response_telemetry_is_aggregated():
    m = load_module()
    body = (
        'data: {"model":"remote-model","choices":[{"delta":{"content":"A"},"finish_reason":null}]}\n\n'
        'data: {"model":"remote-model","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        'data: {"model":"remote-model","choices":[],"usage":{"prompt_tokens":11,"completion_tokens":7,"total_tokens":18}}\n\n'
        'data: [DONE]\n\n'
    ).encode()
    parsed = m.parse_openai_response_body(body)
    assert parsed["model"] == "remote-model"
    assert parsed["usage"] == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert parsed["finish_reasons"] == ["stop"]


def test_provider_telemetry_separates_route_setup_from_model_output():
    m = load_module()
    registered = {"name": "model:tag", "remote_model": "remote-model", "digest": "abc", "digest_verified": True}
    calls = _calls(2)
    route_ok, usage_ok, failures = m.validate_provider_calls("model:tag", registered, calls)
    assert route_ok is True
    assert usage_ok is True
    assert failures == []

    bad = _calls(2)
    bad[0]["response_model"] = "wrong-route"
    route_ok, usage_ok, failures = m.validate_provider_calls("model:tag", registered, bad)
    assert route_ok is False
    assert usage_ok is True
    assert "returned_model_mismatch" in failures


def test_provider_telemetry_rejects_missing_usage_missing_finish_and_truncation():
    m = load_module()
    registered = {"name": "model:tag", "remote_model": "remote-model", "digest": "abc", "digest_verified": True}

    missing_usage = _calls(1)
    missing_usage[0].update({"usage_present": False, "prompt_tokens": 0, "response_tokens": 0, "total_tokens": 0})
    route_ok, usage_ok, failures = m.validate_provider_calls("model:tag", registered, missing_usage)
    assert route_ok is True
    assert usage_ok is False
    assert "provider_usage_incomplete" in failures

    missing_finish = _calls(1)
    missing_finish[0].update({"finish_telemetry_present": False, "finish_reasons": []})
    _, usage_ok, failures = m.validate_provider_calls("model:tag", registered, missing_finish)
    assert usage_ok is False
    assert "provider_finish_telemetry_incomplete" in failures

    truncated = _calls(1)
    truncated[0]["finish_reasons"] = ["length"]
    _, usage_ok, failures = m.validate_provider_calls("model:tag", registered, truncated)
    assert usage_ok is False
    assert "provider_response_truncated" in failures


def test_proxy_injects_and_records_effective_thinking_control():
    m = load_module()
    forwarded, metadata = m.prepare_forward_request_body(json.dumps({
        "model": "model:tag", "stream": True, "messages": [{"role": "user", "content": "synthetic"}]
    }).encode())
    body = json.loads(forwarded)
    assert body["reasoning_effort"] == "high"
    assert body["stream_options"] == {"include_usage": True}
    assert metadata["reasoning_control"] == "high"


def test_registered_digest_must_match_approved_prefix():
    m = load_module()
    row = {"name": "model:tag", "model": "model:tag", "remote_model": "remote", "digest": "abc123ffff"}
    identity = m.validate_registered_identity("model:tag", row, expected_digest="abc123")
    assert identity["digest_verified"] is True
    try:
        m.validate_registered_identity("model:tag", row, expected_digest="deadbeef")
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("digest drift accepted")


def test_missing_l03_session_is_setup_failure_not_model_failure():
    m = load_module()
    infrastructure, critical, attribution = m.classify_failures(
        case_id="L03",
        returncode=0,
        provider_call_count=1,
        telemetry_failures=[],
        semantic_failures=["missing_exact_nonce", "missing_tool_evidence"],
        missing_session_id=True,
    )
    assert "missing_session_id" in infrastructure
    assert critical == []
    assert attribution == "setup_or_route"


def test_tool_live_eligibility_is_derived_fail_closed():
    m = load_module()
    results = []
    for row in m.plan_cases("N", repeats=3):
        case = row["case"]
        call_count = 2
        results.append({
            "case_id": case.id,
            "trial_index": row["trial_index"],
            "ok": True,
            "failures": [],
            "critical_failures": [],
            "infrastructure_failures": [],
            "provider_call_count": call_count,
            "provider_calls": _calls(call_count),
            "route_identity_verified": True,
            "usage_complete": True,
            "elapsed_s": 0.75,
        })

    summary = m.summarize_results("model:tag", results, expected_repeats=3)

    assert summary["coverage_complete"] is True
    assert summary["provider_calls"] == 18
    assert summary["maximum_provider_calls"] == 48
    assert summary["prompt_tokens"] == 180
    assert summary["response_tokens"] == 90
    assert summary["provider_elapsed_s"] == 4.5
    assert summary["wall_elapsed_s"] == 6.75
    assert summary["route_identity_verified"] is True
    assert summary["usage_complete"] is True
    assert summary["thinking_control_verified"] is True
    assert summary["critical_failures"] == 0
    assert summary["infrastructure_failures"] == 0
    assert summary["promotion_eligible"] is True

    results[0]["route_identity_verified"] = False
    assert m.summarize_results("model:tag", results, expected_repeats=3)["promotion_eligible"] is False


def test_tool_live_missing_repeat_or_l03_call_fails_eligibility():
    m = load_module()
    results = []
    for row in m.plan_cases("N", repeats=3):
        case = row["case"]
        results.append({
            "case_id": case.id,
            "trial_index": row["trial_index"],
            "ok": True,
            "failures": [],
            "critical_failures": [],
            "infrastructure_failures": [],
            "provider_call_count": 2,
            "provider_calls": _calls(2),
            "route_identity_verified": True,
            "usage_complete": True,
            "elapsed_s": 0.75,
        })
    results.pop()
    results[-1]["provider_call_count"] = 1
    results[-1]["provider_calls"] = _calls(1)

    summary = m.summarize_results("model:tag", results, expected_repeats=3)

    assert summary["coverage_complete"] is False
    assert summary["call_accounting_complete"] is False
    assert summary["promotion_eligible"] is False
