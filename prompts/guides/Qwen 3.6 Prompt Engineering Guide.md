---
title: "Qwen 3.6 — Prompting Best Practices"
date_created: 2026-04-18
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - qwen
  - reference
  - ollama
  - multimodal
models:
  - qwen3.6:35b-a3b-q8_0
  - Qwen/Qwen3.6-35B-A3B
sources:
  - "https://huggingface.co/Qwen/Qwen3.6-35B-A3B"
  - "https://ollama.com/library/qwen3.6:35b-a3b-q8_0"
  - "https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/23"
  - "https://qwen.ai/blog?id=qwen3.6-35b-a3b"
---

# Qwen 3.6 — Prompting Best Practices

> Compiled from the official HuggingFace model card, the Ollama library Modelfile for `qwen3.6:35b-a3b-q8_0`, and the Qwen team blog post.
> Retrieved: 2026-04-18

This guide covers the Qwen 3.6 model family run locally via Ollama, specifically the `qwen3.6:35b-a3b-q8_0` variant deployed in PA's `shared/llm.py` as the Claude-fallback path for narrative generation (finance reports, spending advisor, portfolio, diarium signal extraction, nutrition priorities).

**Note:** `qwen3.6:35b-a3b-q8_0` is multimodal (text + image input). PA skills currently exercise only the text path; image paths are available without re-quantising.

### Quantisation: why q8_0 inherits the HF preset

- The Ollama library [page for `qwen3.6:35b-a3b-q8_0`](https://ollama.com/library/qwen3.6:35b-a3b-q8_0) ships a Modelfile whose params blob (`presence_penalty: 1.5`, `repeat_penalty: 1`, `min_p: 0`, `temperature: 1`) mirrors the HF card's recommendations (thinking-mode defaults).
- Runtime check (2026-04-18): `curl /api/chat` against this tag with the full non-thinking general preset returns a clean response — both `presence_penalty` and `repeat_penalty` are accepted simultaneously.
- Q8_0 is near-BF16 precision. Bartowski's imatrix GGUF page describes Q8_0 as "extremely high quality, generally unneeded but max available quant"; Qwen's own FP8 variant card states "performance metrics are nearly identical to those of the parent model". Unsloth's Q8_0 GGUF Best Practices section recommends the same sampling parameters as the parent HF card — no variant-specific overrides in any community quant fork we located.
- **Confirmed via firecrawl (2026-04-18)**: searched and scraped the HF model card (`Qwen/Qwen3.6-35B-A3B`), its discussion threads (#14, #23), the Ollama library page and Modelfile blobs for the exact `qwen3.6:35b-a3b-q8_0` tag, Unsloth's Q8_0 GGUF README, Bartowski's imatrix page, and the Qwen3.6 FP8 card. None surface a variant-specific sampling preset — the HF non-thinking general preset applies as-is.
- Other quant tiers (q4, q5, q6) may tolerate slightly higher `temperature` to compensate for quantisation noise — not validated here. Add a variant-specific block if we ever adopt a lower-precision tag.

---

## Chat Template

Qwen 3.6 uses ChatML format with `<|im_start|>` and `<|im_end|>` tokens — identical to Qwen 3.5. When using Ollama's `/api/chat` endpoint, this is handled automatically — just pass `messages` with `role` and `content`.

Like Qwen 3.5, Qwen 3.6 ships with **no default system prompt**. Your system prompt is the only behavioral anchor.

---

## System Prompt: Must Be Substantive

**This rule carries over unchanged from Qwen 3.5.** Qwen 3.6 requires a detailed system prompt. Without one (or with a short one), the model enters pathological loops where it endlessly reconsiders formatting decisions.

Recommendations:
- Always provide a detailed system prompt — not just a one-liner
- Include explicit formatting constraints (output format, tone, length)
- Include explicit permission to express uncertainty (reduces confident hallucination)
- Specify what NOT to do (e.g., "No extra text or explanations" for JSON tasks)
- A 2-line system message is dangerously short

What works: long, structured system prompts similar to Claude or GPT. The model follows detailed instructions well once they are present.

---

## Thinking Mode and `think: false`

**Default:** Qwen 3.6 thinks by default, wrapping reasoning in `<think>...</think>` tags — same as Qwen 3.5.

**No soft switches:** Qwen 3.6 does **not** support `/think` and `/nothink` user-message tokens. You must disable thinking via API parameters only.

**Ollama-specific:**
- **Chat API (`/api/chat`):** Pass `"think": false` as a **top-level** parameter (not inside `options`). Confirmed working against `qwen3.6:35b-a3b-q8_0` (2026-04-18).
- **Generate API (`/api/generate`):** Known broken for Qwen 3.5; untested for 3.6. Prefer `/api/chat`.
- **Content fallback:** The pattern `msg.get("content", "") or msg.get("thinking", "")` remains the correct safety net.

**New in 3.6 — Thinking Preservation:** The model has been additionally trained to **retain thinking traces from historical messages**. Enable via `preserve_thinking: true` (vLLM/SGLang) or `chat_template_kwargs: {"enable_thinking": true, "preserve_thinking": true}` (OpenAI-compatible). Intended for iterative coding or multi-turn agent workflows. Not yet wired into PA skills.

**Impact on quality:** With `think: false`, the model produces direct responses without reasoning traces. For the structured analysis tasks PA uses it for (spending advisor narrative, portfolio interpretation, podcast analysis), this remains the right choice — reasoning tokens without adding final-output value.

---

## Recommended Sampling Parameters

Official Qwen team presets (from HuggingFace model card — Best Practices section):

| Mode | Task Type | temp | top_p | top_k | min_p | presence_penalty | repetition_penalty |
|------|-----------|------|-------|-------|-------|------------------|--------------------|
| Non-thinking | General | 0.7 | 0.8 | 20 | 0.0 | 1.5 | 1.0 |
| Non-thinking | Reasoning | 1.0 | 1.0 | 40 | 0.0 | 2.0 | 1.0 |
| Thinking | General | 1.0 | 0.95 | 20 | 0.0 | 1.5 | 1.0 |
| Thinking | Coding (WebDev) | 0.6 | 0.95 | 20 | 0.0 | 0.0 | 1.0 |

**For PA analysis tasks** (non-thinking, structured narrative): use **temp 0.7, top_p 0.8, top_k 20, min_p 0.0, presence_penalty 1.5, repetition_penalty 1.0**.

Critical clarifications (distinct from Qwen 3.5 guide):
- **`presence_penalty` and `repetition_penalty` are separate parameters.** Both are exposed by Ollama's `/api/chat` options block; both map 1:1 to their HF names. The Qwen 3.5 guide's "presence_penalty maps to repeat_penalty" was a simplification — Qwen 3.6's HF card makes the distinction authoritative.
- **Ollama's `repeat_penalty` parameter corresponds to HF's `repetition_penalty`.** So the correct Ollama options block is: `repeat_penalty: 1.0, presence_penalty: 1.5`.
- **Greedy decoding (temp 0.0) still degrades quality.** The official minimum remains 0.7 for non-thinking general.
- **`presence_penalty` can be tuned 0–2.** Higher values reduce repetition loops but risk language mixing and slight performance drops.
- **`min_p=0.0` is now in the official preset.** In 3.5 community tips suggested `min_p=0.2`; 3.6 walks that back to 0.0 by default.

**PA current state (2026-04-18):** `shared/llm.py::_call_ollama` sends `repeat_penalty: 1.5` (carried over from Qwen 3.5 code) and omits `presence_penalty` and `min_p`. This does not match the official preset. Pending A/B verification before switching — see `shared/scripts/ab_local_models.py` and `memory/project_ollama_mlx.md`.

---

## Prompt Structure: XML vs Markdown

No change from Qwen 3.5. The model handles both XML tags and markdown formatting well.

**Practical guidance:**
- Use **XML tags** for delimiting input sections (e.g., `<transcript>`, `<instructions>`, `<constraints>`) — unambiguous boundaries
- Use **markdown** for specifying the desired output format (headings, tables, bullets)
- Mixing XML delimiters for input with markdown for output is the most robust pattern

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

Qwen 3.6 does **not** have separate "Coder" variants. Like Qwen 3.5, coding capability is unified across the general model through joint multimodal training. The `-q8_0` suffix on the Ollama tag is the quantisation variant, not a different architecture.

**Qwen Code integration:** The Qwen team now ships [Qwen Code](https://github.com/QwenLM/qwen-code), an open-source CLI agent optimised for Qwen models. PA's `code-agent` and `auto-develop` skills remain on Claude for now; Qwen Code is worth evaluating when a local-only coding agent becomes a priority.

**Tool calling note:** Qwen 3.6 continues to use the Qwen3-Coder XML format for tool calling, not the Hermes-style JSON format. Same as 3.5.

---

## Differences from Claude/GPT

| Aspect | Claude/GPT | Qwen 3.6 |
|--------|-----------|-----------|
| System prompt length | Works fine with short prompts | **Needs substantial system prompt** or degrades |
| Thinking control | N/A (Claude) / reasoning_effort (GPT) | `think: false` top-level param, no soft switches; thinking default-on |
| Thinking preservation | Implicit in conversation history | **New 3.6 feature:** `preserve_thinking: true` retains traces across turns |
| Temperature | 0.0-1.0 typical | Official: 0.6-1.0; greedy (0.0) **degrades quality** |
| Penalties | Optional | `presence_penalty` **and** `repetition_penalty` both recommended (1.5 and 1.0 respectively for general non-thinking) |
| Format adherence | Strong with minimal prompting | Strong but needs explicit constraints in system prompt |
| Hallucination | Hedges naturally (Claude) | Will hallucinate confidently unless given explicit permission to hedge |
| Vision input | Built-in across flagships | **Built-in for 3.6** (image-text-to-text); 3.5 text-only guides still applied |
| Context length | 200K (Claude Opus 4.6/4.7) | 262,144 native, extensible to 1,010,000 with YaRN |

---

## Differences from Qwen 3.5

This section captures the deltas that matter for PA's skill ecosystem.

1. **Sampling parameter mapping clarified.** 3.5 guide documented "presence_penalty maps to repeat_penalty in Ollama" as a shortcut. 3.6's HF card is explicit that they are distinct parameters — `presence_penalty=1.5, repetition_penalty=1.0` for non-thinking general. Ollama's `/api/chat` options block supports both simultaneously (verified 2026-04-18). **Action:** `shared/llm.py` should migrate to the split form after A/B verification.
2. **`min_p=0.0` is canonical now.** 3.5 community tips suggested `min_p=0.2` to prevent derailment; 3.6 official preset sets it to 0.0. No action needed unless a skill is explicitly bumping min_p.
3. **Thinking Preservation is new.** 3.6 was additionally trained to leverage historical thinking traces. Useful for multi-turn agents (iterative code review, planning); not yet wired into PA.
4. **Vision is native.** `qwen3.6:35b-a3b-q8_0` accepts image input alongside text. Opens OCR/diagram-description paths we did not have with the 3.5 coding variant. No skill uses this yet.
5. **Context length is much larger.** 262K natively (vs ~128K effective for 3.5); 1M tokens with YaRN config overrides. Useful for doc_indexing and long-transcript podcast analysis, though Ollama's default `num_ctx` caps far below this — would need an explicit `num_ctx` bump in the options block.
6. **Agentic coding improvements.** Qwen team's primary 3.6 claim: "substantial upgrades in agentic coding and frontend/repo-level reasoning." SWE-bench Verified 73.4 (up from 70.0 on 3.5-35B-A3B). Relevant to a future local-only code-review or auto-develop variant.
7. **No architectural soft-switch change.** `/think` and `/nothink` tokens remain unsupported (same as 3.5). Disable via API params only.
8. **Performance parity on general tasks.** On the weekly-finance narrative A/B (1-sample, 2026-04-18), 3.6 produced tighter prose with better category abstraction at 6× the latency of 3.5-coding-nvfp4 (2.5s → 15s). Acceptable for cron/non-interactive paths; unacceptable for interactive skills where fast feedback matters (kept on `"fast"` slot pointing to 3.5-nvfp4).

---

## Actionable Changes for PA Skills

1. **Update `shared/llm.py` Ollama options block** — switch from `{repeat_penalty: 1.5}` to `{repeat_penalty: 1.0, presence_penalty: 1.5, min_p: 0.0}` **after** the `ab_local_models.py` harness confirms non-worse quality + within ±15% latency
2. **Keep temperature floor at 0.7** — confirmed by smoke test (see `shared/data/ab_runs/`); 0.6 and 0.8 produced comparable quality
3. **Cross-link docstrings** — every skill that imports `shared.llm` should link to this guide + the Qwen 3.5 guide (historical) in its header comment
4. **Watch for Thinking Preservation use cases** — multi-turn tool-using agents (future code-agent local variant) should set `preserve_thinking: true`
5. **Consider `num_ctx` bump** for doc_indexing and podcast_summaries if you need >32K context; default Ollama cap is conservative

---

## Sources

- [Qwen3.6-35B-A3B Model Card (HuggingFace)](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) — official sampling parameters, thinking mode, vision, Thinking Preservation
- [Ollama Library — qwen3.6:35b-a3b-q8_0](https://ollama.com/library/qwen3.6:35b-a3b-q8_0) — Modelfile defaults (`presence_penalty: 1.5, repeat_penalty: 1, temperature: 1, min_p: 0`)
- [HuggingFace Discussion #23 — Inconsistent parameters recommendation](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/23) — community-flagged inconsistency between the two param blocks in HF card (affects non-thinking reasoning mode only; non-thinking general is consistent)
- [Qwen3.6 Blog Post](https://qwen.ai/blog?id=qwen3.6-35b-a3b) — release overview, agentic coding benchmarks
- [Qwen Code (GitHub)](https://github.com/QwenLM/qwen-code) — official CLI agent optimised for Qwen
- [Qwen 3.5 Prompt Engineering Guide](Qwen%203.5%20Prompt%20Engineering%20Guide.md) — predecessor reference (rules unchanged except for sampling-param split)
