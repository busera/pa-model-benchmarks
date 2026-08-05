#!/usr/bin/env python3
"""Canonical repository tree and scoped credential gate for MB-006."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "mb006-tree-manifest-v1"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return completed.stdout


def _canonical_repo_root(repo_root: Path) -> Path:
    absolute = Path(os.path.abspath(repo_root))
    resolved = repo_root.resolve()
    if absolute != resolved:
        raise RuntimeError("repository root is symlinked or non-canonical")
    actual = Path(_git(resolved, "rev-parse", "--show-toplevel").decode().strip())
    if actual != resolved:
        raise RuntimeError("path is not the exact Git repository root")
    return resolved


def _parse_status(raw_status: bytes) -> list[dict[str, Any]]:
    records = raw_status.split(b"\0")
    parsed: list[dict[str, Any]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if record.startswith(b"1 "):
            fields = record.split(b" ", 8)
            if len(fields) != 9:
                raise RuntimeError("unsupported malformed porcelain-v2 ordinary record")
            parsed.append({
                "path_bytes": fields[8],
                "porcelain_v2_status": b" ".join(fields[:8]).decode("ascii"),
                "xy": fields[1].decode("ascii"),
                "sub": fields[2].decode("ascii"),
                "head_mode": fields[3].decode("ascii"),
                "index_mode": fields[4].decode("ascii"),
                "worktree_mode": fields[5].decode("ascii"),
            })
            continue
        if record.startswith(b"2 "):
            fields = record.split(b" ", 9)
            if len(fields) != 10 or index >= len(records):
                raise RuntimeError("unsupported malformed porcelain-v2 rename record")
            original_path = records[index]
            index += 1
            parsed.append({
                "path_bytes": fields[9],
                "original_path_bytes": original_path,
                "porcelain_v2_status": b" ".join(fields[:9]).decode("ascii"),
                "xy": fields[1].decode("ascii"),
                "sub": fields[2].decode("ascii"),
                "head_mode": fields[3].decode("ascii"),
                "index_mode": fields[4].decode("ascii"),
                "worktree_mode": fields[5].decode("ascii"),
            })
            continue
        if record.startswith(b"? "):
            parsed.append({
                "path_bytes": record[2:],
                "porcelain_v2_status": "?",
                "xy": "??",
                "sub": "N...",
                "head_mode": "000000",
                "index_mode": "000000",
                "worktree_mode": "000000",
            })
            continue
        if record.startswith(b"u "):
            raise RuntimeError("unsupported unmerged porcelain-v2 record")
        raise RuntimeError("unsupported porcelain-v2 record kind")
    return parsed


def _display_path(path_bytes: bytes) -> str:
    value = os.fsdecode(path_bytes)
    if not value or os.path.isabs(value) or ".." in Path(value).parts:
        raise RuntimeError("dirty path is not a governed repository-relative path")
    return value


def _object_mode(file_stat: os.stat_result) -> str:
    if stat.S_ISREG(file_stat.st_mode):
        return "100755" if file_stat.st_mode & 0o111 else "100644"
    if stat.S_ISLNK(file_stat.st_mode):
        return "120000"
    raise RuntimeError("unsupported non-regular repository object")


def _deleted_mode(record: dict[str, Any]) -> str:
    for key in ("index_mode", "head_mode"):
        mode = record[key]
        if mode != "000000":
            return mode
    return "000000"


def _read_regular_nofollow(path: bytes, expected: os.stat_result) -> bytes:
    nofollow = int(getattr(os, "O_NOFOLLOW_ANY", 0) or getattr(os, "O_NOFOLLOW", 0))
    if not nofollow:
        raise RuntimeError("runtime has no effective no-follow read flag")
    descriptor = os.open(path, os.O_RDONLY | int(getattr(os, "O_CLOEXEC", 0)) | nofollow)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
        ):
            raise RuntimeError("repository object changed during content read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


_ASSIGNMENT = re.compile(
    rb"(?i)\b(?:api[_-]?key|secret|password|passwd|token|client[_-]?secret)\b"
    rb"\s*[:=]\s*['\"](?P<value>[^'\"\r\n]{12,})['\"]",
)
_PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_KNOWN_PREFIX = re.compile(rb"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")
_PLACEHOLDERS = (b"example", b"placeholder", b"your-", b"redacted", b"dummy", b"changeme", b"${", b"<")


def _credential_hits(path: str, content: bytes) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        assignment = _ASSIGNMENT.search(line)
        if assignment and not any(marker in assignment.group("value").lower() for marker in _PLACEHOLDERS):
            hits.append({"path": path, "line": line_number, "rule": "credential_assignment"})
            continue
        if _PRIVATE_KEY.search(line):
            hits.append({"path": path, "line": line_number, "rule": "private_key"})
            continue
        if _KNOWN_PREFIX.search(line):
            hits.append({"path": path, "line": line_number, "rule": "credential_prefix"})
    return hits


def build_tree_manifest(repo_root: Path = ROOT) -> dict[str, Any]:
    root = _canonical_repo_root(repo_root)
    head_oid = _git(root, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    status = _git(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    records = _parse_status(status)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    credential_hits: list[dict[str, Any]] = []
    root_bytes = os.fsencode(root)

    for record in records:
        path_bytes = record["path_bytes"]
        path = _display_path(path_bytes)
        row: dict[str, Any] = {
            "path": path,
            "path_bytes": base64.b64encode(path_bytes).decode("ascii"),
            "porcelain_v2_status": record["porcelain_v2_status"],
        }
        if "original_path_bytes" in record:
            row["original_path_bytes"] = base64.b64encode(record["original_path_bytes"]).decode("ascii")
        if record["sub"] != "N..." or "160000" in {
            record["head_mode"], record["index_mode"], record["worktree_mode"],
        }:
            errors.append(f"submodule object is unsupported: {path}")
            continue
        absolute_bytes = root_bytes + b"/" + path_bytes
        try:
            file_stat = os.lstat(absolute_bytes)
        except FileNotFoundError:
            if "D" not in record["xy"]:
                errors.append(f"dirty path disappeared without deletion status: {path}")
                continue
            row.update({
                "object_kind": "deleted",
                "mode": _deleted_mode(record),
                "deleted": True,
            })
            rows.append(row)
            continue
        try:
            mode = _object_mode(file_stat)
        except RuntimeError:
            errors.append(f"unsupported non-regular repository object: {path}")
            continue
        row["mode"] = mode
        if stat.S_ISREG(file_stat.st_mode):
            content = _read_regular_nofollow(absolute_bytes, file_stat)
            row.update({
                "object_kind": "regular",
                "bytes": len(content),
                "sha256": sha256_bytes(content),
            })
            credential_hits.extend(_credential_hits(path, content))
        elif stat.S_ISLNK(file_stat.st_mode):
            target = os.readlink(absolute_bytes)
            if not isinstance(target, bytes):
                target = os.fsencode(target)
            row.update({
                "object_kind": "symlink",
                "link_target_bytes": base64.b64encode(target).decode("ascii"),
                "link_target_sha256": sha256_bytes(target),
            })
        rows.append(row)

    rows.sort(key=lambda row: row["path"])
    errors = sorted(set(errors))
    credential_hits.sort(key=lambda hit: (hit["path"], hit["line"], hit["rule"]))
    identity = {
        "schema_version": SCHEMA_VERSION,
        "head_oid": head_oid,
        "rows": rows,
    }
    return {
        **identity,
        "aggregate_sha256": sha256_bytes(canonical_json_bytes(identity)),
        "manifest_valid": not errors and not credential_hits,
        "errors": errors,
        "credential_hits": credential_hits,
        "model_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    manifest = build_tree_manifest(args.repo_root)
    serialized = canonical_json_bytes(manifest)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(serialized + b"\n")
    if args.json or args.output is None:
        print(serialized.decode("utf-8"))
    return 0 if manifest["manifest_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
