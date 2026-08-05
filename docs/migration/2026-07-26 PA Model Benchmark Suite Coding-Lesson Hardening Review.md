---
title: "PA Model Benchmark Suite Transferable Coding-Lesson Hardening Review"
date: 2026-07-26
type: benchmark-audit
status: implemented-unreleased
area: "PA Development / LLM A-B Tests"
tags:
  - pa-development
  - pa-model-benchmark
  - benchmark-governance
---
# PA Model Benchmark Suite Transferable Coding-Lesson Hardening Review
[[2026-07-26]]

## Scope correction

This review concerns the **PA Model Benchmark Test Suite**: D daily use, R real-life, W typical workload, F conflict retrieval, T control matrix, X extended capability, and tool-live integration.

The **Coding Model Benchmark Test Suite** is a separate programme centered on `scripts/local_coding_breakpoint_benchmark.py`. Its generated-code sandbox, repair passes, hidden tests, coding goal catalog, reports, and routing authority are outside this change. Coding-benchmark lessons transfer only where they improve the PA harness; coding results do not become PA promotion evidence.

An initial independent review incorrectly audited the Coding Model Benchmark producer. Its findings were not applied to the PA suite. The incidental edit to the July 20 coding report was restored byte-for-byte from the pre-task backup.

## Sources checked

- Miyo search for the July 25 coding-benchmark lessons and PA benchmark guidance.
- Retained July 25 benchmark session/results, used only to identify transferable harness lessons.
- `2026-07-01 PA Model Benchmark Redesign.md`.
- `2026-07-11 LLM Benchmark Suite Review.md`.
- PA D/R/W/F/T/X/tool-live runners, shared manifest/trial/profile modules, and regression tests.
- Local-model-evaluation benchmark hardening and audit references.

## Transferable lessons applied to the PA suite

1. **Model residency and fair order:** shared schedules run model-major inside each trial. Balanced repeats rotate the first model, preserving counterbalancing without repeatedly evicting local models between every task.
2. **Correct Ollama control placement:** native requests use top-level `keep_alive: "30m"`, never `options.keep_alive`.
3. **Stop-state evidence:** PA native-Ollama cells retain sanitized returned-model identity, `done`, `done_reason`, prompt tokens, response tokens, and prompt-free request controls.
4. **Truncation is incomplete evidence:** token/context-limit responses are classified `output_truncated` with `status=incomplete` before semantic/contract scoring. They cannot be misread as model-quality or formatting failures.
5. **Failure attribution:** transport timeout, HTTP transport, unavailable transport, provider-process failure, provider-contract failure, returned-model mismatch, unsupported route, generic runtime failure, and incomplete output are distinct classes.
6. **Returned-route integrity:** native Ollama results fail closed if the provider-returned model identity does not narrowly match the requested tag. The accepted cloud normalization only removes the explicit `:cloud` or `-cloud` suffix.
7. **Denominator-safe monitoring:** every partial PA run now emits completed/planned counts plus per-model passes/completed/planned. `winner_withheld` remains true until the frozen schedule is complete.
8. **Strict output remains primary:** existing PA JSON recovery warnings remain hard failures; no recovered response is promoted as strict compliance.
9. **Manifest completeness:** `benchmark_transport.py` is included in every schema-v1 source hash set.
10. **Positive completion required:** native Ollama cells require `done=true`; `done=false` and missing completion telemetry are incomplete before validation.
11. **Hermes evidence boundary:** maximum-iteration warnings fail closed. Complete Hermes CLI responses retain diagnostic scores but are `status=unverified` and promotion-ineligible because returned-model identity is request-only.
12. **Immutable run evidence:** D/R/W/F/T/X run roots must be fresh and empty; existing manifests or stale output reject the run before cells can append.
13. **Preflight provenance:** Daily-Use writes its immutable manifest before any provider preflight, including preflight-only execution.
14. **Minimum promotion evidence:** Real-Life Pack promotion requires at least three complete repeats; one-repeat runs remain diagnostic.
15. **Fixture privacy:** tracked fixtures declare synthetic provenance and remove named personal-profile contracts and copied exact private values. A structural regression scan embeds no private marker values itself; optional private fixtures remain external and opt-in.

## Deliberately not transferred

- Coding repair/self-correction passes. The PA suite currently scores the requested PA response, not a coding-agent repair loop. If PA agent repair is later evaluated, it must be a separate lane with first-pass and repaired success reported separately.
- Generated-code sandbox and hidden-test classification. Those belong to the Coding Model Benchmark programme. PA tool-live isolation remains governed independently by its existing sandbox.
- Coding output budgets or goal catalogs. PA task budgets remain task-specific; native stop metadata now proves whether they were sufficient.

## Implemented files

- `scripts/benchmark_trials.py`: model-major scheduling and denominator-safe progress snapshots.
- `scripts/model_prompt_profiles.py`: shared top-level Ollama `keep_alive`.
- `scripts/benchmark_transport.py`: sanitized response provenance, identity validation, incomplete-output detection, and failure taxonomy.
- `scripts/benchmark_manifest.py`: transport helper source hashing plus fail-closed run-root and manifest immutability.
- PA native-response integration: `pa_daily_use_benchmark.py`, `pa_real_life_pack_benchmark.py`, `pa_typical_workload_benchmark.py`, `pa_conflict_retrieval_benchmark.py`, `pa_extended_capability_benchmark.py`, and `run_t01_t12_full_matrix_profiled.py`.
- Regression coverage: `test_benchmark_core.py`, `test_benchmark_transport.py`, and `test_pa_daily_use_benchmark.py`.

Backup: `/tmp/pa-model-benchmark-hardening-20260726_113535/`.

## Verification status

Verification evidence must be read as PA-suite harness verification, not a new model benchmark result. No model calls were made and no routing decision changed.

Executable authority has moved to `.`; the previous vault executable surface is archived without deletion. Verification establishes a working-tree result until the exact staged tree receives clean-export, ad-hoc, and independent-review evidence and is committed.

- RED observed for model-major scheduling, missing top-level keep-alive, missing transport module/provenance, and missing denominator-safe progress helper.
- Focused transport/daily/PA regression checks passed after implementation.
- Full scripts suite after independent-review remediation: `140 passed`.
- Changed-file Python compilation passed.
- D/R/W/F/X/T/tool-live self-tests passed with zero model calls.
- `git diff --check` passed.
- An earlier targeted ad-hoc verifier passed before the final status/gate changes. Final targeted verification is rerun after independent review so its hashes bind the released revision.

## Remaining limitations

1. Hermes CLI routes cannot expose native provider `done_reason`, token counters, or returned-model envelope. Maximum-iteration warnings fail closed; otherwise complete responses remain diagnostic-only with `route_identity_unverified` and cannot pass promotion gates.
2. Runner artifact-writing code remains duplicated. Consolidation should be behavior-neutral and separately tested.
3. The Real-Life Pack enforces at least three repeats for promotion. Other lane-level results with smaller samples remain weak evidence and require representative human output review.
4. This hardening does not validate any Coding Model Benchmark report, leaderboard, or producer. Those require their own governed review.
