# PA Model Benchmarks

Benchmark suite for selecting local Ollama, Ollama Cloud, and primary cloud models for personal assistant (PA) workloads.

## Why this benchmark?

Generic LLM benchmarks (MMLU, HumanEval, MT-Bench) measure abstract capability — but they don't tell you whether a model can safely handle the messy, multi-domain, safety-constrained work of a real personal assistant. This suite tests what actually matters for PA routing:

**Safety boundaries, not just accuracy.** Every lane includes hard-fail validators for approval gates (draft, don't send), archive-before-delete, backup-before-edit, privacy routing (local vs cloud), and health non-diagnostic boundaries. A model that scores 90% on MMLU but sends an unapproved external message or recommends hard training on stale HRV data is disqualified.

**Multi-domain realism.** Tasks span daily prioritization, German tax email drafting, health recovery coaching, trading bot decision notes, Obsidian vault operations, cron scheduling semantics, privacy classification, and source conflict resolution — all in one suite. No generic benchmark covers this combination.

**Lane-based, not single-score.** Models are evaluated across 7 lanes (Daily, Real-Life, Workload, Conflict, Control Matrix, Held-Out, Tool-Live), each with its own gate. A model can pass D-lane but fail R-lane — and that distinction matters for routing decisions. No single number hides a critical weakness.

**Anti-overfitting built in.** The H-lane (Held-Out) tests whether a model generalizes beyond the calibration set. Tasks are structurally similar but content-distinct from D-lane, so prompt-engineering shortcuts that pass D-lane but fail H-lane are caught.

**Prompt-profile aware.** Each model gets a registered prompt profile with model-specific system instructions, thinking on/off control, and a prompt engineering guide. This means you're testing the model as it would actually be deployed — with the right system prompt — not with a generic chat template.

**Real tool integration.** The tool-live lane runs actual bounded agent loops with sandboxed file operations, session resume, and identity verification — not just text-in/text-out. This catches models that talk a good game but can't execute safely.

**Serial, reproducible, fail-closed.** Candidates run one at a time with frozen schedules, manifest hashes, and strict Ollama identity verification. No parallel contamination, no alias inference, no quiet retries.

## Quick Start

```bash
# Clone and install
git clone https://github.com/busera/pa-model-benchmarks.git
cd benchmark_pa-model
pip install -e .

# Verify everything works (zero model calls)
python3 -m pytest -q
python3 scripts/pa_daily_use_benchmark.py --self-test
```

See [ADOPTION.md](ADOPTION.md) for a comprehensive guide on registering models, creating prompt guides, adding custom tasks, and running benchmarks.

New users should start with [SETUP_GUIDE.md](SETUP_GUIDE.md) — it walks through the full setup process: inventorying your environment, identifying applicable lanes from your knowledge base, configuring models, and interpreting results.

## Programme boundary

- **PA Model Benchmark Test Suite:** the D/R/W/F/T/H/X and tool-live lanes documented here. It evaluates broad PA behaviour, safety, retrieval, daily work, anti-overfitting, artifacts, and tool integration.
- **Coding Model Benchmark Test Suite:** a separate project for coding-specific evaluation. This repository does not own coding runners, prompts, tests, artifacts, reports, or coding-route evidence.

Lessons may transfer between harnesses, but results, promotion gates, reports, and evidence authority do not. A coding-model score cannot promote a PA default, and PA-suite hardening must not rewrite coding-suite authority.

## Decision model

The suite is lane-based; no single score should be treated as a universal model ranking.

| Suite | Role | Broad promotion? |
|---|---|---|
| D01-D14 Daily-Use Pack | Non-coding, non-project daily PA fit | Required for daily cloud routing |
| R01-R10 Real-Life Pack | High-risk PA behavior | Yes, as one required gate |
| W01-W21 Typical Workload | Representative daily workload fit | Required broad-fit lane |
| F01-F10 Conflict Retrieval | Stale/current source resolution and arithmetic | Required safety gate |
| T01-T12 Control Matrix | Contracts, skills, architecture, and routing controls | Required broad-safety lane |
| X01-X18 Extended Capability | Artifacts, vision, reports, skill workflows | Specialist evidence only |
| H01-H06 Held-Out Daily Pack | Overfitting detection for D01-D14 | Required anti-overfitting lane; separate from calibration |
| Synthetic tool-live | Actual bounded PA file/session behavior | Required category-matched integration lane |

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
$PY scripts/mb006_preflight.py --json
```

Example targeted synthetic run:

```bash
$PY scripts/pa_conflict_retrieval_benchmark.py \
  --models gemma4:31b-cloud,qwen3.6:27b-mlx-bf16 \
  --tasks F01,F03
```

Artifacts are written under `artifacts/<run-id>/`. Benchmark execution can consume cloud quota; self-tests do not call models. Tracked fixtures are synthetic and redact known personal/employer/account markers. Optional private fixtures may be loaded only from an explicit external `PA_BENCHMARK_PRIVATE_FIXTURE_ROOT`; they are never copied into or tracked by this repository.

Repeated runs use `--repeats N --seed N --run-order balanced|random|fixed`. Each cell is stored under `trial-NNN/`; summaries report trial count, mean, population standard deviation, pass rate, and fail-closed eligibility. Provider-side seed support is not assumed: the seed governs execution ordering and is recorded in the manifest.

Every D/R/W/F/T/H/X run claims a fresh, empty run root and writes schema-v1 `manifest.json` before model execution. Existing manifests or stale run-root content fail closed; overwrite/resume is unsupported until an explicit protocol exists. The manifest records a sanitized command identifier, source/selected-task/prompt-profile hashes, Git/Python/Ollama/platform metadata, privacy class, repeat/order controls, and explicit requested model/provider routes. Raw arguments are not retained. Ollama IDs are resolved from `ollama list` where available; unresolved digests remain explicit-route requests rather than being assigned an invented identity.

## PA-suite fairness and evidence rules

1. Every candidate must resolve by exact tag to a non-generic profile in `scripts/model_prompt_profiles.py` and a repository-owned guide snapshot suitable for that exact generation under `prompts/guides/`. Family substring matching is prohibited. Runners fail closed for unmapped candidates or missing guides; manifests hash the selected guide bytes.
2. Prompt profiles may adapt system wording and runtime options, but may not weaken validators or insert task answers.
3. Record the exact model tag, provider route, prompt profile/guide, API mode, thinking control, runtime options, validator results, response, and elapsed time.
4. A runtime error is a failed cell, not missing evidence. Partial/targeted runs must not be presented as full-suite promotion evidence.
5. Synthetic prompt-contained retrieval tests do not prove real PA tool use. Tool-live memory/session/file retrieval remains a separate required integration gate.
6. X01 vision is valid only when the route receives the generated image. Text-only paths must fail closed rather than scoring prompt leakage.
7. Cross-lane decision post-processing is explicit, not automatic. `benchmark_decision.build_category_model_selection` emits separate `ollama_cloud` and `local` leaders under the contract in `docs/decisions/ollama-category-selection-contract.md`; it never emits a universal local-vs-cloud winner. Missing or failed required lanes block an eligible leader. Individual runner rankings remain within-lane diagnostics.
8. Shared repeated-trial scheduling is **model-major within each trial** to avoid repeated local-model eviction/reload; balanced mode rotates the first model between trials. Ollama requests set top-level `keep_alive: "30m"` (not an `options` key).
9. Native PA cells distinguish transport, provider process/contract/identity, unsupported route, strict-format, validator, and incomplete outcomes. Read retained stderr/raw responses before attributing a failure to model quality.
10. PA JSON recovery may support diagnostics, but recovery warnings remain hard failures and never count as strict contract compliance. The PA suite has no repair pass; any future PA agent-repair lane must report first-pass and repaired success separately.
11. Early-stop saves spend only. Skipped cells remain incomplete/ineligible and never become model failures or full-suite evidence.
12. PA output budgets remain task-specific. Native Ollama cells retain requested caps, token counts, and stop reason; token caps, `done=false`, and missing completion telemetry become incomplete evidence before validation.
13. PA CLI output is parsed before validation. Maximum-iteration warnings become incomplete cells. The CLI does not expose returned-model identity, so otherwise complete PA cells retain diagnostic scores but carry `route_identity_unverified`, use `status=unverified`, and cannot pass promotion gates.
14. The Real-Life Pack requires at least three repeats before `promotion_gate=pass`; one-repeat runs remain diagnostic even with complete, perfect-scoring coverage.
15. Ollama aliases are never inferred by stripping `:cloud` or `-cloud`. When `/api/chat` returns a different identity, the runner fetches fresh same-origin `/api/tags` evidence and accepts only one exact requested-tag registration whose raw `remote_model` equals the returned identity and whose digest is retained.

Read `AGENTS.md`, `AUTHORITY.md`, and `docs/standards/benchmark-operating-standard.md` before changing or running the harness.

## Tool-live integration gate

`pa_tool_live_benchmark.py` uses synthetic nonces, a fresh execution root created directly under canonical `/private/tmp`, a temporary isolated `PA_HOME`, a minimal credential-free subprocess environment, and a macOS default-deny `sandbox-exec` policy. Caller-selected, existing, symlinked, and non-`/private/tmp` execution roots are rejected. The policy exposes only system runtime resources, a hard-linked copy of the Python/PA runtime and dependencies inside the trusted root, the synthetic fixture, and the isolated state/artifact root; the original PA installation and personal home files remain unreadable, fixture/artifact executables cannot run directly, and outbound networking is restricted to localhost. The route is an explicit localhost-only custom provider with bounded tools and turns. A loopback proxy injects and records the approved OpenAI-compatible `reasoning_effort=high`, requests streaming usage, verifies requested/returned identity against the approved registration digest, and fails closed on missing usage, missing finish telemetry or truncation without retaining prompts. Default and self-test modes make zero model calls. `--execute --repeats 3` writes complete per-case/trial cells; L03 retains create+resume semantics, and a missing session ID is attributed to setup rather than model output. Cloud-tagged models require explicit `--allow-cloud`, `--expected-digest`, and separate approval. Results are required integration evidence but never broad-promotion evidence by themselves.

```bash
$PY scripts/pa_tool_live_benchmark.py                 # fixture-only, no model call
$PY scripts/pa_tool_live_benchmark.py --execute --model qwen3.6:27b-mlx --expected-digest <approved-digest>
```

## Customization

See [ADOPTION.md](ADOPTION.md) for detailed instructions on:

- Registering new models in `scripts/model_prompt_profiles.py`
- Creating prompt engineering guides in `prompts/guides/`
- Adding custom tasks to each lane runner
- Configuring the serial schedule
- Adding private fixtures

## Known limitations

- Runner artifact and aggregation code remains duplicated; consolidate only after behavior is pinned with tests.
- Direct PA CLI text outside the governed tool-live proxy offers process-exit and warning evidence but no returned-model or native token/stop envelope. Governed tool-live avoids that limitation through the localhost telemetry proxy and exact digest binding.
- Semantic checks are deterministic and field-scoped but not a substitute for representative human output review.
- Confidence intervals use an approximate 95% normal interval and are omitted for a single trial; interpret very small samples cautiously.
- Tool-live memory coverage currently uses a clean PA session/resume contract; direct personal memory-provider testing remains out of scope by default.

## Documentation

- `ADOPTION.md` — comprehensive adoption and customization guide.
- `CONTRIBUTING.md` — contribution guidelines.
- `AGENTS.md` — agent instructions for working in this repository.
- `AUTHORITY.md` — authority boundary between executable code and human decisions.
- `SUITES.md` — programme boundaries and entrypoints.
- `SETUP_GUIDE.md` — agent-facing setup guide: connect the suite to your environment.
- `CHANGELOG.md` — suite changes.
- Dated design and result notes — historical evidence; do not silently rewrite old results.
