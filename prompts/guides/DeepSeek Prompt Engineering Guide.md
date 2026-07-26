---
title: "DeepSeek V3 & R1 — Prompting Best Practices"
date_created: 2026-04-07
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - deepseek
  - reference
  - ollama
models:
  - deepseek-v3.2:cloud
  - deepseek-r1:32b
sources:
  - "https://api-docs.deepseek.com/"
  - "https://github.com/deepseek-ai/deepseek-r1"
  - "https://docs.ollama.com/capabilities/thinking"
---

# DeepSeek V3 & R1 — Prompting Best Practices

> Compiled from official DeepSeek API docs, R1 GitHub README, arxiv paper, and community findings.
> Retrieved: 2026-04-07

This guide covers two DeepSeek models used by PA skills via Ollama: `deepseek-v3.2:cloud` (analysis fallback) and `deepseek-r1:32b` (local fallback).

---

## Model Overview

| Model | Params | Type | Context | Best For |
|-------|--------|------|---------|----------|
| DeepSeek-V3 (v3.2) | 671B MoE (~37B active) | Cloud via Ollama | 128K | Chat, analysis, coding, structured output |
| DeepSeek-R1 (32B) | 32B dense (distilled from 671B R1) | Local | 128K | Multi-step reasoning, math, logic |

**R1-32B is a Qwen-32B base model** distilled from the full R1 — this affects prompting strategies significantly.

---

## DeepSeek-V3 (v3.2) — Standard Chat Model

V3 behaves similarly to GPT-4o and Claude. Standard prompting patterns transfer directly.

### System Prompts
Use normally. Three-tier structure works well: system message (role/tone/scope), user message (task), structured output format.

### Structured Output / JSON
- Set `response_format: {"type": "json_object"}` in the API call
- You **must** include the word "json" in either the system or user prompt
- Provide an example of the desired JSON schema
- Set `max_tokens` high enough to avoid truncation mid-JSON

### Temperature
- 0.0-0.3 for deterministic/extraction tasks
- 0.4-0.7 for balanced creative/analysis
- Higher for brainstorming

### Few-Shot Examples
Supported and effective. Use them to correct consistent failure modes.

### Prompt Caching
The API caches disk-side in 64-token units. Stable prefixes (system prompt + shared context) get up to 90% cost discount on repeated calls. For Ollama cloud proxy, keep system prompts consistent across calls to help KV cache reuse.

### Performance Notes
- Very slow on large contexts via Ollama cloud proxy (388s for 25K transcript, timeout on 122K)
- Highest analysis quality among tested models (9.5/10 in A/B test)
- Reliable for short-to-medium transcripts (<30K chars)

---

## DeepSeek-R1 (32B) — Reasoning Model

**R1 requires fundamentally different prompting than V3, Claude, or GPT.** Do not transfer standard patterns.

### Critical: No System Prompt

All instructions go in the user message. System prompts **degrade R1's performance** — the distilled model was not trained to handle them.

### Critical: No Few-Shot Examples

Few-shot examples **degrade performance**. R1 attempts to mimic the pattern of examples rather than using its reasoning capabilities. Use zero-shot with clear format description instead.

### Critical: Temperature 0.6 Minimum

Lower temperature causes degenerate repetition loops. Official recommendation:
- **Temperature: 0.6** (optimal)
- **Top-p: 0.95**
- Never use greedy decoding (temp 0.0) with R1

### Thinking Mode

R1 uses `<think>...</think>` tags for chain-of-thought reasoning before the final answer.

**think: true (default):**
- Model outputs reasoning block, then final answer
- Better accuracy on complex reasoning tasks
- Higher token cost (reasoning + answer tokens)

**think: false:**
- Suppresses reasoning trace; model outputs answer directly
- Faster, fewer tokens
- Quality may drop on tasks that benefit from multi-step reasoning

**Force thinking when skipped:** R1 occasionally bypasses its thinking phase. If output quality drops, prepend `<think>\n` as assistant prefill to force reasoning.

### Don't Say "Think Step by Step"

R1 reasons natively. Adding chain-of-thought instructions is redundant and sometimes harmful. Keep prompts simple and direct.

### Chain-of-Draft Technique (Token Savings)

If you keep thinking ON, add: "Think step by step, but only keep a minimum draft for each thinking step, with 5 words at most." This reportedly reduces thinking tokens by up to 80% while maintaining reasoning quality.

### What Transfers from Claude/GPT

| Aspect | Transfers? | Notes |
|--------|-----------|-------|
| System prompts | **No** | Put everything in user message |
| Few-shot examples | **No** | Degrades performance; use zero-shot |
| "Think step by step" | **No** | Redundant, sometimes harmful |
| Low temperature | **No** | Use 0.6 minimum |
| Detailed task description | **Yes** | Clear, concise instructions work well |
| Output format specification | **Yes** | Describe desired format in plain language |
| JSON mode | **Yes** | Include "json" keyword in prompt |

---

## Comparison Table

| Aspect | V3 (v3.2) | R1 (32B) |
|--------|-----------|----------|
| System prompt | Use normally | **Avoid entirely** |
| Few-shot | Helpful | **Degrades performance** |
| CoT prompting | Sometimes helps | **Unnecessary** (native reasoning) |
| Temperature | 0.0-0.7 | **0.5-0.7 (0.6 optimal)** |
| Top-p | 1.0 default | **0.95** |
| Best for | Chat, analysis, structured output | Math, logic, multi-step reasoning |
| Speed (local) | N/A (cloud only) | ~66s for 25K transcript |
| Quality (analysis) | 9.5/10 | 4.5/10 (too thin for long-form) |

---

## Implications for PA Skills

### podcast_summaries (R1 as fallback)
When the fallback chain hits `deepseek-r1:32b`, the prompt should differ from the qwen3.5-coding primary:
- Strip the system prompt; move all instructions into the user message
- Remove few-shot examples if present
- Set temperature to 0.6, top_p to 0.95
- Consider whether think mode helps (analysis benefits from reasoning, so `think: true` may be better here)

**A/B test finding:** R1-32B produced only 538 words on a 25K transcript (vs 2,265 from qwen3.5). The model's reasoning architecture is optimized for step-by-step problem solving, not long-form structured generation. Consider removing R1 from the podcast analysis fallback chain.

### rss-daily-brief and other skills
`deepseek-v3.2:cloud` works with standard prompting. The main issue is latency — it's too slow for automated cron pipelines on long contexts.

---

## Sources

- [DeepSeek Official API Docs](https://api-docs.deepseek.com/) — JSON mode, tool calls, context caching, prompt library
- [DeepSeek-R1 GitHub README](https://github.com/deepseek-ai/deepseek-r1) — Official prompting recommendations (most authoritative)
- [DeepSeek-R1 Paper (arxiv 2501.12948)](https://arxiv.org/abs/2501.12948) — Training methodology, distillation
- [DeepSeek-R1-Distill-Qwen-32B HuggingFace](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B) — Model card
- [Ollama Thinking Docs](https://docs.ollama.com/capabilities/thinking) — think parameter API reference
- [Together AI R1 Prompting Guide](https://docs.together.ai/docs/prompting-deepseek-r1) — Practical recommendations
- [BentoML Complete DeepSeek Guide](https://www.bentoml.com/blog/the-complete-guide-to-deepseek-models-from-v3-to-r1-and-beyond)
- [Helicone Thinking Models Guide](https://www.helicone.ai/blog/prompt-thinking-models) — Chain-of-Draft
- [HuggingFace R1-Distill-Qwen-32B Discussion](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B/discussions/2) — System prompt degradation
