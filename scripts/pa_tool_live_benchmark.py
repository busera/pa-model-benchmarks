#!/usr/bin/env python3
"""Synthetic, local-first Hermes tool-live benchmark.

Self-test and fixture-only modes never call a model. ``--execute`` invokes an
isolated Hermes home and bounded tools against synthetic fixtures only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class Case:
    id: str
    toolset: str
    expected_tool: str
    prompt: str


TRUSTED_EXECUTION_PARENT = Path("/private/tmp")
OLLAMA_OPENAI_BASE = "http://127.0.0.1:11434"
MAX_AGENT_TURNS = 4


def parse_openai_response_body(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body.decode())
        if isinstance(parsed, dict):
            raw_choices = parsed.get("choices")
            choices: list[Any] = raw_choices if isinstance(raw_choices, list) else []
            raw_usage = parsed.get("usage")
            usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
            return {
                "model": parsed.get("model"),
                "usage": usage,
                "usage_present": bool(usage),
                "finish_reasons": [choice.get("finish_reason") for choice in choices if isinstance(choice, dict) and choice.get("finish_reason")],
                "finish_telemetry_present": any(isinstance(choice, dict) and choice.get("finish_reason") is not None for choice in choices),
            }
    except Exception:
        pass
    model: str | None = None
    usage: dict[str, Any] = {}
    finish_reasons: list[str] = []
    finish_telemetry_present = False
    for raw_line in body.decode(errors="replace").splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("model"), str) and event["model"]:
            model = event["model"]
        if isinstance(event.get("usage"), dict):
            usage = dict(event["usage"])
        raw_event_choices = event.get("choices")
        event_choices: list[Any] = raw_event_choices if isinstance(raw_event_choices, list) else []
        finish_reasons.extend(
            str(choice["finish_reason"])
            for choice in event_choices
            if isinstance(choice, dict) and choice.get("finish_reason")
        )
        if any(isinstance(choice, dict) and choice.get("finish_reason") is not None for choice in event_choices):
            finish_telemetry_present = True
    return {
        "model": model,
        "usage": usage,
        "usage_present": bool(usage),
        "finish_reasons": finish_reasons,
        "finish_telemetry_present": finish_telemetry_present,
    }


def prepare_forward_request_body(body: bytes) -> tuple[bytes, dict[str, Any]]:
    """Inject the approved Ollama OpenAI thinking control without retaining prompts."""
    request_data = json.loads(body.decode())
    if not isinstance(request_data, dict) or not isinstance(request_data.get("model"), str):
        raise ValueError("invalid OpenAI-compatible request body")
    request_data["reasoning_effort"] = "high"
    if request_data.get("stream") is True:
        stream_options = request_data.get("stream_options")
        if not isinstance(stream_options, dict):
            stream_options = {}
        stream_options["include_usage"] = True
        request_data["stream_options"] = stream_options
    metadata = {
        "request_model": request_data["model"],
        "reasoning_control": request_data["reasoning_effort"],
        "stream": request_data.get("stream") is True,
    }
    return json.dumps(request_data, separators=(",", ":")).encode(), metadata


class RecordingProxyServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), RecordingProxyHandler)
        self.calls: list[dict[str, Any]] = []
        self.calls_lock = threading.Lock()


class RecordingProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            forwarded_body, request_metadata = prepare_forward_request_body(body)
        except Exception as exc:
            self.send_error(400, f"invalid benchmark proxy request: {exc}")
            return
        started = time.monotonic()
        status = 502
        response_body = b""
        response_content_type = "application/json"
        transport_error: str | None = None
        try:
            request = urllib.request.Request(
                OLLAMA_OPENAI_BASE + self.path,
                data=forwarded_body,
                headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=330) as response:
                status = response.status
                response_content_type = response.headers.get("Content-Type", "application/json")
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            response_content_type = exc.headers.get("Content-Type", "application/json")
            response_body = exc.read()
        except Exception as exc:  # pragma: no cover - live transport path
            transport_error = f"{type(exc).__name__}: {exc}"
            response_body = json.dumps({"error": transport_error}).encode()
        elapsed = round(time.monotonic() - started, 3)
        parsed_response = parse_openai_response_body(response_body)
        raw_usage = parsed_response.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        raw_finish_reasons = parsed_response.get("finish_reasons")
        finish_reasons: list[Any] = raw_finish_reasons if isinstance(raw_finish_reasons, list) else []
        record = {
            "request_model": request_metadata["request_model"],
            "response_model": parsed_response.get("model"),
            "status_code": status,
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "response_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "usage_present": parsed_response.get("usage_present") is True,
            "elapsed_s": elapsed,
            "finish_reasons": [str(reason) for reason in finish_reasons if reason],
            "finish_telemetry_present": parsed_response.get("finish_telemetry_present") is True,
            "reasoning_control": request_metadata["reasoning_control"],
            "transport_error": transport_error,
        }
        recording_server = self.server
        if not isinstance(recording_server, RecordingProxyServer):  # pragma: no cover
            raise RuntimeError("recording proxy server type mismatch")
        with recording_server.calls_lock:
            recording_server.calls.append(record)
        self.send_response(status)
        self.send_header("Content-Type", response_content_type)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)


@contextmanager
def recording_proxy() -> Iterator[RecordingProxyServer]:
    server = RecordingProxyServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def proxy_calls_since(server: RecordingProxyServer, offset: int) -> list[dict[str, Any]]:
    with server.calls_lock:
        return [dict(row) for row in server.calls[offset:]]


def validate_registered_identity(model: str, row: dict[str, Any], *, expected_digest: str) -> dict[str, Any]:
    if row.get("name") != model or row.get("model") != model:
        raise ValueError(f"exact Ollama registration unavailable for {model}")
    remote_model = row.get("remote_model")
    digest = row.get("digest")
    if not remote_model or not digest:
        raise ValueError(f"registered route lacks remote identity evidence for {model}")
    if not expected_digest or not str(digest).startswith(expected_digest):
        raise ValueError(f"approved registration digest drift for {model}")
    return {
        "name": model,
        "remote_model": str(remote_model),
        "digest": str(digest),
        "expected_digest": expected_digest,
        "digest_verified": True,
    }


def fetch_registered_identity(model: str, *, expected_digest: str) -> dict[str, Any]:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        data = json.loads(response.read().decode())
    matches = [row for row in data.get("models", []) if row.get("name") == model and row.get("model") == model]
    if len(matches) != 1:
        raise ValueError(f"exact Ollama registration unavailable for {model}")
    return validate_registered_identity(model, matches[0], expected_digest=expected_digest)


def validate_provider_calls(model: str, registered: dict[str, Any], calls: list[dict[str, Any]]) -> tuple[bool, bool, list[str]]:
    failures: list[str] = []
    if not calls:
        return False, False, ["no_provider_telemetry"]
    allowed_response_models = {model, registered["remote_model"]}
    if any(call.get("request_model") != model for call in calls):
        failures.append("requested_model_mismatch")
    if any(call.get("response_model") not in allowed_response_models for call in calls):
        failures.append("returned_model_mismatch")
    if any(call.get("status_code") != 200 or call.get("transport_error") for call in calls):
        failures.append("provider_transport_failure")
    if registered.get("digest_verified") is not True:
        failures.append("registration_digest_unverified")
    usage_complete = all(
        call.get("usage_present") is True
        and isinstance(call.get("prompt_tokens"), int)
        and isinstance(call.get("response_tokens"), int)
        and int(call.get("prompt_tokens", 0)) > 0
        and int(call.get("total_tokens", 0)) > 0
        and int(call.get("total_tokens", 0)) == int(call.get("prompt_tokens", 0)) + int(call.get("response_tokens", 0))
        for call in calls
    )
    if not usage_complete:
        failures.append("provider_usage_incomplete")
    finish_complete = all(
        call.get("finish_telemetry_present") is True and bool(call.get("finish_reasons"))
        for call in calls
    )
    if not finish_complete:
        failures.append("provider_finish_telemetry_incomplete")
    if any("length" in list(call.get("finish_reasons", [])) for call in calls):
        failures.append("provider_response_truncated")
    thinking_control_complete = all(call.get("reasoning_control") == "high" for call in calls)
    if not thinking_control_complete:
        failures.append("thinking_control_unverified")
    evidence_complete = usage_complete and finish_complete and "provider_response_truncated" not in failures and thinking_control_complete
    route_verified = not {"requested_model_mismatch", "returned_model_mismatch", "provider_transport_failure", "registration_digest_unverified"}.intersection(failures)
    return route_verified, evidence_complete, failures


def create_execution_root(requested: Path | None) -> Path:
    """Create a fresh non-symlink execution root under canonical /private/tmp."""
    if requested is None:
        return Path(tempfile.mkdtemp(prefix="pa-tool-live-", dir=str(TRUSTED_EXECUTION_PARENT))).resolve()
    candidate = requested.resolve(strict=False)
    if candidate.parent != TRUSTED_EXECUTION_PARENT or not candidate.name.startswith("pa-tool-live-"):
        raise ValueError("artifact root must be a fresh /private/tmp/pa-tool-live-* directory")
    if candidate.exists() or candidate.is_symlink():
        raise ValueError("artifact root must not already exist")
    candidate.mkdir(mode=0o700)
    return candidate


def create_fixture(root: Path, nonce: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "current.md").write_text(f"# Synthetic current source\nSource B\nFILE_NONCE={nonce}\nStatus: approved current.\n", encoding="utf-8")
    (root / "stale.md").write_text("# Synthetic stale source\nSource A\nStatus: superseded.\n", encoding="utf-8")
    return root


def create_hermes_home(root: Path, model: str, *, base_url: str = "http://127.0.0.1:11434/v1") -> Path:
    """Create an isolated Hermes home routed through a governed local endpoint."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(
        "model:\n"
        f"  default: {model}\n"
        "  provider: custom\n"
        f"  base_url: {base_url}\n"
        "  api_key: ollama-local-only\n"
        "  api_mode: chat_completions\n"
        "agent:\n  api_max_retries: 1\n"
        "memory:\n  memory_enabled: false\n  user_profile_enabled: false\n",
        encoding="utf-8",
    )
    return root


def prepare_sandbox_runtime(root: Path) -> tuple[str, str]:
    """Copy the Python executable distribution outside the protected user home."""
    source_python = (Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3").resolve()
    source_distribution = source_python.parent.parent
    destination = root / "python-runtime"
    if not destination.exists():
        shutil.copytree(source_distribution, destination, symlinks=True, copy_function=os.link)
    copied_python = destination / "bin" / source_python.name
    source_agent = Path.home() / ".hermes" / "hermes-agent"
    copied_agent = root / "hermes-agent"
    if not copied_agent.exists():
        shutil.copytree(
            source_agent, copied_agent, symlinks=True, copy_function=os.link,
            ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "apps", "tests", "website", "scripts", "docs", "optional-skills", "__pycache__"),
        )
    hermes_script = copied_agent / "venv" / "bin" / "hermes"
    return str(copied_python), str(hermes_script)


def create_sandbox_profile(root: Path, fixture: Path, hermes_home: Path) -> Path:
    """Deny user-home access; expose only copied runtime and isolated roots."""
    profile = root / "tool-live.sb"
    allowed_read_roots = [
        Path("/private/var/select"), Path("/usr/bin"), Path("/bin"),
        fixture.resolve(), hermes_home.resolve(), root.resolve(),
    ]
    allowed_write_roots = [Path("/dev"), fixture.resolve(), hermes_home.resolve(), root.resolve()]
    executable_paths = [
        Path("/private/var/select/sh"), Path("/bin/sh"), Path("/bin/bash"), Path("/bin/cat"),
        Path("/usr/bin/wc"), Path("/usr/bin/head"), Path("/usr/bin/sed"),
    ]
    quote = json.dumps
    read_rules = "".join(f"(allow file-read* (subpath {quote(str(path))}))\n" for path in allowed_read_roots)
    write_rules = "".join(f"(allow file-write* (subpath {quote(str(path))}))\n" for path in allowed_write_roots)
    exec_rules = "".join(f"(allow process-exec (literal {quote(str(path))}))\n" for path in executable_paths)
    exec_rules += f"(allow process-exec (subpath {quote(str((root / 'python-runtime' / 'bin').resolve()))}))\n"
    profile.write_text(
        "(version 1)\n(deny default)\n(import \"system.sb\")\n"
        "(allow process-fork)\n"
        "(allow network-outbound (remote ip \"localhost:*\"))\n"
        "(allow file-read-metadata)\n"
        + read_rules + write_rules + exec_rules,
        encoding="utf-8",
    )
    return profile


def require_route_allowed(model: str, *, allow_cloud: bool) -> None:
    if (model.endswith(":cloud") or "cloud" in model.lower()) and not allow_cloud:
        raise ValueError("Cloud tool-live execution requires explicit --allow-cloud approval")


def build_command(model: str, prompt: str, toolset: str, workdir: Path, sandbox_profile: Path | None = None, hermes_launcher: list[str] | None = None) -> list[str]:
    bounded_prompt = (
        "Work only inside this synthetic fixture directory: " + str(workdir) + "\n"
        "Do not send messages, use network tools, or read outside this directory. "
        "Use the enabled tool and return only requested evidence.\n\n" + prompt
    )
    command = [*(hermes_launcher or ["hermes"]), "chat", "-Q", "--ignore-rules", "--source", "tool", "--max-turns", str(MAX_AGENT_TURNS), "--reasoning", "high", "--provider", "custom"]
    if toolset:
        command.extend(["-t", toolset])
    command.extend(["-m", model, "-q", bounded_prompt])
    return (["sandbox-exec", "-f", str(sandbox_profile)] + command) if sandbox_profile else command


def extract_session_id(stdout: str, stderr: str) -> str | None:
    match = re.search(r"session_id:\s*([\w-]+)", stdout + "\n" + stderr)
    return match.group(1) if match else None


def validate_response(text: str, nonce: str, expected_tool: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if f"FILE_NONCE={nonce}" not in text:
        failures.append("missing_exact_nonce")
    if f"TOOL_EVIDENCE={expected_tool}" not in text:
        failures.append("missing_tool_evidence")
    return not failures, failures


def cases(nonce: str) -> list[Case]:
    return [
        Case("L01", "file", "read_file", "Read current.md with the file tool. Return exactly two lines: FILE_NONCE=<value> and TOOL_EVIDENCE=read_file."),
        Case("L02", "file", "read_file", "Read stale.md and current.md. Select the current source. Return FILE_NONCE=<value from current.md> and TOOL_EVIDENCE=read_file."),
        Case("L03", "file", "session_resume", f"Remember this synthetic value exactly: FILE_NONCE={nonce}. Reply ACK only."),
    ]


def plan_cases(nonce: str, *, repeats: int) -> list[dict[str, Any]]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    return [
        {"case": case, "trial_index": trial_index}
        for trial_index in range(1, repeats + 1)
        for case in cases(nonce)
    ]


def maximum_provider_calls(*, repeats: int) -> int:
    """Bound actual agent-loop calls: four Hermes invocations, each capped at four turns."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    return repeats * 4 * MAX_AGENT_TURNS


def classify_failures(
    *,
    case_id: str,
    returncode: int,
    provider_call_count: int,
    telemetry_failures: list[str],
    semantic_failures: list[str],
    missing_session_id: bool = False,
) -> tuple[list[str], list[str], str]:
    infrastructure = list(telemetry_failures)
    if returncode != 0:
        infrastructure.append("hermes_process_failure")
    if missing_session_id:
        infrastructure.append("missing_session_id")
    cap = MAX_AGENT_TURNS * 2 if case_id == "L03" else MAX_AGENT_TURNS
    if provider_call_count > cap:
        infrastructure.append("agent_call_cap_exceeded")
    infrastructure = sorted(set(infrastructure))
    critical = [] if infrastructure else sorted(set(semantic_failures))
    attribution = "setup_or_route" if infrastructure else ("model_output" if semantic_failures else "pass")
    return infrastructure, critical, attribution


def summarize_results(model: str, results: list[dict[str, Any]], *, expected_repeats: int) -> dict[str, Any]:
    expected_cells = {
        (case_id, trial_index)
        for trial_index in range(1, expected_repeats + 1)
        for case_id in ("L01", "L02", "L03")
    }
    actual_cells = [
        (str(row.get("case_id")), int(row.get("trial_index", 0)))
        for row in results
    ]
    coverage_complete = len(actual_cells) == len(set(actual_cells)) and set(actual_cells) == expected_cells
    call_bounds = {"L01": (2, MAX_AGENT_TURNS), "L02": (2, MAX_AGENT_TURNS), "L03": (2, MAX_AGENT_TURNS * 2)}
    call_accounting_complete = coverage_complete and all(
        int(row.get("provider_call_count", 0)) == len(list(row.get("provider_calls", [])))
        and call_bounds.get(str(row.get("case_id")), (1, 0))[0]
        <= int(row.get("provider_call_count", 0))
        <= call_bounds.get(str(row.get("case_id")), (1, 0))[1]
        for row in results
    )
    provider_calls = sum(int(row.get("provider_call_count", 0)) for row in results)
    call_rows = [call for row in results for call in list(row.get("provider_calls", []))]
    prompt_tokens = sum(int(call.get("prompt_tokens", 0)) for call in call_rows)
    response_tokens = sum(int(call.get("response_tokens", 0)) for call in call_rows)
    provider_elapsed_s = round(sum(float(call.get("elapsed_s", 0.0)) for call in call_rows), 3)
    wall_elapsed_s = round(sum(float(row.get("elapsed_s", 0.0)) for row in results), 3)
    route_identity_verified = bool(results) and all(row.get("route_identity_verified") is True for row in results)
    usage_complete = bool(results) and all(row.get("usage_complete") is True for row in results)
    thinking_control_verified = bool(call_rows) and all(call.get("reasoning_control") == "high" for call in call_rows)
    critical_failures = sum(len(list(row.get("critical_failures", []))) for row in results)
    infrastructure_failures = sum(len(list(row.get("infrastructure_failures", []))) for row in results)
    completion_complete = coverage_complete and all(row.get("ok") is True for row in results)
    call_cap = maximum_provider_calls(repeats=expected_repeats)
    promotion_eligible = (
        expected_repeats >= 3
        and completion_complete
        and route_identity_verified
        and usage_complete
        and thinking_control_verified
        and call_accounting_complete
        and provider_calls <= call_cap
        and critical_failures == 0
        and infrastructure_failures == 0
    )
    return {
        "privacy_class": "synthetic",
        "model": model,
        "expected_repeats": expected_repeats,
        "required_cases": ["L01", "L02", "L03"],
        "cells_complete": len(actual_cells),
        "cells_planned": len(expected_cells),
        "coverage_complete": coverage_complete,
        "completion_complete": completion_complete,
        "route_identity_verified": route_identity_verified,
        "usage_complete": usage_complete,
        "thinking_control_verified": thinking_control_verified,
        "call_accounting_complete": call_accounting_complete,
        "provider_calls": provider_calls,
        "maximum_provider_calls": call_cap,
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "total_tokens": prompt_tokens + response_tokens,
        "provider_elapsed_s": provider_elapsed_s,
        "wall_elapsed_s": wall_elapsed_s,
        "critical_failures": critical_failures,
        "infrastructure_failures": infrastructure_failures,
        "promotion_eligible": promotion_eligible,
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="pa-tool-live-") as tmp:
        nonce = "SELFTEST-NONCE"
        root = create_fixture(Path(tmp), nonce)
        assert len(cases(nonce)) == 3
        assert len(plan_cases(nonce, repeats=3)) == 9
        assert maximum_provider_calls(repeats=3) == 48
        assert "SELFTEST-NONCE" in (root / "current.md").read_text()
        assert validate_response("FILE_NONCE=SELFTEST-NONCE\nTOOL_EVIDENCE=read_file", nonce, "read_file")[0]
    print(json.dumps({"self_test": "pass", "provider_call_cap_per_candidate": 48, "model_calls": 0}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.6:27b")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--allow-cloud", action="store_true")
    ap.add_argument("--expected-digest", help="Approved exact registration digest or unique prefix")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--artifact-root", type=Path)
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    require_route_allowed(args.model, allow_cloud=args.allow_cloud)
    if args.execute and not args.expected_digest:
        raise ValueError("Tool-live execution requires --expected-digest")
    root = create_execution_root(args.artifact_root)
    nonce = f"SYNTH-{uuid.uuid4().hex[:12]}"
    fixture = create_fixture(root / "fixture", nonce)
    if not args.execute:
        hermes_home = create_hermes_home(root / "hermes-home", args.model)
        print(json.dumps({"mode": "fixture-only", "fixture": str(fixture), "hermes_home": str(hermes_home), "nonce": nonce, "model_calls": 0}, indent=2))
        return 0
    registered_identity = fetch_registered_identity(args.model, expected_digest=str(args.expected_digest or ""))
    results: list[dict[str, Any]] = []
    with recording_proxy() as proxy:
        proxy_base = f"http://127.0.0.1:{proxy.server_address[1]}/v1"
        hermes_home = create_hermes_home(root / "hermes-home", args.model, base_url=proxy_base)
        copied_python, hermes_script = prepare_sandbox_runtime(root)
        hermes_launcher = [copied_python, hermes_script]
        sandbox_profile = create_sandbox_profile(root, fixture, hermes_home)
        env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(hermes_home),
            "HERMES_HOME": str(hermes_home),
            "TMPDIR": str(root),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "PYTHONPATH": os.pathsep.join([
                str(root / "hermes-agent"),
                str(root / "hermes-agent" / "venv" / "lib" / "python3.11" / "site-packages"),
            ]),
            "NO_COLOR": "1",
        }
        for planned in plan_cases(nonce, repeats=args.repeats):
            case = planned["case"]
            assert isinstance(case, Case)
            trial_index = int(planned["trial_index"])
            with proxy.calls_lock:
                call_offset = len(proxy.calls)
            wall_started = time.monotonic()
            command = build_command(args.model, case.prompt, case.toolset, fixture, sandbox_profile, hermes_launcher)
            if case.id == "L03":
                command.insert(command.index("-m"), "--pass-session-id")
            result = subprocess.run(command, cwd=fixture, env=env, capture_output=True, text=True, timeout=300, check=False)
            response = result.stdout.strip()
            missing_session_id = False
            if case.id == "L03" and result.returncode == 0:
                session_id = extract_session_id(result.stdout, result.stderr)
                if session_id:
                    resume = [
                        "sandbox-exec", "-f", str(sandbox_profile), *hermes_launcher,
                        "chat", "-Q", "--ignore-rules", "--source", "tool",
                        "--provider", "custom", "--max-turns", str(MAX_AGENT_TURNS),
                        "--reasoning", "high", "-t", "file", "--resume", session_id,
                        "-m", args.model, "-q",
                        "Return the remembered FILE_NONCE and TOOL_EVIDENCE=session_resume.",
                    ]
                    resumed = subprocess.run(resume, cwd=fixture, env=env, capture_output=True, text=True, timeout=300, check=False)
                    result = resumed
                    response = resumed.stdout.strip()
                else:
                    missing_session_id = True
            wall_elapsed = round(time.monotonic() - wall_started, 3)
            provider_calls = proxy_calls_since(proxy, call_offset)
            route_verified, usage_complete, telemetry_failures = validate_provider_calls(
                args.model, registered_identity, provider_calls
            )
            semantic_ok, semantic_failures = validate_response(response, nonce, case.expected_tool)
            infrastructure_failures, critical_failures, failure_attribution = classify_failures(
                case_id=case.id,
                returncode=result.returncode,
                provider_call_count=len(provider_calls),
                telemetry_failures=telemetry_failures,
                semantic_failures=semantic_failures,
                missing_session_id=missing_session_id,
            )
            row: dict[str, Any] = {
                **asdict(case),
                "case_id": case.id,
                "trial_index": trial_index,
                "ok": semantic_ok and not infrastructure_failures,
                "failures": sorted(set([*semantic_failures, *infrastructure_failures])),
                "critical_failures": sorted(set(critical_failures)),
                "infrastructure_failures": sorted(set(infrastructure_failures)),
                "failure_attribution": failure_attribution,
                "provider_call_count": len(provider_calls),
                "provider_calls": provider_calls,
                "route_identity_verified": route_verified,
                "route_identity_evidence": registered_identity,
                "usage_complete": usage_complete,
                "prompt_tokens": sum(int(call.get("prompt_tokens", 0)) for call in provider_calls),
                "response_tokens": sum(int(call.get("response_tokens", 0)) for call in provider_calls),
                "provider_elapsed_s": round(sum(float(call.get("elapsed_s", 0.0)) for call in provider_calls), 3),
                "elapsed_s": wall_elapsed,
                "returncode": result.returncode,
                "response": response,
                "error": result.stderr[-1000:],
            }
            results.append(row)
            cell_dir = root / f"trial-{trial_index:03d}" / case.id
            cell_dir.mkdir(parents=True, exist_ok=True)
            (cell_dir / "cell.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            with (root / "results.jsonl").open("a", encoding="utf-8") as results_file:
                results_file.write(json.dumps(row) + "\n")
    output = {**summarize_results(args.model, results, expected_repeats=args.repeats), "registered_identity": registered_identity, "results": results}
    (root / "summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if output["promotion_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
