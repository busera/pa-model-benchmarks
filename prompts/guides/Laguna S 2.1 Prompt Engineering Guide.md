---
title: "Laguna S 2.1 — Prompting Best Practices"
date_created: 2026-07-25
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - coding
  - reference
  - ollama
  - poolside
  - laguna
models:
  - laguna-s-2.1:q4_K_M
  - laguna-xs-2.1:q8_0
  - laguna-xs-2.1:q4_K_M
  - poolside/Laguna-S-2.1
  - poolside/Laguna-XS-2.1
sources:
  - "https://huggingface.co/poolside/Laguna-S-2.1"
  - "https://poolside.ai/blog/introducing-laguna-s-2-1"
  - "https://ollama.com/library/laguna-s-2.1"
---
# Laguna S 2.1 — Prompting Best Practices

> Compiled from Poolside HuggingFace model card, release blog, and Ollama library page.
> Retrieved: 2026-07-25

Laguna S 2.1 is a 118B total parameter Mixture-of-Experts (MoE) model with 8B activated
parameters per token, designed for agentic coding and long-horizon work. It is a
code-specialist from Poolside, not a general-purpose chat model.

## Model positioning

- 118B MoE (8B active per token), 256 routed experts (top-10) + 1 shared expert.
- 48 layers: 12 global attention + 36 sliding-window attention (window 512).
- Context window: 1,048,576 tokens (1M).
- Native reasoning support with interleaved thinking between tool calls.
- Capabilities include completion, tools, and thinking.
- OpenMDW-1.1 license (commercial and non-commercial use permitted).
- Quantized variants: FP8, NVFP4, INT4, GGUF (Q4_K_M used locally).

## Key strength: thinking mode

Poolside reports the greatest delta between thinking and non-thinking mode among all
their models. The internal monologue is especially effective for harder, complex
problems. For agentic coding, they recommend enabling thinking and preserving
reasoning in message history.

Thinking is controlled per request:
- Enable: `enable_thinking: true` (or `--default-chat-template-kwargs '{"enable_thinking": true}'`)
- Disable: `enable_thinking: false`

When thinking is enabled, preserve `reasoning_content` from prior assistant messages
in the conversation history. The model may stop reasoning in follow-up steps if prior
thinking blocks are dropped.

## Coding benchmark prompt pattern

For strict-output coding benchmarks (Stage A drop-in), use final-answer-only mode:

```text
You are a coding implementation model.
Return only valid JSON matching this schema: {"files": [...], "tests": [...], "notes": [...]}
Do not use Markdown fences or surrounding prose.
Modify only the allowed files.
Preserve existing public behavior except for the requested bug/feature.
Include targeted tests and the verification command.
If a requirement is impossible from provided context, return a blocker field instead of inventing code.
```

## Runtime settings

- Stage A (drop-in): `think=false`, `temperature=0.3`, `top_p=0.95` (standard harness).
- Stage B (capability ceiling): `think=true` with preserved reasoning_content for
  harder coding tasks; expect materially higher quality but slower output.
- For structured outputs, use the `format` field with a JSON schema where available.
- Output token budget must be large enough for full file implementations; truncation
  is a failure, not a repair target.

## Vendor benchmark context (upper bounds)

| Benchmark | Score | Notes |
|-----------|-------|-------|
| Terminal-Bench 2.1 | 70.2% | Thinking mode, Poolside harness |
| SWE-Bench Multilingual | 78.5% | Thinking mode |
| SWE-Bench Pro (Public) | 59.4% | Thinking mode |
| DeepSWE v1.1 | 40.4% | Thinking mode, Pool harness |
| SWE Atlas (Codebase QnA) | 46.2% | |
| Toolathlon Verified | 49.7% | |

Per the ollama-local-benchmarking skill, vendor numbers are upper bounds. Stage A
drop-in tests use `think=false` which may underrepresent the model's ceiling.

## PA implications

- Strong candidate for local coding implementation tasks, especially with thinking.
- Stage A (think=false) tests whether it drops into current PA workflows cleanly.
- Stage B (think=true) tests its capability ceiling for harder coding tasks.
- Q4_K_M quantization (75 GB) fits comfortably on 96 GB Apple Silicon with headroom.
- Watch for: thinking-leakage into content field, JSON contract adherence, fence usage.
- If thinking is enabled, capture and separate the `thinking` field from `content`.