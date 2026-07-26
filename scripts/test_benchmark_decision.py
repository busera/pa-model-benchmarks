from __future__ import annotations


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
    assert report["lanes"]["F"]["score"] == 0.99


def test_missing_required_lane_fails_closed():
    from benchmark_decision import build_decision
    report = build_decision({"R": {"eligible": True, "score": 1.0}}, required_lanes=("R", "F"))
    assert report["broad_default_eligible"] is False
    assert report["lanes"]["F"]["status"] == "missing"
