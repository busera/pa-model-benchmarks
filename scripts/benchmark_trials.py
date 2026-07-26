"""Deterministic repeated-trial scheduling and lane statistics."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Iterable


@dataclass(frozen=True)
class Trial:
    model: str
    task_id: str
    trial_index: int
    order_index: int


def make_schedule(models: list[str], tasks: list[str], *, repeats: int, seed: int, order: str = "balanced") -> list[Trial]:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    if order not in {"balanced", "random", "fixed"}:
        raise ValueError("order must be balanced, random, or fixed")
    rng = random.Random(seed)
    result: list[Trial] = []
    index = 0
    for trial in range(1, repeats + 1):
        model_order = list(models)
        if order == "balanced" and model_order:
            shift = (trial - 1) % len(model_order)
            model_order = model_order[shift:] + model_order[:shift]
        elif order == "random":
            rng.shuffle(model_order)
        task_order = list(tasks)
        if order == "random":
            rng.shuffle(task_order)
        for model in model_order:
            for task_id in task_order:
                result.append(Trial(model, task_id, trial, index))
                index += 1
    return result


def progress_snapshot(schedule: Iterable[Trial], completed: Iterable[tuple[str, bool]]) -> dict[str, object]:
    """Return denominator-safe progress without implying a partial winner."""
    planned_trials = list(schedule)
    observations = list(completed)
    per_model: dict[str, dict[str, int]] = {}
    for trial in planned_trials:
        row = per_model.setdefault(trial.model, {"passes": 0, "completed": 0, "planned": 0})
        row["planned"] += 1
    for model, passed in observations:
        if model not in per_model:
            raise ValueError(f"completed observation for unscheduled model: {model}")
        row = per_model[model]
        row["completed"] += 1
        row["passes"] += int(bool(passed))
        if row["completed"] > row["planned"]:
            raise ValueError(f"too many completed observations for model: {model}")
    planned = len(planned_trials)
    completed_count = len(observations)
    return {
        "completed": completed_count,
        "planned": planned,
        "winner_withheld": completed_count < planned,
        "per_model": per_model,
    }


def complete_trial_coverage(observed: Iterable[tuple[str, int]], *, task_ids: Iterable[str], repeats: int) -> bool:
    if repeats < 1:
        return False
    expected = {(task_id, trial) for task_id in task_ids for trial in range(1, repeats + 1)}
    actual = list(observed)
    return len(actual) == len(set(actual)) and set(actual) == expected


def summarize_trials(scores: Iterable[float], *, passed: Iterable[bool], expected_trials: int) -> dict[str, object]:
    values = list(scores)
    passes = list(passed)
    if len(values) != len(passes):
        raise ValueError("scores and passed lengths differ")
    mean = fmean(values) if values else 0.0
    rate = sum(passes) / len(passes) if passes else 0.0
    stddev = pstdev(values) if len(values) > 1 else 0.0
    margin = 1.96 * stddev / math.sqrt(len(values)) if len(values) > 1 else 0.0
    interval = [round(max(0.0, mean - margin), 4), round(min(1.0, mean + margin), 4)] if len(values) > 1 else None
    return {
        "trials": len(values),
        "expected_trials": expected_trials,
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "confidence_interval_95": interval,
        "pass_rate": round(rate, 4),
        "eligible": len(values) == expected_trials and all(passes) and not math.isnan(mean),
    }
