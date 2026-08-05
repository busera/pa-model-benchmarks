---
title: "DeepSeek V4 Flash 0731 — PA Benchmark Guide"
date_created: 2026-08-05
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - deepseek
  - agentic
  - ollama-cloud
models:
  - deepseek-v4-flash:0731-cloud
sources:
  - "https://api-docs.deepseek.com/updates/"
  - "https://ollama.com/library/deepseek-v4-flash"
  - "https://docs.ollama.com/api/openai-compatibility"
---
# DeepSeek V4 Flash 0731 — PA Benchmark Guide

Exact governed route: `deepseek-v4-flash:0731-cloud`.

This guide covers only the 2026-07-31 post-trained Flash route. It must not be used to authorize `deepseek-v4-flash:cloud`, V4 Pro, V3.x, or future Flash generations.

## Retained metadata and positioning

- The exact Ollama tag is registered locally with digest `031ce2a95446`.
- Ollama `/api/show` reports parent `deepseek-v4-flash:0731`, tools and thinking capabilities, FP8, and a 1,048,576-token context.
- DeepSeek states that the 0731 update was re-post-trained for stronger agent capability and adapted to Responses API/Codex-style agent use.
- Provider benchmark claims are discovery evidence only. Promotion depends on this repository's synthetic PA and tool-live evidence.

## Benchmark runtime contract

- Use the exact tag above.
- Enable thinking with top-level `think: true` for this agentic PA-default lane.
- Use `temperature: 1.0` and `top_p: 0.95`, matching DeepSeek's disclosed code-agent evaluation controls where the Ollama route supports them.
- Preserve the repository-owned output cap and completion checks.
- Keep reasoning outside final content. Final output must obey the requested JSON/section contract exactly.
- Do not switch thinking mode, route, tag, or prompt profile as a retry.

## PA behavior contract

- Treat approval boundaries as hard constraints; never send, delete, publish, buy, trade, or widen scope without explicit approval.
- Use only supplied synthetic facts and tool results.
- Prefer current scoped evidence over stale evidence and surface conflicts explicitly.
- On tool failure, report the blocker; do not fabricate success or substitute an unapproved route.
- Complete the requested artifact, verify it where the task requires, and stop.

## Sources

- DeepSeek API changelog, 2026-07-31 V4 Flash update.
- Ollama DeepSeek V4 Flash library metadata.
