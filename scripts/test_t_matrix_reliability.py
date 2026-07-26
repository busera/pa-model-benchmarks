from __future__ import annotations


def test_t_synthetic_classification_never_invokes_real_loaders(monkeypatch):
    import run_t01_t12_full_matrix_profiled as runner

    def forbidden():
        raise AssertionError("real-source loader invoked")

    monkeypatch.setattr(runner.w2, "load_real_t1", forbidden)
    monkeypatch.setattr(runner.w2, "load_real_t4", forbidden)
    assert runner.prompt_for("t1_real") == runner.w2.FIXTURE_T1
    assert runner.prompt_for("t4_real") == runner.w2.FIXTURE_T4


def test_t_aggregate_fails_closed_when_requested_repeat_is_missing():
    from run_t01_t12_full_matrix_profiled import Cell, MODELS, TASKS, aggregate

    cell = Cell(
        run_id="test", canonical_id=TASKS[0]["id"], task=TASKS[0]["key"], part="single",
        model_tag=MODELS[0]["tag"], model_label=MODELS[0]["label"], status="ok",
        started_at="now", finished_at="now", elapsed_s=0.1, response_text="",
        validators={"trial_index": 1}, weighted_score=1.0, hard_fails=[], dims={},
    )
    summary = aggregate([cell], expected_repeats=2)
    row = summary["by_model"][MODELS[0]["tag"]]
    assert row["coverage_complete"] is False
    assert row["trial_statistics"]["eligible"] is False
    assert row["lane_eligible"] is False
