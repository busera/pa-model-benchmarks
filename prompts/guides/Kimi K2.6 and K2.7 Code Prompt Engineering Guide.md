---
title: "Kimi K2.6 and K2.7 Code — Prompting Best Practices"
date_created: 2026-06-26
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - kimi
  - moonshot
  - reference
  - ollama
  - coding
models:
  - kimi-k2.6:cloud
  - kimi-k2.7-code:cloud
  - moonshotai/Kimi-K2.6
sources:
  - "https://docs.together.ai/docs/kimi-k2.6-quickstart"
  - "https://github.com/MoonshotAI/Kimi-K2/blob/main/docs/tool_call_guidance.md"
  - "https://platform.kimi.ai/docs/guide/use-kimi-api-to-complete-tool-calls"
  - "https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart"
---
# Kimi K2.6 and K2.7 Code — Prompting Best Practices

> Compiled from Together AI Kimi K2.6 docs, MoonshotAI Kimi-K2 tool-calling guidance, and Kimi platform docs.
> Retrieved: 2026-06-26

This guide covers Kimi K2.6 as PA's broad non-GPT fallback candidate and Kimi K2.7 Code as a coding-lane challenger. Treat Kimi as a strong agentic / multimodal / tool-calling family, but do not assume broad PA safety without explicit JSON, approval, and source-boundary validation.

## Model positioning

| Model | Role in PA benchmarks | Context / mode | Best fit |
|---|---|---|---|
| `kimi-k2.6:cloud` | PA fallback candidate | 256K context; instant + thinking modes | Broad PA reasoning, long-context, tool workflows, multimodal tasks |
| `kimi-k2.7-code:cloud` | Coding-lane challenger | Coding-focused K2 line | End-to-end coding tasks, repo patches, coding agents |

## Runtime settings

Kimi K2.6 docs distinguish instant and thinking modes:

| Mode | Temperature | top_p | Use |
|---|---:|---:|---|
| Instant / final-answer automation | 0.6 | 0.95 | PA benchmark cells, JSON/sections, no hidden reasoning in final output |
| Thinking mode | 1.0 | 0.95 | Hard reasoning/coding if the harness captures reasoning separately |

For Ollama benchmark runs that require clean `content`, use `think=false` where supported and treat reasoning fields as non-final.

## Prompting pattern for PA automation

Use a substantial system message. Include:

```text
You are the PA benchmark candidate.
Return final answer only.
Do not include hidden reasoning, scratchpad, code fences, or surrounding prose.
For JSON tasks, the first character must be { or [ and the last character must close the JSON.
Use only facts in the prompt; if missing, write a null/empty value or an explicit uncertainty field.
External communications are draft-only unless the user explicitly approved sending.
```

## Tool calling

Moonshot's tool guidance uses OpenAI-style tool definitions with JSON Schema parameters. The model may return `finish_reason='tool_calls'`; the harness must execute the tool, append a `role='tool'` result with `tool_call_id`, and continue until final content is returned.

For PA benchmarks that do not execute tools, do **not** expose fake tools. Test the final-answer contract separately from tool-calling capability.

## Structured output guidance

- Prefer provider/native JSON schema where available.
- If using Ollama chat without schema enforcement, add a strict final-only system message and deterministic validator.
- Do not accept Markdown-fenced JSON in automation lanes.
- Use retries only as a measured adapter path; record adapter complexity.

## PA implications

- Kimi K2.6 can be a broad fallback only when it passes Real-Life Pack and scenario lane gates.
- Kimi K2.7 Code should be evaluated in repo-shaped coding tasks, not broad PA tasks, unless separately benchmarked.
- Multimodal claims need image/screenshot tests before use in Play/PWA/desktop automation lanes.

## Sources

- Together AI Kimi K2.6 quickstart — instant/thinking mode, temperature 0.6 vs 1.0, 256K context, vision/tool support.
- MoonshotAI Kimi-K2 tool calling guidance — JSON Schema tool definitions, OpenAI-style tool loop, `tool_calls` lifecycle.
- Kimi platform K2.7 Code quickstart — coding-focused model positioning.
