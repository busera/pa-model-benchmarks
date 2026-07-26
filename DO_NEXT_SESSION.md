# PA Model Benchmarks — Do Next Session
[[2026-07-26]]

## Starting prompt

> Read and execute this `DO_NEXT_SESSION.md` as the continuation instruction for this project. Verify live state first, then follow its read order, gates, prohibitions, next actions, and completion condition. Continue autonomously until a genuine blocker or explicit approval boundary.

## Objective

Execute **MB-002 — Held-out daily task pack** as the sole active outcome. Freeze a synthetic held-out task/label/validator contract before candidate execution, implement it without copying calibration answers, and produce independently reviewable evidence that remains separate from D01–D14 calibration and broad-promotion authority.

## Repository / project

- Repository: `/Users/busera/Developer/pa-model-benchmarks`
- Branch: `main`
- Implementation baseline before this handoff refresh: `842e5074af83ff2383d11c2f777f855fb47f98f3`
- Product backlog: `/Users/busera/Obsidian/obs_BFB/4_Projects/PA Development/LLM A-B Tests/PA Model Benchmark Backlog.md`
- Executable authority: this repository
- Human decision/report authority: `/Users/busera/Obsidian/obs_BFB/4_Projects/PA Development/LLM A-B Tests/`
- External-action boundary: do not push, publish, tag, activate routing, run cloud candidates, or use private payloads without separate approval.

## Start here

1. Run `git status --short`, `git branch --show-current`, and `git log --oneline -3`; reconcile any drift before editing.
2. Read, in order:
   1. this file;
   2. `PROJECT_STATE.md`;
   3. the `MB-002` section of the authoritative Obsidian backlog;
   4. `README.md`, especially programme boundaries and fairness/evidence rules;
   5. `scripts/pa_daily_use_benchmark.py` and `scripts/test_pa_daily_use_benchmark.py`;
   6. `scripts/benchmark_manifest.py`, `scripts/benchmark_transport.py`, `scripts/benchmark_trials.py`, and their tests;
   7. `docs/migration/2026-07-26 PA Model Benchmark Suite Coding-Lesson Hardening Review.md`.
3. Run `/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3 -m pytest -q` before implementation and confirm the baseline remains green.
4. Mark MB-002 `implementation` only when T01 begins; keep MB-003–MB-005 in backlog.

## Completed state — do not repeat

- Executable authority was migrated from Obsidian to this dedicated repository; the former vault executable surface was archived without deletion.
- PA and Coding Model Benchmark programmes have separate evidence and promotion authority.
- Completion, truncation, route identity, immutable run roots/manifests, repeated-trial gates, fixture privacy, portability, and clean-export behavior were hardened.
- Exact tree `22fe57499450b749271569fd1137b22e3659cc2e` passed independent review with P0/P1/P2 all zero and became initial commit `7ad9413e41184ff90061efa32f975d3989ce8906`.
- Governance closeout is commit `842e5074af83ff2383d11c2f777f855fb47f98f3`.
- Release evidence: 140 working-tree tests, 140 clean-export tests, compilation, eight runner self-tests, and an ad-hoc release verifier passed.
- The PA Development backlog was reconciled. Product-specific health, RSS, memory, runtime, and backlog-advisor cards retain their own lifecycle ownership; do not absorb or duplicate them here.

## Gates and prohibited scope

- Do not derive held-out prompts, expected answers, decision tokens, or validators from existing benchmark outputs or model responses.
- Freeze task definitions, labels, validators, budgets, and source hashes before inspecting candidate results. Candidate failures cannot justify editing the frozen contract; version a future pack instead.
- Use synthetic fixtures only. Do not copy names, employer/account identifiers, exact personal finance/health values, real backlog content, private memory, email, calendar, or vault payloads into tracked files.
- Do not reconstruct private marker lists inside tests. Use generic structural privacy/leakage checks.
- Keep held-out evidence in a separate namespace and summary. It must not silently change D01–D14 scores, existing promotion gates, or historical reports.
- Preserve strict first-pass, recovered-format, incomplete, route-unverified, transport/provider/runtime, skipped, and validator-failure outcomes as separate classes.
- Do not modify Coding Model Benchmark producer behavior as part of MB-002.
- Do not execute cloud-tagged models or private fixtures. T04 is local-only unless Andrew separately approves a different route and payload.
- Do not push, publish, tag, deploy, or activate model routing.

## Immediate next actions

1. **T01 — Freeze the contract.** Inventory D01–D14 and adjacent R/W/F/T/X coverage, then define materially distinct held-out daily cases across low-, medium-, and high-risk work. Record task IDs, synthetic inputs, labels, output shapes, budgets, privacy class, scoring anchors, failure taxonomy, and explicit non-goals before writing runner code.
2. Obtain a focused independent review of the T01 contract for calibration leakage, ambiguous labels, privacy, and duplicated coverage. Resolve findings before implementation.
3. **T02 — Implement RED/GREEN.** Add focused failing tests first, then the smallest repository-owned held-out module/data using existing manifest, transport, and repeated-trial contracts. Keep results and aggregation separate from calibration evidence.
4. **T03 — Prove privacy and portability.** Add generic leakage/privacy checks, source hashing, immutable evidence, clean-export coverage, and tracked-artifact exclusions. Do not embed private literals to test their absence.
5. Run focused tests, full `pytest`, applicable self-tests, compilation, `git diff --check`, and a clean-export test. Inspect first-cell stderr/raw evidence for any runtime failure.
6. Freeze and commit the T01–T03 harness/contract before candidate execution so later observations cannot mutate labels or validators.
7. **T04 — Local evidence only.** If the selected local models are installed and available, run model-major repeated trials against the frozen pack, retain manifests/raw evidence, classify failures before scoring, and obtain independent review. If runtime availability blocks execution, record the exact blocker without weakening or rewriting the frozen contract.
8. Reconcile `PROJECT_STATE.md`, the Obsidian backlog, affected docs, `CHANGELOG.md`, and this file before ending.

## Required verification

- Baseline and final: `/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3 -m pytest -q`
- Focused held-out tests added by MB-002.
- Applicable D/R/W/F/T/X/tool-live self-tests with zero unintended model calls.
- Python compilation/AST parse for tracked scripts.
- Clean-export `pytest` from the exact staged tree.
- Manifest/source/task hash verification and immutable run-root checks.
- Generic synthetic-subject, leakage, portability, and tracked-artifact checks.
- `git diff --check` and exact staged-scope inspection.
- Independent contract review before implementation and independent final review after integration/evidence.

## Documentation closeout

- Update the authoritative Obsidian MB-002 item task-by-task; do not duplicate status in a global PA Development card.
- Keep `PROJECT_STATE.md` as implementation evidence and immediate order, not a competing lifecycle backlog.
- Update `README.md` only if the user/operator contract changes.
- Record shipped changes and evidence in `CHANGELOG.md`.
- Refresh this handoff so it points to the next genuine outcome rather than completed MB-002 work.

## Next-session completion condition

MB-002 is complete only when the held-out contract was frozen before candidate observation, T01–T03 implementation is committed and clean-export reproducible, local-only T04 evidence is either completed and independently reviewed or blocked by a precisely documented runtime dependency, all P0/P1 findings are resolved, project state/backlog/docs agree, and the repository is clean. Stop at any external approval boundary; do not substitute cloud/private execution or routing activation.