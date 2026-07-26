from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_field_semantics_rejects_keyword_stuffing():
    from benchmark_semantics import validate_conflict_fields
    obj = {
        "answer": "Use Source A cash 5036.80; Source B is merely mentioned.",
        "selected_source": "Source A",
        "rejected_sources": ["Source B"],
        "calculation_check": "2.86 coverage",
        "guardrail": "reject stale data and refresh",
    }
    failures = validate_conflict_fields(obj, expected_source="source b", forbidden_answer_terms=("5036.80",))
    assert "wrong_selected_source" in failures
    assert "forbidden_value_in_answer" in failures
    unrelated = validate_conflict_fields(
        {"answer": "Use current data", "selected_source": "Source B", "rejected_sources": ["Source C"]},
        expected_source="source b",
    )
    assert "stale_source_not_rejected_in_field" in unrelated


def test_normalized_number_parses_currency_formats():
    from benchmark_semantics import contains_number
    assert contains_number("Cash is EUR 42,000.00", 42000.00)
    assert contains_number("coverage 2.8x", 2.8)
    assert not contains_number("cash 4200.00", 42000.00)


def test_deterministic_trial_schedule_is_model_major_balanced_and_repeatable():
    from benchmark_trials import make_schedule

    a = make_schedule(["m1", "m2", "m3"], ["T1", "T2"], repeats=3, seed=7, order="balanced")
    b = make_schedule(["m1", "m2", "m3"], ["T1", "T2"], repeats=3, seed=7, order="balanced")

    assert a == b
    assert len(a) == 18
    assert {x.trial_index for x in a} == {1, 2, 3}
    assert [(x.model, x.task_id) for x in a[:6]] == [
        ("m1", "T1"),
        ("m1", "T2"),
        ("m2", "T1"),
        ("m2", "T2"),
        ("m3", "T1"),
        ("m3", "T2"),
    ]
    assert [x.model for x in a[0:6:2]] == ["m1", "m2", "m3"]
    assert [x.model for x in a[6:12:2]] == ["m2", "m3", "m1"]
    assert [x.model for x in a[12:18:2]] == ["m3", "m1", "m2"]


def test_ollama_request_payload_keeps_model_resident_without_polluting_options():
    from model_prompt_profiles import request_payload

    payload = request_payload("qwen3.6:27b-mlx", "Return JSON", num_predict=321)

    assert payload["keep_alive"] == "30m"
    assert "keep_alive" not in payload["options"]
    assert payload["options"]["num_predict"] == 321


def test_progress_snapshot_uses_frozen_denominator_and_withholds_winner():
    from benchmark_trials import make_schedule, progress_snapshot

    schedule = make_schedule(["m1", "m2"], ["T1", "T2"], repeats=1, seed=1, order="fixed")
    partial = progress_snapshot(schedule, [("m1", True), ("m1", False)])
    assert partial == {
        "completed": 2,
        "planned": 4,
        "winner_withheld": True,
        "per_model": {
            "m1": {"passes": 1, "completed": 2, "planned": 2},
            "m2": {"passes": 0, "completed": 0, "planned": 2},
        },
    }
    complete = progress_snapshot(schedule, [("m1", True), ("m1", False), ("m2", True), ("m2", True)])
    assert complete["winner_withheld"] is False
    assert complete["completed"] == complete["planned"] == 4


def test_requested_repeat_coverage_fails_when_final_repeat_missing():
    from benchmark_trials import complete_trial_coverage
    observed = [("R01", 1), ("R02", 1)]
    assert complete_trial_coverage(observed, task_ids=["R01", "R02"], repeats=2) is False
    assert complete_trial_coverage(observed, task_ids=["R01", "R02"], repeats=1) is True


def test_distribution_and_lane_eligibility_fail_closed():
    from benchmark_trials import summarize_trials
    stats = summarize_trials([1.0, 0.5, 1.0], passed=[True, False, True], expected_trials=3)
    assert stats["trials"] == 3
    assert stats["mean"] == 0.8333
    assert stats["pass_rate"] == 0.6667
    assert stats["confidence_interval_95"][0] < stats["mean"] < stats["confidence_interval_95"][1]
    assert stats["eligible"] is False


def test_manifest_parses_ollama_digests():
    from benchmark_manifest import parse_ollama_list
    rows = parse_ollama_list("NAME ID SIZE MODIFIED\nqwen3.5:cloud a7bf6f7891c3 - 3 days ago\n")
    assert rows == {"qwen3.5:cloud": "a7bf6f7891c3"}


def test_manifest_is_reproducible_and_secret_free(tmp_path: Path):
    from benchmark_manifest import build_manifest, write_manifest
    source = tmp_path / "task.py"
    source.write_text("print('safe')\n")
    manifest = build_manifest(
        run_id="r1", models=["model:tag"], task_payload={"id": "T1"}, source_paths=[source],
        repeats=2, seed=4, run_order="balanced", privacy_class="synthetic",
        argv=["runner.py", "--models", "model:tag", "--api-key", "super-secret-value"], probe_commands=False,
        prompt_profiles={"model:tag": {"profile": "test", "effective_system_prompt": "safe prompt"}},
        model_routes={"model:tag": "ollama"},
    )
    path = write_manifest(tmp_path, manifest)
    loaded = json.loads(path.read_text())
    serialized = json.dumps(loaded).lower()
    assert loaded["schema_version"] == 1
    assert loaded["source_hashes"][source.name]
    assert loaded["task_hash"]
    assert loaded["prompt_profile_hashes"]["model:tag"]
    assert loaded["model_identity"]["model:tag"]["provider_route"] == "ollama"
    assert "super-secret-value" not in serialized
    assert str(tmp_path).lower() not in serialized
    assert loaded["repeats"] == 2


def test_manifest_and_run_root_are_immutable(tmp_path: Path):
    from benchmark_manifest import claim_run_root, write_manifest

    root = tmp_path / "fresh"
    claim_run_root(root)
    write_manifest(root, {"run_id": "one"})
    with pytest.raises(FileExistsError, match="manifest already exists"):
        write_manifest(root, {"run_id": "two"})

    stale = tmp_path / "stale"
    stale.mkdir()
    (stale / "results.jsonl").write_text("old\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="run root is not empty"):
        claim_run_root(stale)


def test_manifest_fails_closed_on_missing_source(tmp_path: Path):
    import pytest
    from benchmark_manifest import build_manifest

    with pytest.raises(FileNotFoundError):
        build_manifest(
            run_id="missing", models=["model"], task_payload=[], source_paths=[tmp_path / "absent.py"],
            repeats=1, seed=1, run_order="fixed", privacy_class="synthetic", argv=["runner.py"],
            prompt_profiles={"model": {}}, model_routes={"model": "ollama"}, probe_commands=False,
        )


def test_manifest_hashes_repo_owned_prompt_guide(tmp_path: Path):
    from benchmark_manifest import build_manifest
    manifest = build_manifest(
        run_id="guide", models=["qwen3.6:27b-mlx-bf16"], task_payload=[],
        source_paths=[Path(__file__)], repeats=1, seed=1, run_order="fixed",
        privacy_class="synthetic", argv=["runner.py"],
        model_routes={"qwen3.6:27b-mlx-bf16": "ollama"}, probe_commands=False,
    )
    guide_sources = [key for key in manifest["source_hashes"] if key.endswith("Qwen 3.6 Prompt Engineering Guide.md")]
    assert len(guide_sources) == 1
    assert manifest["source_hashes"][guide_sources[0]]
