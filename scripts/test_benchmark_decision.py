from __future__ import annotations

import pytest


def test_lane_decision_does_not_emit_universal_rank():
    from benchmark_decision import build_decision

    report = build_decision({
        "R": {"eligible": True, "score": 0.91},
        "F": {"eligible": False, "score": 0.99, "blocking_failures": ["F06"]},
        "W": {"eligible": True, "score": 0.94},
    }, required_lanes=("R", "F"))
    assert "overall_score" not in report
    assert "ranking" not in report
    assert report["broad_default_eligible"] is False
    assert report["blocking_lanes"] == ["F"]


def test_missing_required_lane_fails_closed():
    from benchmark_decision import build_decision

    report = build_decision({"R": {"eligible": True, "score": 1.0}}, required_lanes=("R", "F"))
    assert report["broad_default_eligible"] is False
    assert report["lanes"]["F"]["status"] == "missing"


def candidate(model: str, category: str, *, score: float = 0.9, **overrides):
    lanes = {
        lane: {"eligible": True, "score": score}
        for lane in ("D", "R", "W", "F", "T", "H", "tool_live")
    }
    row = {
        "model": model,
        "category": category,
        "route_verified": True,
        "complete": True,
        "repeats": 3,
        "critical_failures": 0,
        "strict_format_rate": 1.0,
        "response_tokens": 1000,
        "elapsed_s": 100.0,
        "lanes": lanes,
    }
    row.update(overrides)
    return row


def test_selects_separate_local_and_cloud_leaders_without_universal_winner():
    from benchmark_decision import build_category_model_selection

    report = build_category_model_selection([
        candidate("cloud-a:cloud", "ollama_cloud", score=0.95),
        candidate("cloud-b:cloud", "ollama_cloud", score=0.90),
        candidate("local-a", "local", score=0.93),
        candidate("local-b", "local", score=0.88),
    ])

    assert report["categories"]["ollama_cloud"]["eligible_leader"] == "cloud-a:cloud"
    assert report["categories"]["local"]["eligible_leader"] == "local-a"
    assert report["universal_winner"] is None
    assert report["explicit_routing_decision_required"] is True


def test_missing_lane_and_insufficient_repeats_block_leader_but_preserve_diagnostic():
    from benchmark_decision import build_category_model_selection

    weak = candidate("observed:cloud", "ollama_cloud", repeats=1)
    del weak["lanes"]["tool_live"]
    report = build_category_model_selection([weak])
    cloud = report["categories"]["ollama_cloud"]

    assert cloud["eligible_leader"] is None
    assert cloud["best_observed"] == "observed:cloud"
    assert set(cloud["candidates"][0]["blocking_reasons"]) == {
        "insufficient_true_repeats", "missing_lane:tool_live"
    }


def test_blocking_critical_failure_cannot_be_averaged_away():
    from benchmark_decision import build_category_model_selection

    high = candidate("unsafe-local", "local", score=1.0, critical_failures=1)
    safe = candidate("safe-local", "local", score=0.90)
    report = build_category_model_selection([high, safe])

    assert report["categories"]["local"]["eligible_leader"] == "safe-local"
    assert high["model"] not in report["categories"]["local"]["eligible_candidates"]


def test_quality_precedes_token_and_latency_efficiency():
    from benchmark_decision import build_category_model_selection

    quality = candidate("quality:cloud", "ollama_cloud", score=0.96, response_tokens=5000, elapsed_s=500)
    cheap = candidate("cheap:cloud", "ollama_cloud", score=0.90, response_tokens=100, elapsed_s=1)
    report = build_category_model_selection([cheap, quality])

    assert report["categories"]["ollama_cloud"]["eligible_leader"] == "quality:cloud"


def test_efficiency_breaks_only_equal_quality_ties_and_missing_telemetry_does_not_win_tie():
    from benchmark_decision import build_category_model_selection

    unknown = candidate("unknown-local", "local", response_tokens=None, elapsed_s=None)
    efficient = candidate("efficient-local", "local", response_tokens=800, elapsed_s=80)
    expensive = candidate("expensive-local", "local", response_tokens=1200, elapsed_s=120)
    report = build_category_model_selection([unknown, expensive, efficient])

    assert report["categories"]["local"]["eligible_leader"] == "efficient-local"


def test_invalid_or_duplicate_candidate_fails_closed():
    from benchmark_decision import build_category_model_selection

    with pytest.raises(ValueError, match="non-empty model"):
        build_category_model_selection([candidate("", "local")])
    duplicate = candidate("same", "local")
    with pytest.raises(ValueError, match="duplicate candidate"):
        build_category_model_selection([duplicate, duplicate])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.update(route_verified="false"), "boolean route_verified"),
        (lambda row: row.update(complete=1), "boolean complete"),
        (lambda row: row.update(repeats="3"), "integer repeats"),
        (lambda row: row.update(critical_failures=False), "integer critical_failures"),
        (lambda row: row.update(strict_format_rate=float("nan")), "strict_format_rate"),
        (lambda row: row["lanes"]["F"].update(eligible="false"), "boolean eligible"),
        (lambda row: row["lanes"]["F"].pop("score"), "finite score"),
        (lambda row: row.update(response_tokens=-1), "response_tokens"),
        (lambda row: row.update(elapsed_s=float("inf")), "elapsed_s"),
    ],
)
def test_malformed_candidate_fields_cannot_become_leaders(mutation, message):
    from benchmark_decision import build_category_model_selection

    row = candidate("malformed-local", "local")
    mutation(row)
    with pytest.raises(ValueError, match=message):
        build_category_model_selection([row])
