---
title: "OpenAI GPT-5.4 and 5.5 — Prompt Engineering Guide"
date_created: 2026-04-24
type: Reference
domain: "[[AI]]"
tags:
  - ai
  - prompt-engineering
  - openai
  - gpt-5-4
  - gpt-5-5
  - reference
models:
  - gpt-5.4
  - gpt-5.4-pro
  - gpt-5.4-mini
  - gpt-5.4-nano
  - gpt-5.5
  - gpt-5.5-pro
sources:
  - "https://developers.openai.com/api/docs/guides/prompt-guidance"
  - "https://help.openai.com/en/articles/10032626-prompt-engineering-best-practices-for-chatgpt"
  - "https://developers.openai.com/api/docs/guides/latest-model"
  - "https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide"
  - "https://developers.openai.com/api/docs/guides/prompt-engineering"
  - "https://developers.openai.com/api/docs/guides/prompt-optimizer"
  - "https://openai.com/index/introducing-gpt-5-5/"
research_method: "Firecrawl search + scrape on official OpenAI sources, with targeted extraction cross-checks"
---

# OpenAI GPT-5.4 and 5.5 — Prompt Engineering Guide

> Compiled from official OpenAI API docs, cookbook guidance, Help Center prompting notes, and the GPT-5.5 launch materials.
> Retrieved: 2026-04-24
> Important caveat: as of 2026-04-24, GPT-5.4 has official API prompt guidance; GPT-5.5 does not yet have a separate public API prompting guide. The GPT-5.5 section below therefore combines direct release claims with GPT-5/GPT-5.4 prompting patterns that are most likely to carry forward.

This is the single reference for prompting OpenAI's GPT-5.4 family today and for preparing prompts that should transfer well to GPT-5.5 once full API guidance lands. The core pattern is simple: these models perform best when you define the output contract, the allowed initiative level, the tool-use rules, and the exact completion criteria. GPT-5.4 is already strong out of the box, but the official docs are clear that prompt structure still matters, especially for agentic work, research, coding, and structured outputs.

## Executive Summary

1. Treat GPT-5.4 as the current production baseline. It is the documented default for broad general-purpose work, coding, and multi-step agentic workflows.
2. Prompt for contracts, not vibes. The biggest gains come from explicit output contracts, explicit verification rules, and a precise definition of done.
3. Use the Responses API for serious agentic work. OpenAI explicitly recommends it because reasoning can persist across turns and tool calls.
4. Control eagerness deliberately. If you do not specify search depth, stopping criteria, or permission boundaries, the model will often be more proactive than you intended.
5. For GPT-5.5, expect stronger autonomy and persistence, not a different prompting philosophy. The launch materials emphasize that it carries more of the work itself, uses tools more reliably, and stays on task longer. That means weak prompts will fail harder and good control prompts will matter more, not less.

---

## What Official OpenAI Guidance Actually Says

### 1. GPT-5.4 is optimized for production-grade assistants and agents

The GPT-5.4 prompt guidance says the model is designed for long-running tasks, disciplined execution, stronger behavior/style control, and reliable multi-step reasoning over long contexts. OpenAI's own wording matters here: the model is especially effective when prompts clearly specify:

- the output contract
- tool-use expectations
- completion criteria
- grounding and citation rules
- the right reasoning effort for the task

This is a strong signal that GPT-5.4 should be prompted more like an operator with a written runbook than like a chat partner you loosely “ask nicely.”

### 2. The core prompting unit is the contract

OpenAI repeatedly pushes the same pattern across docs:

- define exactly what the model should return
- define when it should act vs ask
- define how long it should keep going
- define how it should verify its own work
- define what counts as blocked

That is a shift away from older prompt-engineering folklore about tone tricks and toward operational constraints.

### 3. ChatGPT best practices still apply, but they are now the floor, not the ceiling

The Help Center guidance remains valid:

- be clear and specific
- iterate
- ask for the tone you want

That is still true, but for GPT-5.4 and likely GPT-5.5 it is incomplete. For high-value work, “clear and specific” now means explicit execution rules and validation criteria, not just a better-written request.

### 4. GPT-5.5 appears to extend the same pattern toward higher autonomy

The GPT-5.5 release page describes a model that:

- understands intent faster
- can carry more of the work itself
- plans, uses tools, checks its work, navigates ambiguity, and keeps going
- is more persistent than GPT-5.4
- uses fewer tokens to complete the same coding tasks

That suggests the prompting layer should become more governance-oriented: more boundaries, more stop conditions, and more explicit irreversibility rules.

---

## Model Positioning

## GPT-5.4

Use GPT-5.4 when you want one model that can move across:

- reasoning
- writing
- coding
- tool use
- long-context synthesis
- document-heavy or spreadsheet-heavy workflows

Officially documented strengths include:

- long-running task performance
- multi-step agent workflows
- token efficiency
- instruction following
- broad coding competence inherited from GPT-5.3-Codex work
- 1M token context window
- built-in computer use
- native compaction support

### GPT-5.4 variants

- `gpt-5.4`: default general-purpose flagship
- `gpt-5.4-pro`: harder problems, deeper reasoning
- `gpt-5.4-mini`: high-volume agent/coding/computer-use workflows
- `gpt-5.4-nano`: simple high-throughput work where speed/cost dominate

## GPT-5.5

As of this note, GPT-5.5 is described publicly through release material rather than a dedicated API prompting guide.

OpenAI positions it as:

- smarter and more intuitive than GPT-5.4
- stronger in agentic coding and knowledge work
- more persistent in long-running tasks
- more reliable with tool use
- similar per-token latency to GPT-5.4
- not yet fully documented for API use at the same prompt-detail level as GPT-5.4

Working assumption: if a prompt is well-designed for GPT-5.4 agentic work, it should transfer well to GPT-5.5, but GPT-5.5 will likely need even firmer guardrails around scope, side effects, and stopping behavior.

---

## The Practical Prompting Principles

## 1. Define the output contract first

OpenAI's GPT-5.4 guidance strongly favors explicit output contracts.

Good:

```text
<output_contract>
- Return exactly these sections in this order: Summary, Risks, Recommendation.
- Keep Summary under 120 words.
- Put all assumptions in Risks.
- End Recommendation with one decisive next action.
- Do not add any other sections.
</output_contract>
```

Weak:

```text
Give me a concise recommendation.
```

Why this matters: GPT-5.4 and 5.5 are capable enough to improvise structure. If you care about consistency, remove the improvisation space.

## 2. Define initiative explicitly

One of the biggest official themes is default follow-through policy: when should the model act without asking, and when should it stop and ask permission?

Good default policy:

```text
<default_follow_through_policy>
- If intent is clear and the next step is reversible and low-risk, proceed.
- Ask permission before irreversible actions, external side effects, or materially outcome-changing choices.
- If you proceed under a reasonable assumption, state the assumption briefly in the final answer.
</default_follow_through_policy>
```

This is critical for GPT-5.5. The release language suggests it will be more eager to carry work across tools and ambiguity. Without permission boundaries, that becomes operational drift.

## 3. Define completion criteria

Official GPT-5.4 guidance is unusually explicit on this point: define what “done” means.

Good:

```text
<completeness_contract>
- Treat the task as incomplete until all requested deliverables are present.
- If any item cannot be completed, mark it [blocked] and say exactly what is missing.
- For research tasks, stop only when additional searching is unlikely to change the conclusion.
</completeness_contract>
```

Weak:

```text
Help me research this.
```

The stronger the model, the more it benefits from clear stop conditions.

## 4. Add a verification loop

This is one of the most useful official GPT-5.4 patterns and should be standard in serious prompts.

```text
<verification_loop>
Before finalizing:
- check correctness against every requirement
- check grounding against sources or tool outputs
- check formatting against the requested schema
- check safety and side effects before acting
</verification_loop>
```

This is not decoration. It changes behavior.

## 5. Control research depth and search behavior

The GPT-5 cookbook guidance is excellent here. OpenAI explicitly recommends prompting for research process, not just research outcome.

Useful pattern:

```text
<research_mode>
- Work in 3 passes:
  1) Plan: list 3-6 sub-questions.
  2) Retrieve: search each sub-question and follow 1-2 second-order leads.
  3) Synthesize: resolve contradictions and write the answer with citations.
- Stop only when more searching is unlikely to change the answer.
</research_mode>
```

If you want less wandering, constrain it:

```text
<context_gathering>
- Search depth: low.
- Get enough context fast.
- Run one parallel batch, then act.
- Search again only if validation fails or signals conflict.
</context_gathering>
```

## 6. Use tool persistence rules for agentic work

GPT-5 guidance repeatedly stresses that tool use should be persistent, not tentative.

```text
<tool_persistence_rules>
- Use tools whenever they materially improve correctness, completeness, or grounding.
- Do not stop early when another tool call would materially improve the result.
- Retry with a different strategy if the first tool result is partial or empty.
</tool_persistence_rules>
```

This matters most for coding, research, investigation, and QA tasks.

## 7. Ask for citations and grounding when accuracy matters

GPT-5.4 docs explicitly recommend grounding and citation rules for evidence-rich synthesis.

Good:

```text
<grounding>
- Base claims only on the provided sources or tool outputs.
- Cite each substantive claim inline using [Source N].
- If sources conflict, present both views and state what would resolve the conflict.
</grounding>
```

This is especially important for finance, legal, audit, policy, and scientific work.

## 8. Structured outputs need hard boundaries

For JSON, SQL, XML, or schema-constrained responses, OpenAI recommends very explicit structured-output contracts.

```text
<structured_output_contract>
- Output only valid JSON.
- Do not wrap in markdown fences.
- Do not add commentary.
- Use exactly these keys: task, status, risks.
- If required data is missing, return an error object instead of guessing.
</structured_output_contract>
```

Do not rely on “return JSON please.” That is too weak.

## 9. For coding, prompt for end-to-end execution rather than advice

The GPT-5 cookbook and GPT-5.4 docs both point in the same direction: ask the model to complete the work, not merely comment on it.

Better:

```text
<autonomy_and_persistence>
Persist until the task is fully handled end-to-end within the current turn when feasible. Do not stop at analysis. Carry the work through implementation, verification, and explanation of outcomes.
</autonomy_and_persistence>
```

Worse:

```text
Can you suggest what I should change?
```

If you want implementation, ask for implementation.

## 10. Use reusable prompts and the prompt optimizer for stable workflows

OpenAI's more modern prompting stack includes:

- reusable prompts with variables in the dashboard / Responses API
- prompt optimizer support
- evals and graders to tune prompts empirically

For recurring business workflows, this is stronger than endlessly editing freehand prompt text.

---

## Parameter Guidance That Actually Matters

## Reasoning effort

From the GPT-5.4 documentation:

- `none`: fastest, fewest reasoning tokens, now the default for newer GPT-5.x models
- `low` / `medium`: often enough for routine analysis, synthesis, and coding tasks
- `high` / `xhigh`: use when failure cost is high and longer thinking is justified

Practical view:

- Use `none` or `low` for routine formatting, extraction, transformations, and straightforward coding
- Use `medium` for most business analysis, debugging, and research synthesis
- Use `high` or `xhigh` for difficult planning, large-system debugging, ambiguous root-cause analysis, or high-stakes reviews

Do not use higher reasoning effort by habit. Use it where the extra depth changes the outcome.

## Verbosity

GPT-5.4 exposes verbosity control, but OpenAI's docs note you can still steer verbosity through prompting. That means API knobs help, but they do not replace prompt-level structure.

Use both when needed:

- API control for broad token budget and style range
- prompt contract for section-level length and detail constraints

## Responses API vs Chat Completions

For GPT-5.4 agentic workflows, OpenAI's guidance is clear: prefer the Responses API.

Why:

- reasoning can persist across turns and tool calls
- lower token waste
- better long-horizon agent behavior
- easier use of reusable prompts and newer controls

If you are still prompting GPT-5.x as if it were only a chat endpoint, you are leaving capability on the table.

---

## Recommended Prompt Skeletons

## A. General high-quality work prompt

```text
You are a careful, execution-oriented assistant.

<instruction_priority>
- Follow the latest user instructions over earlier style preferences.
- Do not violate safety, privacy, or permission constraints.
</instruction_priority>

<task>
[Describe the actual task]
</task>

<context>
[Relevant background, source material, constraints]
</context>

<output_contract>
- Return exactly these sections: Summary, Analysis, Recommendation.
- Keep Summary under 120 words.
- Put decisive next action at the end of Recommendation.
</output_contract>

<grounding>
- Base claims only on provided context or tool outputs.
- Flag uncertainty explicitly.
</grounding>

<verification_loop>
Before finalizing:
- check correctness
- check grounding
- check formatting
- check safety / side effects
</verification_loop>
```

## B. Research prompt

```text
You are conducting evidence-based research.

<research_mode>
- Work in 3 passes: Plan, Retrieve, Synthesize.
- Start with 3-6 sub-questions.
- Follow 1-2 second-order leads per sub-question.
- Stop when additional search is unlikely to change the conclusion.
</research_mode>

<grounding>
- Cite every substantive claim.
- Distinguish facts, inferences, and unresolved conflicts.
</grounding>

<output_contract>
- Return: Executive Summary, Findings, Contradictions, Recommendation, Sources.
</output_contract>
```

## C. Coding / implementation prompt

```text
You are an implementation agent.

<autonomy_and_persistence>
- Do the work end-to-end when feasible.
- Do not stop at analysis if implementation and verification are possible.
</autonomy_and_persistence>

<tool_persistence_rules>
- Use tools whenever they improve correctness.
- Retry with another strategy if the first attempt fails.
</tool_persistence_rules>

<default_follow_through_policy>
- Proceed without asking for reversible, low-risk changes.
- Ask permission before destructive changes, production actions, or external side effects.
</default_follow_through_policy>

<output_contract>
- Return: What changed, Validation, Risks/Follow-ups.
</output_contract>

<verification_loop>
- run the relevant checks or tests
- confirm whether validation passed
- note any unverified areas explicitly
</verification_loop>
```

## D. Structured-output prompt

```text
<structured_output_contract>
- Output only valid JSON.
- Use exactly this schema:
  {
    "decision": "string",
    "confidence": "low|medium|high",
    "reasons": ["string"],
    "missing_information": ["string"]
  }
- Do not add markdown fences or commentary.
- If the input is insufficient, populate missing_information instead of guessing.
</structured_output_contract>
```

---

## GPT-5.4 vs GPT-5.5 Prompting Differences

| Area | GPT-5.4 | GPT-5.5 |
|---|---|---|
| Public prompt guidance | Detailed official API docs available | No dedicated API prompt guide yet |
| Expected initiative | High when prompted clearly | Likely higher by default; release stresses stronger autonomy |
| Tool use | Strong and disciplined | Release claims more reliable tool use |
| Persistence | Good for long-running tasks | Release claims it stays on task significantly longer |
| Prompting strategy | Contract-heavy prompting works well | Same strategy should transfer, but stronger guardrails likely needed |
| Main risk | Under-specifying output/verification | Under-specifying boundaries and side-effect thresholds |

My working view: GPT-5.5 is not a “new prompting philosophy” model. It looks like a “same control surface, stronger engine” model. So the right move is not to invent new tricks. It is to make GPT-5.4-grade prompts more explicit about permissions, stopping conditions, and verification.

---

## What To Do More Of

- Specify exact deliverables and section order.
- State what counts as complete.
- Separate reversible actions from approval-required actions.
- Add verification instructions.
- Add citation/grounding rules for factual work.
- Tell the model how aggressively to research or use tools.
- Use Responses API and reusable prompts for recurring workflows.
- Tune prompts with evals and prompt optimizer instead of guessing.

## What To Do Less Of

- Do not rely on vague prompts like “help me think about this.”
- Do not assume the model knows when to stop searching.
- Do not assume it will ask before taking a side-effectful action.
- Do not ask for “JSON” without a schema or error behavior.
- Do not confuse tone instructions with execution instructions.
- Do not treat GPT-5.5's higher autonomy as an excuse for lower prompt quality.

---

## Migration Guidance for Existing Prompts

If you have an older prompt that already worked on GPT-4.x or early GPT-5, upgrade it in this order:

1. Add an explicit output contract.
2. Add a follow-through / permission policy.
3. Add completion criteria.
4. Add a verification loop.
5. Add grounding or citation rules if the task is factual.
6. Add research-depth or tool-persistence rules if the task is agentic.
7. Only then adjust tone, verbosity, or style.

This ordering matters. Structure first, polish second.

---

## Suggested Default House Style for OpenAI GPT-5.x

For most serious work, use this as the default mental model:

- clear task
- explicit context
- explicit contract
- explicit initiative boundaries
- explicit verification
- explicit reporting of uncertainty or blockers

If you do only one thing differently with GPT-5.4 and GPT-5.5, do this: stop writing prompts as requests and start writing them as operating instructions.

---

## Bottom Line

GPT-5.4 rewards operationally precise prompts. GPT-5.5 appears to reward them even more. The highest-value pattern across the official guidance is not clever wording; it is governance: define the work, define the boundaries, define what done means, and define how the model must check itself before it stops.

That is the durable prompting pattern to carry forward across the GPT-5.x line.

---

## Sources

- [Prompt guidance for GPT-5.4](https://developers.openai.com/api/docs/guides/prompt-guidance) — strongest source for contract-based prompting, follow-through policy, completeness, verification, and research-mode patterns
- [Prompt engineering best practices for ChatGPT](https://help.openai.com/en/articles/10032626-prompt-engineering-best-practices-for-chatgpt) — baseline clarity, specificity, iteration, and tone guidance
- [Using GPT-5.4](https://developers.openai.com/api/docs/guides/latest-model) — model positioning, variants, 1M context, computer use, compaction, Responses API migration notes, reasoning controls
- [GPT-5 prompting guide](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide) — best source for agentic eagerness, tool preambles, persistence, and research/control patterns
- [Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) — reusable prompts, message role hierarchy, production consistency notes
- [Prompt optimizer](https://developers.openai.com/api/docs/guides/prompt-optimizer) — prompt iteration via datasets, graders, and optimizer loop
- [Introducing GPT-5.5](https://openai.com/index/introducing-gpt-5-5/) — strongest current public source for GPT-5.5 behavior, autonomy, persistence, and benchmark deltas vs GPT-5.4
