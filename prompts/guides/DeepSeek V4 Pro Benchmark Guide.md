# DeepSeek V4 Pro — Benchmark Contract Guide

Exact governed tag: `deepseek-v4-pro:cloud`

## Evidence boundary

This repository has retained synthetic held-out evidence for the exact tag and metadata registration from `ollama list`. The retained run completed 18/18 H-lane cells at three repeats with a 0.9882 weighted score and one critical failure. Those observations do not establish provider availability for a future run and do not justify unstated model capabilities.

No current retained vendor prompt guide for this exact generation is available in the repository. This guide therefore defines only a conservative benchmark contract. It does not transfer DeepSeek V3, R1, or another generation's claimed architecture, context, or reasoning behavior.

## Governed benchmark profile

- API route: Ollama native `/api/chat` after separately approved exact-route preflight.
- Thinking lane: `think=false` only. This is a benchmark lane selection, not a claim about an unsupported alternate mode.
- Sampling: `temperature=0.2`, `top_p=0.95`, retained from the prior exact-tag benchmark profile.
- Prompt: use the common PA system contract, exact output schema or ordered sections, explicit uncertainty permission, and final-answer-only output.
- Validation: reject malformed/recovered format, incomplete completion telemetry, route mismatch, and semantic hard failures separately.

## Prohibitions

- Do not infer guidance from DeepSeek V3 or R1 merely because the family name matches.
- Do not claim callability from registration metadata.
- Do not add a thinking-on lane without exact retained/provider evidence and a separately frozen denominator.
- Do not use private fixtures or model output to tune frozen validators.
