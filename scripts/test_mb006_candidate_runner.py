from __future__ import annotations

import importlib.util
from dataclasses import replace
import json
import os
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("mb006_candidate_runner.py")


def load_module():
    spec = importlib.util.spec_from_file_location("mb006_candidate_runner_tested", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_command_plan_is_one_candidate_only_and_strictly_serial(tmp_path):
    m = load_module()
    model = "deepseek-v4-flash:0731-cloud"
    plan = m.build_command_plan(model=model, run_id="night-deepseek", expected_digest="031ce2a95446", python="python3")
    assert [step["lane"] for step in plan] == ["preflight", "D", "R", "W", "F", "T", "H", "tool_live"]
    for step in plan:
        command = step["command"]
        assert model in command
        assert "nemotron-3-ultra:cloud" not in command
    assert "--preflight-only" in plan[0]["command"]
    assert "--skip-preflight" in plan[1]["command"]
    assert plan[-1]["command"][plan[-1]["command"].index("--expected-digest") + 1] == "031ce2a95446"
    assert plan[-1]["command"][plan[-1]["command"].index("--artifact-root") + 1].startswith("/private/tmp/pa-tool-live-")


def test_runner_rejects_unapproved_model():
    m = load_module()
    try:
        m.validate_candidate("other:cloud")
    except ValueError as exc:
        assert "frozen" in str(exc)
    else:
        raise AssertionError("unapproved model accepted")


@pytest.mark.parametrize("run_id", ["../../outside", "/tmp/outside", "a/b", ".", "..", " space ", "x" * 97])
def test_run_id_is_a_bounded_leaf_before_any_path_is_built(run_id):
    m = load_module()
    with pytest.raises(ValueError):
        m.build_command_plan(
            model="deepseek-v4-flash:0731-cloud",
            run_id=run_id,
            expected_digest="031ce2a95446",
        )


def test_governed_child_rejects_symlink_escape(tmp_path):
    m = load_module()
    base = tmp_path / "base"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    (base / "night-run").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        m.governed_child(base, "night-run")


def test_governed_child_rejects_symlinked_canonical_base(tmp_path):
    m = load_module()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_base = tmp_path / "control"
    linked_base.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        m.governed_child(linked_base, "night-run")


def test_execute_rejects_prepositioned_direct_lane_symlink_before_registration(tmp_path, monkeypatch):
    m = load_module()
    artifacts = tmp_path / "artifacts"
    control = artifacts / "mb006-serial-control"
    outside = tmp_path / "outside"
    artifacts.mkdir()
    control.mkdir()
    outside.mkdir()
    (artifacts / "night-D").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "ARTIFACTS", artifacts)
    monkeypatch.setattr(m, "CONTROL_ROOT", control)
    monkeypatch.setattr(m, "STATE_PATH", control / "state.json")
    monkeypatch.setattr(m, "validate_live_registration", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("registration called")))
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess called")))
    with pytest.raises(ValueError):
        m.execute_candidate(
            model="deepseek-v4-flash:0731-cloud",
            run_id="night",
            expected_digest="031ce2a95446",
            state_path=control / "state.json",
        )


def _provider_evidence(model):
    return {
        "requested_model": model,
        "actual_model": model,
        "request_controls": {"think": True},
        "incomplete_reason": None,
        "evidence_failure": None,
        "provider_response": {
            "done": True,
            "done_reason": "stop",
            "prompt_tokens": 10,
            "response_tokens": 5,
        },
    }


def _lifecycle_events(m, model="deepseek-v4-flash:0731-cloud"):
    from benchmark_transport import ProviderCallEvent

    schedule = m.t_matrix.expected_call_schedule(run_id="night-T", repeats=3)
    events = []
    for identity in schedule:
        cap = (
            80 if identity.task_id == "T07" and identity.call_ordinal == 1
            else 500 if identity.task_id == "T07"
            else m.t_matrix.w2.TASK_CONFIG.get(identity.part, {}).get("num_predict", 1200)
        )
        # Thinking-on models get 2x num_predict (matching request_payload/build_ollama_payload)
        from model_prompt_profiles import profile_for_model
        profile = profile_for_model(model)
        if profile.top_level.get("think") is True:
            cap = cap * 2
        common = {
            "identity": identity,
            "request_sha256": f"{len(events):064x}"[-64:],
            "requested_model": model,
            "effective_controls": {"think": True, "options": {"num_predict": cap}},
        }
        events.append(ProviderCallEvent(state="started", **common))
        events.append(ProviderCallEvent(
            state="completed", raw_response_sha256=f"{len(events):064x}"[-64:],
            actual_model=model, prompt_tokens=10, response_tokens=5,
            done=True, done_reason="stop", elapsed_s=0.1, **common,
        ))
    return schedule, events


def _write_authentic_t_call_artifacts(m, root, model="deepseek-v4-flash:0731-cloud"):
    from benchmark_transport import ProviderCallEvent, canonical_json_bytes, sanitized_request_metadata, sha256_bytes
    from model_prompt_profiles import profile_for_model

    run_id = "night-T"
    schedule = m.t_matrix.expected_call_schedule(run_id=run_id, repeats=3)
    m.t_matrix.write_expected_call_schedule(root, run_id=run_id, models=[model], repeats=3)
    profile = profile_for_model(model)
    responses = {}
    t9_context = {trial: [] for trial in range(1, 4)}
    events = []
    for identity in schedule:
        if identity.task_id == "T07":
            if identity.call_ordinal == 1:
                messages = [{"role": "user", "content": m.t_matrix.w2.FIXTURE_T7_TURN1}]
            else:
                first_key = replace(identity, call_ordinal=1).key
                messages = [
                    {"role": "user", "content": m.t_matrix.w2.FIXTURE_T7_TURN1},
                    {"role": "assistant", "content": responses[first_key]},
                    {"role": "user", "content": m.t_matrix.w2.FIXTURE_T7_TURN2},
                ]
        elif identity.task_id == "T09":
            messages = [*t9_context[identity.trial_index], {"role": "user", "content": m.t_matrix.prompt_for(identity.part)}]
        else:
            messages = [{"role": "user", "content": m.t_matrix.prompt_for(identity.part)}]
        cap = (
            80 if identity.task_id == "T07" and identity.call_ordinal == 1
            else 500 if identity.task_id == "T07"
            else m.t_matrix.w2.TASK_CONFIG.get(identity.part, {}).get("num_predict", 1200)
        )
        # Thinking-on models get 2x num_predict (matching request_payload/build_ollama_payload)
        if profile.top_level.get("think") is True:
            cap = cap * 2
        effective_messages = [{"role": "system", "content": profile.system_prompt()}, *messages]
        payload = {
            "model": model, "messages": effective_messages, "stream": False,
            "keep_alive": "30m", "options": {"num_predict": cap, **profile.options},
            **profile.top_level,
        }
        request_bytes = canonical_json_bytes(payload)
        content = f"assistant:{identity.trial_index}:{identity.task_id}:{identity.part}:{identity.call_ordinal}"
        raw_bytes = canonical_json_bytes({
            "model": model, "done": True, "done_reason": "stop",
            "prompt_eval_count": 10, "eval_count": 5,
            "message": {"content": content},
        })
        request_path, response_path = m.t_matrix.call_artifact_paths(root, identity)
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_bytes(request_bytes)
        response_path.write_bytes(raw_bytes)
        common = {
            "identity": identity, "request_sha256": sha256_bytes(request_bytes),
            "requested_model": model, "effective_controls": sanitized_request_metadata(payload),
            "route_metadata": {"chat_url": m.t_matrix.BASE, "content_type": "application/json"},
        }
        events.extend([
            ProviderCallEvent(state="started", **common),
            ProviderCallEvent(
                state="completed", raw_response_sha256=sha256_bytes(raw_bytes),
                actual_model=model, prompt_tokens=10, response_tokens=5,
                done=True, done_reason="stop", elapsed_s=0.1, **common,
            ),
        ])
        responses[identity.key] = content
        if identity.task_id == "T09":
            t9_context[identity.trial_index] = [
                *messages, {"role": "assistant", "content": content},
            ]
    ledger = root / "provider-call-ledger.jsonl"
    ledger.write_bytes(b"".join(canonical_json_bytes(event.as_dict()) + b"\n" for event in events))
    return schedule, events


def test_t_call_artifacts_verify_canonical_requests_raw_responses_and_t07_chain(tmp_path):
    m = load_module()
    _write_authentic_t_call_artifacts(m, tmp_path)

    result = m.verify_t_call_artifacts(
        tmp_path, model="deepseek-v4-flash:0731-cloud", run_id="night-T",
    )

    assert result == {"verified": True, "completed_calls": 48, "failures": []}


def test_t_call_artifacts_reject_prompt_substitution_even_with_rehashed_event(tmp_path):
    from benchmark_transport import canonical_json_bytes, sha256_bytes

    m = load_module()
    schedule, events = _write_authentic_t_call_artifacts(m, tmp_path)
    target = schedule[0]
    request_path, _ = m.t_matrix.call_artifact_paths(tmp_path, target)
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    payload["messages"][0]["content"] += " substituted"
    tampered = canonical_json_bytes(payload)
    request_path.write_bytes(tampered)
    events = [replace(event, request_sha256=sha256_bytes(tampered)) if event.identity == target else event for event in events]
    (tmp_path / "provider-call-ledger.jsonl").write_bytes(
        b"".join(canonical_json_bytes(event.as_dict()) + b"\n" for event in events)
    )

    result = m.verify_t_call_artifacts(tmp_path, model="deepseek-v4-flash:0731-cloud", run_id="night-T")

    assert "request_payload_mismatch" in result["failures"]


def test_t_call_artifacts_reject_raw_response_tamper_and_missing_t07_call_one(tmp_path):
    m = load_module()
    schedule, _ = _write_authentic_t_call_artifacts(m, tmp_path)
    target = schedule[0]
    _, response_path = m.t_matrix.call_artifact_paths(tmp_path, target)
    response_path.write_bytes(response_path.read_bytes() + b" ")
    assert "raw_response_fingerprint_mismatch" in m.verify_t_call_artifacts(
        tmp_path, model="deepseek-v4-flash:0731-cloud", run_id="night-T",
    )["failures"]

    _write_authentic_t_call_artifacts(m, tmp_path)
    t07_first = next(identity for identity in schedule if identity.task_id == "T07" and identity.call_ordinal == 1)
    _, t07_response = m.t_matrix.call_artifact_paths(tmp_path, t07_first)
    t07_response.unlink()
    result = m.verify_t_call_artifacts(tmp_path, model="deepseek-v4-flash:0731-cloud", run_id="night-T")
    assert "missing_raw_response_artifact" in result["failures"]
    assert "t07_chain_unverifiable" in result["failures"]


def test_t_call_lifecycle_accepts_exact_48_call_schedule():
    m = load_module()
    schedule, events = _lifecycle_events(m)

    result = m.verify_call_lifecycle(schedule, events, model="deepseek-v4-flash:0731-cloud")

    assert result == {"verified": True, "completed_calls": 48, "failures": []}


def test_t_call_lifecycle_rejects_duplicate_swapped_missing_and_shifted_identities():
    m = load_module()
    schedule, events = _lifecycle_events(m)
    t07 = [identity for identity in schedule if identity.task_id == "T07" and identity.trial_index == 1]

    duplicate = list(events)
    duplicate[duplicate.index(next(event for event in duplicate if event.identity == t07[1] and event.state == "started"))] = replace(
        next(event for event in duplicate if event.identity == t07[1] and event.state == "started"), identity=t07[0],
    )
    assert m.verify_call_lifecycle(schedule, duplicate, model="deepseek-v4-flash:0731-cloud")["verified"] is False

    swapped = [
        replace(event, identity=t07[1] if event.identity == t07[0] else t07[0] if event.identity == t07[1] else event.identity)
        for event in events
    ]
    assert "request_control_drift" in m.verify_call_lifecycle(schedule, swapped, model="deepseek-v4-flash:0731-cloud")["failures"]

    missing = [event for event in events if event.identity != t07[1]]
    assert "not_attempted" in m.verify_call_lifecycle(schedule, missing, model="deepseek-v4-flash:0731-cloud")["failures"]

    shifted_identity = replace(t07[1], task_id="T08")
    shifted = [replace(event, identity=shifted_identity) if event.identity == t07[1] else event for event in events]
    shifted_result = m.verify_call_lifecycle(schedule, shifted, model="deepseek-v4-flash:0731-cloud")
    assert "unexpected_call_identity" in shifted_result["failures"]
    assert "not_attempted" in shifted_result["failures"]


def test_t_call_lifecycle_preserves_independent_t07_80_500_oracle():
    m = load_module()
    schedule, events = _lifecycle_events(m)
    call_two = next(identity for identity in schedule if identity.task_id == "T07" and identity.trial_index == 1 and identity.call_ordinal == 2)
    duplicated_first_controls = [
        replace(event, effective_controls={"think": True, "options": {"num_predict": 80}})
        if event.identity == call_two else event
        for event in events
    ]

    result = m.verify_call_lifecycle(schedule, duplicated_first_controls, model="deepseek-v4-flash:0731-cloud")

    assert result["verified"] is False
    assert "request_control_drift" in result["failures"]


def test_t_call_lifecycle_rejects_shifted_complete_call_order():
    m = load_module()
    schedule, events = _lifecycle_events(m)
    shifted = [events[2], events[3], events[0], events[1], *events[4:]]

    result = m.verify_call_lifecycle(schedule, shifted, model="deepseek-v4-flash:0731-cloud")

    assert result["verified"] is False
    assert "call_order_drift" in result["failures"]


@pytest.mark.parametrize(
    ("terminal_state", "with_response"),
    [
        ("failed_transport", False),
        ("failed_parse", True),
        ("failed_identity", True),
        ("failed_contract", True),
    ],
)
def test_t_call_lifecycle_terminal_failures_are_attempted_but_ineligible(terminal_state, with_response):
    m = load_module()
    schedule, events = _lifecycle_events(m)
    target = schedule[0]
    terminal_index = next(index for index, event in enumerate(events) if event.identity == target and event.state == "completed")
    events[terminal_index] = replace(
        events[terminal_index], state=terminal_state,
        raw_response_sha256=events[terminal_index].raw_response_sha256 if with_response else None,
        actual_model=None, prompt_tokens=None, response_tokens=None,
        done=None, done_reason=None,
    )

    result = m.verify_call_lifecycle(schedule, events)

    assert result["verified"] is False
    assert f"terminal_state={terminal_state}" in result["failures"]
    assert "not_attempted" not in result["failures"]


def test_t_call_lifecycle_unmatched_started_is_interrupted_not_unattempted():
    m = load_module()
    schedule, events = _lifecycle_events(m)
    target = schedule[0]
    events = [event for event in events if not (event.identity == target and event.state != "started")]

    result = m.verify_call_lifecycle(schedule, events)

    assert "interrupted_incomplete" in result["failures"]
    assert "not_attempted" not in result["failures"]


def test_direct_lane_verifier_rejects_duplicate_coverage_and_empty_summary():
    m = load_module()
    model = "deepseek-v4-flash:0731-cloud"
    rows = []
    for trial in range(1, 4):
        for number in range(1, 15):
            evidence = _provider_evidence(model)
            rows.append({"task_id": f"D{number:02d}", "model_tag": model, "status": "ok", "elapsed_s": 0.1, "checks": {**evidence, "trial_index": trial}})
    rows[-1] = dict(rows[0])
    result = m.verify_direct_lane_rows("D", rows, {}, model)
    assert result["verified"] is False
    assert "duplicate_or_missing_coverage" in result["failures"]
    assert "invalid_summary" in result["failures"]


def test_t_lane_verifier_counts_45_unique_artifacts_and_48_provider_calls():
    m = load_module()
    model = "deepseek-v4-flash:0731-cloud"
    rows = []
    for trial in range(1, 4):
        for task in m.t_matrix.TASKS:
            for part in task["parts"]:
                evidence = [_provider_evidence(model)]
                if task["id"] == "T07":
                    evidence.append(_provider_evidence(model))
                rows.append({
                    "canonical_id": task["id"], "part": part, "model_tag": model,
                    "status": "ok", "elapsed_s": 0.1,
                    "validators": {"trial_index": trial, "provider_call_evidence": evidence},
                })
        for task_id in ("T06", "T09"):
            rows.append({
                "canonical_id": task_id, "part": "aggregate", "model_tag": model,
                "status": "ok", "elapsed_s": 0.1,
                "validators": {"trial_index": trial, "aggregate": True},
            })
    summary = {"by_model": {model: {"coverage_complete": True, "trial_statistics": {"eligible": True}}}}
    result = m.verify_direct_lane_rows("T", rows, summary, model)
    assert result == {"verified": True, "artifact_rows": 51, "provider_calls": 48, "failures": []}


def test_t_lane_verifier_rejects_misdistributed_multiturn_envelopes():
    m = load_module()
    model = "deepseek-v4-flash:0731-cloud"
    rows = []
    for trial in range(1, 4):
        for task in m.t_matrix.TASKS:
            for part in task["parts"]:
                evidence = [_provider_evidence(model)]
                if task["id"] == "T01":
                    evidence.append(_provider_evidence(model))
                rows.append({
                    "canonical_id": task["id"], "part": part, "model_tag": model,
                    "status": "ok", "elapsed_s": 0.1,
                    "validators": {"trial_index": trial, "provider_call_evidence": evidence},
                })
        for task_id in ("T06", "T09"):
            rows.append({
                "canonical_id": task_id, "part": "aggregate", "model_tag": model,
                "status": "ok", "elapsed_s": 0.1,
                "validators": {"trial_index": trial, "aggregate": True},
            })
    summary = {"by_model": {model: {"coverage_complete": True, "trial_statistics": {"eligible": True}}}}
    result = m.verify_direct_lane_rows("T", rows, summary, model)
    assert result["provider_calls"] == 48
    assert result["verified"] is False
    assert "unexpected_provider_calls_per_artifact" in result["failures"]


def test_serial_state_requires_deepseek_verification_before_nemotron(tmp_path):
    m = load_module()
    state_path = tmp_path / "state.json"
    assert m.candidate_allowed("deepseek-v4-flash:0731-cloud", state_path) is True
    assert m.candidate_allowed("nemotron-3-ultra:cloud", state_path) is False
    m.write_serial_state(state_path, model="deepseek-v4-flash:0731-cloud", status="verified")
    assert m.candidate_allowed("nemotron-3-ultra:cloud", state_path) is True


def test_safe_serial_lock_rejects_symlink_without_changing_target(tmp_path):
    m = load_module()
    target = tmp_path / "target"
    target.write_bytes(b"do-not-change")
    target.chmod(0o600)
    lock = tmp_path / "serial.lock"
    lock.symlink_to(target)

    with pytest.raises(OSError):
        with m.safe_serial_lock(lock):
            pytest.fail("symlink lock acquired")

    assert target.read_bytes() == b"do-not-change"


def test_safe_serial_lock_rejects_directory_hardlink_and_wrong_permissions(tmp_path):
    m = load_module()
    directory = tmp_path / "directory.lock"
    directory.mkdir()
    with pytest.raises((OSError, RuntimeError)):
        with m.safe_serial_lock(directory):
            pytest.fail("directory lock acquired")

    source = tmp_path / "source.lock"
    source.write_bytes(b"stale")
    source.chmod(0o600)
    hardlink = tmp_path / "hardlink.lock"
    os.link(source, hardlink)
    with pytest.raises(RuntimeError, match="link count"):
        with m.safe_serial_lock(hardlink):
            pytest.fail("hard-linked lock acquired")
    assert source.read_bytes() == b"stale"

    permissive = tmp_path / "permissive.lock"
    permissive.write_bytes(b"stale")
    permissive.chmod(0o644)
    with pytest.raises(RuntimeError, match="permissions"):
        with m.safe_serial_lock(permissive):
            pytest.fail("permissive lock acquired")
    assert permissive.read_bytes() == b"stale"


def test_safe_serial_lock_rejects_path_swap_before_first_write(tmp_path, monkeypatch):
    m = load_module()
    lock = tmp_path / "serial.lock"
    lock.write_bytes(b"original-stale")
    lock.chmod(0o600)
    displaced = tmp_path / "displaced.lock"
    original_validate = m._validate_lock_descriptor
    calls = 0

    def swap_after_first_validation(descriptor, path):
        nonlocal calls
        result = original_validate(descriptor, path)
        calls += 1
        if calls == 1:
            path.rename(displaced)
            path.write_bytes(b"replacement")
            path.chmod(0o600)
        return result

    monkeypatch.setattr(m, "_validate_lock_descriptor", swap_after_first_validation)
    with pytest.raises(RuntimeError, match="inode"):
        with m.safe_serial_lock(lock):
            pytest.fail("swapped lock acquired")

    assert displaced.read_bytes() == b"original-stale"
    assert lock.read_bytes() == b"replacement"


def test_safe_serial_lock_reuses_valid_stale_regular_file(tmp_path):
    m = load_module()
    lock = tmp_path / "serial.lock"
    lock.write_bytes(b"stale-pid")
    lock.chmod(0o600)

    with m.safe_serial_lock(lock):
        assert lock.read_text(encoding="ascii") == f"pid={os.getpid()}\n"

    assert lock.stat().st_mode & 0o777 == 0o600
    assert lock.stat().st_nlink == 1


def test_execute_lock_contention_has_zero_run_state_registration_or_subprocess_side_effects(tmp_path, monkeypatch):
    m = load_module()
    artifacts = tmp_path / "artifacts"
    control = artifacts / "mb006-serial-control"
    artifacts.mkdir()
    control.mkdir()
    lock = tmp_path / "serial.lock"
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "ARTIFACTS", artifacts)
    monkeypatch.setattr(m, "CONTROL_ROOT", control)
    monkeypatch.setattr(m, "STATE_PATH", control / "state.json")
    monkeypatch.setattr(m, "LOCK_PATH", lock)
    monkeypatch.setattr(m, "validate_live_registration", lambda *args, **kwargs: pytest.fail("registration called"))
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: pytest.fail("subprocess called"))

    with m.safe_serial_lock(lock):
        with pytest.raises(RuntimeError, match="active"):
            m.execute_candidate(
                model="deepseek-v4-flash:0731-cloud", run_id="night",
                expected_digest="031ce2a95446", state_path=control / "state.json",
            )

    assert not (control / "night").exists()
    assert not (control / "state.json").exists()


def test_self_test_makes_zero_model_calls(monkeypatch):
    m = load_module()
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess invoked")))
    assert m.self_test() == 0
