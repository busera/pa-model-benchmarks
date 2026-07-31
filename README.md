# LLM A-B Tests

Benchmark suite for selecting local Ollama, Ollama Cloud, and primary cloud models for Andrew's Hermes PA workloads.

Executable authority: `/Users/busera/Developer/pa-model-benchmarks`. Human routing decisions, interpreted reports, and the benchmark index remain in the Obsidian folder documented by `OBSIDIAN_AUTHORITY.md`.

Product backlog authority: `4_Projects/PA Development/LLM A-B Tests/PA Model Benchmark Backlog.md` in the Obsidian vault. `PROJECT_STATE.md` records implementation evidence and immediate execution order; it is not a second lifecycle backlog.

## Programme boundary

- **PA Model Benchmark Test Suite:** the D/R/W/F/T/X and tool-live lanes documented here. It evaluates broad Hermes PA behaviour, safety, retrieval, daily work, artifacts, and tool integration.
- **Coding Model Benchmark Test Suite:** moved to `/Users/busera/Developer/Benchmark Coding`. That project owns coding runners, prompts, tests, artifacts, reports, and coding-route evidence.

Lessons may transfer between harnesses, but results, promotion gates, reports, and evidence authority do not. A coding-model score cannot promote a PA default, and PA-suite hardening must not rewrite coding-suite authority.

## Decision model

The suite is lane-based; no single score should be treated as a universal model ranking.

| Suite | Role | Broad promotion? |
|---|---|---|
| D01-D14 Daily-Use Pack | Non-coding, non-project daily PA fit | Required for daily cloud routing |
| R01-R10 Real-Life Pack | High-risk PA behavior | Yes, as one required gate |
| W01-W21 Typical Workload | Daily workload fit | No |
| F01-F10 Conflict Retrieval | Stale/current source resolution and arithmetic | Required safety gate |
| T01-T12 Control Matrix | Contracts, skills, architecture, coding | Safety/specialist evidence |
| X01-X18 Extended Capability | Artifacts, vision, reports, skill workflows | Specialist evidence only |
| H01-H06 Held-Out Daily Pack | Overfitting detection for D01-D14 | Diagnostic; separate from calibration |

See the Obsidian `2026-07-01 PA Model Benchmark Redesign.md` report for the target composite and promotion policy.

## Current daily-routing reports

- `2026-07-19 PA Daily-Use Local vs Cloud Ollama Benchmark Report.md` — canonical same-surface local-vs-cloud comparison.
- `2026-07-19 PA Daily-Use Cloud Model Benchmark Report.md` — cloud screen and stability evidence.

Current bounded quota-continuity chain: `openai-codex/gpt-5.6-sol` → `ollama-cloud/deepseek-v4-pro:cloud` → `ollama-cloud/nemotron-3-ultra:cloud` → local `qwen3.6:27b-mlx-bf16`. Qwen3.6 27B MLX remains the reviewed latency-first local route. No model is approved as an unattended broad daily default.

## Quick verification

```bash
PY=${PYTHON:-python3}
$PY -m pytest -q
$PY scripts/pa_daily_use_benchmark.py --self-test
$PY scripts/pa_real_life_pack_benchmark.py --self-test
$PY scripts/pa_typical_workload_benchmark.py --self-test
$PY scripts/pa_conflict_retrieval_benchmark.py --self-test
$PY scripts/pa_extended_capability_benchmark.py --self-test
$PY scripts/run_t01_t12_full_matrix_profiled.py --self-test
$PY scripts/pa_tool_live_benchmark.py --self-test
$PY scripts/pa_held_out_benchmark.py --self-test
```

Example targeted synthetic run:

```bash
$PY scripts/pa_conflict_retrieval_benchmark.py \
  --models gemma4:31b-cloud,qwen3.6:27b-mlx-bf16 \
  --tasks F01,F03
```

Artifacts are written under `artifacts/<run-id>/`. Benchmark execution can consume cloud quota; self-tests do not call models. Tracked fixtures are synthetic and redact known personal/employer/account markers. Optional private fixtures may be loaded only from an explicit external `PA_BENCHMARK_PRIVATE_FIXTURE_ROOT`; they are never copied into or tracked by this repository.

Repeated runs use `--repeats N --seed N --run-order balanced|random|fixed`. Each cell is stored under `trial-NNN/`; summaries report trial count, mean, population standard deviation, pass rate, and fail-closed eligibility. Provider-side seed support is not assumed: the seed governs execution ordering and is recorded in the manifest.

Every D/R/W/F/T/X run claims a fresh, empty run root and writes schema-v1 `manifest.json` before model execution. Existing manifests or stale run-root content fail closed; overwrite/resume is unsupported until an explicit protocol exists. The manifest records a sanitized command identifier, source/selected-task/prompt-profile hashes, Git/Python/Hermes/Ollama/platform metadata, privacy class, repeat/order controls, and explicit requested model/provider routes. Raw arguments are not retained. Ollama IDs are resolved from `ollama list` where available; unresolved digests remain explicit-route requests rather than being assigned an invented identity.

## PA-suite fairness and evidence rules

1. Every candidate must resolve to a non-generic profile in `scripts/model_prompt_profiles.py` and a repository-owned guide snapshot under `prompts/guides/`. Runners fail closed for unmapped candidates or missing guides; manifests hash the selected guide bytes.
2. Prompt profiles may adapt system wording and runtime options, but may not weaken validators or insert task answers.
3. Record the exact model tag, provider route, prompt profile/guide, API mode, thinking control, runtime options, validator results, response, and elapsed time.
4. A runtime error is a failed cell, not missing evidence. Partial/targeted runs must not be presented as full-suite promotion evidence.
5. Synthetic prompt-contained retrieval tests do not prove real Hermes tool use. Tool-live memory/session/file retrieval remains a separate required integration gate.
6. X01 vision is valid only when the route receives the generated image. The Hermes CLI text-only path now fails closed rather than scoring prompt leakage.
7. Cross-lane decision post-processing is explicit, not automatic: callers normalize completed lane summaries and pass them to `benchmark_decision.build_decision`. The helper never emits a universal score/rank; missing or failed required lanes block broad-default eligibility. Individual runners still emit within-lane diagnostic rankings and must not be read as a cross-lane decision.
8. Shared repeated-trial scheduling is **model-major within each trial** to avoid repeated local-model eviction/reload; balanced mode rotates the first model between trials. Ollama requests set top-level `keep_alive: "30m"` (not an `options` key).
9. Native PA cells distinguish transport, provider process/contract/identity, unsupported route, strict-format, validator, and incomplete outcomes. Read retained stderr/raw responses before attributing a failure to model quality.
10. PA JSON recovery may support diagnostics, but recovery warnings remain hard failures and never count as strict contract compliance. The PA suite has no repair pass; any future PA agent-repair lane must report first-pass and repaired success separately.
11. Early-stop saves spend only. Skipped cells remain incomplete/ineligible and never become model failures or full-suite evidence.
12. PA output budgets remain task-specific. Native Ollama cells retain requested caps, token counts, and stop reason; token caps, `done=false`, and missing completion telemetry become incomplete evidence before validation. Coding-artifact budgets are governed by `/Users/busera/Developer/Benchmark Coding`.
13. Hermes CLI output is parsed before validation. Maximum-iteration warnings become incomplete cells. The CLI does not expose returned-model identity, so otherwise complete Hermes cells retain diagnostic scores but carry `route_identity_unverified`, use `status=unverified`, and cannot pass promotion gates.
14. The Real-Life Pack requires at least three repeats before `promotion_gate=pass`; one-repeat runs remain diagnostic even with complete, perfect-scoring coverage.

## Tool-live integration gate

`pa_tool_live_benchmark.py` uses synthetic nonces, a fresh execution root created directly under canonical `/private/tmp`, a temporary isolated `HERMES_HOME`, a minimal credential-free subprocess environment, and a macOS default-deny `sandbox-exec` policy. Caller-selected, existing, symlinked, and non-`/private/tmp` execution roots are rejected. The policy exposes only system runtime resources, a hard-linked copy of the Python/Hermes runtime and dependencies inside the trusted root, the synthetic fixture, and the isolated state/artifact root; the original Hermes installation and personal home files remain unreadable, fixture/artifact executables cannot run directly, and outbound networking is restricted to localhost. The route is an explicit localhost-only custom provider with bounded tools and turns. Default and self-test modes make zero model calls. `--execute` runs real synthetic file reads and an isolated session-resume check; cloud-tagged models require explicit `--allow-cloud`. Results are specialist integration evidence and never broad-promotion evidence by themselves.

```bash
$PY scripts/pa_tool_live_benchmark.py                 # fixture-only, no model call
$PY scripts/pa_tool_live_benchmark.py --execute --model qwen3.6:27b-mlx
```

## Known limitations

- Runner artifact and aggregation code remains duplicated; consolidate only after behavior is pinned with tests.
- Hermes CLI offers process-exit and warning evidence but no returned-model or native token/stop envelope. Its cells remain diagnostic-only until identity telemetry is available.
- Semantic checks are deterministic and field-scoped but not a substitute for representative human output review.
- Confidence intervals use an approximate 95% normal interval and are omitted for a single trial; interpret very small samples cautiously.
- Tool-live memory coverage currently uses a clean Hermes session/resume contract; direct personal memory-provider testing remains out of scope by default.

## Documentation

- `DO_NEXT_SESSION.md` — executable continuation front door and sole next-session objective.
- `PROJECT_STATE.md` — current status, risks, and next actions.
- `CHANGELOG.md` — suite changes.
- Dated design and result notes — historical evidence; do not silently rewrite old results.
