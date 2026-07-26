---
title: "Ornith 1.0 — Prompting Best Practices"
date_created: 2026-07-25
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - coding
  - reference
  - ollama
  - ornith
  - deepreinforce
models:
  - ornith:35b-q8_0
  - ornith:35b-q4_K_M
  - ornith:9b-q8_0
sources:
  - "https://ollama.com/library/ornith"
  - "https://deep-reinforce.com/ornith_1_0.html"
---
# Ornith 1.0 — Prompting Best Practices

> Compiled from Ollama library page and DeepReinforce blog.
> Retrieved: 2026-07-25

Ornith 1.0 is a self-improving open-source coding model family from DeepReinforce,
built on Gemma 4 and Qwen 3.5 base models. MIT licensed.

## Model positioning

- 35B MoE (256 routed experts + 1 shared), 40 layers (10 global + 30 sliding window).
- 9B Dense variant for edge deployment.
- 256K context window.
- Self-improving RL: jointly learns solution rollouts AND the scaffolds that guide them.
- Capabilities: completion, tools, thinking.

## Benchmark results (vendor, upper bounds)

| Model | Terminal-Bench 2.1 | SWE-Bench Verified | SWE-Bench Pro |
|-------|-------------------|-------------------|---------------|
| Ornith-35B | 64.2 | 75.6 | 50.4 |
| Ornith-9B | 43.1 | 69.4 | 42.9 |

## Our benchmark result

- `ornith:35b-q8_0` (37 GB, think=false): **6/9 (67%)** — 21,725 tokens, 618s.
- Underwhelming vs vendor claim (75.6% SWE-Bench Verified). Vendor benchmarks are upper bounds.
- Same pass rate as gemma4:31b-mlx (67%) but with 2x token usage.
- Failed C4, C5, C3-AS — same wall as other 67% models.

## Runtime settings

- think=false for benchmark (think=true not tested yet).
- temperature=0.3, top_p=0.95 (our benchmark profile).
- Vendor used temperature=1.0, top_k=20, top_p=1.0 for their benchmarks.
- No known macOS issues (unlike Laguna family).

## PA implications

- Not a replacement for qwen3.6:27b-mlx (78%) — same pass rate but more tokens.
- Not recommended for PA general usage — coding specialist only.
- Possible candidate for think=true testing if 67% at think=false is below threshold.