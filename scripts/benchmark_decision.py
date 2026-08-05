"""Fail-closed, provider-category PA model decisions."""
from __future__ import annotations

from copy import deepcopy
from math import inf, isfinite
from typing import Any, Iterable

CATEGORIES = ("ollama_cloud", "local")
REQUIRED_BROAD_LANES = ("D", "R", "W", "F", "T", "H", "tool_live")
RISK_ORDER = ("F", "R", "D", "H", "W", "T", "tool_live")


def _finite_unit_interval(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _require_candidate_shape(
    candidate: dict[str, Any], *, required_lanes: tuple[str, ...]
) -> None:
    model = candidate.get("model")
    if not isinstance(model, str) or not model or model != model.strip():
        raise ValueError("every candidate requires a non-empty model with exact spelling")
    if candidate.get("category") not in CATEGORIES:
        raise ValueError(f"unsupported candidate category: {candidate.get('category')!r}")
    for field in ("route_verified", "complete"):
        if not isinstance(candidate.get(field), bool):
            raise ValueError(f"candidate {model!r} requires boolean {field}")
    for field in ("repeats", "critical_failures"):
        value = candidate.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"candidate {model!r} requires non-negative integer {field}")
    if not _finite_unit_interval(candidate.get("strict_format_rate")):
        raise ValueError(f"candidate {model!r} requires finite strict_format_rate in [0, 1]")
    lanes = candidate.get("lanes")
    if not isinstance(lanes, dict):
        raise ValueError(f"candidate {model!r} requires lane evidence")
    for lane in required_lanes:
        row = lanes.get(lane)
        if not isinstance(row, dict):
            continue
        if not isinstance(row.get("eligible"), bool):
            raise ValueError(f"candidate {model!r} lane {lane!r} requires boolean eligible")
        if not _finite_unit_interval(row.get("score")):
            raise ValueError(f"candidate {model!r} lane {lane!r} requires finite score in [0, 1]")
    tokens = candidate.get("response_tokens")
    if tokens is not None and (
        not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0
    ):
        raise ValueError(f"candidate {model!r} response_tokens must be null or a non-negative integer")
    elapsed = candidate.get("elapsed_s")
    if elapsed is not None and (
        not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not isfinite(float(elapsed))
        or elapsed < 0
    ):
        raise ValueError(f"candidate {model!r} elapsed_s must be null or finite and non-negative")


def build_decision(
    lanes: dict[str, dict[str, Any]], *, required_lanes: Iterable[str]
) -> dict[str, Any]:
    """Return lane eligibility without creating a universal score or rank."""
    result = deepcopy(lanes)
    required = tuple(required_lanes)
    for lane in required:
        if lane not in result:
            result[lane] = {
                "status": "missing",
                "eligible": False,
                "blocking_failures": ["missing_evidence"],
            }
        else:
            result[lane].setdefault("status", "complete")
            result[lane].setdefault("blocking_failures", [])
    blocking = [lane for lane in required if not bool(result[lane].get("eligible"))]
    return {
        "schema_version": 1,
        "decision_model": "lane-specific-fail-closed",
        "lanes": result,
        "required_lanes": list(required),
        "blocking_lanes": blocking,
        "broad_default_eligible": not blocking,
        "explicit_routing_decision_required": True,
    }


def _candidate_blockers(
    candidate: dict[str, Any], *, required_lanes: tuple[str, ...], minimum_repeats: int
) -> list[str]:
    blockers: list[str] = []
    if candidate.get("route_verified") is not True:
        blockers.append("route_identity_unverified")
    if candidate.get("complete") is not True:
        blockers.append("incomplete_schedule")
    if candidate["repeats"] < minimum_repeats:
        blockers.append("insufficient_true_repeats")
    if candidate["critical_failures"]:
        blockers.append("blocking_critical_failures")
    lanes = candidate.get("lanes")
    if not isinstance(lanes, dict):
        return blockers + ["missing_lane_evidence"]
    for lane in required_lanes:
        row = lanes.get(lane)
        if not isinstance(row, dict):
            blockers.append(f"missing_lane:{lane}")
        elif row.get("eligible") is not True:
            blockers.append(f"failed_lane:{lane}")
    return blockers


def _score(candidate: dict[str, Any], lane: str) -> float:
    row = candidate.get("lanes", {}).get(lane, {})
    value = row.get("score") if isinstance(row, dict) else None
    return float(value) if isinstance(value, (int, float)) else -inf


def _quality_key(candidate: dict[str, Any], required_lanes: tuple[str, ...]) -> tuple[Any, ...]:
    lane_scores = tuple(_score(candidate, lane) for lane in RISK_ORDER if lane in required_lanes)
    worst = min((_score(candidate, lane) for lane in required_lanes), default=-inf)
    strict_rate = candidate.get("strict_format_rate")
    strict = float(strict_rate) if isinstance(strict_rate, (int, float)) else -inf
    response_tokens = candidate.get("response_tokens")
    token_key = -int(response_tokens) if isinstance(response_tokens, int) and response_tokens >= 0 else -inf
    elapsed = candidate.get("elapsed_s")
    elapsed_key = -float(elapsed) if isinstance(elapsed, (int, float)) and elapsed >= 0 else -inf
    return (worst, *lane_scores, strict, token_key, elapsed_key, str(candidate.get("model", "")))


def build_category_model_selection(
    candidates: Iterable[dict[str, Any]],
    *,
    required_lanes: Iterable[str] = REQUIRED_BROAD_LANES,
    minimum_repeats: int = 3,
) -> dict[str, Any]:
    """Select one eligible leader per provider category, never across categories.

    `best_observed` is diagnostic only. Missing telemetry loses efficiency tie-breaks but
    does not invalidate an otherwise quality-eligible candidate.
    """
    if minimum_repeats < 1:
        raise ValueError("minimum_repeats must be >= 1")
    required = tuple(required_lanes)
    if not required or len(set(required)) != len(required):
        raise ValueError("required_lanes must be non-empty and unique")

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in candidates:
        row = deepcopy(raw)
        _require_candidate_shape(row, required_lanes=required)
        model = str(row["model"])
        category = str(row["category"])
        identity = (category, model)
        if identity in seen:
            raise ValueError(f"duplicate candidate: {category}/{model}")
        seen.add(identity)
        row["blocking_reasons"] = _candidate_blockers(
            row, required_lanes=required, minimum_repeats=minimum_repeats
        )
        row["eligible"] = not row["blocking_reasons"]
        normalized.append(row)

    decisions: dict[str, Any] = {}
    for category in CATEGORIES:
        rows = [row for row in normalized if row.get("category") == category]
        eligible = [row for row in rows if row["eligible"]]
        eligible.sort(key=lambda row: _quality_key(row, required), reverse=True)
        observed = [
            row for row in rows
            if row.get("route_verified") is True and row.get("complete") is True
        ]
        observed.sort(key=lambda row: _quality_key(row, required), reverse=True)
        decisions[category] = {
            "eligible_leader": eligible[0]["model"] if eligible else None,
            "best_observed": observed[0]["model"] if observed else None,
            "best_observed_is_diagnostic": True,
            "eligible_candidates": [row["model"] for row in eligible],
            "candidates": rows,
        }

    return {
        "schema_version": 2,
        "decision_model": "provider-category-fail-closed-quality-first",
        "required_lanes": list(required),
        "minimum_true_repeats": minimum_repeats,
        "categories": decisions,
        "universal_winner": None,
        "explicit_routing_decision_required": True,
    }
