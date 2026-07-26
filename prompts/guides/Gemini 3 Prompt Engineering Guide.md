# Gemini 3 Prompt Engineering Guide

Source status: created 2026-06-28 from Google Gemini 3 developer and structured-output documentation.

## Sources checked

- Google AI for Developers: Gemini 3 Developer Guide.
- Google AI for Developers: Structured outputs / JSON Schema guidance.

## Key source findings

- Google says Gemini 3 is built for reasoning, agentic workflows, coding, and multimodal tasks.
- Gemini 3 uses dynamic thinking by default in the native API; lower thinking levels reduce latency/cost for simpler tasks.
- Google structured-output docs recommend schema-constrained JSON for extraction/classification/tool workflows.
- The native Gemini API can enforce response schemas, but the Ollama Cloud route may not expose the same schema controls. Therefore PA benchmarks must enforce structure through prompt plus deterministic validators.

## Prompting rules

1. Use direct, clear instructions. Avoid over-complicated prompt boilerplate.
2. Put task objective, constraints, and output format near the end of the prompt where practical.
3. For JSON tasks, require raw JSON only and exact keys; no Markdown fences.
4. For multimodal tasks, name the expected evidence: objects, table values, chart trend, visual uncertainty.
5. For source-grounded tasks, explicitly forbid outside facts and require uncertainty for missing inputs.
6. For agentic/coding tasks, define completion criteria and allowed changes.

## Runtime defaults for Ollama Cloud PA benchmarks

- API: Ollama `/api/chat`
- `stream=false`
- `think=false` where supported by Ollama
- `temperature=0.2`
- `top_p=0.95`

Native Gemini thinking controls are not assumed available through the Ollama Cloud tag. If the route later exposes Gemini thinking-level controls, use low/minimal for strict extraction/JSON tasks and medium/high only for deliberate reasoning-lane experiments.

## Caveats

- Do not claim native Gemini schema enforcement if the test path is Ollama Cloud and only prompt-level format control was available.
- Treat Gemini as a cloud/reference challenger; do not compare it to local models without labeling provider-route differences.
