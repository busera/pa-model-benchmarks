from __future__ import annotations

import importlib
import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def test_production_sources_have_no_user_or_vault_absolute_paths():
    offenders = []
    for path in SCRIPTS.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "/Users/busera/" in text:
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


def test_tracked_fixtures_use_synthetic_subjects_without_named_profile_contracts():
    named_profile = re.compile(r"\b[A-Z][a-z]{2,}'s (?:PA|iPhone|custom|ad-hoc)\b")
    offenders = []
    for path in SCRIPTS.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if named_profile.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == []

    profiles = importlib.import_module("model_prompt_profiles")
    assert "synthetic user" in profiles.BASE_PA_CONTRACT
    for name in (
        "pa_daily_use_benchmark",
        "pa_real_life_pack_benchmark",
        "pa_typical_workload_benchmark",
        "pa_conflict_retrieval_benchmark",
        "pa_extended_capability_benchmark",
        "pa_held_out_benchmark",
    ):
        module = importlib.import_module(name)
        assert "synthetic" in module.SYSTEM.lower()


def test_active_runner_roots_resolve_to_repository():
    for name in (
        "pa_daily_use_benchmark",
        "pa_real_life_pack_benchmark",
        "pa_typical_workload_benchmark",
        "pa_conflict_retrieval_benchmark",
        "pa_extended_capability_benchmark",
        "pa_held_out_benchmark",
    ):
        module = importlib.import_module(name)
        assert module.BASE_DIR == REPO
        assert module.ARTIFACTS_DIR == REPO / "artifacts" if hasattr(module, "ARTIFACTS_DIR") else True


def test_legacy_private_fixture_loaders_are_opt_in(monkeypatch):
    monkeypatch.delenv("PA_BENCHMARK_PRIVATE_FIXTURE_ROOT", raising=False)
    wave2 = importlib.import_module("legacy_t_matrix.wave2")
    assert wave2.load_real_t1() == wave2.FIXTURE_T1
    assert wave2.load_real_t4() == wave2.FIXTURE_T4
