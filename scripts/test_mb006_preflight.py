from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import mb006_preflight as preflight


SCRIPT = Path(__file__).with_name("mb006_preflight.py")


def test_frozen_roster_and_exact_call_denominator():
    manifest = preflight.build_preflight_manifest()

    assert manifest["roster"] == {
        "ollama_cloud": [
            "deepseek-v4-flash:0731-cloud",
            "nemotron-3-ultra:cloud",
        ],
        "local": [],
    }
    assert manifest["thinking_lanes"] == {
        "deepseek-v4-flash:0731-cloud": ["think_true"],
        "nemotron-3-ultra:cloud": ["think_true"],
    }
    assert manifest["repeats"] == 3
    assert manifest["lane_provider_call_caps_per_repeat"] == {
        "D": 14,
        "R": 10,
        "W": 21,
        "F": 10,
        "T": 16,
        "H": 6,
        "tool_live": 16,
    }
    assert manifest["exact_direct_calls_per_candidate"] == 231
    assert manifest["tool_live_call_cap_per_candidate"] == 48
    assert manifest["provider_call_cap_per_candidate"] == 279
    assert manifest["aggregate_provider_call_cap"] == 558
    assert manifest["route_preflight_calls_per_candidate"] == 1
    assert manifest["total_response_cap_per_candidate"] == 280
    assert manifest["aggregate_total_response_cap"] == 560
    assert manifest["privacy_class"] == "synthetic"
    assert manifest["approval_boundary"] == "approved_two_model_scored_matrix"
    assert manifest["registration_metadata"]["deepseek-v4-flash:0731-cloud"] is not preflight.FROZEN_REGISTRATION["deepseek-v4-flash:0731-cloud"]
    preflight.validate_manifest(manifest)


def test_preflight_fails_closed_on_roster_denominator_or_repeat_drift():
    baseline = preflight.build_preflight_manifest()

    changed_roster = copy.deepcopy(baseline)
    changed_roster["roster"]["ollama_cloud"].append("unapproved:cloud")
    with pytest.raises(ValueError, match="frozen roster"):
        preflight.validate_manifest(changed_roster)

    wrong_denominator = copy.deepcopy(baseline)
    wrong_denominator["provider_call_cap_per_candidate"] = 278
    with pytest.raises(ValueError, match="denominator"):
        preflight.validate_manifest(wrong_denominator)

    wrong_cell_denominator = copy.deepcopy(baseline)
    wrong_cell_denominator["cell_records_per_candidate"] = 227
    with pytest.raises(ValueError, match="cell denominator"):
        preflight.validate_manifest(wrong_cell_denominator)

    missing_repeats = copy.deepcopy(baseline)
    missing_repeats["repeats"] = 1
    with pytest.raises(ValueError, match="three true repeats"):
        preflight.validate_manifest(missing_repeats)

    missing_registration = copy.deepcopy(baseline)
    del missing_registration["registration_metadata"]["deepseek-v4-flash:0731-cloud"]
    with pytest.raises(ValueError, match="registration metadata"):
        preflight.validate_manifest(missing_registration)

    wrong_privacy = copy.deepcopy(baseline)
    wrong_privacy["privacy_class"] = "private-cloud-approved"
    with pytest.raises(ValueError, match="synthetic privacy"):
        preflight.validate_manifest(wrong_privacy)

    wrong_cloud_exposure = copy.deepcopy(baseline)
    wrong_cloud_exposure["quota_assumption"]["response_cap"] = 557
    with pytest.raises(ValueError, match="Cloud response exposure"):
        preflight.validate_manifest(wrong_cloud_exposure)


def test_preflight_fails_closed_when_runner_controls_or_guide_coverage_drift(monkeypatch):
    manifest = preflight.build_preflight_manifest()

    monkeypatch.setattr(preflight.t_matrix, "provider_calls_for_repeats", lambda repeats: 47)
    with pytest.raises(ValueError, match="T-lane"):
        preflight.validate_manifest(manifest)

    monkeypatch.undo()
    monkeypatch.setattr(preflight.tool_live, "maximum_provider_calls", lambda repeats: 47)
    with pytest.raises(ValueError, match="tool-live"):
        preflight.validate_manifest(manifest)

    monkeypatch.undo()
    monkeypatch.setattr(preflight, "guide_path", lambda profile: Path("/missing/exact-guide.md"))
    with pytest.raises(ValueError, match="missing exact guide coverage"):
        preflight.validate_manifest(manifest)


def test_no_call_cli_emits_valid_manifest():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=SCRIPT.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    manifest = json.loads(completed.stdout)
    assert manifest["validation"] == "pass"
    assert manifest["model_calls"] == 0
    assert manifest["exact_direct_calls_per_candidate"] == 231
    assert manifest["provider_call_cap_per_candidate"] == 279
    assert manifest["aggregate_provider_call_cap"] == 558
    assert manifest["aggregate_total_response_cap"] == 560
