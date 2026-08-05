# Prompt Engineering Guide Template

Replace this template with model-specific guidance. The benchmark harness hashes the guide bytes at run time, so the file you register in `scripts/model_prompt_profiles.py` must exist and match.

## Model identity

- **Name:** [Model name, e.g., "MyModel 7B"]
- **Tag:** [Exact Ollama tag, e.g., "mymodel:7b"]
- **Thinking mode:** [Yes/No — does the model support a thinking/reasoning mode?]

## System prompt guidance

You are a PA benchmark candidate. Your task is to complete the specified benchmark case.

Follow the common PA contract:
- Read the task prompt carefully and return only the requested format.
- For JSON tasks, return raw valid JSON with exactly the requested keys.
- For section tasks, return exactly the requested section headers.
- Do not add markdown fences around JSON.
- Do not add analysis, reasoning, or commentary outside the requested format.
- Preserve approval and scope boundaries exactly as stated in the task.
- Use English only unless the task explicitly requests another language.
- Do not invent data, prices, health diagnoses, or evidence not supplied in the task.

## Model-specific notes

Add model-specific guidance here:
- Decoding parameters that work best (temperature, top_p, etc.)
- Known failure modes to avoid (e.g., verbose output, fence-wrapping JSON)
- Whether thinking mode is recommended for this benchmark
- Any format quirks (e.g., the model tends to add preamble before JSON)

## Registered profile

In `scripts/model_prompt_profiles.py`, register this guide:

```python
profiles["mymodel:7b"] = PromptProfile(
    name="mymodel",
    guide="Prompt Engineering Guide Template.md",
    system_suffix="""Model-specific system suffix text here.""",
    top_level={"think": False},
    options={"temperature": 0.2, "top_p": 0.95},
)
```

## Serial schedule

Add the model tag to `FROZEN_SERIAL_SCHEDULE` in `scripts/mb006_preflight.py`:

```python
FROZEN_SERIAL_SCHEDULE = [
    # ... existing models ...
    "mymodel:7b",
]
```

And register the digest:

```python
FROZEN_REGISTRATION = {
    # ... existing models ...
    "mymodel:7b": {"digest": "<digest from `ollama list`>", "registration": "ollama_list_metadata_only"},
}
```