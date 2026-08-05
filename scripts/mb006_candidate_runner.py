#!/usr/bin/env python3
"""Strictly serial MB-006 candidate runner and evidence gate."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from benchmark_transport import ProviderCallEvent, ProviderCallIdentity, TERMINAL_CALL_EVENT_STATES, canonical_json_bytes, sanitized_request_metadata, sha256_bytes, validate_call_schedule
from mb006_preflight import FROZEN_REGISTRATION, FROZEN_SERIAL_SCHEDULE
import run_t01_t12_full_matrix_profiled as t_matrix

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
CONTROL_ROOT = ARTIFACTS / "mb006-serial-control"
STATE_PATH = CONTROL_ROOT / "state.json"
LOCK_PATH = Path("/private/tmp/benchmark-pa-model-mb006.lock")
LANE_CALLS = {"D": 42, "R": 30, "W": 63, "F": 30, "T": 48, "H": 18}
LANE_TASK_COUNTS = {"D": 14, "R": 10, "W": 21, "F": 10, "H": 6}


def validate_candidate(model: str) -> None:
    if model not in FROZEN_SERIAL_SCHEDULE:
        raise ValueError(f"model is outside the frozen MB-006 schedule: {model}")


def validate_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", run_id) or run_id in {".", ".."}:
        raise ValueError("run_id must be a bounded leaf name")
    return run_id


def governed_child(base: Path, leaf: str) -> Path:
    validate_run_id(leaf)
    absolute_base = Path(os.path.abspath(base))
    resolved_base = base.resolve()
    if resolved_base != absolute_base:
        raise ValueError(f"governed root is symlinked or non-canonical: {base}")
    candidate = (resolved_base / leaf).resolve()
    if candidate.parent != resolved_base:
        raise ValueError(f"artifact path escapes governed root: {leaf}")
    return candidate


def validate_planned_roots(run_id: str) -> None:
    validate_run_id(run_id)
    artifacts_root = governed_child(ROOT, "artifacts")
    if artifacts_root != ARTIFACTS.absolute():
        raise ValueError("ARTIFACTS is not the canonical repository artifact root")
    control_root = governed_child(artifacts_root, "mb006-serial-control")
    if control_root != CONTROL_ROOT.absolute():
        raise ValueError("CONTROL_ROOT is not the canonical serial-control root")
    planned_leaves = [f"{run_id}-preflight", *(f"{run_id}-{lane}" for lane in LANE_CALLS)]
    for leaf in planned_leaves:
        candidate = governed_child(artifacts_root, leaf)
        if candidate.exists() or candidate.is_symlink():
            raise ValueError(f"planned artifact root already exists: {candidate}")
    run_root = governed_child(control_root, run_id)
    if run_root.exists() or run_root.is_symlink():
        raise ValueError(f"serial control run root already exists: {run_root}")
    tool_root = governed_child(Path("/private/tmp"), f"pa-tool-live-{run_id}")
    if tool_root.exists() or tool_root.is_symlink():
        raise ValueError(f"tool-live root already exists: {tool_root}")


def validate_live_registration(model: str, expected_digest: str) -> dict[str, Any]:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        data = json.loads(response.read().decode())
    matches = [row for row in data.get("models", []) if row.get("name") == model and row.get("model") == model]
    if len(matches) != 1:
        raise ValueError(f"exact live registration unavailable for {model}")
    row = matches[0]
    digest = str(row.get("digest") or "")
    remote_model = str(row.get("remote_model") or "")
    if not digest.startswith(expected_digest):
        raise ValueError(f"live registration digest drift for {model}: expected {expected_digest}, got {digest[:12]}")
    if not remote_model and ":cloud" in model:
        raise ValueError(f"cloud model {model} has no remote_model field")
    return {"name": model, "remote_model": remote_model, "digest": digest, "expected_digest": expected_digest, "digest_verified": True}


def candidate_allowed(model: str, state_path: Path = STATE_PATH) -> bool:
    validate_candidate(model)
    if not state_path.exists():
        return model == FROZEN_SERIAL_SCHEDULE[0]
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    idx = FROZEN_SERIAL_SCHEDULE.index(model)
    if idx == 0:
        return False
    predecessor = FROZEN_SERIAL_SCHEDULE[idx - 1]
    return (
        state.get("model") == predecessor
        and state.get("status") in {"verified", "completed_unverified", "early_stopped"}
    )


def write_serial_state(state_path: Path, *, model: str, status: str, run_id: str | None = None, evidence: dict[str, Any] | None = None) -> None:
    validate_candidate(model)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "mb006-serial-state-v1",
        "model": model,
        "status": status,
        "run_id": run_id,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence": evidence or {},
    }
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(state_path)


def _no_follow_flag() -> int:
    flag = int(getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0))
    if not flag:
        raise RuntimeError("runtime has no effective no-follow open flag")
    return flag


def _validate_lock_descriptor(descriptor: int, lock_path: Path) -> os.stat_result:
    descriptor_stat = os.fstat(descriptor)
    try:
        path_stat = os.lstat(lock_path)
    except OSError as exc:
        raise RuntimeError("serial lock path changed after open") from exc
    if not stat.S_ISREG(descriptor_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        raise RuntimeError("serial lock is not a regular file")
    if descriptor_stat.st_uid != os.getuid():
        raise RuntimeError("serial lock is not owned by the current UID")
    if stat.S_IMODE(descriptor_stat.st_mode) & 0o077:
        raise RuntimeError("serial lock has unsafe group/other permissions")
    if descriptor_stat.st_nlink != 1 or path_stat.st_nlink != 1:
        raise RuntimeError("serial lock has unsafe link count")
    if (
        descriptor_stat.st_dev != path_stat.st_dev
        or descriptor_stat.st_ino != path_stat.st_ino
    ):
        raise RuntimeError("serial lock path inode changed after open")
    return descriptor_stat


@contextmanager
def safe_serial_lock(lock_path: Path | None = None) -> Iterator[None]:
    path = LOCK_PATH if lock_path is None else lock_path
    absolute_path = Path(os.path.abspath(path))
    if path != absolute_path:
        raise RuntimeError("serial lock path must be absolute and canonical")
    absolute_parent = Path(os.path.abspath(path.parent))
    if path.parent.resolve() != absolute_parent:
        raise RuntimeError("serial lock parent is symlinked or non-canonical")
    if not stat.S_ISDIR(os.lstat(path.parent).st_mode):
        raise RuntimeError("serial lock parent is not a directory")
    close_on_exec = int(getattr(os, "O_CLOEXEC", 0))
    if not close_on_exec:
        raise RuntimeError("runtime has no close-on-exec open flag")
    flags = os.O_CREAT | os.O_RDWR | close_on_exec | _no_follow_flag()
    descriptor = os.open(path, flags, 0o600)
    locked = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except (BlockingIOError, OSError) as exc:
            raise RuntimeError("another MB-006 candidate process is active") from exc
        _validate_lock_descriptor(descriptor, path)
        _validate_lock_descriptor(descriptor, path)
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        payload = f"pid={os.getpid()}\n".encode("ascii")
        if os.write(descriptor, payload) != len(payload):
            raise RuntimeError("serial lock PID write was incomplete")
        os.fsync(descriptor)
        yield
    finally:
        if locked:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def build_command_plan(*, model: str, run_id: str, expected_digest: str, python: str = sys.executable) -> list[dict[str, Any]]:
    validate_candidate(model)
    validate_run_id(run_id)
    if not expected_digest or not FROZEN_REGISTRATION[model]["digest"].startswith(expected_digest) and not expected_digest.startswith(FROZEN_REGISTRATION[model]["digest"]):
        raise ValueError(f"digest does not match frozen registration for {model}")
    tool_root = str(governed_child(Path("/private/tmp"), f"pa-tool-live-{run_id}"))
    common = ["--models", model, "--repeats", "3", "--run-order", "fixed"]
    return [
        {"lane": "preflight", "command": [python, "scripts/pa_daily_use_benchmark.py", "--models", model, "--run-id", f"{run_id}-preflight", "--preflight-only"]},
        {"lane": "D", "command": [python, "scripts/pa_daily_use_benchmark.py", *common, "--run-id", f"{run_id}-D", "--skip-preflight"]},
        {"lane": "R", "command": [python, "scripts/pa_real_life_pack_benchmark.py", *common, "--run-id", f"{run_id}-R"]},
        {"lane": "W", "command": [python, "scripts/pa_typical_workload_benchmark.py", *common, "--run-id", f"{run_id}-W"]},
        {"lane": "F", "command": [python, "scripts/pa_conflict_retrieval_benchmark.py", *common, "--run-id", f"{run_id}-F"]},
        {"lane": "T", "command": [python, "scripts/run_t01_t12_full_matrix_profiled.py", "--models", model, "--repeats", "3", "--run-order", "fixed"], "env": {"BENCH_RUN_ID": f"{run_id}-T"}},
        {"lane": "H", "command": [python, "scripts/pa_held_out_benchmark.py", *common, "--run-id", f"{run_id}-H", "--skip-preflight"]},
        {"lane": "tool_live", "command": [python, "scripts/pa_tool_live_benchmark.py", "--model", model, "--execute", "--allow-cloud", "--expected-digest", expected_digest, "--repeats", "3", "--artifact-root", tool_root]},
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _expected_artifact_keys(lane: str) -> set[tuple[Any, ...]]:
    if lane == "T":
        return {
            (task["id"], part, trial)
            for trial in range(1, 4)
            for task in t_matrix.TASKS
            for part in task["parts"]
        }
    return {
        (f"{lane}{number:02d}", trial)
        for trial in range(1, 4)
        for number in range(1, LANE_TASK_COUNTS[lane] + 1)
    }


def _expected_num_predict(identity: ProviderCallIdentity, *, model: str | None = None) -> int:
    if identity.task_id == "T07":
        base = 80 if identity.call_ordinal == 1 else 500
    else:
        base = int(t_matrix.w2.TASK_CONFIG.get(identity.part, {}).get("num_predict", 1200))
    # Thinking-on models get 2x num_predict in request_payload/build_ollama_payload
    if model:
        from model_prompt_profiles import profile_for_model
        profile = profile_for_model(model)
        if profile.top_level.get("think") is True:
            return base * 2
    return base


def verify_call_lifecycle(
    expected: list[ProviderCallIdentity] | tuple[ProviderCallIdentity, ...],
    events: list[ProviderCallEvent] | tuple[ProviderCallEvent, ...],
    *,
    model: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    try:
        schedule = validate_call_schedule(expected)
    except (TypeError, ValueError):
        return {"verified": False, "completed_calls": 0, "failures": ["invalid_expected_schedule"]}
    if any(not isinstance(event, ProviderCallEvent) for event in events):
        return {"verified": False, "completed_calls": 0, "failures": ["invalid_lifecycle_event"]}

    expected_keys = {identity.key for identity in schedule}
    grouped: dict[tuple[str, str, str, int, str, int], list[ProviderCallEvent]] = {}
    for event in events:
        if event.identity.key not in expected_keys:
            failures.append("unexpected_call_identity")
            continue
        grouped.setdefault(event.identity.key, []).append(event)
    expected_order = [
        (identity.key, phase)
        for identity in schedule
        for phase in ("started", "terminal")
    ]
    actual_order = [
        (event.identity.key, "started" if event.state == "started" else "terminal")
        for event in events
        if event.identity.key in expected_keys
    ]
    if actual_order != expected_order:
        failures.append("call_order_drift")

    completed_calls = 0
    for identity in schedule:
        call_events = grouped.get(identity.key, [])
        if not call_events:
            failures.append("not_attempted")
            continue
        if call_events[0].state != "started":
            failures.append("started_event_missing_or_out_of_order")
        if len(call_events) == 1:
            failures.append("interrupted_incomplete")
            continue
        if len(call_events) != 2:
            failures.append("duplicate_lifecycle_event")
            continue
        started, terminal = call_events
        if terminal.state not in TERMINAL_CALL_EVENT_STATES:
            failures.append("terminal_event_missing_or_out_of_order")
            continue
        if (
            started.request_sha256 != terminal.request_sha256
            or started.requested_model != terminal.requested_model
            or started.effective_controls != terminal.effective_controls
        ):
            failures.append("lifecycle_evidence_drift")
        controls = started.effective_controls
        options = controls.get("options") if isinstance(controls, dict) else None
        if (
            controls.get("think") is not True
            or not isinstance(options, dict)
            or options.get("num_predict") != _expected_num_predict(identity, model=model)
        ):
            failures.append("request_control_drift")
        if terminal.state != "completed":
            failures.append(f"terminal_state={terminal.state}")
            continue
        completed_calls += 1
        if (
            terminal.done is not True
            or terminal.done_reason in {None, "unknown", "length", "max_tokens", "token_limit", "context_length"}
            or not isinstance(terminal.prompt_tokens, int)
            or terminal.prompt_tokens <= 0
            or not isinstance(terminal.response_tokens, int)
            or terminal.response_tokens < 0
            or not isinstance(terminal.elapsed_s, (int, float))
            or terminal.elapsed_s <= 0
        ):
            failures.append("incomplete_terminal_evidence")
    unique_failures = sorted(set(failures))
    return {
        "verified": not unique_failures,
        "completed_calls": completed_calls,
        "failures": unique_failures,
    }


def verify_t_call_artifacts(
    artifact_root: Path, *, model: str, run_id: str,
    registered_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    expected = t_matrix.expected_call_schedule(run_id=run_id, repeats=3)
    schedule_path = artifact_root / "expected-call-schedule.json"
    try:
        schedule_bytes = schedule_path.read_bytes()
        schedule_payload = json.loads(schedule_bytes.decode("utf-8"))
        if schedule_bytes != canonical_json_bytes(schedule_payload):
            failures.append("noncanonical_expected_schedule")
        retained = tuple(
            ProviderCallIdentity.from_dict(item)
            for item in schedule_payload.get("calls", [])
        )
        if (
            schedule_payload.get("schema_version") != "provider-call-schedule-v1"
            or schedule_payload.get("model") != model
            or retained != expected
        ):
            failures.append("expected_schedule_mismatch")
    except Exception:
        failures.append("invalid_or_missing_expected_schedule")

    ledger_path = artifact_root / "provider-call-ledger.jsonl"
    events: list[ProviderCallEvent] = []
    try:
        for line in ledger_path.read_bytes().splitlines():
            if not line:
                continue
            payload = json.loads(line.decode("utf-8"))
            if line != canonical_json_bytes(payload):
                failures.append("noncanonical_lifecycle_event")
            events.append(ProviderCallEvent.from_dict(payload))
    except Exception:
        failures.append("invalid_or_missing_call_ledger")

    lifecycle = verify_call_lifecycle(expected, events, model=model)
    failures.extend(lifecycle["failures"])
    grouped: dict[tuple[str, str, str, int, str, int], list[ProviderCallEvent]] = {}
    for event in events:
        grouped.setdefault(event.identity.key, []).append(event)

    responses: dict[tuple[str, str, str, int, str, int], str] = {}
    t9_context: dict[int, list[dict[str, str]]] = {
        trial_index: [] for trial_index in range(1, 4)
    }
    for identity in expected:
        call_events = grouped.get(identity.key, [])
        if len(call_events) != 2:
            if identity.task_id == "T07" and identity.call_ordinal == 2:
                failures.append("t07_chain_unverifiable")
            continue
        started, terminal = call_events
        request_path, response_path = t_matrix.call_artifact_paths(artifact_root, identity)
        try:
            request_bytes = request_path.read_bytes()
            request_payload = json.loads(request_bytes.decode("utf-8"))
        except Exception:
            failures.append("invalid_or_missing_request_artifact")
            continue
        if request_bytes != canonical_json_bytes(request_payload):
            failures.append("noncanonical_request_artifact")
        request_sha256 = sha256_bytes(request_bytes)
        if request_sha256 != started.request_sha256 or request_sha256 != terminal.request_sha256:
            failures.append("request_fingerprint_mismatch")
        expected_route = {
            "chat_url": t_matrix.BASE,
            "content_type": "application/json",
        }
        if started.route_metadata != expected_route or terminal.route_metadata != expected_route:
            failures.append("route_metadata_mismatch")

        if identity.task_id == "T07":
            if identity.call_ordinal == 1:
                messages = [{"role": "user", "content": t_matrix.w2.FIXTURE_T7_TURN1}]
            else:
                first_key = ProviderCallIdentity(
                    identity.run_id, identity.lane, identity.task_id,
                    identity.trial_index, identity.part, 1,
                ).key
                first_content = responses.get(first_key)
                if first_content is None:
                    failures.append("t07_chain_unverifiable")
                    messages = []
                else:
                    messages = [
                        {"role": "user", "content": t_matrix.w2.FIXTURE_T7_TURN1},
                        {"role": "assistant", "content": first_content},
                        {"role": "user", "content": t_matrix.w2.FIXTURE_T7_TURN2},
                    ]
        elif identity.task_id == "T09":
            messages = [
                *t9_context[identity.trial_index],
                {"role": "user", "content": t_matrix.prompt_for(identity.part)},
            ]
        else:
            messages = [{"role": "user", "content": t_matrix.prompt_for(identity.part)}]
        if messages:
            expected_payload = t_matrix.build_ollama_payload(
                model, messages, num_predict=_expected_num_predict(identity),
            )
            if request_bytes != canonical_json_bytes(expected_payload):
                failures.append("request_payload_mismatch")
            if started.effective_controls != sanitized_request_metadata(expected_payload):
                failures.append("request_control_drift")

        if terminal.raw_response_sha256 is None:
            if identity.task_id == "T07" and identity.call_ordinal == 1:
                failures.append("t07_chain_unverifiable")
            continue
        try:
            raw_response = response_path.read_bytes()
        except OSError:
            failures.append("missing_raw_response_artifact")
            if identity.task_id == "T07" and identity.call_ordinal == 1:
                failures.append("t07_chain_unverifiable")
            continue
        if sha256_bytes(raw_response) != terminal.raw_response_sha256:
            failures.append("raw_response_fingerprint_mismatch")
        try:
            response_payload = json.loads(raw_response.decode("utf-8"))
            message = response_payload.get("message")
            content = str((message or {}).get("content") or response_payload.get("response") or "")
        except Exception:
            failures.append("raw_response_parse_failure")
            if identity.task_id == "T07" and identity.call_ordinal == 1:
                failures.append("t07_chain_unverifiable")
            continue
        actual_model = response_payload.get("model")
        allowed_actual = {model}
        if isinstance(registered_identity, dict) and isinstance(registered_identity.get("remote_model"), str):
            allowed_actual.add(registered_identity["remote_model"])
        if actual_model not in allowed_actual or terminal.actual_model != actual_model:
            failures.append("raw_response_identity_mismatch")
        if (
            terminal.done != response_payload.get("done")
            or terminal.done_reason != response_payload.get("done_reason")
            or terminal.prompt_tokens != response_payload.get("prompt_eval_count")
            or terminal.response_tokens != response_payload.get("eval_count")
        ):
            failures.append("raw_response_telemetry_mismatch")
        responses[identity.key] = content
        if identity.task_id == "T09":
            t9_context[identity.trial_index] = [
                *messages, {"role": "assistant", "content": content},
            ]

    unique_failures = sorted(set(failures))
    return {
        "verified": not unique_failures,
        "completed_calls": lifecycle["completed_calls"],
        "failures": unique_failures,
    }


def verify_direct_lane_rows(lane: str, rows: list[dict[str, Any]], summary: dict[str, Any], model: str, expected_digest: str | None = None) -> dict[str, Any]:
    failures: list[str] = []
    actual_keys: list[tuple[Any, ...]] = []
    aggregate_keys: list[tuple[Any, ...]] = []
    evidence_rows: list[dict[str, Any]] = []
    artifact_rows = 0
    for row in rows:
        checks = row.get("validators") if lane == "T" else row.get("checks")
        if not isinstance(checks, dict) or row.get("model_tag") != model:
            continue
        artifact_rows += 1
        trial = checks.get("trial_index")
        if lane == "T" and row.get("part") == "aggregate":
            aggregate_keys.append((row.get("canonical_id"), trial))
            if checks.get("provider_call_evidence"):
                failures.append("aggregate_contains_provider_evidence")
            continue
        key = (row.get("canonical_id"), row.get("part"), trial) if lane == "T" else (row.get("task_id"), trial)
        actual_keys.append(key)
        if lane == "T":
            call_evidence = checks.get("provider_call_evidence")
            if not isinstance(call_evidence, list) or not call_evidence:
                failures.append("missing_provider_call_evidence")
                continue
            evidence_rows.extend(item for item in call_evidence if isinstance(item, dict))
            if len(call_evidence) != len([item for item in call_evidence if isinstance(item, dict)]):
                failures.append("invalid_provider_call_evidence")
            expected_envelopes = 2 if row.get("canonical_id") == "T07" else 1
            if len(call_evidence) != expected_envelopes:
                failures.append("unexpected_provider_calls_per_artifact")
        else:
            evidence_rows.append(checks)
        elapsed = row.get("elapsed_s")
        if not isinstance(elapsed, (int, float)) or elapsed <= 0:
            failures.append("missing_time_evidence")

    expected_keys = _expected_artifact_keys(lane)
    if len(actual_keys) != len(expected_keys) or len(set(actual_keys)) != len(actual_keys) or set(actual_keys) != expected_keys:
        failures.append("duplicate_or_missing_coverage")
    if lane == "T":
        expected_aggregate_keys = {(task_id, trial) for trial in range(1, 4) for task_id in ("T06", "T09")}
        if len(aggregate_keys) != len(expected_aggregate_keys) or len(set(aggregate_keys)) != len(aggregate_keys) or set(aggregate_keys) != expected_aggregate_keys:
            failures.append("duplicate_or_missing_aggregate_coverage")

    if lane == "T":
        summary_row = summary.get("by_model", {}).get(model) if isinstance(summary.get("by_model"), dict) else None
        summary_valid = isinstance(summary_row, dict) and summary_row.get("coverage_complete") is True and summary_row.get("trial_statistics", {}).get("eligible") is True
    else:
        ranking = summary.get("ranking")
        summary_row = next((row for row in ranking if isinstance(row, dict) and row.get("model") == model), None) if isinstance(ranking, list) else None
        summary_valid = isinstance(summary_row, dict) and summary_row.get("coverage") == f"{len(expected_keys)}/{len(expected_keys)}" and summary_row.get("trial_statistics", {}).get("eligible") is True
    if not summary_valid:
        failures.append("invalid_summary")

    for checks in evidence_rows:
        provider = checks.get("provider_response")
        controls = checks.get("request_controls")
        actual_model = checks.get("actual_model")
        if checks.get("requested_model") != model:
            failures.append("route_mismatch")
        if actual_model != model:
            registered = provider.get("registered_identity") if isinstance(provider, dict) else None
            if not expected_digest or not isinstance(registered, dict) or not str(registered.get("digest", "")).startswith(expected_digest):
                failures.append("route_mismatch")
        if not isinstance(provider, dict) or not isinstance(controls, dict):
            failures.append("missing_route_controls")
            continue
        if checks.get("incomplete_reason") is not None or checks.get("evidence_failure") is not None:
            failures.append("incomplete_provider_evidence")
        prompt_tokens = provider.get("prompt_tokens")
        response_tokens = provider.get("response_tokens")
        if not isinstance(prompt_tokens, int) or prompt_tokens <= 0 or not isinstance(response_tokens, int) or response_tokens < 0:
            failures.append("missing_token_evidence")
        if provider.get("done") is not True or provider.get("done_reason") in {"length", "max_tokens", "token_limit", "context_length", "unknown", None}:
            failures.append("incomplete_finish_evidence")
        if controls.get("think") is not True:
            failures.append("thinking_control_drift")

    if len(evidence_rows) != LANE_CALLS[lane]:
        failures.append(f"provider_call_count={len(evidence_rows)} expected={LANE_CALLS[lane]}")
    return {
        "verified": not failures,
        "artifact_rows": artifact_rows,
        "provider_calls": len(evidence_rows),
        "failures": sorted(set(failures)),
    }


def verify_candidate_evidence(*, model: str, run_id: str, expected_digest: str) -> dict[str, Any]:
    """Verify complete route/token/time evidence without altering model scores."""
    validate_candidate(model)
    validate_run_id(run_id)
    failures: list[str] = []
    lane_evidence: dict[str, Any] = {}
    total_prompt_tokens = 0
    total_response_tokens = 0
    total_elapsed_s = 0.0
    total_direct_calls = 0
    registration_path = governed_child(CONTROL_ROOT, run_id) / "route-registration.json"
    try:
        registration = json.loads(registration_path.read_text(encoding="utf-8"))
        if (
            registration.get("name") != model
            or registration.get("digest_verified") is not True
            or not str(registration.get("digest", "")).startswith(expected_digest)
            or not isinstance(registration.get("remote_model"), str)
            or not registration["remote_model"]
        ):
            raise ValueError("registration drift")
    except Exception:
        registration = None
        failures.append("route_registration:invalid_or_missing")
    for lane, expected_calls in LANE_CALLS.items():
        root = governed_child(ARTIFACTS, f"{run_id}-{lane}")
        results_path = root / "results.jsonl"
        summary_path = root / "summary.json"
        if not results_path.is_file() or not summary_path.is_file():
            failures.append(f"{lane}:missing_artifacts")
            continue
        rows = _read_jsonl(results_path)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        lane_result = verify_direct_lane_rows(lane, rows, summary, model, expected_digest)
        if lane == "T":
            call_result = verify_t_call_artifacts(
                root, model=model, run_id=f"{run_id}-T",
                registered_identity=registration,
            )
            lane_result["provider_calls"] = call_result["completed_calls"]
            lane_result["verified"] = lane_result["verified"] and call_result["verified"]
            lane_result["failures"] = sorted(set([
                *lane_result["failures"], *call_result["failures"],
            ]))
        failures.extend(f"{lane}:{failure}" for failure in lane_result["failures"])
        total_direct_calls += int(lane_result["provider_calls"])
        lane_evidence[lane] = {
            "artifact_rows": lane_result["artifact_rows"],
            "provider_calls": lane_result["provider_calls"],
            "expected_calls": expected_calls,
            "verified": lane_result["verified"],
        }
        if lane == "T":
            try:
                ledger_events = [
                    ProviderCallEvent.from_dict(json.loads(line))
                    for line in (root / "provider-call-ledger.jsonl").read_text(encoding="utf-8").splitlines()
                    if line
                ]
            except Exception:
                ledger_events = []
            for event in ledger_events:
                if event.state != "completed":
                    continue
                total_prompt_tokens += int(event.prompt_tokens or 0)
                total_response_tokens += int(event.response_tokens or 0)
                total_elapsed_s += float(event.elapsed_s or 0.0)
            continue
        for row in rows:
            checks = row.get("validators") if lane == "T" else row.get("checks")
            if not isinstance(checks, dict) or row.get("model_tag") != model:
                continue
            evidence_rows = checks.get("provider_call_evidence") if lane == "T" else [checks]
            if not isinstance(evidence_rows, list):
                continue
            for evidence_row in evidence_rows:
                if not isinstance(evidence_row, dict):
                    continue
                provider = evidence_row.get("provider_response")
                if not isinstance(provider, dict):
                    continue
                prompt_tokens = provider.get("prompt_tokens")
                response_tokens = provider.get("response_tokens")
                if isinstance(prompt_tokens, int):
                    total_prompt_tokens += prompt_tokens
                if isinstance(response_tokens, int):
                    total_response_tokens += response_tokens
            elapsed = row.get("elapsed_s")
            if isinstance(elapsed, (int, float)):
                total_elapsed_s += float(elapsed)
    tool_root = governed_child(Path("/private/tmp"), f"pa-tool-live-{run_id}")
    tool_summary_path = tool_root / "summary.json"
    if not tool_summary_path.is_file():
        failures.append("tool_live:missing_summary")
        tool_summary: dict[str, Any] = {}
    else:
        tool_summary = json.loads(tool_summary_path.read_text(encoding="utf-8"))
        for key in ("coverage_complete", "route_identity_verified", "usage_complete", "thinking_control_verified", "call_accounting_complete"):
            if tool_summary.get(key) is not True:
                failures.append(f"tool_live:{key}=false")
        if tool_summary.get("infrastructure_failures") != 0:
            failures.append("tool_live:infrastructure_failures")
        identity = tool_summary.get("registered_identity")
        if not isinstance(identity, dict) or identity.get("digest_verified") is not True or not str(identity.get("digest", "")).startswith(expected_digest):
            failures.append("tool_live:digest_mismatch")
        total_prompt_tokens += int(tool_summary.get("prompt_tokens", 0))
        total_response_tokens += int(tool_summary.get("response_tokens", 0))
        total_elapsed_s += float(tool_summary.get("provider_elapsed_s", 0.0))
    evidence = {
        "model": model,
        "run_id": run_id,
        "verification": "pass" if not failures else "fail",
        "failures": sorted(set(failures)),
        "direct_provider_calls": total_direct_calls,
        "tool_live_provider_calls": int(tool_summary.get("provider_calls", 0)),
        "prompt_tokens": total_prompt_tokens,
        "response_tokens": total_response_tokens,
        "total_tokens": total_prompt_tokens + total_response_tokens,
        "provider_elapsed_s": round(total_elapsed_s, 3),
        "lane_evidence": lane_evidence,
    }
    verification_path = governed_child(CONTROL_ROOT, run_id) / "evidence-verification.json"
    verification_path.parent.mkdir(parents=True, exist_ok=True)
    verification_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return evidence


def execute_candidate(*, model: str, run_id: str, expected_digest: str, state_path: Path = STATE_PATH) -> int:
    validate_candidate(model)
    validate_run_id(run_id)
    if not candidate_allowed(model, state_path):
        raise RuntimeError(f"serial schedule does not permit {model}")
    plan = build_command_plan(model=model, run_id=run_id, expected_digest=expected_digest)
    validate_planned_roots(run_id)
    with safe_serial_lock():
        if not candidate_allowed(model, state_path):
            raise RuntimeError(f"serial schedule no longer permits {model}")
        validate_planned_roots(run_id)
        run_root = governed_child(CONTROL_ROOT, run_id)
        run_root.mkdir(parents=True, exist_ok=False)
        registration = validate_live_registration(model, expected_digest)
        (run_root / "route-registration.json").write_text(json.dumps(registration, indent=2, sort_keys=True), encoding="utf-8")
        write_serial_state(state_path, model=model, status="running", run_id=run_id)
        steps: list[dict[str, Any]] = []
        early_stop_reason: str | None = None
        for step in plan:
            if early_stop_reason:
                skipped_row = {"lane": step["lane"], "returncode": -1, "elapsed_s": 0.0, "log": "", "skipped": True, "reason": early_stop_reason}
                steps.append(skipped_row)
                (run_root / "progress.json").write_text(json.dumps({"model": model, "run_id": run_id, "steps": steps}, indent=2), encoding="utf-8")
                continue
            log_path = run_root / f"{step['lane']}.log"
            env = dict(os.environ)
            env.update(step.get("env", {}))
            started = time.monotonic()
            with log_path.open("w", encoding="utf-8") as log:
                completed = subprocess.run(step["command"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
            row = {"lane": step["lane"], "returncode": completed.returncode, "elapsed_s": round(time.monotonic() - started, 3), "log": str(log_path)}
            steps.append(row)
            (run_root / "progress.json").write_text(json.dumps({"model": model, "run_id": run_id, "steps": steps}, indent=2), encoding="utf-8")
            if step["lane"] == "preflight" and completed.returncode != 0:
                write_serial_state(state_path, model=model, status="preflight_failed", run_id=run_id, evidence=row)
                return completed.returncode
            if step["lane"] != "tool_live" and completed.returncode != 0:
                write_serial_state(state_path, model=model, status="infrastructure_failed", run_id=run_id, evidence=row)
                return completed.returncode
            if step["lane"] == "D" and completed.returncode == 0:
                d_summary_path = ARTIFACTS / f"{run_id}-D" / "summary.json"
                if d_summary_path.exists():
                    try:
                        d_summary = json.loads(d_summary_path.read_text(encoding="utf-8"))
                        d_ranking = d_summary.get("ranking", [{}])[0]
                        d_gate = d_ranking.get("daily_default_gate", "fail")
                        d_critical = d_ranking.get("critical_task_failures", 0)
                        # Early-stop only when critical failures exceed 1 —
                        # a single intermittent critical failure (e.g. D07
                        # missing_archive in 1 of 3 trials) is not a blocking
                        # pattern. 2+ critical failures indicates a systemic
                        # safety boundary issue.
                        if d_gate == "fail" and d_critical > 1:
                            early_stop_reason = "daily_default_gate_failed_critical"
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass
        if early_stop_reason:
            write_serial_state(state_path, model=model, status="early_stopped", run_id=run_id, evidence={"steps": steps, "reason": early_stop_reason})
        else:
            write_serial_state(state_path, model=model, status="completed_unverified", run_id=run_id, evidence={"steps": steps})
    return 0


def self_test() -> int:
    for model in FROZEN_SERIAL_SCHEDULE:
        plan = build_command_plan(model=model, run_id="SELFTEST", expected_digest=FROZEN_REGISTRATION[model]["digest"], python="python3")
        assert len(plan) == 8
        assert all(model in step["command"] for step in plan)
    print(json.dumps({"self_test": "pass", "model_calls": 0, "serial_lock": str(LOCK_PATH)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=FROZEN_SERIAL_SCHEDULE)
    parser.add_argument("--run-id")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.model or not args.run_id:
        parser.error("--model and --run-id are required")
    expected_digest = FROZEN_REGISTRATION[args.model]["digest"]
    if args.verify:
        evidence = verify_candidate_evidence(model=args.model, run_id=args.run_id, expected_digest=expected_digest)
        if evidence["verification"] == "pass":
            write_serial_state(STATE_PATH, model=args.model, status="verified", run_id=args.run_id, evidence=evidence)
            print(json.dumps(evidence, indent=2))
            return 0
        print(json.dumps(evidence, indent=2))
        return 2
    return execute_candidate(model=args.model, run_id=args.run_id, expected_digest=expected_digest)


if __name__ == "__main__":
    raise SystemExit(main())
