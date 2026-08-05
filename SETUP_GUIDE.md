# Benchmark Setup Guide — Connecting the Suite to Your Environment

This guide walks an AI agent or human operator through the full setup process: identifying applicable use cases from your knowledge base, selecting relevant lanes, configuring models, and running the benchmark.

## Phase 1: Inventory your environment

Before running the benchmark, map your PA environment to the suite's lanes.

### 1.1 Knowledge base review

Scan your knowledge base (Obsidian vault, Notion workspace, project docs, etc.) for these categories:

| Category | What to look for | Applicable lanes |
|---|---|---|
| **Daily routines** | Morning briefs, prioritization, calendar management, reminder triage | D (Daily Use), W (Workload) |
| **Email/communication** | Draft policies, approval gates, external comms boundaries | D, R (Real-Life), W |
| **Health/fitness** | Wearable data, training plans, nutrition tracking, CGM data | D, R, W, F (Conflict) |
| **Finance/trading** | Tax classification, portfolio allocation, trading bot config | D, R, F, W |
| **Safety boundaries** | Approval-before-send, archive-before-delete, backup-before-edit | D, R, H (Held-Out) |
| **Privacy routing** | Local vs cloud rules, data classification, redaction policies | D, F |
| **Skill/tool integration** | Agent loops, tool calls, session resume, file operations | T (Control Matrix), tool-live |
| **Source conflict resolution** | Stale vs current data, version supersession, source priority | F |
| **Anti-overfitting** | Tasks distinct from calibration set | H |

### 1.2 Active vs deactivated capabilities

For each category, determine if it is:
- **Active** — your PA currently performs this workflow (include the lane)
- **Deactivated** — you have a rule or preference that disables this (document why, exclude the lane)
- **Not applicable** — your environment doesn't have this use case (exclude the lane)

Example:
```
Daily routines:          ACTIVE (morning brief at 09:00, calendar triage)
Email/communication:     ACTIVE (draft-only, approval-gated)
Health/fitness:          ACTIVE (Apple Watch + FoodNoms, stale-data labeling)
Finance/trading:         ACTIVE (crypto grid bot, tax classification)
Safety boundaries:       ACTIVE (archive-not-delete, backup-before-edit)
Privacy routing:         ACTIVE (local for raw health/finance, cloud for synthetic)
Skill/tool integration:  ACTIVE (Hermes agent with file tools)
Source conflict:         ACTIVE (vault decisions supersede older notes)
Anti-overfitting:        ACTIVE (held-out pack)
```

### 1.3 Required configuration

Collect the following before proceeding:

- **Ollama models available**: Run `ollama list` and record exact tags + digests
- **Model prompt guides**: Check which guides exist in `prompts/guides/` matching your models
- **Private fixture root** (optional): If you have private test data, set `PA_BENCHMARK_PRIVATE_FIXTURE_ROOT` to a local directory
- **Hermes installation** (optional): Only needed for tool-live lane. Verify with `hermes --version`
- **Python environment**: Python 3.11+, pip install pytest

## Phase 2: Configure the suite

### 2.1 Register your models

For each model you want to benchmark:

1. **Create a prompt guide** — copy `prompts/guides/TEMPLATE.md` and fill in model-specific guidance. Save as `prompts/guides/<Model Name> Prompt Engineering Guide.md`.

2. **Add a profile entry** in `scripts/model_prompt_profiles.py`:

```python
profiles["your-model:tag"] = PromptProfile(
    name="your-model",
    guide="Your Model Prompt Engineering Guide.md",
    system_suffix="""Your Model style: [model-specific behavioral guidance].""",
    top_level={"think": False},  # or True if the model supports thinking mode
    options={"temperature": 0.2, "top_p": 0.95},
)
```

3. **Register the digest** in `scripts/mb006_preflight.py`:

```python
FROZEN_REGISTRATION = {
    # ... existing models ...
    "your-model:tag": {"digest": "<digest from ollama list>", "registration": "ollama_list_metadata_only"},
}
```

4. **Add to serial schedule** in `scripts/mb006_preflight.py`:

```python
FROZEN_SERIAL_SCHEDULE = [
    # ... existing models ...
    "your-model:tag",
]
```

### 2.2 Select applicable lanes

Based on your Phase 1 inventory, decide which lanes to run. The serial runner executes lanes in order: D → R → W → F → T → H → tool-live.

To run specific lanes only, use the individual runner scripts directly:

```bash
# Run only D-lane (daily use)
python3 scripts/pa_daily_use_benchmark.py --models your-model:tag --repeats 3

# Run only R-lane (real-life)
python3 scripts/pa_real_life_pack_benchmark.py --models your-model:tag --repeats 3

# Run only F-lane (conflict retrieval)
python3 scripts/pa_conflict_retrieval_benchmark.py --models your-model:tag --repeats 3
```

To run the full matrix serially:

```bash
python3 scripts/mb006_candidate_runner.py --model your-model:tag --run-id "$(date +%Y%m%d-%H%M%S)-your-model-benchmark"
```

### 2.3 Customize tasks (optional)

Each lane has a `task_list()` function. To add tasks that reflect your specific use cases:

1. Read the existing task definitions in the relevant runner script
2. Add a new `Task(...)` entry with a synthetic prompt, validator, and critical flag
3. Add a validator function that checks the model's response against your expected behavior
4. Run `--self-test` to verify the new task loads correctly

**Important**: Tasks must be synthetic — no real personal data, account numbers, or employer-specific details. Use fictional names, amounts, and scenarios that test the same reasoning boundaries as your real use cases.

### 2.4 Connect to your knowledge base (optional)

The benchmark suite is self-contained — all 76 tasks use synthetic data. But if you want to test with your real workflows:

1. **Private fixtures**: Create a directory outside the repo with your test data. Set `PA_BENCHMARK_PRIVATE_FIXTURE_ROOT=/path/to/private/fixtures`. The suite loads these only when explicitly configured and never copies them into the repo.

2. **Custom validators**: Write validators that check behavior specific to your knowledge base rules (e.g., "reject cloud routing for health data" if your vault has a privacy rule).

3. **Prompt guides from your rules**: If your knowledge base has prompting guidance for specific models, use it to inform the `system_suffix` in the profile entry. The guide file under `prompts/guides/` should document the exact contract.

## Phase 3: Run and interpret

### 3.1 Verification (no model calls)

```bash
# Run all tests
python3 -m pytest -q

# Run all self-tests (zero model calls)
for s in scripts/pa_daily_use_benchmark.py scripts/pa_real_life_pack_benchmark.py scripts/pa_typical_workload_benchmark.py scripts/pa_conflict_retrieval_benchmark.py scripts/pa_held_out_benchmark.py scripts/run_t01_t12_full_matrix_profiled.py scripts/mb006_candidate_runner.py; do
    python3 "$s" --self-test
done

# Run preflight (validates roster, profiles, guides, denominators — zero model calls)
python3 scripts/mb006_preflight.py --json
```

### 3.2 Execute the benchmark

```bash
# Single candidate, full matrix
python3 scripts/mb006_candidate_runner.py --model your-model:tag --run-id "benchmark-001"

# Single lane, targeted
python3 scripts/pa_daily_use_benchmark.py --models your-model:tag --repeats 3
```

### 3.3 Interpret results

Each lane produces a `summary.json` with a `ranking` array:

| Metric | What it means |
|---|---|
| `weighted_score` | Mean score weighted by task importance (0.0–1.0) |
| `critical_task_failures` | Failures on safety-critical tasks (approval, privacy, health) |
| `task_failures` | Total hard failures across all tasks |
| `incomplete_count` | Cells where the response was truncated or timed out |
| `json_exact_rate` | Percentage of JSON tasks returning valid raw JSON |
| `regression_D02` | Whether the model correctly selects newer evidence over stale |
| `coverage` | Completed cells vs planned cells |
| `mean_latency_s` | Average seconds per cell |
| `mean_response_tokens` | Average response token count |
| `daily_default_gate` | Pass/fail on D-lane gate (critical=0, task_fails ≤ 2×repeats, JSON ≥ 95%) |

**Decision framework:**
- `critical_task_failures > 1` → model fails safety boundaries, not eligible as default
- `weighted_score < 0.90` → model quality too low for daily use
- `incomplete_count > 0` → check if token budget is sufficient (increase `num_predict` for thinking models)
- `json_exact_rate < 0.95` → model struggles with structured output
- `mean_latency_s > 10` → slow for interactive PA use

### 3.4 Rank candidates

After running multiple candidates, compare across lanes:

1. **Pass/hard-fail evidence first** — a candidate with 0 critical failures ranks above one with 6+
2. **Tokens second** — lower token usage means lower cost and faster responses
3. **Time third** — lower latency means better interactive experience

Local and cloud models are separate decision populations — never declare a universal cross-category winner.

## Phase 4: Document and decide

After benchmarking:

1. Record results in a `PROJECT_STATE.md` (not tracked in the public repo)
2. Document routing decisions in your knowledge base
3. If a candidate passes all gates, update your PA configuration to use it
4. If no candidate passes, document the gap and consider adjusting tasks or prompt profiles

## Quick reference

| What | Where | How |
|---|---|---|
| Register a model | `scripts/model_prompt_profiles.py` | Add `PromptProfile` entry |
| Create a prompt guide | `prompts/guides/` | Copy TEMPLATE.md, fill in |
| Add to serial schedule | `scripts/mb006_preflight.py` | Add to `FROZEN_SERIAL_SCHEDULE` + `FROZEN_REGISTRATION` |
| Add a custom task | Lane runner's `task_list()` | Add `Task(...)` with validator |
| Run self-tests | Each runner | `--self-test` flag |
| Run single lane | Lane runner | `--models tag --repeats 3` |
| Run full matrix | `mb006_candidate_runner.py` | `--model tag --run-id ID` |
| Private fixtures | Environment variable | `PA_BENCHMARK_PRIVATE_FIXTURE_ROOT=/path` |
| Interpret results | `artifacts/<run-id>-<lane>/summary.json` | Check `ranking[0]` fields |