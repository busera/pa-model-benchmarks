from __future__ import annotations

import importlib.util
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


def test_isolated_home_uses_local_openai_compatible_endpoint(tmp_path):
    m = load_module()
    home = m.create_hermes_home(tmp_path / "hermes-home", "qwen3.6:27b")
    config = (home / "config.yaml").read_text()
    assert "http://127.0.0.1:11434/v1" in config
    assert "provider: custom" in config
