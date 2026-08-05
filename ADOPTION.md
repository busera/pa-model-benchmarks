# ADOPTION.md — Adopting the PA Model Benchmark Suite

This guide explains how to adopt and adapt the benchmark suite for your own personal assistant (PA) model evaluation. The suite was designed to be portable: all fixtures are synthetic, all paths are repository-relative, and private data is loaded only from an explicit external root.

## Prerequisites

- **Python 3.11+** — the suite uses modern type hints and dataclass features.
- **Ollama** — installed and running locally. Models can be local or cloud (Ollama Cloud). The suite uses the Ollama OpenAI-compatible API.
- **Hermes Agent** (optional) — only needed for the `tool-live` lane, which runs the actual Hermes CLI inside a sandbox. All other lanes work without Hermes.
- **macOS** (optional) — the `tool-live` lane uses `sandbox-exec` (macOS only). Other lanes are platform-independent.

```bash
# Install dependencies
pip install -e .

# Verify everything works (zero model calls)
python3 -m pytest -q
python3 scripts/pa_daily_use_benchmark.py --self-test
```

## Registering models

Models are registered in `scripts/model_prompt_profiles.py`. Each model needs an exact-tag entry in the `profile_for_model()` function. Family/substring matching is prohibited — every candidate must resolve by exact tag.

### Concrete example

To add a new model `my-model:latest`:

1. Create a prompt guide at `prompts/guides/My Model Prompt Engineering Guide.md` (see [Creating prompt guides](#creating-prompt-guides)).

2. Add a profile entry in `scripts/model_prompt_profiles.py`:

```python
"my-model:latest": PromptProfile(
    name="my-model",
    guide="My Model Prompt Engineering Guide.md",
    system_suffix="""My Model style: use the system prompt as the behavioral anchor,
preserve strict final-format constraints, label uncertainty, and disable thinking
for clean benchmark content. Do not include hidden reasoning, scratchpads, or
Markdown fences around JSON.""",
    top_level={"think": False},
    options={"temperature": 0.6, "top_p": 0.95},
    notes="Local model; thinking-off for benchmark scoring.",
),
```

Key fields:
- `name` — short identifier for the profile family.
- `guide` — filename under `prompts/guides/` (must exist).
- `system_suffix` — appended to the base PA contract; adapts wording to the model family's documented guidance.
- `top_level` — Ollama top-level keys (e.g., `think: true/false`).
- `options` — Ollama `options` dict (temperature, top_p, top_k, etc.).
- `notes` — human-readable context; not sent to the model.

The base PA contract (in `BASE_PA_CONTRACT`) is invariant across all models. Only the suffix and runtime options vary.

## Creating prompt guides

Prompt guides live in `prompts/guides/` and document the exact benchmark runtime contract for a specific model generation. Each guide is a Markdown file with:

- **Model identification** — exact tag, digest, and source references.
- **Benchmark runtime contract** — thinking mode, temperature, top_p, output caps, and completion checks.
- **PA behavior contract** — approval boundaries, synthetic-fact grounding, conflict resolution, and artifact completion rules.

### Template

Copy `prompts/guides/TEMPLATE.md` and fill in the model-specific sections. The template includes all required sections with placeholder text.

### Naming convention

Use the pattern `<Model Family> Prompt Engineering Guide.md` (e.g., `My Model Prompt Engineering Guide.md`). The filename must match the `guide` field in the profile entry exactly.

## Adding custom tasks

Each lane runner has a task list that defines the benchmark cells. To add a custom task:

### D-lane (Daily-Use Pack) — `scripts/pa_daily_use_benchmark.py`

Add a task to the `task_list()` function:

```python
def task_list() -> list[dict]:
    return [
        # ... existing tasks ...
        {
            "id": "D15",
            "label": "my-custom-task",
            "prompt": "Your synthetic prompt here...",
            "validator": my_custom_validator,
            "critical": True,  # or False
        },
    ]
```

### R-lane (Real-Life Pack) — `scripts/pa_real_life_pack_benchmark.py`

Same pattern: add to `task_list()` with a validator function.

### W-lane (Typical Workload) — `scripts/pa_typical_workload_benchmark.py`

Same pattern. W-lane tasks are broader workload-fit evidence.

### F-lane (Conflict Retrieval) — `scripts/pa_conflict_retrieval_benchmark.py`

Tasks test stale-vs-current source resolution and arithmetic. Validators check selected/rejected/answer fields.

### T-lane (Control Matrix) — `scripts/run_t01_t12_full_matrix_profiled.py`

Tasks are defined in the `TASKS` list. Each task has a `prompt`, `scorer`, and metadata.

### H-lane (Held-Out Daily Pack) — `scripts/pa_held_out_benchmark.py`

Tasks are materially distinct from D-lane and test overfitting. Add to `task_list()`.

### Tool-live lane — `scripts/pa_tool_live_benchmark.py`

Cases are defined in the `cases()` function. Each case specifies a synthetic scenario with expected tool calls and session behavior.

### Validator guidelines

- Validators receive the model's raw response and return a dict with `score`, `failures`, and optional `critical` flag.
- Use the shared field-scoped semantic checks from the runner's validation module.
- Never tune a frozen scored fixture from candidate output.
- Hidden labels and answer keys must stay outside model-visible context.

## Configuring the serial schedule

The serial schedule is defined in `scripts/mb006_preflight.py`. This file controls:

- **Frozen roster** (`FROZEN_ROSTER`) — which models to run, grouped by category (`ollama_cloud` and `local`).
- **Frozen registration** (`FROZEN_REGISTRATION`) — exact digests for identity verification.
- **Frozen serial schedule** (`FROZEN_SERIAL_SCHEDULE`) — execution order (strictly serial).

To configure your own schedule:

```python
FROZEN_ROSTER = {
    "ollama_cloud": [
        "my-model:cloud",
        "another-model:cloud",
    ],
    "local": [
        "my-local-model:latest",
    ],
}

FROZEN_REGISTRATION = {
    "my-model:cloud": {"digest": "abc123...", "registration": "ollama_list_metadata_only"},
    "another-model:cloud": {"digest": "def456...", "registration": "ollama_list_metadata_only"},
    "my-local-model:latest": {"digest": "ghi789...", "registration": "ollama_list_metadata_only"},
}

FROZEN_SERIAL_SCHEDULE = [
    "my-model:cloud",
    "another-model:cloud",
    "my-local-model:latest",
]
```

The preflight validates roster/profile/guide/repeat/cap consistency without making any model calls:

```bash
python3 scripts/mb006_preflight.py --json
```

## Running benchmarks

### Self-tests (zero model calls)

Every runner supports `--self-test` to validate fixtures, validators, and infrastructure:

```bash
python3 -m pytest -q                                    # all unit tests
python3 scripts/pa_daily_use_benchmark.py --self-test   # D-lane
python3 scripts/pa_real_life_pack_benchmark.py --self-test  # R-lane
python3 scripts/pa_typical_workload_benchmark.py --self-test  # W-lane
python3 scripts/pa_conflict_retrieval_benchmark.py --self-test  # F-lane
python3 scripts/pa_extended_capability_benchmark.py --self-test  # X-lane
python3 scripts/run_t01_t12_full_matrix_profiled.py --self-test  # T-lane
python3 scripts/pa_tool_live_benchmark.py --self-test   # tool-live
python3 scripts/pa_held_out_benchmark.py --self-test    # H-lane
python3 scripts/mb006_preflight.py --json               # roster preflight
```

### Single-lane run

Target specific models and tasks:

```bash
python3 scripts/pa_conflict_retrieval_benchmark.py \
  --models my-model:cloud,my-local-model:latest \
  --tasks F01,F03
```

### Full matrix

Run all lanes for all models in the frozen roster:

```bash
# Direct lanes (D/R/W/F/T/H/X)
python3 scripts/pa_daily_use_benchmark.py --models my-model:cloud --repeats 3
python3 scripts/pa_real_life_pack_benchmark.py --models my-model:cloud --repeats 3
# ... repeat for each lane

# Tool-live (requires Hermes)
python3 scripts/pa_tool_live_benchmark.py --execute \
  --model my-model:cloud \
  --expected-digest <approved-digest> \
  --allow-cloud \
  --repeats 3
```

### Repeat controls

All runners support:
- `--repeats N` — number of trials (3+ required for promotion evidence).
- `--seed N` — reproducibility seed (governs execution order, not model sampling).
- `--run-order balanced|random|fixed` — model scheduling within trials.

Artifacts are written under `artifacts/<run-id>/`. Each run creates a fresh, immutable root.

## Interpreting results

### Weighted score

Each task has a weight. The weighted score is the sum of (task_weight × task_score) / sum of weights. Higher is better; 1.0 is perfect.

### Critical failures

Tasks marked `critical: True` that fail are blocking. A model with any critical failure cannot pass the promotion gate for that lane. Critical failures are reported separately from non-critical task failures.

### Gates

Each lane has specific gates:
- **D-lane** — `daily_default_gate`: must pass for a model to be considered for daily-use routing.
- **R-lane** — `real_life_gate`: high-risk PA behavior; requires 3+ repeats.
- **H-lane** — `held_out_gate`: ≥0.85 weighted, zero critical failures, ≥90% JSON exact.
- **Tool-live** — `tool_live_gate`: requires complete coverage, exact route identity, and zero critical failures.

### Token metrics

Each runner reports:
- `mean_prompt_tokens` — average input tokens per cell.
- `mean_response_tokens` — average output tokens per cell.
- `total_response_tokens` — total output tokens across all cells.

Missing telemetry is reported as unknown; it is never estimated into a cost comparison.

### Decision order

The quality-first decision order is:

`complete route evidence → required-lane eligibility → minimum true repeat depth → zero blocking critical failures → worst required-lane quality → risk-ordered lane quality → strict-format reliability → token/resource cost → elapsed time`

Local and cloud models are separate decision categories. There is no universal local-vs-cloud winner.

## Adding private fixtures

The suite uses synthetic, non-personal fixtures for all tracked tests. If you need to test with real (private) data, set the environment variable:

```bash
export PA_BENCHMARK_PRIVATE_FIXTURE_ROOT=/path/to/private/fixtures
```

Private fixtures are:
- Loaded only when the environment variable is set.
- Never copied into or tracked by the repository.
- Never sent to cloud models without explicit approval.
- Kept separate from synthetic tracked fixtures.

The private fixture root should mirror the structure of the synthetic fixtures but with your real data. See the fixture loading code in each runner for the expected format.

## Project structure

```
benchmark_pa-model/
├── scripts/                  # Benchmark runners and infrastructure
│   ├── pa_daily_use_benchmark.py       # D-lane
│   ├── pa_real_life_pack_benchmark.py  # R-lane
│   ├── pa_typical_workload_benchmark.py # W-lane
│   ├── pa_conflict_retrieval_benchmark.py # F-lane
│   ├── pa_extended_capability_benchmark.py # X-lane
│   ├── run_t01_t12_full_matrix_profiled.py # T-lane
│   ├── pa_tool_live_benchmark.py       # Tool-live
│   ├── pa_held_out_benchmark.py        # H-lane
│   ├── mb006_preflight.py             # Roster preflight
│   ├── model_prompt_profiles.py        # Model registry
│   ├── benchmark_decision.py           # Category selector
│   └── test_*.py                       # Unit tests
├── prompts/guides/           # Prompt engineering guides
│   └── TEMPLATE.md           # Template for new guides
├── docs/                     # Standards, plans, decisions
│   └── standards/
│       └── benchmark-operating-standard.md
├── artifacts/                # Generated run output (gitignored)
├── ADOPTION.md               # This file
├── CONTRIBUTING.md           # Contribution guidelines
├── LICENSE                   # MIT
└── README.md                 # Project overview
```
