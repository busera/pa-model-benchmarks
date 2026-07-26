"""Fail-closed lane-specific benchmark decision reporting."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


def build_decision(lanes: dict[str, dict[str, Any]], *, required_lanes: Iterable[str]) -> dict[str, Any]:
    """Return eligibility without creating a universal composite score or rank."""
    result = deepcopy(lanes)
    required = tuple(required_lanes)
    for lane in required:
        if lane not in result:
            result[lane] = {"status": "missing", "eligible": False, "blocking_failures": ["missing_evidence"]}
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
