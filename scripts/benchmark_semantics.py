"""Field-scoped semantic checks used by deterministic benchmark validators."""
from __future__ import annotations

import re
from typing import Any, Iterable


def _text(value: Any) -> str:
    if isinstance(value, (list, tuple, dict)):
        return str(value).lower()
    return str(value or "").lower()


def contains_number(text: str, expected: float, tolerance: float = 0.005) -> bool:
    """Return true when text contains a normalized number near expected."""
    for raw in re.findall(r"[-+]?\d[\d,.]*", text):
        candidate = raw.rstrip(".,")
        if "," in candidate and "." in candidate:
            candidate = candidate.replace(",", "")
        elif "," in candidate:
            tail = candidate.rsplit(",", 1)[-1]
            candidate = candidate.replace(",", "." if len(tail) <= 2 else "")
        try:
            if abs(float(candidate) - expected) <= tolerance:
                return True
        except ValueError:
            continue
    return False


def validate_conflict_fields(
    obj: dict[str, Any], *, expected_source: str | None,
    forbidden_answer_terms: Iterable[str] = (), required_answer_terms: Iterable[str] = (),
    expected_rejected_terms: Iterable[str] = ("source a",),
) -> list[str]:
    """Validate source and direct answer fields without whole-response keyword leakage."""
    failures: list[str] = []
    selected = _text(obj.get("selected_source"))
    answer = _text(obj.get("answer"))
    rejected = _text(obj.get("rejected_sources"))
    if expected_source and expected_source.lower() not in selected:
        failures.append("wrong_selected_source")
    expected_rejections = tuple(term.lower() for term in expected_rejected_terms)
    if expected_source == "source b" and (
        not expected_rejections or not any(term in rejected for term in expected_rejections) or "source b" in rejected
    ):
        failures.append("stale_source_not_rejected_in_field")
    if any(term.lower() in answer for term in forbidden_answer_terms):
        failures.append("forbidden_value_in_answer")
    if any(term.lower() not in answer for term in required_answer_terms):
        failures.append("required_decision_missing_from_answer")
    return sorted(set(failures))
