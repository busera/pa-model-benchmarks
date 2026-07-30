# Project State — LLM A-B Tests

## Current state

- **Status:** Active; MB-002 v2.1 held-out execution is complete, and the Coding Model Benchmark now uses a format-neutral workspace producer. The former strict-JSON breakpoint producer is archived and non-authoritative.
- **Executable authority:** `/Users/busera/Developer/pa-model-benchmarks`; Obsidian is the human decision/report authority.
- **Hardening release state:** complete. Exact tree `22fe57499450b749271569fd1137b22e3659cc2e` passed independent review with no P0/P1/P2 findings and was bound as initial commit `7ad9413e41184ff90061efa32f975d3989ce8906`.
- **Last reviewed:** 2026-07-30.
- **Current focused verification:** `227` working-tree tests pass after review and live-run remediation: symlink-safe prompt reads; read-only hidden-test inputs; complete harness/generated-file integrity binding; fail-closed correction aborts; exact-slot resume provenance; provider completion/model-identity validation; byte-preserving raw Codex source after identified framing; positive pytest collection/JUnit census; explicit skip/import/assertion taxonomies; and an unguessable write-only completion nonce bound to pytest's returned code. The first full diagnostic run `20260730-gemma4-full-format-neutral-c0-c5` exposed a retry-order defect and noisy failed-test census attribution; both are retained as pre-final diagnostic evidence and covered by RED/GREEN regressions. Pre-final corrected calibration `20260730-gemma4-full-format-neutral-c0-c5-corrected` completed `6/6` cells: Gemma passed C0–C3 and failed C4–C5, yielding an observed diagnostic ceiling C3 and breakpoint C4. It did not execute the final staged runner and is not promotion authority. `kimi-k3:cloud` attempt `20260730-kimi-k3-cloud-full-format-neutral-c0-c5` completed zero model calls due Ollama Cloud HTTP 402 and is not model evidence. Full held-out run `20260726-held-out-full` remains complete at `252/252` cells (`14` models × `6` tasks × `3` repeats).
- **Next-session outcome:** MB-003 (synthetic local tool-live execution) remains the next governed outcome; MB-004 (D07 held-out diagnosis) follows. MB-002 v2.1 artifacts and evidence are under `docs/held-out/` and `artifacts/20260726-held-out-full/`.
- **Current decision architecture:** D/R/W/F/T/X lane separation with fail-closed required-lane gates; no universal winner score.
- **Programme boundary:** the D/R/W/F/T/X/tool-live PA Model Benchmark and the separate Coding Model Benchmark are governed independently; lessons may transfer, but results and promotion authority do not.
- **Coding execution contract:** `coding_workspace_benchmark.py` uses workspace mode `W`: one host-selected file per call, ordinary raw/fenced Python, immediate compilation of that generated file, sandboxed workspace hidden tests, and up to three total workspace passes (initial plus at most two test-feedback corrections). Ollama evidence requires affirmative completion and matching model identity; incomplete responses fail before source extraction. Hermes/Codex cells are diagnostic/unverified because returned-model identity is unavailable. Completion evidence distinguishes assertion failure, skip/empty census, generated-code collection error, and premature process exit. `scripts/_Archive/legacy_coding_breakpoint/` preserves the retired JSON-envelope runner/tests; historical scores are not comparable.
- **Approved quota-continuity routing (2026-07-26):** keep `openai-codex/gpt-5.6-sol` as primary. On primary-route failure, use `ollama-cloud/deepseek-v4-pro:cloud` (L1), then `ollama-cloud/nemotron-3-ultra:cloud` (L1b), then local `qwen3.6:27b-mlx-bf16` through the named `custom:local-ollama` endpoint (L2). This is an operational continuity decision, not unattended broad-model promotion.
- **Daily cloud conclusion:** DeepSeek V4 Pro led the held-out run (`0.9882`, `100%` JSON exact, one critical vendor-routing miss). Nemotron 3 Ultra is the safer consistency challenger (`0.9803`, zero critical failures; systematic H02 deadline-risk omission). Kimi K2.6 is demoted from the provisional broad fallback (`0.7462`, five critical failures, `77.8%` JSON exact).
- **Daily local conclusion:** Qwen3.6 27B MLX BF16 remains the quality-first general local fallback (`0.9672`, one critical miss, `100%` JSON exact). Gemma4 31B MLX remains the bounded coding/reviewer specialist rather than the broad local fallback (`0.9449`, three critical misses). Qwen3.6 27B MLX remains latency-first for reviewed private interaction. No local model is approved for unattended files, messages, deletion, cron, or high-impact skills.

## Implemented foundations

- Held-out daily task pack (`pa_held_out_benchmark.py`): six materially distinct tasks (H01–H06) covering batch de-duplication, time estimation, scope creep, rule conflict resolution, error acknowledgment, and delegation routing. Separate `held_out_gate` (≥0.85 weighted, zero critical failures, ≥90% JSON exact); results cannot alter D01–D14 promotion gates. Validators were defined from task specifications alone, not from candidate outputs.
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

1. Execute MB-003 (synthetic local tool-live execution) or MB-004 (D07 held-out diagnosis) from the Obsidian backlog.
2. Run the synthetic tool-live suite against Qwen3.6 27B MLX BF16 in an isolated local sandbox.
3. Diagnose D07 with explicit skill injection, then test any remediation on unchanged held-out D07 variants.
4. Measure sustained memory pressure and energy cost before recommending frequent local use.
5. Keep private/cloud tool-live payloads opt-in and synthetic/redacted.
6. Keep semantic/content routing decommissioned. Use role/profile dispatch for model selection and introduce deterministic source-aware privacy controls only for concrete workflows that require them. See the retired evidence in [[2026-07-19 PA Semantic Model Router Benchmark and Implementation Plan]].

Lifecycle ownership and the full five-part contracts for these outcomes live in the Obsidian `PA Model Benchmark Backlog.md`; do not duplicate their status here or in the global PA Development board.

## Promotion rule

No model becomes the broad PA default from a composite score. It needs complete required-lane coverage, zero blocking high-risk failures, repeated-trial evidence, representative output review, valid tool/vision integration evidence for claimed capabilities, privacy-route acceptance, and Andrew's explicit routing decision.
