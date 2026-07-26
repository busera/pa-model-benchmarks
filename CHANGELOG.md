# Changelog — LLM A-B Tests

## 2026-07-26 — dedicated Developer repository migration

- Established `/Users/busera/Developer/pa-model-benchmarks` as executable authority and retained Obsidian as human decision/report authority.
- Copied and byte-verified 39 source files, 11,150 artifact files, and 18 prompt guides before portability changes.
- Removed hard-coded vault/user runtime roots; active runners now resolve the repository from `__file__`, Python subprocesses use `sys.executable`, and private legacy fixture loading is explicit opt-in through `PA_BENCHMARK_PRIVATE_FIXTURE_ROOT`.
- Prompt-guide snapshots are repository-owned and source-hashed in run manifests.
- Added programme boundaries, canonical `pyproject.toml` test configuration, generated-artifact ignores, migration manifest, and clean-export portability tests.
- Moved the previous vault executable surface to `/Users/busera/_Archive/PA Model Benchmarks/vault-executable-surface-20260726_123531`; no permanent deletion.
- Verification after independent-review remediation: working tree `140 passed`; clean-export and targeted ad-hoc verification are rerun against the final staged tree before release binding.

## 2026-07-26 — PA Model Benchmark hardening from transferable coding lessons

### Scope

- Explicitly separated the D/R/W/F/T/X/tool-live **PA Model Benchmark Test Suite** from the `local_coding_breakpoint_benchmark.py` **Coding Model Benchmark Test Suite**.
- Coding results, repair passes, hidden tests, generated-code sandbox controls, reports, and routing authority remain outside this PA-suite change.
- Restored the incidentally edited July 20 coding report byte-for-byte to its pre-task state after the scope conflation was identified.

### Changed

- Shared PA repeated-trial scheduling is model-major inside each trial; balanced repeats rotate the first model.
- Shared native Ollama requests set top-level `keep_alive: "30m"`.
- Added a source-hashed shared transport contract that retains sanitized returned-model, stop, token, and request-control metadata; fails closed on model mismatch; and classifies truncation as incomplete before semantic scoring.
- PA runners now distinguish transport timeout/HTTP/unavailable, provider process/contract/identity, unsupported route, runtime, and incomplete-output evidence.
- Native Ollama responses now require affirmative `done=true`; `done=false` and missing completion telemetry fail closed before semantic validation.
- Hermes CLI maximum-iteration warnings now fail closed. Complete Hermes results retain diagnostic scoring but are `unverified` and promotion-ineligible because the CLI exposes requested route only, not returned-model identity.
- Run roots and manifests are immutable: stale run IDs, existing output, and manifest overwrite now fail closed before any model cell is appended.
- Daily-Use writes its immutable manifest before any preflight provider request, including `--preflight-only` runs.
- Real-Life Pack promotion requires at least three complete repeats; one-repeat runs remain diagnostic.
- Tracked fixtures declare synthetic provenance, remove named personal-profile contracts and copied exact profile values, and are protected by a structural privacy regression scan that embeds no private values itself. Optional private fixtures remain external and opt-in.
- Partial-run output now includes frozen completed/planned denominators, per-model coverage, and `winner_withheld` until completion.
- Added [[2026-07-26 PA Model Benchmark Suite Coding-Lesson Hardening Review]] and updated README/project state/index.
- Added the Developer-repo/code plus Obsidian-decision-note split; migration is now executed and recorded under `docs/migration/`.

### Verification

- RED was demonstrated for missing model-major scheduling, keep-alive, transport provenance, and denominator-safe progress.
- Full scripts suite after independent-review fixes: `140 passed`. Final compilation, self-tests, clean export, and targeted ad-hoc verification follow on the exact staged tree.
- No model calls or routing changes are part of this hardening; independent review is PA-suite-only.

## 2026-07-19 — daily-use local-vs-cloud comparison

### Added

- Capability-based inventory of 14 local non-cloud tags; five embedding-only models and one TTS-specialized Orpheus model excluded from text scoring.
- Eight-model, 112-cell local D01–D14 screen.
- Two additional balanced repeats for Qwen3.6 27B MLX and BF16, combined into 42/42 cells per finalist.
- Machine-readable inventory, adjudication ledger, and same-surface comparison artifacts.
- Canonical Markdown and self-contained HTML local-vs-cloud report.

### Decision

- No local model matched Kimi K2.6 or cloud Nemotron overall.
- Qwen3.6 27B MLX BF16 is the reviewed local quality candidate; Qwen3.6 27B MLX is the reviewed local latency candidate.
- Both local finalists failed loaded-skill change control D07 in all three observations; no unattended promotion.

### Verification

- Local screen coverage: 112/112 cells.
- Combined stability coverage: 42/42 cells per finalist with trials 1–3 complete.
- Exact JSON: 100% for both local finalists.
- Daily runner self-test and focused/core pytest rerun passed.
- Inventory, manifests, adjudication ledger, comparison data, report links, and HTML structure verified.

## 2026-07-19 — daily-use cloud lane

### Added

- D01-D14 synthetic non-coding, non-project daily-use benchmark.
- Exact-tag Ollama preflight, repeated balanced trials, per-cell artifacts, schema-v1 manifests, strict promotion gate, and latency distribution reporting.
- Five-model screen plus three-trial GLM-5.2/Kimi K2.6/Nemotron 3 Ultra stability run.
- Canonical Markdown and self-contained HTML report with raw and human-adjudicated rankings.

### Changed

- Daily model selection no longer derives from the mixed coding/project/artifact composite.
- Kimi K2.6 is provisional for reviewed low-risk interaction; no Ollama candidate passed unattended promotion.
- Six superseded broad-routing reports moved to `_Backups/2026-07-19 Superseded Cloud Daily Benchmark Reports/`; no deletion.
- June cloud, local-vs-cloud, GLM, and scenario-routing reports now point to the daily-use canonical report.

### Verification

- Full stability coverage: 42/42 cells per shortlisted model.
- Exact native Ollama preflight passed for all five screened tags.
- `pytest` passed: 34 focused/core tests.
- Canonical HTML, Markdown, manifests, report links, and Journal link verified.

## 2026-07-11 — reliability priorities 1–6

### Added

- Shared field-scoped semantic validation with adversarial negative tests.
- Repeated-trial controls (`--repeats`, `--seed`, `--run-order`), trial-safe artifact paths, pass rates, standard deviation, and approximate 95% confidence intervals across R/W/F/T/X.
- Schema-v1 reproducibility manifests with source/task hashes, runtime/platform/Git provenance, privacy classification, and resolvable Ollama IDs.
- Synthetic, local-first Hermes tool-live suite with isolated localhost-only Hermes home, file retrieval, conflict resolution, session continuity, and explicit cloud approval.
- Lane-specific fail-closed decision helper that deliberately omits universal scores and rankings.
- Project-owned T01–T12 fixture/scorer snapshots with provenance and source hashes.
- Dated implementation plan with acceptance criteria, rollback, and TDD order.

### Changed

- F-suite critical checks now validate the selected, rejected, and answer fields rather than accepting terms anywhere in the response.
- All repeated cells include `trial_index`; repeated artifacts no longer overwrite one another.
- T-matrix paths are repository-relative and no longer import executable code from `/Users/busera/Temp/Hermes`.

### Verification

- `py_compile scripts/*.py scripts/legacy_t_matrix/*.py` passed.
- `pytest -q scripts` passed: `59 passed in 0.15s`.
- R, W, F, X, T, and tool-live self-tests passed with zero model calls.
- Tool-live fixture-only smoke and real isolated local-Ollama smoke passed all three synthetic cases (file nonce, current-vs-stale conflict, session resume).
- Static security scan and diff hygiene passed before independent review.

## 2026-07-11 — initial hardening

### Fixed

- Added fail-closed prompt-profile coverage checks to the R, W, F, and X runners; unmapped model families can no longer silently run under the generic profile.
- Restored the Real-Life Pack's suite-specific system contract on the Ollama route, matching the contract already supplied to the Hermes route.
- Removed answer leakage from X01's vision prompt.
- Made the Hermes text-only X01 route fail closed because it does not attach the generated image.
- Corrected W-suite summary metadata: critical-task failures allowed is zero, while the gate remains workload-fit evidence rather than broad-promotion approval.
- Applied the recorded OpenAI prompt profile to actual Hermes requests across R/W/F/X and the T-matrix runner.
- Made R/W/F gates fail on missing, duplicate, or runtime-error cells rather than normalizing partial coverage away.
- Enforced exact ordered section contracts in the Real-Life Pack.

### Added

- Prompt-profile governance tests.
- Vision anti-leakage and route-capability regression test.
- `README.md` with suite map, commands, fairness rules, and limitations.
- `PROJECT_STATE.md` with current risks and prioritized next work.

### Verification

- `py_compile` passed for all changed runners and tests.
- `pytest -q scripts` passed: `39 passed in 0.07s`.
- R, W, F, and X self-tests all passed.
- Unknown-profile CLI probe exited non-zero before creating an artifact directory.
- `git diff --check` passed.
