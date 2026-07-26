---
title: "GLM 5.2 — Prompting Best Practices"
date_created: 2026-06-26
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - glm
  - z-ai
  - reference
  - ollama
  - coding
models:
  - glm-5.2:cloud
  - zai-org/GLM-5.2
sources:
  - "https://docs.together.ai/docs/glm-5.2-quickstart"
  - "https://huggingface.co/blog/zai-org/glm-52-blog"
  - "https://semgrep.dev/blog/2026/we-have-mythos-at-home-glm-52-beats-claude-in-our-cyber-benchmarks"
  - "https://www.interconnects.ai/p/glm-52-is-the-step-change-for-open"
---
# GLM 5.2 — Prompting Best Practices

> Compiled from Together AI GLM-5.2 quickstart, Z.ai/Hugging Face release material, and independent commentary/benchmark writeups.
> Retrieved: 2026-06-26

GLM 5.2 is built for long-horizon coding and agentic work. Public evidence supports watchlisting it for human-reviewed coding/agent experiments. PA evidence rejects it for strict automation unless an adapter/harness proves valid final-only output.

## Model positioning

- MoE model designed for long-horizon coding and agentic workflows.
- Supports structured outputs, function calling, streaming, adjustable reasoning effort, and large context.
- Together AI route exposes `zai-org/GLM-5.2` with 262K context; Ollama Cloud tag tested as `glm-5.2:cloud` reports 1M context.

## Runtime settings

| Scenario | Reasoning | Temperature | top_p | Notes |
|---|---|---:|---:|---|
| Coding agent / long-horizon planning | enabled, effort `high` or `max` | 1.0 | 0.95 | Stream and capture reasoning separately; set generous token budget. |
| PA strict JSON / automation | disabled where supported | 1.0 initially; test 0.6/0.2 adapter if fences persist | 0.95 | Final answer only; schema validation mandatory. |
| Simple factual / short answer | disabled | provider default or low temp | 0.95 | Prefer faster final-only route. |

## Critical PA caveat

In PA tests, `glm-5.2:cloud` repeatedly produced Markdown-fenced JSON or visible scaffolding despite final-only instructions. Therefore:

- Do not use it for state-changing PA automation.
- Do not route strict JSON tasks to it unless provider-native `response_format` / schema enforcement is available and benchmarked.
- Treat any adapter as part of the measured model lane, not as a free correction.

## Prompting pattern for adapter testing

```text
You are GLM-5.2 running in a production benchmark.
Return FINAL ANSWER ONLY.
Do not include analysis, planning, requirement parsing, Markdown, or code fences.
For JSON tasks: output raw valid JSON only. The first character must be { or [. The last character must be } or ].
If a required value is not in the prompt, use null or an explicit uncertainty field; do not invent it.
```

## Best use in PA

- Watchlist: human-reviewed coding/prose, long-horizon codebase experiments, cyber/code analysis.
- Reject for now: inbox triage automation, Obsidian edits, notification sending/drafting pipelines, strict JSON coding harnesses.

## Sources

- Together AI GLM-5.2 quickstart — thinking default, reasoning effort, structured output/function-calling support, temp/top_p examples.
- Z.ai / Hugging Face GLM-5.2 blog — 1M context and long-horizon coding claims.
- Semgrep GLM 5.2 cyber benchmark — strong prompt-only IDOR results and the lesson that harness matters.
- Interconnects AI analysis — open-weight coding-agent threshold commentary.
