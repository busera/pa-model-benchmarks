---
title: "Mistral — Prompting Best Practices"
date_created: 2026-06-26
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - mistral
  - reference
  - ollama
models:
  - mistral-large-3:675b-cloud
  - mistral-small3.2:24b
sources:
  - "https://docs.mistral.ai/models/best-practices/prompt-engineering"
---
# Mistral — Prompting Best Practices

> Compiled from Mistral's official prompt-engineering documentation.
> Retrieved: 2026-06-26

Mistral's official guidance emphasizes clear, complete, hierarchical prompts, Markdown/XML structure, examples for format control, and provider-enforced JSON output where predictable structured responses are required.

## Runtime and prompting rules

| Scenario | Guidance |
|---|---|
| General PA tasks | Role + purpose in system prompt; self-contained user prompt. |
| Structured output | Use JSON output format / schema enforcement where available. Otherwise provide exact schema and reject fenced/surrounding text. |
| Complex context | Use Markdown headings or XML-style tags for context, task, constraints, and output contract. |
| Examples | Few-shot examples can help format adherence; keep examples close to the real task. |

## PA prompt pattern

```text
You are Andrew's PA benchmark candidate. Your task is to complete the specified benchmark case.
<context>...</context>
<constraints>...</constraints>
<output_contract>Return exactly ...</output_contract>
Before finalizing, silently check that the output matches the requested schema. Return only the final answer.
```

## PA caveat

Both Mistral Large 3 and local Mistral have shown schema/fence fragility in PA tests. Do not use them for strict PA routing unless a model-specific adapter plus native JSON mode passes the same gates.

## Sources

- Mistral Docs — Prompting: clear/complete prompts, hierarchical structure, Markdown/XML formatting, examples, and structured output enforcement.
