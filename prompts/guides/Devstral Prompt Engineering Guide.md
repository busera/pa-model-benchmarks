# Devstral Prompt Engineering Guide

Source status: created 2026-06-28 from live web lookup and Mistral-family guidance. Use for PA benchmark prompt/runtime profiles until superseded by a richer vendor-specific guide.

## Sources checked

- Mistral AI prompt-engineering docs: system prompt, clear objectives, examples, constraints, output format.
- Unsloth Devstral run/fine-tune documentation snippet: Devstral official recommended inference temperature range is low, around `0.0` to `0.15`.

## Benchmark profile intent

Devstral is a Mistral/code-agent-family model. For Andrew's PA benchmarks, treat it as a coding/agentic specialist candidate, not a broad PA default until the Real-Life and Typical packs prove otherwise.

## Prompting rules

1. Use a clear system turn with the role, boundaries, and exact output contract.
2. Keep instructions hierarchical: objective → constraints → required format → evidence/grounding rules.
3. For coding tasks, require a narrow patch/JSON contract and forbid unrelated file changes.
4. For PA safety tasks, keep external communication draft-only unless explicit approval is present.
5. For JSON tasks, require raw JSON only: no Markdown fences, no prose, no comments.
6. Ask the model to state unsupported values as `null` or explicit uncertainty rather than inventing facts.
7. Do not add task-specific answer hints; prompt adaptation may only improve format control and model-family alignment.

## Runtime defaults for deterministic PA benchmarks

- API: Ollama `/api/chat`
- `stream=false`
- `think=false` where supported by Ollama
- `temperature=0.15`
- `top_p=0.95`

Rationale: Devstral guidance favors low temperature. PA benchmark scoring is contract-heavy, so deterministic/low-variance output matters more than creativity.

## Caveats

- If a Devstral tag behaves like a strict Mistral coding model, coding/patch scores may be more representative than broad PA narrative scores.
- If schema failures appear, do not weaken validators. Record the failure and consider a single documented final-answer/JSON adapter rescue only if the failure is format hygiene rather than capability.
