# MB-006 — Ollama Cloud and Local Hermes PA Leader Selection

## Goal

Produce decision-grade, separate answers for the strongest eligible Ollama Cloud and local Ollama models for a broad Hermes PA setup.

## Delivered in this governance transfer

- project-local agent and operating standards;
- explicit programme/authority separation from Benchmark Coding;
- deterministic category-separated fail-closed selector;
- tests proving missing lanes, insufficient repeats, critical failures, and efficiency-first shortcuts cannot win;
- exact candidate record and report contract.

## T03 frozen proposal (2026-08-05)

The approved two-model overnight packet is frozen at `docs/plans/2026-08-05-mb006-t03-proposed-execution-packet.md`: `deepseek-v4-flash:0731-cloud` followed by `nemotron-3-ultra:cloud`, both thinking-on. Kimi K3 is excluded because it incurs extra usage credits. Each exact tag has a repository guide; unknown tags fail closed.

The full D/R/W/F/T/H/tool-live schedule is 228 logical cells per candidate. Direct suites make exactly 231 calls; real Hermes tool-live agent turns are measured and capped at 48, producing a 279-response scored cap per candidate and 558 scored responses overall. One exact-route preflight per candidate raises total exposure to 280 per candidate and 560 overall. `scripts/mb006_preflight.py --json` validates roster, profiles, guides, repeats, exact direct denominator and both caps before provider execution.

## Remaining execution work

1. Obtain independent exact-current-tree review after the realistic Hermes telemetry changes.
2. Preflight each exact route once and classify route/setup failure separately from model quality.
3. Run DeepSeek V4 Flash 0731 fully, verify artifact completeness and token/time telemetry, then run Nemotron fully. No overlap or automatic retries.
4. Compare pass/hard-fail results first, then tokens and time; routing remains a separate owner decision.
5. Qualitatively review representative outputs and failure clusters.
6. Normalize immutable summaries into `build_category_model_selection`.
7. Publish one report with separate local and Ollama Cloud decisions, exact hashes, `N/R`/`N/A`, and explicit approval boundary.
8. Complete local sustained resource-cost evidence before frequent-use recommendation.

## Non-goals

- no coding-score transfer;
- no validator or fixture tuning from observed outputs;
- no private cloud payloads;
- no universal local-vs-cloud score;
- no automatic Hermes routing mutation;
- no benchmark run in this governance-only change.
