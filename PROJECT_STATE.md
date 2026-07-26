# Project State — LLM A-B Tests

## Current state

- **Status:** Active; daily local-vs-cloud benchmark complete; no candidate promoted unattended.
- **Executable authority:** `/Users/busera/Developer/pa-model-benchmarks`; Obsidian is the human decision/report authority.
- **Hardening release state:** complete. Exact tree `22fe57499450b749271569fd1137b22e3659cc2e` passed independent review with no P0/P1/P2 findings and was bound as initial commit `7ad9413e41184ff90061efa32f975d3989ce8906`.
- **Last reviewed:** 2026-07-26.
- **Current focused verification:** exact reviewed tree passed `140` tests in both working-tree and clean-export runs, compilation, eight runner self-tests, and the targeted ad-hoc verifier before commit binding.
- **Next-session outcome:** MB-002 held-out daily task pack is `next-up`; its contract/labels must be frozen before implementation results are inspected, and local candidate execution follows only after T01–T03 pass.
- **Current decision architecture:** D/R/W/F/T/X lane separation with fail-closed required-lane gates; no universal winner score.
- **Programme boundary:** the D/R/W/F/T/X/tool-live PA Model Benchmark and the separate Coding Model Benchmark are governed independently; lessons may transfer, but results and promotion authority do not.
- **Daily cloud routing:** Kimi K2.6 provisional for reviewed low-risk interaction; Nemotron 3 Ultra consistency challenger.
- **Daily local routing:** Qwen3.6 27B MLX BF16 is quality-first and Qwen3.6 27B MLX latency-first for bounded reviewed private work. Both failed D07 in all three observations and are blocked from unattended files, messages, deletion, cron, and skills. See `2026-07-19 PA Daily-Use Local vs Cloud Ollama Benchmark Report.md`.

## Implemented foundations

- Shared field-scoped semantic checks reject wrong selected sources, stale-source acceptance, forbidden values in the decision field, malformed schemas, contradictions, and keyword stuffing patterns.
- All R/W/F/X/T runners support deterministic repeated-trial scheduling with repeat identity, model-major execution inside each trial, balanced/random/fixed order, pass rates, variance, and approximate 95% confidence intervals. Balanced mode rotates model order between trials.
- Shared Ollama request construction uses top-level `keep_alive: "30m"` to reduce eviction/reload artifacts while keeping model-family sampling controls under `options`.
- Native Ollama PA cells fail closed on returned-model mismatch, retain sanitized stop/token/request-control provenance, classify token/context caps as incomplete before scoring, and distinguish transport/provider/unsupported/runtime failures.
- Native Ollama completion must be affirmative; `done=false` or absent completion telemetry is incomplete. Hermes maximum-iteration warnings are incomplete, while other Hermes results remain diagnostic-only and promotion-ineligible because returned-model identity is unavailable.
- D/R/W/F/T/X run roots and manifests are immutable; reused IDs and stale output fail closed before model execution.
- Daily-Use writes the immutable manifest before any preflight model request, including preflight-only runs.
- Real-Life Pack broad promotion requires at least three complete repeats; one-repeat runs are diagnostic only.
- Tracked fixtures are synthetic and contain no named personal-profile contracts or copied exact private values; private fixtures are external opt-in inputs and never tracked.
- All runner starts produce schema-v1 manifests with source/task hashes (including the shared transport contract), Git/runtime/platform provenance, command controls, privacy class, and Ollama model IDs when available.
- Partial-run monitoring exposes frozen completed/planned denominators and per-model coverage; a winner is withheld until the schedule is complete.
- Synthetic tool-live suite exercises bounded Hermes file tools and session resume in a temporary localhost-only `HERMES_HOME`; cloud routes fail closed without `--allow-cloud`.
- T01–T12 fixtures/scorers are project-owned under `scripts/legacy_t_matrix/`; `/Users/busera/Temp/Hermes` is no longer an executable dependency.
- `benchmark_decision.py` provides explicit cross-lane post-processing after callers normalize runner summaries; it emits lane-specific eligibility only and is not automatically invoked by individual runners. A high score cannot override missing evidence or a failed required lane.

## Residual risks

1. Deterministic semantic checks still require qualitative review of representative outputs; they are stronger than token checks but not an LLM judge.
2. Approximate confidence intervals are weak with small trial counts and do not imply provider-side deterministic seeding.
3. Tool-live direct personal memory-provider access remains excluded by default; current safe evidence covers synthetic file retrieval and clean session continuity.
4. Runner artifact and Hermes CLI composition code remains duplicated. Hermes CLI cannot expose the underlying provider envelope; process exit and maximum-iteration warnings are retained, but route identity remains request-only and therefore promotion-ineligible.
5. Historical X01 text-only Hermes results remain invalid vision evidence.

## Next execution priorities

1. Execute MB-002 from `DO_NEXT_SESSION.md`: freeze and review its held-out task/label contract, then implement and verify without using candidate results to tune validators.
2. Run the synthetic tool-live suite against Qwen3.6 27B MLX BF16 in an isolated local sandbox.
3. Diagnose D07 with explicit skill injection, then test any remediation on unchanged held-out D07 variants.
4. Measure sustained memory pressure and energy cost before recommending frequent local use.
5. Keep private/cloud tool-live payloads opt-in and synthetic/redacted.
6. Keep semantic/content routing decommissioned. Use role/profile dispatch for model selection and introduce deterministic source-aware privacy controls only for concrete workflows that require them. See the retired evidence in [[2026-07-19 PA Semantic Model Router Benchmark and Implementation Plan]].

Lifecycle ownership and the full five-part contracts for these outcomes live in the Obsidian `PA Model Benchmark Backlog.md`; do not duplicate their status here or in the global PA Development board.

## Promotion rule

No model becomes the broad PA default from a composite score. It needs complete required-lane coverage, zero blocking high-risk failures, repeated-trial evidence, representative output review, valid tool/vision integration evidence for claimed capabilities, privacy-route acceptance, and Andrew's explicit routing decision.
