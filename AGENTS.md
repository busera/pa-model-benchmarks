# Project Agent Instructions

This file is the mandatory entry point for work in this repository.

## Programme boundary

This repository owns broad PA model evaluation: D/R/W/F/T/X/H and tool-live evidence for local Ollama, Ollama Cloud, and approved control routes. A separate coding-benchmark programme owns coding-specific evaluation.

Methods may transfer between programmes. Scores, fixtures, reports, gates, and promotion authority may not. Normal execution must remain repository-local and must not import another benchmark checkout, user-level skills, or untracked prompt material.

## Mandatory startup order

1. Read this file.
2. Read `docs/standards/benchmark-operating-standard.md`.
3. Read `README.md`, `AUTHORITY.md`, `SUITES.md`.
4. Read `SETUP_GUIDE.md` if setting up the suite for a new environment or connecting to an existing knowledge base.
5. Read `ADOPTION.md` for model registration, prompt guides, and custom task details.
6. Inspect `git status --short --branch --untracked-files=all` before changes.
7. Read the relevant implementation and tests before editing.
8. For a model run, inspect the exact tracked profile in `scripts/model_prompt_profiles.py` and its repository-owned guide under `prompts/guides/`.

## Authority order

1. `AGENTS.md` — startup, isolation, and control rules.
2. `docs/standards/benchmark-operating-standard.md` — canonical engineering and benchmark standard.
3. `README.md` and `SUITES.md` — operator and suite contracts.
4. `SETUP_GUIDE.md` and `ADOPTION.md` — environment setup and customization.
5. Tracked code, tests, profiles, guides, and manifests — executable truth.
6. Project backlog and reports — product lifecycle and interpreted decisions.

## Working rules

- Keep each material change tied to one `MB-*` outcome.
- Make the smallest coherent change and add regression coverage.
- Never weaken validators, required lanes, identity checks, privacy controls, or completion gates to improve a score.
- Never tune a frozen scored fixture from candidate output or hidden failure details.
- Use a fresh create-only run ID; never overwrite, splice, or repair historical artifacts.
- Keep local and Ollama Cloud candidates in separate decision populations. Never emit a universal local-vs-cloud winner.
- Execute selected benchmark models strictly serially. A later model starts only after the prior process exits and its immutable summary validates.
- A full requested matrix means every supported selected lane/cell. Early stop creates incomplete, unranked evidence unless explicitly approved for that wave.
- Separate route/provider failure, completion/control failure, strict-format failure, semantic failure, tool-integration failure, and promotion eligibility.
- Provider preflight proves availability only. Passing tests or a report never changes live PA routing automatically.
- Keep fixtures synthetic and non-personal. Cloud use remains roster- and corpus-specific approval.
- Archive rather than delete. Do not mutate prior evidence.

## Canonical verification

Run from the repository root:

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

Before completion: compile modified Python, run focused tests, run the full suite and applicable self-tests, run `git diff --check`, inspect all changed paths, and obtain independent exact-candidate review for harness, migration, promotion, or routing-grade changes.

Do not commit, push, publish, activate routing, execute cloud models, or expose private data unless the current approved scope explicitly includes that action.
