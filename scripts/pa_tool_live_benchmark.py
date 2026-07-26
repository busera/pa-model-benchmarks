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
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    id: str
    toolset: str
    expected_tool: str
    prompt: str


TRUSTED_EXECUTION_PARENT = Path("/private/tmp")


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


def create_hermes_home(root: Path, model: str) -> Path:
    """Create an isolated Hermes home routed only to local Ollama's OpenAI API."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(
        "model:\n"
        f"  default: {model}\n"
        "  provider: custom\n"
        "  base_url: http://127.0.0.1:11434/v1\n"
        "  api_key: ollama-local-only\n"
        "  api_mode: chat_completions\n"
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
    command = [*(hermes_launcher or ["hermes"]), "chat", "-Q", "--ignore-rules", "--source", "tool", "--max-turns", "4", "--provider", "custom"]
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


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="pa-tool-live-") as tmp:
        nonce = "SELFTEST-NONCE"
        root = create_fixture(Path(tmp), nonce)
        assert len(cases(nonce)) == 3
        assert "SELFTEST-NONCE" in (root / "current.md").read_text()
        assert validate_response("FILE_NONCE=SELFTEST-NONCE\nTOOL_EVIDENCE=read_file", nonce, "read_file")[0]
    print(json.dumps({"self_test": "pass", "model_calls": 0}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.6:27b")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--allow-cloud", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--artifact-root", type=Path)
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    require_route_allowed(args.model, allow_cloud=args.allow_cloud)
    root = create_execution_root(args.artifact_root)
    nonce = f"SYNTH-{uuid.uuid4().hex[:12]}"
    fixture = create_fixture(root / "fixture", nonce)
    hermes_home = create_hermes_home(root / "hermes-home", args.model)
    if not args.execute:
        print(json.dumps({"mode": "fixture-only", "fixture": str(fixture), "nonce": nonce, "model_calls": 0}, indent=2))
        return 0
    results = []
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
    for case in cases(nonce):
        command = build_command(args.model, case.prompt, case.toolset, fixture, sandbox_profile, hermes_launcher)
        if case.id == "L03":
            command.insert(command.index("-m"), "--pass-session-id")
        result = subprocess.run(command, cwd=fixture, env=env, capture_output=True, text=True, timeout=300, check=False)
        response = result.stdout.strip()
        if case.id == "L03" and result.returncode == 0:
            session_id = extract_session_id(result.stdout, result.stderr)
            if session_id:
                resume = ["sandbox-exec", "-f", str(sandbox_profile), *hermes_launcher, "chat", "-Q", "--ignore-rules", "--source", "tool", "--provider", "custom", "--max-turns", "4", "-t", "file", "--resume", session_id, "-m", args.model, "-q", "Return the remembered FILE_NONCE and TOOL_EVIDENCE=session_resume."]
                resumed = subprocess.run(resume, cwd=fixture, env=env, capture_output=True, text=True, timeout=300, check=False)
                result = resumed
                response = resumed.stdout.strip()
        ok, failures = validate_response(response, nonce, case.expected_tool)
        results.append({**asdict(case), "ok": ok and result.returncode == 0, "failures": failures, "returncode": result.returncode, "response": response, "error": result.stderr[-1000:]})
    output = {"privacy_class": "synthetic", "model": args.model, "results": results, "promotion_eligible": False}
    (root / "summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
