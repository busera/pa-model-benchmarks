---
title: "Qwen3-Coder — Prompting Best Practices"
date_created: 2026-06-26
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - qwen
  - coding
  - reference
  - ollama
models:
  - qwen3-coder:480b-cloud
  - Qwen3-Coder-480B-A35B-Instruct
  - Qwen3-Coder-Next
sources:
  - "https://github.com/QwenLM/Qwen3-Coder"
  - "https://qwen.ai/blog?id=qwen3-coder"
  - "https://qwen.readthedocs.io/en/latest/framework/function_call.html"
  - "https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output"
---
# Qwen3-Coder — Prompting Best Practices

> Compiled from Qwen3-Coder GitHub, Qwen blog, Qwen function-calling docs, and Alibaba structured-output documentation.
> Retrieved: 2026-06-26

Qwen3-Coder is a code-specialist family for agentic coding, repository-scale tasks, and tool workflows. It should be benchmarked as an implementation challenger, not as a broad PA fallback unless separately tested.

## Model positioning

- Qwen3-Coder-480B-A35B-Instruct is a 480B MoE model with 35B active parameters and 256K native context, extendable to 1M.
- The family is optimized for agentic coding, browser-use, and tool-use.
- Qwen3-Coder function calling relies on updated Qwen tool parsers in SGLang/vLLM; ensure runtime parser compatibility before judging tool-call failures.
- Qwen3-Coder instruct models are non-thinking chat models and should not emit thinking blocks in normal output.

## Coding benchmark prompt pattern

Use strict, repo-shaped contracts:

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

- Prefer non-thinking / final-only mode.
- Use enough output tokens for full patches; truncation should be scored as failure, not manually repaired.
- For structured outputs, use provider JSON schema mode where available.
- For tool use, verify the runtime supports Qwen's parser/special tokens before concluding the model is at fault.

## PA implications

- Good candidate for repo-shaped implementation tasks with executable verification.
- Keep GPT-5.5 or another frontier reviewer as final reviewer for high-risk PA code.
- Do not use coding benchmark success as evidence for email, health, finance, or notification routing.

## Sources

- QwenLM/Qwen3-Coder GitHub — model variants, non-thinking chat note, function-calling parser caveat.
- Qwen blog — 480B/35B active, 256K context, agentic coding and Qwen Code positioning.
- Qwen function-calling docs — tool-call framework.
- Alibaba Model Studio structured-output docs — JSON object/schema enforcement.
