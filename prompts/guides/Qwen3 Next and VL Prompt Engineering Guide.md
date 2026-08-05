# Qwen3 Next and VL Prompt Engineering Guide

Source status: created 2026-06-28 from Qwen official quickstart guidance and current benchmark needs.

## Sources checked

- Qwen official ReadTheDocs quickstart: Qwen3 model families, thinking vs non-thinking behavior, recommended generation parameters.
- Ollama thinking-control guidance: use the provider/runtime thinking switch where available; PA benchmarks require clean final-answer content.

## Qwen-family generation guidance

For non-thinking/instruct-style Qwen tasks, the Qwen docs recommend:

- `temperature=0.7`
- `top_p=0.8`
- `top_k=20`
- `min_p=0`
- presence penalty between 0 and 2 where supported, with higher values risking language mixing.

For thinking-style Qwen tasks, docs commonly recommend:

- `temperature=0.6`
- `top_p=0.95`
- `top_k=20`
- `min_p=0`

the benchmark harness is final-answer/contract based, so use non-thinking mode unless explicitly evaluating reasoning traces.

## Prompting rules for Qwen3 Next

1. Use a strong system prompt as the behavioral anchor.
2. State uncertainty permission explicitly: do not fabricate missing facts.
3. Use clear delimiters/conceptual boundaries for source material and required output.
4. For JSON tasks, demand raw JSON only and exact keys.
5. For section tasks, list required section labels in order.
6. Disable thinking / hidden reasoning in final benchmark output.

## Prompting rules for Qwen3 VL / vision tags

1. State the visual task explicitly: identify, describe, compare, extract table/chart data, or assess uncertainty.
2. Require uncertainty labeling when image details are unreadable or unavailable through the current route.
3. Do not let the model invent image facts not present in the prompt or attached image path.
4. For chart/table/image tasks, request structured observations first, then concise conclusion.
5. Keep the same deterministic validators; vision capability is scored separately, not given a pass for prose plausibility.

## Runtime defaults for deterministic PA benchmarks

- API: Ollama `/api/chat`
- `stream=false`
- `think=false` where supported
- `temperature=0.7`
- `top_p=0.8`
- `top_k=20`
- `min_p=0.0`
- `presence_penalty=1.5` for Qwen3 Next / text tasks when supported
- `repeat_penalty=1.0`

## Caveats

- If a cloud Qwen tag is listed but `/api/show` returns Gone/unavailable, exclude it from the run and record availability failure.
- Qwen3 VL via Ollama must be verified for actual image input support before treating X01 as a true vision result.
