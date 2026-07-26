---
title: "OpenAI GPT-5.6 — Prompt Engineering Guide"
date_created: 2026-07-16
date_updated: 2026-07-16
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - openai
  - gpt-5-6
  - reference
models:
  - gpt-5.6
  - gpt-5.6-sol
  - gpt-5.6-terra
  - gpt-5.6-luna
sources:
  - "https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6"
  - "https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6"
source_status: "Official OpenAI documentation"
retrieved: 2026-07-16
---

# OpenAI GPT-5.6 — Prompt Engineering Guide
[[2026-07-16]]

> Primary source: [Prompting guidance for GPT-5.6 Sol](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)
> Companion source: [Using GPT-5.6](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)
> Retrieved: 2026-07-16

This is the model-specific prompt reference for the GPT-5.6 family. GPT-5.6 works best when prompts define the outcome, material constraints, available evidence, approval boundaries, and completion bar, while leaving the model room to choose an efficient path. The central migration lesson is not to add more scaffolding: simplify first, preserve true invariants, and make targeted changes only when representative evaluations expose a measured gap.

## Executive Summary

1. **Use outcome-first prompts.** Define the destination, success criteria, constraints, evidence requirements, and stopping conditions rather than prescribing every reasoning step.
2. **Simplify before adding.** Remove repeated rules, redundant examples, obsolete process instructions, and irrelevant tools one group at a time. Re-run the same evaluations after each change.
3. **State each invariant once.** Contradictory or repeated instructions can cause more instability than missing detail.
4. **Separate safe autonomy from approval-required actions.** Let the model complete reversible, in-scope local work; require confirmation for external writes, destructive actions, purchases, material costs, or scope expansion.
5. **Use decision rules for judgment calls.** Reserve `ALWAYS`, `NEVER`, `must`, and `only` for genuine invariants.
6. **Expose only relevant tools.** Define prerequisite retrieval, parallel versus sequential calling, fallback behavior, and the validation required before completion.
7. **Use Programmatic Tool Calling only for bounded reduction workflows.** Multiple calls alone are not a reason to use it.
8. **Treat grounding as a prompt contract.** Specify what needs support, what counts as enough evidence, and what to do when evidence is absent or conflicting.
9. **Tune reasoning and pro mode empirically.** Preserve the previous model's effort as the baseline, test one level lower, and increase effort only when evaluations show a meaningful gain.
10. **Validate the final artifact.** Give the model access to relevant checks and define the completion evidence required.

---

## Model Positioning and Runtime Controls

### GPT-5.6 family

- `gpt-5.6` — alias that routes to `gpt-5.6-sol`.
- `gpt-5.6-sol` — flagship capability for complex production workflows.
- `gpt-5.6-terra` — strong capability at a lower price.
- `gpt-5.6-luna` — efficient option for high-volume workloads.

Use the Responses API for reasoning, tool calling, persisted state, and multi-turn workflows.

### Reasoning effort

GPT-5.6 supports:

- `none`
- `low`
- `medium`
- `high`
- `xhigh`
- `max`

Recommended evaluation sequence:

1. Preserve the GPT-5.5 or GPT-5.4 effort setting as the migration baseline.
2. Test the same setting and one level lower on representative tasks.
3. Use `low` for latency-sensitive work when it preserves quality.
4. Use `medium` as a balanced starting point.
5. Use `high` or `xhigh` only when evaluations show a material gain.
6. Reserve `max` for the hardest quality-first workloads; do not make it a global default.

Before raising reasoning effort, check whether the prompt is missing a success criterion, dependency rule, tool-routing rule, or verification loop.

### Pro mode

Pro mode is an execution mode, not a separate model slug. Set `reasoning.mode: "pro"` while keeping the chosen GPT-5.6 model. Reasoning mode and reasoning effort are independent.

Use pro mode selectively when:

- the task is genuinely difficult;
- a marginal reliability gain materially affects the outcome;
- the task has clear evaluation criteria; and
- higher latency and token use are acceptable.

Keep the same outcome-focused prompt used in standard mode. Do not instruct the model to “use pro mode,” “think harder,” or generate hidden candidate answers. Compare standard and pro mode on task success, completeness, evidence, latency, tokens, and cost.

### Verbosity

GPT-5.6 is more concise by default than GPT-5.5. Re-test broad instructions such as “be concise” because they may now make responses too short.

Use `text.verbosity` for the request-wide default:

- `low`
- `medium`
- `high`

Use the prompt for task-specific length, structure, and preservation rules. For short answers, state what must remain before saying what may be omitted.

```text
Lead with the conclusion. Preserve the evidence needed to support it, any material caveat, and the next action. Remove introductions, repetition, generic reassurance, and optional background first.
```

---

## Core Prompting Principles

## 1. Simplify prompts first

Start from a prompt and tool set that already works. Remove one category at a time, then rerun the same evaluations.

Trim:

- repeated statements of the same rule;
- repeated style or process instructions that do not change behavior;
- examples that do not correct a measured behavior gap;
- process instructions for behavior the model already performs reliably;
- irrelevant tools and verbose tool descriptions.

Keep:

- the user-visible outcome;
- success criteria and stopping conditions;
- safety, business, evidence, privacy, and permission constraints;
- context-dependent tool-routing rules;
- required output shape and validation requirements.

OpenAI reports directional internal coding-agent results in which leaner prompts improved evaluation scores by roughly 10–15%, reduced total tokens by 41–66%, and reduced cost by 33–67%. These are not universal guarantees; validate prompt reductions on the actual workload.

## 2. Prompt for the outcome, not a rigid process

Prefer:

```markdown
Goal: Resolve the customer's issue end to end.

Success means:
- make the eligibility decision from available policy and account evidence
- complete every allowed action before responding
- return completed_actions, customer_message, and blockers
- if required evidence is missing, request the smallest missing field
```

Avoid prescribing detailed search or reasoning steps unless the sequence is a real business, safety, or validation requirement.

Preserve explicit user values. Where a value is implicit, provide decision criteria rather than universal defaults, keyword maps, or broad semantic shortcuts.

## 3. Define explicit stopping conditions

```text
Resolve the request in the fewest useful tool loops, but do not let loop
minimization outrank correctness, required evidence, calculations, citations,
or validation.

After each result, decide whether the core request can now be answered with
useful evidence. If yes, answer. If required evidence is still missing, name
the missing fact and use the smallest useful fallback.
```

Stopping rules should define when to:

- answer;
- retry;
- use a fallback;
- narrow the conclusion;
- ask for missing information;
- abstain; or
- report a blocker.

## 4. Use absolute language only for true invariants

Use `ALWAYS`, `NEVER`, `must`, and `only` for rules that genuinely cannot vary, such as safety boundaries, required fields, legal restrictions, or prohibited actions.

For context-dependent choices—searching, asking a question, selecting a tool, retrying, or continuing—use decision rules. Blanket rules can cause over-triggering, unnecessary approval requests, or wasted work.

## 5. Separate personality from collaboration style

Personality controls tone, warmth, directness, formality, humor, empathy, and polish.

Collaboration style controls when the model:

- asks questions;
- makes assumptions;
- takes initiative;
- explains trade-offs;
- verifies work; and
- handles uncertainty.

Keep both sections short. Neither replaces goals, success criteria, tool rules, evidence requirements, or stop conditions.

```text
Personality: Calm, direct, evidence-led, and concise. Omit generic praise and
unnecessary sign-offs.

Collaboration: Inspect available evidence before asking questions. Proceed with
safe in-scope work, surface material assumptions, explain important trade-offs,
and stop before approval-required actions.
```

Broad tone labels can be ambiguous. Prefer observable writing choices:

```text
State the answer directly. If the user reports a problem, acknowledge the
specific issue before giving the next step. Use reassurance only when relevant.
```

## 6. Preserve the requested artifact during editing

For rewrites, summaries, and customer-facing drafts:

```text
Preserve the requested artifact, length, structure, genre, and factual claims
first. Improve clarity, flow, and correctness without adding new claims,
sections, or a more promotional tone unless requested.
```

---

## Autonomy and Approval Boundaries

GPT-5.6 can be proactive and persistent. Define what the request authorizes so it can complete safe work without stopping unnecessarily while respecting side-effect boundaries.

```text
For requests to answer, explain, review, diagnose, or plan, inspect the relevant
materials and report the result. Do not implement changes unless the request
also asks for them.

For requests to change, build, or fix, make the requested in-scope local changes
and run relevant non-destructive validation without asking first.

Require confirmation for external writes, destructive actions, purchases,
material costs, or a material expansion of scope.
```

Name safe local actions when relevant, such as:

- reading files;
- inspecting logs;
- editing explicitly in-scope local files;
- running tests, linters, builds, or smoke checks;
- making reversible local transformations.

Keep the policy in one place and state each rule once. Repetition of “ask first” or “do not mutate” can cause unnecessary approval requests.

For long-running work, name the active layer:

- research;
- design;
- implementation;
- review; or
- external coordination.

This prevents silent movement from analysis into implementation or from local work into external action.

---

## Tool Routing

### Tool descriptions

Expose only task-relevant tools. Each description should say:

- what the tool does;
- when to use it;
- the important return fields and types; and
- expected error or empty-result behavior.

### Prerequisites

```text
Before taking an action, resolve required discovery, retrieval, and validation
steps. Do not skip a prerequisite because the intended final state seems obvious.
```

### Parallel versus sequential calls

- Parallelize independent reads or retrieval calls.
- Keep calls sequential when one result determines the next action.
- After parallel retrieval, synthesize the results before acting.
- Do not parallelize side-effecting actions merely to save time.

### Empty or partial results

If a tool returns empty, partial, or suspiciously narrow results, try one or two meaningful fallbacks before concluding that no result exists. Absence of retrieved evidence is not automatically proof of factual absence.

---

## Programmatic Tool Calling

Programmatic Tool Calling (PTC) is appropriate for bounded workflows in which code can process many tool results or large intermediate outputs and return a much smaller structured result.

Use PTC for:

- filtering;
- joining;
- sorting and ranking;
- deduplication;
- aggregation;
- batching similar records;
- repeated deterministic validation; and
- compacting large structured results into a defined schema.

Prefer direct tool calls when:

- one call is sufficient;
- intermediate outputs are already small;
- each result may change the next decision;
- an action requires approval;
- the final answer must preserve citations or native artifacts; or
- semantic judgment is required between calls.

Multiple, parallel, or dependent calls alone do not justify PTC.

```text
Use Programmatic Tool Calling only for the bounded record-reduction stage.
Call only the documented read-only tools. Filter and deduplicate the results,
then emit exactly the required compact schema with evidence fields.

Retry transient failures at most twice. Stop when the schema is complete or a
required field remains unavailable after the allowed retries. Use direct tool
calls for approval, semantic judgment, citations, and final validation. Do not
switch routes or repeat completed work after the handoff.
```

Test both outputs independently:

- the `program_output` item; and
- the final assistant `message`.

A correct program result does not guarantee that the final message preserves every required field, citation, caveat, or decision.

---

## Grounding, Citations, and Retrieval Budgets

Define:

- which claims require support;
- what sources are allowed;
- what counts as enough evidence;
- how citations must be attached;
- what to do when evidence is missing; and
- how to handle conflicting sources.

```text
For ordinary Q&A, begin with one broad search using short, discriminative
keywords. If the top results support the core request, answer from them.

Retrieve again only when a required fact, owner, date, ID, or source is missing;
the user requested exhaustive coverage or comparison; a named artifact must be
read; or an important claim would otherwise be unsupported.

Do not search again only to improve phrasing, add optional examples, or support
nonessential detail.
```

For research and synthesis:

- cite only retrieved sources;
- attach citations to the claims they support;
- separate direct facts from inference;
- state material conflicts between sources;
- narrow the answer or report missing evidence instead of guessing.

For creative drafting, distinguish source-backed facts from creative wording. Do not invent names, metrics, dates, roadmap status, customer outcomes, or product capabilities to make a draft stronger.

---

## Long-Running Workflows and State

For tool-heavy tasks, use a short visible preamble before the first tool call and sparse updates at major phase changes. Do not narrate routine calls.

```text
Before tool calls for a multi-step task, send a one- or two-sentence update that
states the first step. During the task, update only when a major phase begins or
a finding changes the plan. Each update should state one concrete outcome and
the next step.
```

### State and compaction

- Preserve assistant phase values when replaying history manually.
- With `previous_response_id`, prior assistant state is preserved automatically.
- Compact after major milestones rather than every turn.
- Keep the prompt functionally consistent after compaction.
- Treat compacted items as opaque state.

### Persisted reasoning

Persisted reasoning is useful when the objective, assumptions, and priorities remain stable across turns. Use current-turn behavior when earlier reasoning is no longer relevant.

Do not enable persisted reasoning as an automatic optimization for every workflow. Stale reasoning can add tokens, increase latency, and anchor the model to outdated assumptions.

### Prompt caching

Keep reusable prompt prefixes stable. Avoid unnecessary churn in large system prompts. Use explicit cache breakpoints only when measured cache behavior and cost justify them.

---

## Frontend, Visual, and Vision Tasks

GPT-5.6 has stronger frontend aesthetics, layout, visual hierarchy, and design judgment, but still needs product context and explicit constraints.

For incremental frontend changes:

- inspect and preserve existing design tokens, components, and patterns;
- do not add unrequested features or decorative UI;
- preserve responsive behavior and expected states;
- render and inspect the result before finalizing.

```text
Render the artifact before finalizing. Inspect layout, clipping, spacing,
missing content, responsive behavior, and visual consistency. Revise until the
rendered output meets the requirements.
```

For vision, computer-use, localization, or OCR work requiring spatial precision, choose image detail intentionally. Use original detail for large, dense, or coordinate-sensitive images only when the additional input cost and latency are justified.

---

## Validation and Completion

For coding and implementation:

```text
After making changes, run the most relevant available validation:
- targeted tests for changed behavior
- type checks or lint checks when applicable
- build checks for affected packages
- a minimal smoke test when full validation is too expensive

If a check cannot be run, explain why and identify the next-best validation.
```

For implementation plans, include:

- requirements;
- named resources or files;
- state transitions or data flow;
- validation checks;
- failure behavior;
- privacy or security considerations; and
- open questions that materially affect implementation.

A task is complete only when the requested artifact exists and the required validation has been performed or explicitly reported as blocked.

---

## Recommended Prompt Structure

Use this as a starting point for complex work. Keep each section short and add detail only where it changes behavior.

```text
Role: [the model's function and relevant context]

Personality: [observable tone and collaboration choices]

Goal: [user-visible outcome]

Success criteria: [what must be true before the final answer]

Constraints: [safety, business, evidence, privacy, permission, and side-effect limits]

Tools: [which tools to use, when, prerequisites, and exclusions]

Output: [sections, format, length, evidence, and tone]

Stop rules: [when to retry, use a fallback, narrow, ask, abstain, or stop]
```

### Compact general-purpose template

```text
Role: You are a careful execution partner for [domain].

Goal: [Define the user-visible result.]

Success criteria:
- [Required outcome 1]
- [Required outcome 2]
- [Required validation or evidence]

Constraints:
- Base factual claims on provided or retrieved evidence.
- Proceed with safe, reversible, in-scope local work.
- Require approval for external, destructive, costly, or scope-expanding actions.

Tools:
- Resolve prerequisite retrieval before acting.
- Parallelize independent reads; sequence dependent calls.
- Retry empty or partial results with one or two meaningful fallbacks.

Output:
- Lead with the conclusion.
- Include material evidence, caveats, blockers, and the next action.
- Omit repetition and optional background first.

Stop rules:
- Stop when all success criteria are met and validation is complete.
- If required evidence remains missing, name the smallest missing fact.
- Do not guess to manufacture completeness.
```

### Coding and implementation template

```text
Role: You are the implementation partner for this repository.

Goal: Complete the requested change end to end.

Success criteria:
- implement the requested behavior without unrelated scope changes
- preserve existing architecture and conventions unless change is required
- run targeted tests plus relevant lint, type, build, or smoke checks
- report the files changed, validation results, and residual risks

Constraints:
- Inspect the repository and relevant instructions before editing.
- Make reversible, in-scope local changes without asking first.
- Require confirmation for destructive actions, production writes, external
  communication, purchases, or material scope expansion.
- Do not stop at a plan or stub when implementation and validation are possible.

Stop rules:
- Continue until the requested artifact works and relevant checks pass.
- If blocked, report the exact blocker and the best verified fallback.
```

### Evidence-led research template

```text
Goal: Answer [question] using current, relevant evidence.

Success criteria:
- support every material factual claim with a retrieved source
- separate facts, inferences, assumptions, and unresolved conflicts
- answer the decision the user needs to make, not merely summarize sources

Retrieval:
- Begin with one broad search using short, discriminative terms.
- Retrieve again only for missing required facts, named artifacts, exhaustive
  comparison, or otherwise unsupported material claims.
- Treat empty retrieval as missing evidence, not proof of absence.

Output:
- Conclusion
- Evidence
- Material uncertainty or conflicts
- Recommendation and next action
```

---

## Migration Workflow from GPT-5.5 or GPT-5.4

1. Switch the model while preserving the current reasoning effort.
2. Run representative evaluations before changing the prompt.
3. Remove obsolete scaffolding, repeated instructions, redundant examples, and irrelevant tools one group at a time.
4. Add only the smallest targeted instruction that fixes a measured regression.
5. Re-run the same evaluations after every prompt, tool, or reasoning change.
6. Test the baseline effort and one level lower.
7. Test standard versus pro mode only on tasks likely to benefit.
8. Compare quality before counting token, latency, call, or cost reductions as improvements.

Do not rewrite a working prompt stack and change the model, tools, and reasoning settings simultaneously. That makes regressions impossible to attribute.

When a prompt regresses:

1. inspect a small set of real traces;
2. identify the specific failure mode;
3. locate the likely missing, conflicting, or over-repeated instruction;
4. make a surgical edit; and
5. rerun the same cases.

---

## Common Failure Modes

### Over-prompting

**Symptom:** unnecessary searches, approvals, retries, narration, or excessive output.

**Fix:** remove repeated process rules, replace blanket mandates with decision rules, and expose fewer tools.

### Under-specified completion

**Symptom:** the model stops at analysis, a plan, a stub, or an unverified artifact.

**Fix:** define the user-visible outcome, completion criteria, validation, and blocker behavior.

### Conflicting instructions

**Symptom:** unstable tool use, inconsistent length, or oscillation between acting and asking.

**Fix:** keep one authoritative rule for each behavior and remove stale duplicates.

### Excessive brevity

**Symptom:** the conclusion is present but evidence, caveats, or next actions are missing.

**Fix:** specify the content that must be preserved; remove low-value material first rather than applying a blanket word limit.

### Unnecessary PTC

**Symptom:** a simple or judgment-heavy workflow is routed through program code, obscuring citations or approval boundaries.

**Fix:** reserve PTC for bounded deterministic reduction and use direct calls for judgment, approval, citations, and final validation.

### Treating missing evidence as “no”

**Symptom:** an empty or narrow retrieval result becomes a factual claim of absence.

**Fix:** use one or two meaningful fallbacks, then report missing evidence or narrow the claim.

### Stale persisted reasoning

**Symptom:** the model remains anchored to assumptions that no longer fit the current turn.

**Fix:** use current-turn reasoning when objectives, assumptions, or priorities have changed.

### Raising effort instead of fixing the prompt

**Symptom:** cost and latency rise without a reliable quality gain.

**Fix:** inspect success criteria, dependency rules, routing, and validation before increasing effort.

---

## Evaluation Checklist

Before promoting a GPT-5.6 prompt or runtime profile, verify:

- [ ] The user-visible outcome is explicit.
- [ ] Success criteria and stopping conditions are testable.
- [ ] Safety, privacy, evidence, business, and approval constraints are preserved.
- [ ] Each instruction appears once and contradictions have been removed.
- [ ] Irrelevant tools and examples have been removed.
- [ ] Safe autonomy and approval-required actions are clearly separated.
- [ ] Tool prerequisites, parallelism, fallbacks, and validation are defined where needed.
- [ ] PTC is limited to a bounded deterministic stage, if used.
- [ ] The final message—not only intermediate tool or program output—passes the output contract.
- [ ] Citation and missing-evidence behavior are tested for grounded tasks.
- [ ] The existing reasoning effort and one lower setting were compared.
- [ ] Pro mode or higher effort is used only where measured gains justify the cost.
- [ ] Representative task quality remains intact before token, latency, or cost reductions are counted as improvements.
- [ ] Coding and visual artifacts were actually tested or rendered before completion.

---

## What to Do More Of

- State outcomes, success criteria, evidence requirements, and stop rules.
- Keep prompts lean and internally consistent.
- Use decision rules for context-dependent behavior.
- Define approval boundaries once.
- Let the model select an efficient path within clear constraints.
- Use targeted validation and representative evaluations.
- Separate deterministic reduction from semantic judgment.
- Preserve important evidence, caveats, decisions, and next actions when shortening output.

## What to Do Less Of

- Repeating the same instruction in multiple sections.
- Prescribing every reasoning or tool step without a real dependency.
- Using absolute language for judgment calls.
- Exposing unrelated tools.
- Adding examples that do not fix measured behavior.
- Increasing reasoning effort before repairing the prompt contract.
- Treating fewer calls or tokens as improvement when answer quality regresses.
- Rewriting an entire working prompt stack during model migration.

---

## Bottom Line

GPT-5.6 rewards lean, outcome-first prompt contracts. Define what success looks like, preserve true constraints, set approval and evidence boundaries, expose the right tools, and require relevant validation. Then let the model choose the efficient path. The correct migration strategy is controlled subtraction plus measured, surgical additions—not a larger system prompt.

## Sources

- [Prompting guidance for GPT-5.6 Sol](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6) — primary source for prompt simplification, outcome-first instructions, collaboration style, autonomy, tool routing, PTC, grounding, state, reasoning effort, frontend work, validation, and migration.
- [Using GPT-5.6](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6) — companion source for model-family positioning, model aliases, Responses API controls, persisted reasoning, explicit prompt caching, pro mode, original image detail, and reasoning-effort options.
