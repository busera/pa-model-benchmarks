# PA Model Benchmark Operating Standard

This is the canonical project-local standard for broad Hermes PA benchmark engineering, execution, evidence, and model-selection decisions.

## 1. Objective and boundary

The programme must answer two separate questions:

A. What is the strongest eligible **Ollama Cloud** model for broad Hermes PA use?
B. What is the strongest eligible **local Ollama** model for broad Hermes PA use?

There is no universal local-vs-cloud winner. Privacy, availability, latency, quota, and local resource cost make the categories operationally different. Coding-specialist authority remains in `../benchmark-coding`; coding results cannot promote a broad PA model.

## 2. Decision order

Apply a fail-closed, quality-first decision order inside each category:

`complete route evidence → required-lane eligibility → minimum true repeat depth → zero blocking critical failures → worst required-lane quality → risk-ordered lane quality → strict-format reliability → token/resource cost → elapsed time`

- Required broad-PA evidence is D, R, W, F, T, H, and a category-matched synthetic tool-live gate.
- X is specialist evidence and cannot rescue a failed broad gate.
- Local recommendations additionally require a separately reported sustained resource-cost assessment before frequent/unattended operation.
- Missing lanes, partial coverage, route-unverified cells, unsupported controls, or insufficient repeats block an eligible leader. They may support a clearly labelled `best_observed` diagnostic only.
- The deterministic selector in `scripts/benchmark_decision.py` emits separate `local` and `ollama_cloud` decisions and never a cross-category rank.
- Routing remains an explicit human decision after the report.

## 3. Evidence chain and failure classes

Treat every run as one evidence system:

`request controls → provider response → returned identity/completion checks → strict contract → semantic validator → tool integration → immutable cell → summary → category decision`

Keep distinct:

- transport/provider availability;
- requested and returned route/model identity;
- completion, truncation, and thinking-control behavior;
- strict-format/recovery warnings;
- semantic/task failure;
- tool/session/integration failure;
- quality eligibility and routing approval.

Do not convert one class into another or average blocking failures away.

## 4. Fairness and profiles

- Objectives, source facts, output schema, validators, budgets, approval boundaries, and acceptance criteria remain invariant across models.
- Model-family wording and safe runtime options may vary only through tracked exact profiles and repository-owned guides.
- Unknown/generic profiles and missing guides fail before scored calls.
- Record exact requested tag, provider route, returned identity, profile and guide hashes, API mode, thinking control, runtime options, completion telemetry, prompt/response tokens, and elapsed time.
- Evaluate supported thinking modes as separate lanes when the decision claims a thinking-mode route. Never merge on/off evidence.
- Provider preflight uses one minimal synthetic request on the exact route. Metadata alone is not callability proof.

## 5. Ollama identity and route integrity

- Local tags and Ollama Cloud tags are separate categories even though both use the local Ollama daemon.
- Never infer a returned remote alias by stripping `:cloud`, `-cloud`, namespace, case, or another suffix.
- Exact returned identity needs no alias lookup.
- A different returned identity is acceptable only with fresh same-origin `/api/tags` evidence containing exactly one raw record whose `name` and `model` equal the exact requested tag, whose non-empty `remote_model` equals the returned identity byte-for-byte, and whose non-empty digest is retained.
- Missing, malformed, duplicate, normalized, cross-origin, or conflicting identity evidence fails closed.
- Availability or entitlement failures are route evidence, not intrinsic quality scores.

## 6. Fixtures, privacy, and calibration

- Use synthetic, non-personal fixtures for tracked and cloud-executable tests.
- Private fixtures remain external, opt-in, and local unless the operator separately approves the exact cloud model and corpus.
- Hidden labels and validator answer keys stay outside model-visible context.
- Never edit a frozen scored fixture from candidate output. General harness defects require a regression, a new version where material, and a fresh run ID.
- Validator calibration evidence is not promotion evidence. Use held-out H tasks and representative qualitative review to detect overfitting.

## 7. Scheduling, repeats, and completeness

- Execute models strictly serially to avoid local-memory contention and ambiguous telemetry.
- Within repeated trials, use the governed model-major schedule; balanced mode rotates first position.
- At least three true repeats are required for every decision-relevant task/lane. Distinct tasks or families are not repeats.
- A requested full matrix runs every supported selected cell. Early stop saves quota only; skipped cells stay incomplete and unranked unless the operator explicitly approves the wave boundary.
- Do not rank partial rows or silently shrink denominators.

## 8. Artifacts and reports

- New runs use fresh create-only `artifacts/<run-id>/` roots.
- Never overwrite, splice, or repair historical manifests, cells, responses, summaries, or reports.
- Every decision report states exact tree/commit, run ID/path, route/model/returned identity, lane/task denominator, repeat depth, critical failures, strict-format rate, telemetry completeness, material hashes, and approval limits.
- Reports must show both category decisions, including `no eligible leader` when applicable. `best_observed` is diagnostic and cannot be phrased as approved routing.
- Preserve input and response tokens separately. Missing telemetry remains unknown; do not estimate it into a cost winner.

## 9. Engineering and change control

- Python 3.11 or newer; use small typed functions, specific exceptions, explicit timeouts, dependency-injected seams, and behavior-focused tests.
- Before editing: read the `MB-*` contract, inspect Git state, trace definitions/callers/tests, and back up significant files when Git rollback is insufficient.
- Before completion: compile modified Python, run focused and full tests, applicable no-call self-tests, `git diff --check`, privacy/credential scans, and exact changed-path inspection.
- Harness, migration, promotion, and routing-grade changes require independent exact-candidate review. Any later byte change invalidates that review.
- Do not commit, push, publish, change routing, or execute unapproved cloud/private workloads merely because verification passes.
- Archive over delete; prior evidence is immutable.
