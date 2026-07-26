"""Immutable, secret-free benchmark run manifests."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _probe(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        value = (result.stdout or result.stderr).strip().splitlines()
        return value[0][:300] if value else None
    except (OSError, subprocess.SubprocessError):
        return None


def parse_ollama_list(output: str) -> dict[str, str]:
    """Parse the stable NAME/ID prefix of ``ollama list`` output."""
    identities: dict[str, str] = {}
    for line in output.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 2:
            identities[columns[0]] = columns[1]
    return identities


def _ollama_identities() -> dict[str, str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10, check=False)
        return parse_ollama_list(result.stdout) if result.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError):
        return {}


def _safe_source_id(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return path.name


def build_manifest(*, run_id: str, models: list[str], task_payload: Any, source_paths: list[Path], repeats: int, seed: int, run_order: str, privacy_class: str, argv: list[str], prompt_profiles: dict[str, Any] | None = None, model_routes: dict[str, str] | None = None, probe_commands: bool = True) -> dict[str, Any]:
    if privacy_class not in {"synthetic", "private-local", "private-cloud-approved"}:
        raise ValueError("unsupported privacy class")
    shared_sources = [
        Path(__file__),
        Path(__file__).with_name("benchmark_trials.py"),
        Path(__file__).with_name("benchmark_semantics.py"),
        Path(__file__).with_name("benchmark_decision.py"),
        Path(__file__).with_name("benchmark_transport.py"),
        Path(__file__).with_name("model_prompt_profiles.py"),
    ]
    if prompt_profiles is None:
        try:
            from model_prompt_profiles import guide_path, profile_for_model
            profiles_by_model = {model: profile_for_model(model) for model in models}
            prompt_profiles = {
                model: {
                    "name": profile.name,
                    "guide": profile.guide,
                    "effective_system_prompt": profile.system_prompt(),
                    "options": profile.options,
                    "top_level": profile.top_level,
                }
                for model, profile in profiles_by_model.items()
            }
            guide_sources = [guide_path(profile) for profile in profiles_by_model.values()]
        except (ImportError, ValueError):
            prompt_profiles = {}
            guide_sources = []
    else:
        guide_sources = []
    all_sources = [
        *source_paths,
        *(p for p in shared_sources if p not in source_paths),
        *(p for p in guide_sources if p not in source_paths and p not in shared_sources),
    ]
    missing_sources = [str(p) for p in all_sources if not p.is_file()]
    if missing_sources:
        raise FileNotFoundError(f"manifest source paths missing: {missing_sources}")
    sources = {_safe_source_id(p): sha256_bytes(p.read_bytes()) for p in all_sources}
    profile_hashes = {
        model: sha256_bytes(json.dumps(profile, sort_keys=True, ensure_ascii=False, default=str).encode())
        for model, profile in (prompt_profiles or {}).items()
    }
    runtime: dict[str, Any] = {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine()}
    local_identities: dict[str, str] = {}
    if probe_commands:
        runtime.update({"git_commit": _probe(["git", "rev-parse", "HEAD"]), "ollama_version": _probe(["ollama", "--version"]), "hermes_version": _probe(["hermes", "--version"])})
        local_identities = _ollama_identities()
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "models": models,
        "privacy_class": privacy_class,
        "repeats": repeats,
        "seed": seed,
        "run_order": run_order,
        "command": Path(argv[0]).name if argv else None,
        "task_hash": sha256_bytes(json.dumps(task_payload, sort_keys=True, ensure_ascii=False, default=str).encode()),
        "prompt_profile_hashes": profile_hashes,
        "source_hashes": sources,
        "runtime": runtime,
        "model_identity": {
            model: {
                "requested_tag": model,
                "provider_route": (model_routes or {}).get(model, "unspecified"),
                "api_mode": "openai-codex" if (model_routes or {}).get(model) == "hermes" else "ollama-native" if (model_routes or {}).get(model) == "ollama" else "unspecified",
                "digest": local_identities.get(model) if (model_routes or {}).get(model) == "ollama" else None,
                "status": "resolved" if (model_routes or {}).get(model) == "ollama" and model in local_identities else "explicit-route-requested",
            }
            for model in models
        },
    }


def claim_run_root(root: Path) -> Path:
    """Claim a fresh run directory; resume/overwrite requires a future explicit protocol."""
    if root.exists():
        existing = sorted(path.name for path in root.iterdir())
        if existing:
            raise FileExistsError(f"run root is not empty: {root} ({existing[:5]})")
    else:
        root.mkdir(parents=True)
    return root


def write_manifest(root: Path, manifest: dict[str, Any]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "manifest.json"
    if path.exists():
        raise FileExistsError(f"manifest already exists: {path}")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=False))
    return path
