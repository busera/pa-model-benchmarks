#!/usr/bin/env python3
"""Governance tests for benchmark model prompt profiles."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("model_prompt_profiles.py")


def load_module():
    spec = importlib.util.spec_from_file_location("model_prompt_profiles_tested", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_candidate_families_have_governed_profiles():
    m = load_module()
    candidates = [
        "gpt-5.5",
        "kimi-k2.6:cloud",
        "deepseek-v4-pro:cloud",
        "nemotron-3-ultra:cloud",
        "qwen3-coder:480b-cloud",
        "qwen3.6:27b-mlx-bf16",
        "gemma4:31b-cloud",
        "glm-5.2:cloud",
        "mistral-large-3:675b-cloud",
        "minimax-m3:cloud",
        "gemini-3-flash-preview:cloud",
        "devstral-2:123b-cloud",
    ]
    m.require_profile_coverage(candidates)
    assert all(m.profile_for_model(tag).name != "generic" for tag in candidates)
    assert all(m.guide_path(m.profile_for_model(tag)).is_file() for tag in candidates)


def test_prompt_guides_are_repo_owned_not_vault_runtime_dependencies():
    m = load_module()
    guide = m.guide_path(m.profile_for_model("qwen3.6:27b-mlx-bf16"))
    assert guide == SCRIPT.parent.parent / "prompts" / "guides" / "Qwen 3.6 Prompt Engineering Guide.md"
    assert "/Obsidian/" not in str(guide)


def test_unknown_candidate_fails_closed_before_benchmarking():
    m = load_module()
    try:
        m.require_profile_coverage(["unmapped-frontier-model:cloud"])
    except ValueError as exc:
        assert "Missing model-specific prompt profile" in str(exc)
        assert "unmapped-frontier-model:cloud" in str(exc)
    else:
        raise AssertionError("unknown model should not be benchmarked with the generic profile")
