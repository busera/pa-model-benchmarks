from __future__ import annotations

import json

import pytest


def test_t_synthetic_classification_never_invokes_real_loaders(monkeypatch):
    import run_t01_t12_full_matrix_profiled as runner

    def forbidden():
        raise AssertionError("real-source loader invoked")

    monkeypatch.setattr(runner.w2, "load_real_t1", forbidden)
    monkeypatch.setattr(runner.w2, "load_real_t4", forbidden)
    assert runner.prompt_for("t1_real") == runner.w2.FIXTURE_T1
    assert runner.prompt_for("t4_real") == runner.w2.FIXTURE_T4


def test_t_aggregate_fails_closed_when_requested_repeat_is_missing():
    from run_t01_t12_full_matrix_profiled import Cell, TASKS, aggregate, select_models

    models = select_models(["deepseek-v4-pro:cloud"])

    cell = Cell(
        run_id="test", canonical_id=TASKS[0]["id"], task=TASKS[0]["key"], part="single",
        model_tag=models[0]["tag"], model_label=models[0]["label"], status="ok",
        started_at="now", finished_at="now", elapsed_s=0.1, response_text="",
        validators={"trial_index": 1}, weighted_score=1.0, hard_fails=[], dims={},
    )
    summary = aggregate([cell], models=models, expected_repeats=2)
    row = summary["by_model"][models[0]["tag"]]
    assert row["coverage_complete"] is False
    assert row["trial_statistics"]["eligible"] is False
    assert row["lane_eligible"] is False


def test_t_selected_models_are_explicit_exact_and_model_major():
    import run_t01_t12_full_matrix_profiled as runner

    selected = runner.select_models([
        "nemotron-3-ultra:cloud",
        "deepseek-v4-pro:cloud",
    ])

    assert [row["tag"] for row in selected] == [
        "nemotron-3-ultra:cloud",
        "deepseek-v4-pro:cloud",
    ]
    schedule = runner.make_schedule(
        [row["tag"] for row in selected],
        [task["id"] for task in runner.TASKS],
        repeats=3,
        seed=0,
        order="fixed",
    )
    first_model = selected[0]["tag"]
    assert [trial.model for trial in schedule[: len(runner.TASKS)]] == [first_model] * len(runner.TASKS)


def test_t_selection_fails_closed_on_empty_duplicate_or_unknown_tags():
    import pytest
    import run_t01_t12_full_matrix_profiled as runner

    for tags in ([], ["deepseek-v4-pro:cloud", "deepseek-v4-pro:cloud"], ["legacy-unavailable:cloud"]):
        with pytest.raises(ValueError):
            runner.select_models(tags)


def test_t_provider_call_accounting_preserves_multicall_tasks():
    import run_t01_t12_full_matrix_profiled as runner

    assert runner.provider_calls_per_repeat() == 16
    assert runner.provider_calls_for_repeats(3) == 48


def test_t_expected_call_schedule_has_48_unique_host_owned_identities():
    import run_t01_t12_full_matrix_profiled as runner

    schedule = runner.expected_call_schedule(run_id="night-T", repeats=3)

    assert len(schedule) == 48
    assert len({identity.key for identity in schedule}) == 48
    assert all(identity.run_id == "night-T" and identity.lane == "T" for identity in schedule)
    t07 = [identity for identity in schedule if identity.task_id == "T07"]
    assert [(identity.trial_index, identity.call_ordinal) for identity in t07] == [
        (1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2),
    ]
    assert all(identity.call_ordinal == 1 for identity in schedule if identity.task_id != "T07")


def test_t_expected_schedule_is_frozen_before_any_provider_call(tmp_path, monkeypatch):
    import run_t01_t12_full_matrix_profiled as runner

    called = []
    monkeypatch.setattr(runner, "call_ollama", lambda *args, **kwargs: called.append((args, kwargs)))

    path = runner.write_expected_call_schedule(
        tmp_path, run_id="night-T", models=["deepseek-v4-flash:0731-cloud"], repeats=3,
    )

    assert called == []
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "provider-call-schedule-v1"
    assert len(payload["calls"]) == 48


def test_t7_host_assigns_distinct_ordinals_and_frozen_80_500_controls(tmp_path, monkeypatch):
    import run_t01_t12_full_matrix_profiled as runner
    from benchmark_transport import ProviderResult

    monkeypatch.setattr(runner, "ARTIFACT_ROOT", tmp_path / "artifacts")
    monkeypatch.setattr(runner, "RESULTS", tmp_path / "results.jsonl")
    calls = []

    def fake_call(model, messages, *, identity, num_predict, timeout_s):
        calls.append((identity, num_predict, messages))
        return ProviderResult(
            content="ACK" if identity.call_ordinal == 1 else "{}",
            requested_model=model, returned_model=model, done_reason="stop",
            prompt_tokens=10, response_tokens=2, incomplete_reason=None,
            evidence_failure=None,
            provider_metadata={"done": True, "done_reason": "stop", "prompt_tokens": 10, "response_tokens": 2},
            request_metadata={"think": True, "options": {"num_predict": num_predict}},
        )

    monkeypatch.setattr(runner, "call_ollama", fake_call)
    model = runner.select_models(["deepseek-v4-flash:0731-cloud"])[0]
    runner.run_part(model, "T07", "t7_multiturn", "t7_multiturn", trial_index=2)

    assert [(identity.call_ordinal, cap) for identity, cap, _ in calls] == [(1, 80), (2, 500)]
    assert calls[1][2][1] == {"role": "assistant", "content": "ACK"}


def test_t7_artifact_retains_both_provider_call_envelopes(tmp_path, monkeypatch):
    import run_t01_t12_full_matrix_profiled as runner
    from benchmark_transport import ProviderResult

    monkeypatch.setattr(runner, "ARTIFACT_ROOT", tmp_path / "artifacts")
    monkeypatch.setattr(runner, "RESULTS", tmp_path / "results.jsonl")
    responses = [
        ProviderResult(
            content="ACK", requested_model="deepseek-v4-flash:0731-cloud",
            returned_model="deepseek-v4-flash:0731-cloud", done_reason="stop",
            prompt_tokens=10, response_tokens=2, incomplete_reason=None,
            evidence_failure=None, provider_metadata={"done": True, "done_reason": "stop", "prompt_tokens": 10, "response_tokens": 2},
            request_metadata={"think": True},
        ),
        ProviderResult(
            content="{}", requested_model="deepseek-v4-flash:0731-cloud",
            returned_model="deepseek-v4-flash:0731-cloud", done_reason="stop",
            prompt_tokens=20, response_tokens=3, incomplete_reason=None,
            evidence_failure=None, provider_metadata={"done": True, "done_reason": "stop", "prompt_tokens": 20, "response_tokens": 3},
            request_metadata={"think": True},
        ),
    ]
    monkeypatch.setattr(runner, "call_ollama", lambda *args, **kwargs: responses.pop(0))
    model = runner.select_models(["deepseek-v4-flash:0731-cloud"])[0]
    cell, _ = runner.run_part(model, "T07", "t7_multiturn", "t7_multiturn", trial_index=1)
    evidence = cell.validators["provider_call_evidence"]
    assert len(evidence) == 2
    assert sum(row["provider_response"]["prompt_tokens"] for row in evidence) == 30


def test_t_response_artifact_persistence_failure_records_terminal_lifecycle_without_real_network(
    tmp_path, monkeypatch,
):
    import pytest
    import run_t01_t12_full_matrix_profiled as runner
    from benchmark_transport import ProviderCallIdentity, ProviderCallLifecycleError

    model = "deepseek-v4-flash:0731-cloud"
    raw_response = json.dumps({
        "model": model,
        "message": {"content": "{}"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 2,
    }).encode()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return raw_response

    fake_provider_calls = []

    def fake_urlopen(request, timeout):
        fake_provider_calls.append((request.full_url, timeout))
        return FakeResponse()

    original_write_bytes = runner.Path.write_bytes

    def fail_response_artifact(path, content):
        if path.name.endswith(".response.bin"):
            raise OSError("synthetic response artifact persistence failure")
        return original_write_bytes(path, content)

    monkeypatch.setattr(runner, "ARTIFACT_ROOT", tmp_path / "artifacts")
    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(runner.Path, "write_bytes", fail_response_artifact)
    identity = ProviderCallIdentity("night-T", "T", "T01", 1, "t1_brief", 1)

    with pytest.raises(ProviderCallLifecycleError) as caught:
        runner.call_ollama(model, [{"role": "user", "content": "synthetic"}], identity=identity)

    assert isinstance(caught.value.__cause__, OSError)
    assert [event.state for event in caught.value.events] == ["started", "failed_contract"]
    ledger = [
        json.loads(line)
        for line in (runner.ARTIFACT_ROOT / "provider-call-ledger.jsonl").read_text().splitlines()
    ]
    assert [event["state"] for event in ledger] == ["started", "failed_contract"]
    assert fake_provider_calls == [(runner.BASE, 600)]


@pytest.mark.parametrize(
    ("provider_path", "terminal_state", "original_error_type", "failure_class"),
    [
        ("transport", "failed_transport", OSError, "transport_unavailable"),
        ("response_artifact", "failed_contract", OSError, "provider_contract_error"),
        ("parse", "failed_parse", json.JSONDecodeError, "provider_contract_error"),
        ("identity", "failed_identity", RuntimeError, "provider_model_mismatch"),
        ("completed", "completed", type(None), "runtime_error"),
    ],
)
def test_t_terminal_append_failure_carries_constructed_lifecycle_for_every_terminal_path(
    tmp_path, monkeypatch, provider_path, terminal_state, original_error_type, failure_class,
):
    import run_t01_t12_full_matrix_profiled as runner
    from benchmark_transport import (
        ModelIdentityMismatch,
        ProviderCallIdentity,
        ProviderCallLifecycleError,
    )

    model = "deepseek-v4-flash:0731-cloud"
    valid_response = json.dumps({
        "model": model,
        "message": {"content": "{}"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 2,
    }).encode()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"not-json" if provider_path == "parse" else valid_response

    def fake_urlopen(request, timeout):
        if provider_path == "transport":
            raise OSError("synthetic provider transport failure")
        return FakeResponse()

    original_write_bytes = runner.Path.write_bytes

    def maybe_fail_response_artifact(path, content):
        if provider_path == "response_artifact" and path.name.endswith(".response.bin"):
            raise OSError("synthetic response artifact persistence failure")
        return original_write_bytes(path, content)

    def maybe_fail_identity(*args, **kwargs):
        if provider_path == "identity":
            raise ModelIdentityMismatch(
                "synthetic returned identity mismatch",
                requested_model=model,
                returned_model="unexpected-model",
            )
        return None

    append_attempts = []
    original_append_call_event = runner.append_call_event

    def fail_terminal_append(path, event):
        append_attempts.append(event)
        if event.state != "started":
            raise OSError("synthetic terminal ledger persistence failure")
        original_append_call_event(path, event)

    monkeypatch.setattr(runner, "ARTIFACT_ROOT", tmp_path / "artifacts")
    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(runner.Path, "write_bytes", maybe_fail_response_artifact)
    monkeypatch.setattr(runner, "resolve_ollama_registered_identity", maybe_fail_identity)
    monkeypatch.setattr(runner, "append_call_event", fail_terminal_append)
    identity = ProviderCallIdentity("night-T", "T", "T01", 1, "t1_brief", 1)

    with pytest.raises(ProviderCallLifecycleError) as caught:
        runner.call_ollama(
            model, [{"role": "user", "content": "synthetic"}], identity=identity,
        )

    error = caught.value
    assert [event.state for event in error.events] == ["started", terminal_state]
    assert [event.state for event in append_attempts] == ["started", terminal_state]
    ledger = [
        json.loads(line)
        for line in (runner.ARTIFACT_ROOT / "provider-call-ledger.jsonl").read_text().splitlines()
    ]
    assert [event["state"] for event in ledger] == ["started"]
    assert isinstance(error.terminal_persistence_error, OSError)
    assert str(error.terminal_persistence_error) == "synthetic terminal ledger persistence failure"
    assert isinstance(error.original_error, original_error_type)
    if error.original_error is None:
        assert error.__cause__ is error.terminal_persistence_error
    else:
        assert error.__cause__ is error.original_error
    assert any("terminal ledger persistence" in note for note in error.__notes__)
    checks = runner.exception_checks(error)
    assert checks["failure_class"] == failure_class
    assert checks["terminal_persistence_error"] == {
        "type": "OSError",
        "message": "synthetic terminal ledger persistence failure",
    }


def test_t_outer_runner_retains_carried_terminal_event_when_terminal_append_fails(
    tmp_path, monkeypatch,
):
    import run_t01_t12_full_matrix_profiled as runner

    class InvalidJsonResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"not-json"

    original_append_call_event = runner.append_call_event

    def fail_terminal_append(path, event):
        if event.state != "started":
            raise OSError("synthetic terminal ledger persistence failure")
        original_append_call_event(path, event)

    monkeypatch.setattr(runner, "ARTIFACT_ROOT", tmp_path / "artifacts")
    monkeypatch.setattr(runner, "RESULTS", tmp_path / "artifacts" / "results.jsonl")
    monkeypatch.setattr(
        runner.urllib.request, "urlopen", lambda request, timeout: InvalidJsonResponse(),
    )
    monkeypatch.setattr(runner, "append_call_event", fail_terminal_append)
    model = runner.select_models(["deepseek-v4-flash:0731-cloud"])[0]

    cell, _ = runner.run_part(
        model, "T01", "t1_brief", "t1_brief", trial_index=1,
    )

    assert cell.status == "error"
    assert cell.hard_fails == ["provider_contract_error"]
    assert cell.validators["failure_class"] == "provider_contract_error"
    assert [
        event["state"] for event in cell.validators["provider_call_lifecycle"]
    ] == ["started", "failed_parse"]


def test_append_call_event_truncates_on_fsync_failure(tmp_path):
    """If fsync fails after bytes reach the file, the ledger must remain
    at its pre-append state — no partial terminal event."""
    import run_t01_t12_full_matrix_profiled as runner
    from benchmark_transport import ProviderCallEvent, ProviderCallIdentity

    ledger_path = tmp_path / "provider-call-ledger.jsonl"
    identity = ProviderCallIdentity("test", "T", "T01", 1, "t1_brief", 1)
    fp = "0" * 64
    started = ProviderCallEvent(
        identity=identity, state="started", request_sha256=fp,
        requested_model="test-model", effective_controls={},
    )
    runner.append_call_event(ledger_path, started)
    assert ledger_path.read_text().count("started") == 1

    def fail_fsync(fd):
        raise OSError("synthetic fsync failure")

    terminal = ProviderCallEvent(
        identity=identity, state="failed_transport", request_sha256=fp,
        requested_model="test-model", effective_controls={},
    )

    monkeypatch_target = runner.os
    original = monkeypatch_target.fsync
    monkeypatch_target.fsync = fail_fsync
    try:
        with pytest.raises(OSError, match="synthetic fsync failure"):
            runner.append_call_event(ledger_path, terminal)
    finally:
        monkeypatch_target.fsync = original

    lines = ledger_path.read_text().splitlines()
    assert len(lines) == 1, f"ledger should contain only [started], got {lines}"
    assert json.loads(lines[0])["state"] == "started"


def test_append_call_event_truncates_on_write_failure(tmp_path):
    """If the file cannot be opened for append, ledger stays at pre-append state."""
    import run_t01_t12_full_matrix_profiled as runner
    from benchmark_transport import ProviderCallEvent, ProviderCallIdentity

    ledger_path = tmp_path / "provider-call-ledger.jsonl"
    identity = ProviderCallIdentity("test", "T", "T01", 1, "t1_brief", 1)
    fp = "0" * 64
    started = ProviderCallEvent(
        identity=identity, state="started", request_sha256=fp,
        requested_model="test-model", effective_controls={},
    )
    runner.append_call_event(ledger_path, started)

    terminal = ProviderCallEvent(
        identity=identity, state="completed", request_sha256=fp,
        raw_response_sha256=fp,
        requested_model="test-model", effective_controls={},
    )

    ledger_path.chmod(0o444)
    try:
        with pytest.raises((OSError, PermissionError)):
            runner.append_call_event(ledger_path, terminal)
    finally:
        ledger_path.chmod(0o644)

    lines = ledger_path.read_text().splitlines()
    assert len(lines) == 1, f"ledger should contain only [started], got {lines}"
    assert json.loads(lines[0])["state"] == "started"
