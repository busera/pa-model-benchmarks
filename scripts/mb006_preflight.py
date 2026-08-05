#!/usr/bin/env python3
"""Deterministic, no-call MB-006 roster and denominator preflight."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pa_conflict_retrieval_benchmark as conflict
import pa_daily_use_benchmark as daily
import pa_held_out_benchmark as held_out
import pa_real_life_pack_benchmark as real_life
import pa_tool_live_benchmark as tool_live
import pa_typical_workload_benchmark as workload
import run_t01_t12_full_matrix_profiled as t_matrix
from model_prompt_profiles import guide_path, profile_for_model, require_profile_coverage


REPEATS = 3
FROZEN_ROSTER = {
    "ollama_cloud": [
        "deepseek-v4-flash:0731-cloud",
        "nemotron-3-ultra:cloud",
    ],
    "local": [],
}
FROZEN_REGISTRATION = {
    "deepseek-v4-flash:0731-cloud": {"digest": "031ce2a95446", "registration": "ollama_list_metadata_only"},
    "nemotron-3-ultra:cloud": {"digest": "6d55374b63bb", "registration": "ollama_list_metadata_only"},
    "glm-5.2:cloud": {"digest": "ce8fd6f94793", "registration": "ollama_list_metadata_only"},
    "gemma4:31b-cloud": {"digest": "c382fbfbc73b", "registration": "ollama_list_metadata_only"},
    "deepseek-v4-pro:cloud": {"digest": "22bfd5026abd", "registration": "ollama_list_metadata_only"},
    "qwen3.6:27b-mlx-bf16": {"digest": "2ae7c58c2cf4", "registration": "ollama_list_metadata_only"},
    "qwen3.6:35b-a3b-coding-mxfp8": {"digest": "ccbab0f4045b", "registration": "ollama_list_metadata_only"},
}
FROZEN_SERIAL_SCHEDULE = [
    "deepseek-v4-flash:0731-cloud",
    "nemotron-3-ultra:cloud",
    "glm-5.2:cloud",
    "gemma4:31b-cloud",
    "deepseek-v4-pro:cloud",
    "qwen3.6:27b-mlx-bf16",
    "qwen3.6:35b-a3b-coding-mxfp8",
]


def frozen_models() -> list[str]:
    return [tag for category in ("ollama_cloud", "local") for tag in FROZEN_ROSTER[category]]


def lane_cells_per_repeat() -> dict[str, int]:
    return {
        "D": len(daily.task_list()),
        "R": len(real_life.task_list()),
        "W": len(workload.task_list()),
        "F": len(conflict.task_list()),
        "T": len(t_matrix.TASKS),
        "H": len(held_out.task_list()),
        "tool_live": len(tool_live.cases("COUNT-ONLY")),
    }


def lane_provider_call_caps_per_repeat() -> dict[str, int]:
    cells = lane_cells_per_repeat()
    return {
        "D": cells["D"],
        "R": cells["R"],
        "W": cells["W"],
        "F": cells["F"],
        "T": t_matrix.provider_calls_per_repeat(),
        "H": cells["H"],
        "tool_live": tool_live.maximum_provider_calls(repeats=1),
    }


def build_preflight_manifest() -> dict[str, Any]:
    models = frozen_models()
    cells_per_repeat = lane_cells_per_repeat()
    call_caps_per_repeat = lane_provider_call_caps_per_repeat()
    cells_per_candidate = sum(cells_per_repeat.values()) * REPEATS
    provider_call_cap_per_candidate = sum(call_caps_per_repeat.values()) * REPEATS
    exact_direct_calls_per_candidate = sum(value for lane, value in call_caps_per_repeat.items() if lane != "tool_live") * REPEATS
    candidate_count = len(models)
    route_preflight_calls_per_candidate = 1
    total_response_cap_per_candidate = provider_call_cap_per_candidate + route_preflight_calls_per_candidate
    return {
        "schema_version": "mb006-t03-preflight-v2",
        "packet_status": "approved_two_model_night_run",
        "roster": {category: list(tags) for category, tags in FROZEN_ROSTER.items()},
        "registration_metadata": {tag: dict(metadata) for tag, metadata in FROZEN_REGISTRATION.items()},
        "registration_limit": "metadata_registration_is_not_callability_evidence",
        "thinking_lanes": {tag: ["think_true"] for tag in models},
        "repeats": REPEATS,
        "lane_cells_per_repeat": cells_per_repeat,
        "lane_provider_call_caps_per_repeat": call_caps_per_repeat,
        "cell_records_per_candidate": cells_per_candidate,
        "exact_direct_calls_per_candidate": exact_direct_calls_per_candidate,
        "tool_live_call_cap_per_candidate": call_caps_per_repeat["tool_live"] * REPEATS,
        "provider_call_cap_per_candidate": provider_call_cap_per_candidate,
        "aggregate_cell_records": cells_per_candidate * candidate_count,
        "aggregate_provider_call_cap": provider_call_cap_per_candidate * candidate_count,
        "route_preflight_calls_per_candidate": route_preflight_calls_per_candidate,
        "total_response_cap_per_candidate": total_response_cap_per_candidate,
        "aggregate_total_response_cap": total_response_cap_per_candidate * candidate_count,
        "serial_schedule": list(FROZEN_SERIAL_SCHEDULE),
        "schedule_contract": "one candidate at a time; D,R,W,F,T,H,tool-live; three true repeats; no overlapping model processes",
        "runtime_assumption": {
            "average_provider_call_seconds_range": [15, 60],
            "candidate_model_time_hours_cap_range": [
                round(provider_call_cap_per_candidate * 15 / 3600, 2),
                round(provider_call_cap_per_candidate * 60 / 3600, 2),
            ],
            "aggregate_model_time_hours_cap_range": [
                round(provider_call_cap_per_candidate * candidate_count * 15 / 3600, 2),
                round(provider_call_cap_per_candidate * candidate_count * 60 / 3600, 2),
            ],
            "excludes": ["provider_queueing", "cold_loads", "tool_sandbox_setup", "retry_or_overload_pauses"],
        },
        "quota_assumption": {
            "response_cap": total_response_cap_per_candidate * len(FROZEN_ROSTER["ollama_cloud"]),
            "actual_responses": "measured_from_provider_telemetry",
            "availability": "unknown_until_approved_exact_route_preflight",
            "retries": 0,
        },
        "privacy_class": "synthetic",
        "excluded_specialist_lane": "X",
        "approval_boundary": "approved_two_model_scored_matrix",
        "model_calls": 0,
    }


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("roster") != FROZEN_ROSTER:
        raise ValueError("frozen roster drift")
    if manifest.get("registration_metadata") != FROZEN_REGISTRATION:
        raise ValueError("frozen registration metadata drift")
    if manifest.get("serial_schedule") != FROZEN_SERIAL_SCHEDULE:
        raise ValueError("frozen roster serial schedule drift")
    if manifest.get("repeats") != REPEATS:
        raise ValueError("MB-006 requires exactly three true repeats")
    models = frozen_models()
    require_profile_coverage(models)
    for tag in models:
        profile = profile_for_model(tag)
        expected_thinking = True
        if profile.top_level != {"think": expected_thinking}:
            raise ValueError(f"thinking-lane drift for {tag}")
        expected_lane = ["think_true"]
        if manifest.get("thinking_lanes", {}).get(tag) != expected_lane:
            raise ValueError(f"thinking-lane manifest drift for {tag}")
        guide = guide_path(profile)
        if not guide.is_file() or tag not in guide.read_text(encoding="utf-8"):
            raise ValueError(f"missing exact guide coverage for {tag}: {guide}")
    selected = t_matrix.select_models(models)
    if [row["tag"] for row in selected] != models:
        raise ValueError("T-lane selected-model roster drift")
    if hasattr(t_matrix, "MODELS"):
        raise ValueError("T-lane fixed-roster drift")
    expected_cells = {"D": 14, "R": 10, "W": 21, "F": 10, "T": 12, "H": 6, "tool_live": 3}
    if lane_cells_per_repeat() != expected_cells or manifest.get("lane_cells_per_repeat") != expected_cells:
        raise ValueError("cell denominator mismatch")
    cells_per_candidate = sum(expected_cells.values()) * REPEATS
    if manifest.get("cell_records_per_candidate") != cells_per_candidate:
        raise ValueError("per-candidate cell denominator mismatch")
    if manifest.get("aggregate_cell_records") != cells_per_candidate * len(models):
        raise ValueError("aggregate cell denominator mismatch")
    expected_call_caps = {"D": 14, "R": 10, "W": 21, "F": 10, "T": 16, "H": 6, "tool_live": 16}
    actual_call_caps = lane_provider_call_caps_per_repeat()
    if t_matrix.provider_calls_for_repeats(REPEATS) != 48:
        raise ValueError("T-lane repeat/call controls drift")
    if tool_live.maximum_provider_calls(repeats=REPEATS) != 48:
        raise ValueError("tool-live repeat/call-cap controls drift")
    if actual_call_caps != expected_call_caps or manifest.get("lane_provider_call_caps_per_repeat") != expected_call_caps:
        raise ValueError("provider-call-cap denominator mismatch")
    exact_direct_calls = sum(value for lane, value in expected_call_caps.items() if lane != "tool_live") * REPEATS
    call_cap_per_candidate = sum(expected_call_caps.values()) * REPEATS
    if manifest.get("exact_direct_calls_per_candidate") != exact_direct_calls:
        raise ValueError("exact direct-call denominator mismatch")
    if manifest.get("tool_live_call_cap_per_candidate") != 48:
        raise ValueError("tool-live per-candidate call-cap mismatch")
    if manifest.get("provider_call_cap_per_candidate") != call_cap_per_candidate:
        raise ValueError("per-candidate call-cap denominator mismatch")
    if manifest.get("aggregate_provider_call_cap") != call_cap_per_candidate * len(models):
        raise ValueError("aggregate call-cap denominator mismatch")
    if manifest.get("route_preflight_calls_per_candidate") != 1:
        raise ValueError("route preflight exposure mismatch")
    if manifest.get("total_response_cap_per_candidate") != call_cap_per_candidate + 1:
        raise ValueError("total response cap mismatch")
    if manifest.get("aggregate_total_response_cap") != (call_cap_per_candidate + 1) * len(models):
        raise ValueError("aggregate total response cap mismatch")
    cloud_response_cap = (call_cap_per_candidate + 1) * len(FROZEN_ROSTER["ollama_cloud"])
    quota_assumption = manifest.get("quota_assumption", {})
    if not isinstance(quota_assumption, dict) or quota_assumption.get("response_cap") != cloud_response_cap:
        raise ValueError("Cloud response exposure mismatch")
    if manifest.get("model_calls") != 0:
        raise ValueError("preflight must record zero model calls")
    if manifest.get("privacy_class") != "synthetic":
        raise ValueError("MB-006 packet requires synthetic privacy class")
    if manifest.get("approval_boundary") != "approved_two_model_scored_matrix":
        raise ValueError("approval boundary drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit the validated no-call manifest")
    args = parser.parse_args()
    manifest = build_preflight_manifest()
    validate_manifest(manifest)
    manifest["validation"] = "pass"
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print("MB-006 approved two-model preflight: PASS")
        print(f"models={len(frozen_models())} exact_direct_calls_per_candidate={manifest['exact_direct_calls_per_candidate']} scored_call_cap_per_candidate={manifest['provider_call_cap_per_candidate']} total_response_cap_per_candidate={manifest['total_response_cap_per_candidate']} aggregate_total_response_cap={manifest['aggregate_total_response_cap']} model_calls=0")
        print("AUTHORIZED: exact-route preflight and scored matrix for the frozen two-model roster")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
