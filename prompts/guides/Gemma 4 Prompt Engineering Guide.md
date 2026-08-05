---
title: "Gemma 4 — Prompting Best Practices"
date_created: 2026-06-26
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - gemma
  - google
  - reference
  - ollama
  - multimodal
models:
  - gemma4:31b-cloud
  - gemma4:31b-it-q8_0
sources:
  - "https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4"
---
# Gemma 4 — Prompting Best Practices

> Compiled from Google AI for Developers Gemma 4 prompt-formatting documentation.
> Retrieved: 2026-06-26

Gemma 4 introduces explicit conversation, modality, thinking, and tool-control tokens. Through Ollama chat the template is mostly handled by the runtime, but benchmark prompts should still respect the model's conversation-level thinking and tool-use design.

## Model positioning

- Gemma 4 supports text, image, and audio inputs, long context up to 256K, thinking mode, and tool-calling control tokens.
- PA evidence keeps `gemma4:31b-cloud` as a structured coding / multimodal challenger, not broad PA fallback.

## Runtime and prompting rules

| Use | Guidance |
|---|---|
| System instructions | Put behavior and thinking/tool settings in one consolidated system turn. |
| Thinking mode | Enable only when the harness can separate private reasoning from final output. For automation benchmarks, prefer final-only / no visible reasoning. |
| Tool calling | Gemma 4 has dedicated tool declaration/call/response tokens. Do not fake tool use in non-tool benchmarks. |
| JSON output | Use provider/schema enforcement where possible; otherwise final-only prompt plus strict validator. |

## PA system-prompt pattern

```text
You are the PA benchmark candidate.
Use the task facts only.
Return the exact requested format.
No hidden reasoning, no Markdown fences around JSON, no surrounding commentary.
If the task requires JSON, return raw JSON only.
```

## Multimodal caution

Gemma 4's image/audio support should be evaluated with explicit screenshot/document/audio cases before routing multimodal PA work to it. Text-only benchmark scores do not prove visual or audio reliability.

## Sources

- Google AI for Developers — Gemma 4 prompt formatting, control tokens, multimodal placeholders, thinking mode, and tool-calling lifecycle.
