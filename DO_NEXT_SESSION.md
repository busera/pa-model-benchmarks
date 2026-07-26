# PA Model Benchmarks — Do Next Session
[[2026-07-26]]

## Starting prompt

> Read and execute this `DO_NEXT_SESSION.md` as the continuation instruction for this project. Verify live state first, then follow its read order, gates, prohibitions, next actions, and completion condition. Continue autonomously until a genuine blocker or explicit approval boundary.

## Objective

Execute **MB-003 — Synthetic local tool-live execution** as the sole active outcome. Exercise the existing synthetic tool-live gate against the selected local candidate in its isolated localhost-only sandbox. If MB-003 is blocked by runtime availability, proceed to **MB-004 — D07 held-out diagnosis** instead.

## Repository / project

- Repository: `/Users/busera/Developer/pa-model-benchmarks`
- Branch: `main`
- Last commit: `232b398` (MB-002 T01–T03) plus T04 evidence commit
- Product backlog: `/Users/busera/Obsidian/obs_BFB/4_Projects/PA Development/LLM A-B Tests/PA Model Benchmark Backlog.md`
- Executable authority: this repository
- Human decision/report authority: `/Users/busera/Obsidian/obs_BFB/4_Projects/PA Development/LLM A-B Tests/`
- External-action boundary: do not push, publish, tag, activate routing, run cloud candidates, or use private payloads without separate approval.

## Start here

1. Run `git status --short`, `git branch --show-current`, and `git log --oneline -3`; reconcile any drift before editing.
2. Read, in order:
   1. this file;
   2. `PROJECT_STATE.md`;
   3. the `MB-003` and `MB-004` sections of the authoritative Obsidian backlog;
   4. `README.md`, especially the tool-live integration gate section;
   5. `scripts/pa_tool_live_benchmark.py` and its test file;
   6. `docs/held-out/2026-07-26 MB-002 T04 Local Candidate Evidence.md` — for context on local model performance.
3. Run `/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3 -m pytest -q` before implementation and confirm the baseline remains green (174 tests expected).

## Completed state — do not repeat

- MB-001: governed migration and initial repository binding — done.
- MB-002: held-out daily task pack — done. T01–T04 complete, 174 tests, clean-export, T04 local evidence with both Qwen3.6 27B variants failing the held-out gate. Validator precision findings documented for future pack versioning.
- All hardening (completion, provenance, immutable run roots, repeat gates, portability, fixture privacy) is complete.
- The held-out contract is frozen at `docs/held-out/2026-07-26 MB-002 Held-Out Daily Task Pack Contract.md`. Do not edit it after candidate observation.

## Gates and prohibited scope

- Do not execute cloud-tagged models or private fixtures. MB-003 is local-only unless Andrew separately approves a different route and payload.
- Do not push, publish, tag, deploy, or activate model routing.
- Use synthetic nonces, isolated `HERMES_HOME`, no personal memory/provider payload, no cloud route.
- Tool-live results are specialist integration evidence, not broad-promotion authority.

## Immediate next actions (MB-003)

1. Verify the selected local candidate (`qwen3.6:27b-mlx-bf16`) is installed and available.
2. Execute the frozen tool-live suite with `--execute --model qwen3.6:27b-mlx-bf16` in its isolated localhost-only sandbox.
3. Classify tool/session/runtime failures using the existing fail-closed taxonomy.
4. Record evidence, latency, completion, and diagnostic recommendation.
5. Reconcile `PROJECT_STATE.md`, the Obsidian backlog, `CHANGELOG.md`, and this file before ending.

## Alternative: MB-004 — D07 held-out diagnosis

If MB-003 is blocked by runtime availability, proceed to MB-004:
1. Classify existing D07 failures from prior benchmark runs.
2. Freeze held-out D07 variants (do not use evaluated examples for tuning).
3. Test explicit skill injection as a remediation.
4. Compare baseline, intervention, and held-out results without changing validators after results.

## Required verification

- Baseline: `/opt/homebrew/Caskroom/miniconda/base/envs/claude-skills/bin/python3 -m pytest -q` (174 tests expected).
- Tool-live self-test: `python3 scripts/pa_tool_live_benchmark.py` (no model calls).
- Tool-live execution: `python3 scripts/pa_tool_live_benchmark.py --execute --model qwen3.6:27b-mlx-bf16`.
- `git diff --check` and exact staged-scope inspection.

## Documentation closeout

- Update the authoritative Obsidian MB-003 (or MB-004) item with closure evidence.
- Keep `PROJECT_STATE.md` as implementation evidence and immediate order.
- Record shipped changes and evidence in `CHANGELOG.md`.
- Refresh this handoff so it points to the next genuine outcome.

## Next-session completion condition

MB-003 is complete when the synthetic tool-live suite has been executed against the selected local candidate in its isolated sandbox, tool/session/runtime failures are classified, evidence is recorded and independently reviewable, and project state/backlog/docs agree. Stop at any external approval boundary.