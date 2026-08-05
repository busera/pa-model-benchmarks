# Ollama Category Selection Contract

## Decision questions

1. Best eligible Ollama Cloud model for broad Hermes PA use.
2. Best eligible local Ollama model for broad Hermes PA use.

The outputs are separate. The report must not declare one universal local-vs-cloud winner.

## Required candidate record

`build_category_model_selection` consumes normalized records with:

- `model`: exact requested model tag;
- `category`: `ollama_cloud` or `local`;
- `route_verified`: returned identity and completion route are trustworthy;
- `complete`: full selected schedule completed;
- `repeats`: true repeat depth per decision-relevant cell;
- `critical_failures`: blocking high-risk failures across required lanes;
- `lanes`: D/R/W/F/T/H/tool-live rows with `eligible` and `score`;
- `strict_format_rate`;
- optional complete `response_tokens` and `elapsed_s` telemetry.

## Eligibility

A broad leader requires:

- verified exact route/identity;
- complete schedule;
- at least three true repeats;
- zero blocking critical failures;
- eligible D, R, W, F, T, H, and category-matched synthetic tool-live lanes.

X remains specialist evidence. Local frequent-use guidance additionally waits for MB-005 resource-cost evidence; that operating assessment does not alter quality scores.

## Ordering

Eligible candidates are ordered by:

1. worst required-lane score;
2. risk-ordered lane scores: F, R, D, H, W, T, tool-live;
3. strict-format rate;
4. response tokens where complete;
5. elapsed time where complete.

Missing efficiency telemetry loses an efficiency tie-break but does not erase quality evidence. `best_observed` is diagnostic only and cannot be presented as an approved route.

## Evidence boundary

The selector does not read artifacts or infer eligibility. Callers must normalize immutable summaries and preserve their hashes in the interpreted report. A future report generator should reject missing bindings rather than reconstruct or estimate them.

## MB-006 T03 proposed execution binding

The approved overnight candidate binding is in `docs/plans/2026-08-05-mb006-t03-proposed-execution-packet.md`: `deepseek-v4-flash:0731-cloud` and `nemotron-3-ultra:cloud`, both thinking-on. Kimi K3 is excluded because it incurs extra usage credits.

The complete schedule is D14/R10/W21/F10/T12/H6/tool-live3 logical cells per repeat. Direct D/R/W/F/T/H calls total 77 per repeat. Tool-live uses the actual Hermes agent loop, so calls are measured rather than assumed and capped at 16 per repeat. Three repeats produce 228 logical cells, 231 exact direct calls and a 279-response scored cap per candidate; two candidates cap at 558 scored responses. One exact-route preflight per candidate raises total exposure to 280 per candidate and 560 overall. Exact tag/profile/guide coverage, route identity, approved registration digest, thinking mode, token usage, finish reason and timing are evidence requirements. Setup or route failures block evidence but are not scored as model failures.

The operator approved exact-route preflight and scored synthetic execution for these two candidates on 2026-08-05. No retry, roster expansion or routing change is implied.
