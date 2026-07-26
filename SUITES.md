# Benchmark Programme Boundaries

## PA Model Benchmark Test Suite

Entrypoints:

- `scripts/pa_daily_use_benchmark.py` — D lane
- `scripts/pa_real_life_pack_benchmark.py` — R lane
- `scripts/pa_typical_workload_benchmark.py` — W/F workload lanes
- `scripts/pa_conflict_retrieval_benchmark.py` — conflict/retrieval lane
- `scripts/pa_extended_capability_benchmark.py` — X diagnostics
- `scripts/run_t01_t12_full_matrix_profiled.py` — T control matrix
- `scripts/pa_tool_live_benchmark.py` — synthetic tool-live evidence

Authority: PA routing and workload-fit evidence only. Promotion requires lane-specific gates and complete eligible trials.

## Coding Model Benchmark Test Suite

Entrypoints:

- `scripts/local_coding_breakpoint_benchmark.py`
- `scripts/iphone_ai_coach_coding_benchmark_profiled.py`

Supporting goal/scorer sources:

- `scripts/local_coding_promotion_goals.py`
- `scripts/pa_derived_coding_goals.py`

Authority: coding complexity, generated-code, sandbox, hidden-test, and coding routing evidence only.

## Shared infrastructure

Scheduling, prompt profiles, manifests, transport classification, and decision post-processing may be shared. Results, repair behavior, hidden tests, promotion gates, and routing authority may not be transferred between programmes.

A report or artifact must identify its programme explicitly. Neither programme's result supersedes the other's report.
