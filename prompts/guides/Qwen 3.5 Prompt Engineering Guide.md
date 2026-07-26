---
title: "Qwen 3.5 — Prompting Best Practices"
date_created: 2026-04-07
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - qwen
  - reference
  - ollama
models:
  - qwen3.5:35b-a3b-coding-nvfp4
  - qwen3.5:35b
sources:
  - "https://huggingface.co/Qwen/Qwen3.5-35B-A3B"
  - "https://github.com/QwenLM/Qwen3.5/blob/main/README.md"
  - "https://docs.ollama.com/capabilities/thinking"
  - "https://huggingface.co/blog/qwen-3-chat-template-deep-dive"
---

# Qwen 3.5 — Prompting Best Practices

> Compiled from official HuggingFace model cards, Qwen GitHub, Ollama docs, and community findings.
> Retrieved: 2026-04-07

This guide covers the Qwen 3.5 model family run locally via Ollama, specifically the `qwen3.5:35b-a3b-coding-nvfp4` variant used by PA skills (podcast_summaries, doc_sort, obs_teach-me, rss-daily-brief).

---

## Chat Template

Qwen 3.5 uses ChatML format with `<|im_start|>` and `<|im_end|>` tokens. When using Ollama's `/api/chat` endpoint, this is handled automatically — just pass `messages` with `role` and `content`.

Unlike Qwen 2.5, Qwen 3.5 ships with **no default system prompt**. Your system prompt is the only behavioral anchor.

---

## System Prompt: Must Be Substantive

**This is the most critical finding.** Qwen 3.5 requires a detailed system prompt. Without one (or with a short one), the model enters pathological loops where it endlessly reconsiders formatting decisions.

Recommendations:
- Always provide a detailed system prompt — not just a one-liner
- Include explicit formatting constraints (output format, tone, length)
- Include explicit permission to express uncertainty (reduces confident hallucination)
- Specify what NOT to do (e.g., "No extra text or explanations" for JSON tasks)
- A 2-line system message is dangerously short for Qwen 3.5

What works: long, structured system prompts similar to Claude or GPT. The model follows detailed instructions well once they are present.

---

## Thinking Mode and `think: false`

**Default:** Qwen 3.5 thinks by default, wrapping reasoning in `<think>...</think>` tags.

**Qwen 3.5 vs Qwen 3:** Qwen 3 supported `/think` and `/nothink` soft switches in the user message. Qwen 3.5 does **not** support these. You must disable thinking via API parameters only.

**Ollama-specific:**
- **Chat API (`/api/chat`):** Pass `"think": false` as a **top-level** parameter (not inside `options`). This works correctly.
- **Generate API (`/api/generate`):** `think: false` is **broken** for Qwen 3.5 — the model still thinks and exhausts `num_predict` tokens, returning empty responses. Avoid this API.
- **Content fallback:** The pattern `msg.get("content", "") or msg.get("thinking", "")` is the correct safety net.

**Impact on quality:** With `think: false`, the model produces direct responses without reasoning traces. For structured analysis tasks (podcast summaries, doc analysis), this is the right choice — the reasoning would consume tokens without adding value to the final output. Instruction-following remains strong in non-thinking mode.

---

## Recommended Sampling Parameters

Official Qwen team presets (from HuggingFace model card):

| Mode | Task Type | temp | top_p | top_k | presence_penalty |
|------|-----------|------|-------|-------|-----------------|
| Non-thinking | General | 0.7 | 0.8 | 20 | 1.5 |
| Non-thinking | Reasoning | 1.0 | 1.0 | 40 | 2.0 |
| Thinking | General | 1.0 | 0.95 | 20 | 1.5 |
| Thinking | Coding | 0.6 | 0.95 | 20 | 0.0 |

**For PA analysis tasks** (non-thinking, structured analysis): use **temp 0.7, top_p 0.8, top_k 20, presence_penalty 1.5**.

Critical warnings:
- **Greedy decoding (temp 0.0) degrades quality.** The official recommendation starts at 0.6.
- **presence_penalty is important** — prevents repetition loops. Values 1.0-2.0 recommended. In Ollama, this maps to `repeat_penalty` in the options block.
- Community tip: `min_p=0.2` (instead of 0.0) prevents derailment during long generations.

---

## Prompt Structure: XML vs Markdown

Qwen 3.5 handles both XML tags and markdown formatting well. It is among the best models at following XML output structures.

**Practical guidance:**
- Use **XML tags** for delimiting input sections (e.g., `<transcript>`, `<instructions>`, `<constraints>`) — they provide unambiguous boundaries that survive tokenization better than whitespace
- Use **markdown** for specifying the desired output format (headings, tables, bullets) — the model follows markdown formatting instructions reliably
- Mixing XML delimiters for input sections with markdown for output format is the most robust pattern

Example:
```
<instructions>
Your task description here with explicit constraints.
</instructions>

<context>
Episode: ...
Podcast: ...
</context>

<transcript>
{transcript text}
</transcript>
```

---

## Coding Models vs General Models

Qwen 3.5 does **not** have separate "Coder" variants. Unlike Qwen 3 (which had Qwen3-Coder), Qwen 3.5 unifies coding capability into all models through joint multimodal training.

The `-coding` suffix on the Ollama tag (`qwen3.5:35b-a3b-coding-nvfp4`) refers to the quantization/packaging variant, not a different model architecture. No special "coding-specific" prompt patterns are needed.

**Tool calling note:** Qwen 3.5 was trained on the Qwen3-Coder XML format for tool calling, not the Hermes-style JSON format. This matters if you add function-calling features.

---

## Differences from Claude/GPT

| Aspect | Claude/GPT | Qwen 3.5 |
|--------|-----------|-----------|
| System prompt length | Works fine with short prompts | **Needs substantial system prompt** or degrades |
| Thinking control | N/A (Claude) / reasoning_effort (GPT) | `think: false` top-level param, no soft switches |
| Temperature | 0.0-1.0 typical | Official: 0.6-1.0; greedy (0.0) **degrades quality** |
| Presence penalty | Optional | **Recommended** (1.5 general, 2.0 reasoning) |
| Format adherence | Strong with minimal prompting | Strong but needs explicit constraints in system prompt |
| Hallucination | Hedges naturally (Claude) | Will hallucinate confidently unless given explicit permission to hedge |

---

## Actionable Changes for PA Skills

1. **Expand the system message** — move constraints and behavioral rules into the system prompt (not just the user prompt)
2. **Raise temperature** from 0.3 to 0.7 (official recommendation for non-thinking general tasks)
3. **Add `repeat_penalty: 1.5`** to the Ollama options block
4. **Wrap input sections in XML tags** (`<transcript>`, `<episode_info>`, `<instructions>`)
5. **Add explicit uncertainty permission** to system prompt: "If you cannot determine something from the transcript, state that explicitly rather than speculating."

---

## Sources

- [Qwen3.5-35B-A3B Model Card (HuggingFace)](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) — official sampling parameters, thinking mode
- [Qwen3.5 GitHub README](https://github.com/QwenLM/Qwen3.5/blob/main/README.md) — model variants, deployment
- [Ollama Thinking Docs](https://docs.ollama.com/capabilities/thinking) — `think` parameter behavior
- [HuggingFace Blog: Qwen-3 Chat Template Deep Dive](https://huggingface.co/blog/qwen-3-chat-template-deep-dive) — ChatML format
- [Hacker News: Qwen3.5 system prompt discussion](https://news.ycombinator.com/item?id=47201388) — community reports on long system prompt requirement
- [Qwen3 Prompt Engineering Guide (Structured Output)](https://qwen3lm.com/qwen3-prompt-engineering-structured-output/)
- [Ollama GitHub Issue #14793](https://github.com/ollama/ollama/issues/14793) — generate API ignores think=false
- [SWIFT Qwen3 Best Practices](https://swift.readthedocs.io/en/v3.5/BestPractices/Qwen3-Best-Practice.html)
