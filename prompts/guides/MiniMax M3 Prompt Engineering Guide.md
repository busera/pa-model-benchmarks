# MiniMax M3 Prompt Engineering Guide

Source status: created 2026-06-28 from available web research plus deterministic PA benchmark requirements. Replace with richer vendor guidance if MiniMax publishes model-specific prompting details.

## Sources checked

- Web search for MiniMax M3 prompt-engineering guidance did not surface a clear authoritative model-specific guide in the first-pass search.
- Generic structured-output best practices were used conservatively: clear final format, low creativity for JSON/schema tasks, explicit no-fabrication rule.

## Benchmark profile intent

Treat `minimax-m3:cloud` as an Ollama Cloud challenger with unknown prompt idiosyncrasies. The prompt profile should avoid creativity and force final-answer hygiene. Do not promote it from vendor claims or generic model reputation.

## Prompting rules

1. Keep the system prompt short, explicit, and contract-oriented.
2. Put the exact output schema or section list in the user task.
3. For JSON, require raw JSON only: no Markdown fences, no prose, no comments.
4. For recommendations, require evidence/assumption separation and concrete next actions.
5. For unavailable facts, require `null`, empty arrays, or explicit uncertainty.
6. Do not include few-shot examples that reveal task-specific answers.

## Runtime defaults for deterministic PA benchmarks

- API: Ollama `/api/chat`
- `stream=false`
- `think=false` where supported
- `temperature=0.2`
- `top_p=0.95`

## Caveats

- If MiniMax output shows chatty scaffolding or non-JSON wrappers, record the failure. A one-pass final-answer adapter rescue is acceptable only if validators remain unchanged.
- Cloud response timing may lack local Ollama eval-duration fields; use lower-bound throughput estimates only.
