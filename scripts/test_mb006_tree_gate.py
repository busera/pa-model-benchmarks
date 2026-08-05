from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).with_name("mb006_tree_gate.py")


def load_module():
    spec = importlib.util.spec_from_file_location("mb006_tree_gate_tested", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def initialized_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Tree Gate Test")
    git(repo, "config", "user.email", "tree-gate@example.invalid")
    git(repo, "config", "core.filemode", "true")
    (repo / "modified.txt").write_text("original\n", encoding="utf-8")
    (repo / "deleted.txt").write_text("delete me\n", encoding="utf-8")
    (repo / "script.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (repo / "target-a").write_text("a\n", encoding="utf-8")
    (repo / "target-b").write_text("b\n", encoding="utf-8")
    (repo / "tracked-link").symlink_to("target-a")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "initial")
    return repo


def rows_by_path(manifest):
    return {row["path"]: row for row in manifest["rows"]}


def test_tree_manifest_censuses_modified_untracked_deleted_and_symlink_bytes(tmp_path):
    m = load_module()
    repo = initialized_repo(tmp_path)
    (repo / "modified.txt").write_text("changed\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("new\n", encoding="utf-8")
    (repo / "deleted.txt").unlink()
    (repo / "tracked-link").unlink()
    (repo / "tracked-link").symlink_to("target-b")

    first = m.build_tree_manifest(repo)
    second = m.build_tree_manifest(repo)
    rows = rows_by_path(first)

    assert first["manifest_valid"] is True
    assert first["credential_hits"] == []
    assert first["head_oid"] == git(repo, "rev-parse", "HEAD")
    assert first["aggregate_sha256"] == second["aggregate_sha256"]
    assert list(rows) == sorted(rows)
    assert rows["modified.txt"]["object_kind"] == "regular"
    assert rows["modified.txt"]["mode"] == "100644"
    assert rows["modified.txt"]["bytes"] == len(b"changed\n")
    assert len(rows["modified.txt"]["sha256"]) == 64
    assert rows["deleted.txt"]["object_kind"] == "deleted"
    assert rows["deleted.txt"]["deleted"] is True
    assert rows["tracked-link"]["object_kind"] == "symlink"
    assert rows["tracked-link"]["mode"] == "120000"
    assert rows["tracked-link"]["link_target_bytes"] == "dGFyZ2V0LWI="
    assert len(rows["tracked-link"]["link_target_sha256"]) == 64
    assert rows["untracked.txt"]["porcelain_v2_status"] == "?"


def test_tree_manifest_head_and_executable_mode_changes_alter_identity(tmp_path):
    m = load_module()
    repo = initialized_repo(tmp_path)
    (repo / "modified.txt").write_text("changed\n", encoding="utf-8")
    before_head = m.build_tree_manifest(repo)
    git(repo, "add", "modified.txt")
    git(repo, "commit", "-qm", "move head")
    after_head = m.build_tree_manifest(repo)
    assert before_head["head_oid"] != after_head["head_oid"]
    assert before_head["aggregate_sha256"] != after_head["aggregate_sha256"]

    script = repo / "script.sh"
    script.write_text("#!/bin/sh\necho changed\n", encoding="utf-8")
    script.chmod(0o644)
    non_executable = m.build_tree_manifest(repo)
    script.chmod(0o755)
    executable = m.build_tree_manifest(repo)
    assert rows_by_path(non_executable)["script.sh"]["mode"] == "100644"
    assert rows_by_path(executable)["script.sh"]["mode"] == "100755"
    assert non_executable["aggregate_sha256"] != executable["aggregate_sha256"]


def test_tree_manifest_symlink_target_and_deletion_change_identity(tmp_path):
    m = load_module()
    repo = initialized_repo(tmp_path)
    link = repo / "tracked-link"
    link.unlink()
    link.symlink_to("target-b")
    target_b = m.build_tree_manifest(repo)
    link.unlink()
    link.symlink_to("target-a-longer")
    target_other = m.build_tree_manifest(repo)
    assert target_b["aggregate_sha256"] != target_other["aggregate_sha256"]

    (repo / "modified.txt").unlink()
    deleted = m.build_tree_manifest(repo)
    assert target_other["aggregate_sha256"] != deleted["aggregate_sha256"]
    assert rows_by_path(deleted)["modified.txt"]["deleted"] is True


def test_tree_manifest_credential_gate_redacts_secret_value(tmp_path):
    m = load_module()
    repo = initialized_repo(tmp_path)
    secret = "sk-" + "live-" + "abcdefghijklmnopqrstuvwxyz123456"
    (repo / "credential.py").write_text(f'API_KEY = "{secret}"\n', encoding="utf-8")

    manifest = m.build_tree_manifest(repo)

    assert manifest["manifest_valid"] is False
    assert manifest["credential_hits"] == [
        {"path": "credential.py", "line": 1, "rule": "credential_assignment"},
    ]
    assert secret not in str(manifest)


def test_tree_manifest_handles_nul_framed_odd_path_and_rejects_fifo(tmp_path, monkeypatch):
    m = load_module()
    repo = initialized_repo(tmp_path)
    odd_name = "odd\nname.txt"
    (repo / odd_name).write_text("safe\n", encoding="utf-8")
    manifest = m.build_tree_manifest(repo)
    assert odd_name in rows_by_path(manifest)

    fifo = repo / "unsupported.fifo"
    os.mkfifo(fifo)
    original_git = m._git

    def git_with_reported_fifo(repo_root, *args):
        output = original_git(repo_root, *args)
        if args and args[0] == "status":
            return output + b"? unsupported.fifo\0"
        return output

    monkeypatch.setattr(m, "_git", git_with_reported_fifo)
    invalid = m.build_tree_manifest(repo)
    assert invalid["manifest_valid"] is False
    assert any("unsupported" in error for error in invalid["errors"])


def test_tree_manifest_rejects_gitlink_submodule_object(tmp_path):
    m = load_module()
    repo = initialized_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},nested-submodule")

    manifest = m.build_tree_manifest(repo)

    assert manifest["manifest_valid"] is False
    assert any("submodule" in error for error in manifest["errors"])
