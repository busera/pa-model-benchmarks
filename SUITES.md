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
- `scripts/pa_held_out_benchmark.py` — H held-out anti-overfitting lane
- `scripts/mb006_preflight.py` — deterministic MB-006 roster/profile/denominator validation; zero model calls

Authority: PA routing and workload-fit evidence only. Broad category leadership requires complete D/R/W/F/T/H and category-matched synthetic tool-live evidence, at least three true repeats, zero blocking critical failures, exact route identity, representative output review, and an explicit routing decision. X remains specialist evidence.

The approved MB-006 overnight comparison has 76 logical cells per repeat. Direct D/R/W/F/T/H execution is exactly 77 provider calls per repeat. Tool-live runs four real PA invocations per repeat and measures the actual agent-loop turns, capped at 16 responses per repeat. At three repeats this is 228 cells, 231 exact direct calls and a 279-response scored cap per candidate; the two-model scored cap is 558 responses. One exact-route preflight call per candidate raises total exposure to 280 per candidate and 560 overall. `mb006_preflight.py` validates the exact roster, direct denominator, agent-loop cap and total exposure without calling a model.

The T runner requires explicit `--models <exact-tag,...>` and has no fixed execution roster. Tool-live uses three true repeats, a sandboxed real PA CLI, exact route registration evidence and a loopback proxy that records response identity, finish reason, token usage and latency. Setup/route/transport/telemetry failures are blocked and attributed separately; only a verified completed route can produce a model-output failure.

Local Ollama and Ollama Cloud are separate decision categories. The selector may name one eligible leader per category; it must never create a universal cross-category winner.

## Coding Model Benchmark Test Suite

Coding benchmark authority is a separate project. This PA repository does not own coding runners, hidden tests, generated-code artifacts, interpreted coding reports, or coding-route promotion.

## Shared infrastructure

Prompt guides and generic manifest/transport patterns may be independently retained where each programme needs them. Results, repair behavior, hidden tests, promotion gates, and routing authority may not be transferred between programmes.

A report or artifact must identify its programme explicitly. Neither programme's result supersedes the other's report.
