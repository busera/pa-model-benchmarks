---
aliases:
  - Claude Prompt Guide
  - Anthropic Prompting Best Practices
tags:
  - ai
  - prompt-engineering
  - claude
  - reference
domain: "[[AI]]"
type: Reference
source: "https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices"
date_created: 2026-04-04
---

# Anthropic Claude 4.6 — Prompting Best Practices

> Source: [Anthropic Docs — Prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices)
> Retrieved: 2026-04-04

This is the single reference for prompt engineering with Claude's latest models, including Claude Opus 4.6, Claude Sonnet 4.6, and Claude Haiku 4.5. It covers foundational techniques, output control, tool use, thinking, and agentic systems.

---

## General Principles

### Be Clear and Direct

Claude responds well to clear, explicit instructions. Being specific about your desired output can help enhance results. If you want "above and beyond" behavior, explicitly request it rather than relying on the model to infer this from vague prompts.

Think of Claude as a brilliant but new employee who lacks context on your norms and workflows. The more precisely you explain what you want, the better the result.

**Golden rule:** Show your prompt to a colleague with minimal context on the task and ask them to follow it. If they'd be confused, Claude will be too.

- Be specific about the desired output format and constraints.
- Provide instructions as sequential steps using numbered lists or bullet points when the order or completeness of steps matters.

**Less effective:**
```text
Create an analytics dashboard
```

**More effective:**
```text
Create an analytics dashboard. Include as many relevant features and interactions as possible. Go beyond the basics to create a fully-featured implementation.
```

### Add Context to Improve Performance

Providing context or motivation behind your instructions, such as explaining to Claude why such behavior is important, can help Claude better understand your goals and deliver more targeted responses.

**Less effective:**
```text
NEVER use ellipses
```

**More effective:**
```text
Your response will be read aloud by a text-to-speech engine, so never use ellipses since the text-to-speech engine will not know how to pronounce them.
```

Claude is smart enough to generalize from the explanation.

### Use Examples Effectively

Examples are one of the most reliable ways to steer Claude's output format, tone, and structure. A few well-crafted examples (known as few-shot or multishot prompting) can dramatically improve accuracy and consistency.

When adding examples, make them:
- **Relevant:** Mirror your actual use case closely.
- **Diverse:** Cover edge cases and vary enough that Claude doesn't pick up unintended patterns.
- **Structured:** Wrap examples in `<example>` tags (multiple examples in `<examples>` tags) so Claude can distinguish them from instructions.

> Include 3-5 examples for best results. You can also ask Claude to evaluate your examples for relevance and diversity, or to generate additional ones based on your initial set.

### Structure Prompts with XML Tags

XML tags help Claude parse complex prompts unambiguously, especially when your prompt mixes instructions, context, examples, and variable inputs. Wrapping each type of content in its own tag (e.g. `<instructions>`, `<context>`, `<input>`) reduces misinterpretation.

Best practices:
- Use consistent, descriptive tag names across your prompts.
- Nest tags when content has a natural hierarchy (documents inside `<documents>`, each inside `<document index="n">`).

### Give Claude a Role

Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference:

```python
import anthropic

client = anthropic.Anthropic()

message = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    system="You are a helpful coding assistant specializing in Python.",
    messages=[
        {"role": "user", "content": "How do I sort a list of dictionaries by key?"}
    ],
)
print(message.content)
```

### Long Context Prompting

When working with large documents or data-rich inputs (20k+ tokens):

- **Put longform data at the top**: Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples. This can significantly improve performance across all models. Queries at the end can improve response quality by up to 30% in tests.

- **Structure document content and metadata with XML tags**: Wrap each document in `<document>` tags with `<document_content>` and `<source>` subtags.

```xml
<documents>
  <document index="1">
    <source>annual_report_2023.pdf</source>
    <document_content>
      {{ANNUAL_REPORT}}
    </document_content>
  </document>
</documents>

Analyze the annual report. Identify strategic advantages and recommend Q3 focus areas.
```

- **Ground responses in quotes**: For long document tasks, ask Claude to quote relevant parts first before carrying out its task.

### Model Self-Knowledge

If you would like Claude to identify itself correctly:

```text
The assistant is Claude, created by Anthropic. The current model is Claude Opus 4.6.
```

For apps that need model strings:

```text
When an LLM is needed, please default to Claude Opus 4.6 unless the user requests otherwise. The exact model string for Claude Opus 4.6 is claude-opus-4-6.
```

---

## Output and Formatting

### Communication Style and Verbosity

Claude's latest models have a more concise and natural communication style:

- **More direct and grounded:** Provides fact-based progress reports rather than self-celebratory updates
- **More conversational:** Slightly more fluent and colloquial, less machine-like
- **Less verbose:** May skip detailed summaries for efficiency unless prompted otherwise

Claude may skip verbal summaries after tool calls, jumping directly to the next action. If you prefer more visibility:

```text
After completing a task that involves tool use, provide a quick summary of the work you've done.
```

### Control the Format of Responses

1. **Tell Claude what to do instead of what not to do**
   - Instead of: "Do not use markdown in your response"
   - Try: "Your response should be composed of smoothly flowing prose paragraphs."

2. **Use XML format indicators**
   - Try: "Write the prose sections of your response in `<smoothly_flowing_prose_paragraphs>` tags."

3. **Match your prompt style to the desired output**

4. **Use detailed prompts for specific formatting preferences:**

```text
When writing reports, documents, technical explanations, analyses, or any long-form content, write in clear, flowing prose using complete paragraphs and sentences. Use standard paragraph breaks for organization and reserve markdown primarily for inline code, code blocks, and simple headings. Avoid using bold and italics.

DO NOT use ordered lists or unordered lists unless: a) you're presenting truly discrete items where a list format is the best option, or b) the user explicitly requests a list or ranking.

Instead of listing items with bullets or numbers, incorporate them naturally into sentences.
```

### LaTeX Output

Claude Opus 4.6 defaults to LaTeX for mathematical expressions. If you prefer plain text:

```text
Format your response in plain text only. Do not use LaTeX, MathJax, or any markup notation such as \( \), $, or \frac{}{}. Write all math expressions using standard text characters (e.g., "/" for division, "*" for multiplication, and "^" for exponents).
```

### Migrating Away from Prefilled Responses

Starting with Claude 4.6 models, prefilled responses on the last assistant turn are no longer supported.

- **Controlling output formatting:** Use Structured Outputs or ask the model to conform to your output structure.
- **Eliminating preambles:** Use direct instructions: "Respond directly without preamble."
- **Avoiding bad refusals:** Claude is much better at appropriate refusals now.
- **Continuations:** Move the continuation to the user message with the previous response text.
- **Context hydration:** Inject reminders into the user turn or hydrate via tools.

---

## Tool Use

### Tool Usage

Claude's latest models benefit from explicit direction to use specific tools. If you say "can you suggest some changes," Claude will sometimes provide suggestions rather than implementing them.

**Less effective (Claude will only suggest):**
```text
Can you suggest some changes to improve this function?
```

**More effective (Claude will make the changes):**
```text
Change this function to improve its performance.
```

To make Claude more proactive about taking action:

```text
By default, implement changes rather than only suggesting them. If the user's intent is unclear, infer the most useful likely action and proceed, using tools to discover any missing details instead of guessing.
```

Claude Opus 4.6 is more responsive to the system prompt than previous models. If your prompts were designed to reduce undertriggering on tools, these models may now overtrigger. Where you might have said "CRITICAL: You MUST use this tool when...", you can use "Use this tool when...".

### Optimize Parallel Tool Calling

Claude's latest models excel at parallel tool execution — running multiple speculative searches, reading several files at once, executing bash commands in parallel.

```text
If you intend to call multiple tools and there are no dependencies between the tool calls, make all of the independent tool calls in parallel. Prioritize calling tools simultaneously whenever the actions can be done in parallel rather than sequentially.
```

---

## Thinking and Reasoning

### Overthinking and Excessive Thoroughness

Claude Opus 4.6 does significantly more upfront exploration than previous models. If your prompts previously encouraged thoroughness, tune that guidance:

- **Replace blanket defaults with targeted instructions.** Instead of "Default to using [tool]," use "Use [tool] when it would enhance your understanding."
- **Remove over-prompting.** Tools that undertriggered before are likely to trigger appropriately now.
- **Use effort as a fallback.** Lower the `effort` setting to reduce thinking.

```text
When you're deciding how to approach a problem, choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning.
```

### Leverage Thinking & Interleaved Thinking

Claude 4.6 uses adaptive thinking (`thinking: {type: "adaptive"}`), where Claude dynamically decides when and how much to think. Claude calibrates based on the `effort` parameter and query complexity.

```python
client.messages.create(
    model="claude-opus-4-6",
    max_tokens=64000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},
    messages=[{"role": "user", "content": "..."}],
)
```

Tips:
- **Prefer general instructions over prescriptive steps.** "Think thoroughly" often produces better reasoning than hand-written step-by-step plans.
- **Multishot examples work with thinking.** Use `<thinking>` tags inside examples.
- **Ask Claude to self-check.** "Before you finish, verify your answer against [test criteria]."

---

## Agentic Systems

### Long-Horizon Reasoning and State Tracking

Claude's latest models excel at long-horizon reasoning with exceptional state tracking. Claude maintains orientation across extended sessions by focusing on incremental progress.

#### Context Awareness and Multi-Window Workflows

Claude 4.6 models feature context awareness — tracking remaining context window throughout a conversation.

```text
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. As you approach your token budget limit, save your current progress and state to memory before the context window refreshes.
```

#### Multi-Context Window Workflows

1. **Use a different prompt for the first context window**: Set up framework (write tests, create setup scripts), then iterate on a todo-list.
2. **Have the model write tests in structured format**: Create tests before starting work in `tests.json`.
3. **Set up quality of life tools**: Encourage setup scripts (`init.sh`) to start servers, run tests, linters.
4. **Starting fresh vs compacting**: Claude's latest models are extremely effective at discovering state from the local filesystem.
5. **Provide verification tools**: Playwright MCP server or computer use for testing UIs.
6. **Encourage complete usage of context**: "Continue working systematically until you have completed this task."

#### State Management Best Practices

- **Use structured formats for state data**: JSON for test results, task status
- **Use unstructured text for progress notes**: Freeform for general progress tracking
- **Use git for state tracking**: Git provides log + checkpoints. Claude 4.6 performs especially well with git.
- **Emphasize incremental progress**: Ask Claude to track progress and work incrementally.

### Balancing Autonomy and Safety

Without guidance, Claude Opus 4.6 may take actions that are difficult to reverse or affect shared systems.

```text
Consider the reversibility and potential impact of your actions. You are encouraged to take local, reversible actions like editing files or running tests, but for actions that are hard to reverse, affect shared systems, or could be destructive, ask the user before proceeding.

Examples of actions that warrant confirmation:
- Destructive operations: deleting files or branches, dropping database tables, rm -rf
- Hard to reverse operations: git push --force, git reset --hard, amending published commits
- Operations visible to others: pushing code, commenting on PRs/issues, sending messages
```

### Research and Information Gathering

For optimal research results:

1. **Provide clear success criteria**
2. **Encourage source verification**
3. **For complex tasks, use structured approach:**

```text
Search for this information in a structured way. As you gather data, develop several competing hypotheses. Track your confidence levels in your progress notes. Regularly self-critique your approach. Update a hypothesis tree or research notes file.
```

### Subagent Orchestration

Claude 4.6 demonstrates significantly improved native subagent orchestration. The model can recognize when tasks benefit from delegating to subagents and does so proactively.

**Watch for overuse** — Claude Opus 4.6 has a strong predilection for subagents and may spawn them when simpler approaches suffice.

```text
Use subagents when tasks can run in parallel, require isolated context, or involve independent workstreams. For simple tasks, sequential operations, single-file edits, or tasks where you need to maintain context across steps, work directly rather than delegating.
```

### Reduce File Creation in Agentic Coding

Claude may create new files for testing/iteration as a "temporary scratchpad."

```text
If you create any temporary new files, scripts, or helper files for iteration, clean up these files by removing them at the end of the task.
```

### Overeagerness

Claude Opus 4.6 tends to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested.

```text
Avoid over-engineering. Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused:

- Scope: Don't add features, refactor code, or make "improvements" beyond what was asked.
- Documentation: Don't add docstrings, comments, or type annotations to code you didn't change.
- Defensive coding: Don't add error handling for scenarios that can't happen.
- Abstractions: Don't create helpers or utilities for one-time operations.
```

### Avoiding Hard-Coding and Test-Focused Solutions

```text
Write a high-quality, general-purpose solution using standard tools. Do not hard-code values or create solutions that only work for specific test inputs. Implement the actual logic that solves the problem generally. If tests are incorrect, inform me rather than working around them.
```

### Minimizing Hallucinations in Agentic Coding

```text
Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering. Investigate and read relevant files BEFORE answering questions about the codebase.
```

---

## Capability-Specific Tips

### Improved Vision Capabilities

Claude Opus 4.6 has improved vision capabilities — better image processing and data extraction, especially with multiple images. Giving Claude a crop tool to "zoom" into relevant image regions shows consistent uplift.

### Frontend Design

Claude Opus 4.6 excels at building complex web applications with strong frontend design. Without guidance, models can default to generic "AI slop" aesthetic.

```text
Focus on:
- Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter.
- Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency.
- Motion: Use animations for effects and micro-interactions.
- Backgrounds: Create atmosphere and depth rather than defaulting to solid colors.

Avoid: Overused font families (Inter, Roboto), cliched color schemes (purple gradients on white), predictable layouts, cookie-cutter design.
```

---

## Migration Considerations

When migrating to Claude 4.6 from earlier generations:

1. **Be specific about desired behavior**
2. **Frame instructions with modifiers** — e.g., "Go beyond the basics to create a fully-featured implementation"
3. **Request features explicitly** — Animations and interactive elements need explicit requests
4. **Update thinking configuration** — Use adaptive thinking with effort parameter
5. **Migrate away from prefilled responses** — Deprecated in Claude 4.6
6. **Tune anti-laziness prompting** — Dial back "CRITICAL: You MUST..." language to normal prompting

### Migrating from Sonnet 4.5 to Sonnet 4.6

Sonnet 4.6 defaults to effort level `high`. Recommended settings:
- **Medium** for most applications
- **Low** for high-volume or latency-sensitive workloads
- Set max output token budget to 64k at medium or high effort

**For coding use cases**, start with `medium` effort.
**For chat and non-coding**, start with `low` effort.

---

*Retrieved from [Anthropic Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) on 2026-04-04.*
