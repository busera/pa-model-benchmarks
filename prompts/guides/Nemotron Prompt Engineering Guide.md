---
title: "NVIDIA Nemotron — Prompting Best Practices"
date_created: 2026-06-26
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - nemotron
  - nvidia
  - reference
  - ollama
models:
  - nemotron-3-ultra:cloud
  - nvidia/NVIDIA-Nemotron-3-Super-120B-A12B
sources:
  - "https://docs.nvidia.com/nemo/datadesigner/dev-notes/structured-outputs-from-nemotron"
  - "https://deepinfra.com/blog/nvidia-nemotron-3-super-model-overview-guide"
---
# NVIDIA Nemotron — Prompting Best Practices

> Compiled from NVIDIA NeMo Data Designer structured-output notes and public Nemotron 3 Super integration material.
> Retrieved: 2026-06-26

Nemotron should be treated as a long-context, multilingual, structured-output-friendly family. PA evidence keeps it useful for German / domain import routing lanes, but not as the broad winner.

## Model positioning

- Nemotron 3 Super-class materials describe 1M context, function calling, JSON outputs, and multilingual capability.
- NVIDIA's structured-output work emphasizes schema diversity, rejection sampling, and programmatic validation — exactly the operating pattern PA should use for automation.

## Runtime and prompting rules

| Scenario | Guidance |
|---|---|
| JSON / YAML / XML | Provide explicit schema, validate programmatically, and reject malformed output. |
| Long-context retrieval | Put source context before task; require exact source references and uncertainty labels. |
| German/formal output | State target language and allowed exceptions; validate language leakage. |
| PA automation | Use final-only answer, no fences, exact keys, and deterministic validators. |

## PA prompt pattern

```text
You are Andrew's PA benchmark candidate.
Follow the schema exactly. Do not include Markdown fences or commentary.
If a field is not supported by the prompt facts, use null and include the uncertainty in the designated field.
Validate your final answer against the schema before returning it.
```

## Sources

- NVIDIA NeMo Data Designer — structured outputs for Nemotron: schema-constrained JSON/YAML/XML, rejection sampling, validation.
- DeepInfra Nemotron 3 Super overview — 1M context, JSON/function-calling support, multilingual and coding benchmark claims.
