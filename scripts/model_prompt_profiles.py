#!/usr/bin/env python3
"""Model-specific prompt and runtime profiles for PA model benchmarks.

Benchmark prompt-guide snapshots are repository-owned under ``prompts/guides``.
Obsidian may hold the working guidance, but benchmark evidence hashes the snapshot
shipped with the exact executable revision.

This module keeps benchmark runners from unfairly using one generic prompt/config for
all model families. It does not weaken task validators; it only adapts the system
preamble and safe runtime options to each model family's documented guidance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_GUIDES_DIR = REPO_ROOT / "prompts" / "guides"


BASE_PA_CONTRACT = """You are being benchmarked as a PA for a synthetic user.
Use only the facts given in the task. Do not invent external facts, balances, file contents, records, or messages.
External communication is draft-only unless explicit approval is present.
When the task involves recommendations, separate evidence from assumptions and state concrete next actions.
Return only the requested final format.
Do not reveal hidden reasoning, planning, requirement parsing, or self-talk.
For JSON tasks, return raw JSON only: no Markdown fences, no leading/trailing prose, exact requested keys.
For section tasks, return only the requested section labels in the requested order.
If a required value is unsupported, use null/empty value or an explicit uncertainty field rather than fabricating.
"""


@dataclass(frozen=True)
class PromptProfile:
    name: str
    guide: str
    system_suffix: str = ""
    options: dict[str, Any] = field(default_factory=dict)
    top_level: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def system_prompt(self) -> str:
        suffix = self.system_suffix.strip()
        return BASE_PA_CONTRACT.strip() + ("\n\n" + suffix if suffix else "")


def guide_path(profile: PromptProfile) -> Path:
    return PROMPT_GUIDES_DIR / profile.guide


def profile_for_model(model_tag: str) -> PromptProfile:
    tag = model_tag.lower()

    if tag.startswith("gpt-") or "openai" in tag:
        return PromptProfile(
            name="openai-gpt",
            guide="OpenAI GPT-5.4 and 5.5 Prompt Engineering Guide.md",
            system_suffix="""OpenAI/GPT contract style: prioritize output contract, permission boundaries, completion criteria, grounding, and verification. Keep initiative bounded by the task; do not continue beyond the requested artifact.""",
            options={},
            notes="Hermes/OpenAI route handles model-specific runtime options outside Ollama.",
        )

    if "qwen3-coder" in tag:
        return PromptProfile(
            name="qwen3-coder",
            guide="Qwen3-Coder Prompt Engineering Guide.md",
            system_suffix="""Qwen3-Coder style: non-thinking final answer; strict patch/schema contract; modify only allowed artifacts; output blockers instead of invented code. For JSON or patch payloads, no Markdown fences.""",
            top_level={"think": False},
            options={"temperature": 0.6, "top_p": 0.95, "top_k": 20, "repeat_penalty": 1.0},
        )

    if "qwen3-next" in tag:
        return PromptProfile(
            name="qwen3-next",
            guide="Qwen3 Next and VL Prompt Engineering Guide.md",
            system_suffix="""Qwen3 Next style: use the system prompt as the behavioral anchor, preserve strict final-format constraints, label uncertainty, and disable thinking for clean benchmark content. Do not include hidden reasoning, scratchpads, or Markdown fences around JSON.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0},
        )

    if "qwen3-vl" in tag or "qwen2.5vl" in tag or "qwen2.5-vl" in tag:
        return PromptProfile(
            name="qwen-vl",
            guide="Qwen3 Next and VL Prompt Engineering Guide.md",
            system_suffix="""Qwen VL style: treat visual evidence separately from assumptions, state uncertainty when image/chart details are unreadable or unavailable, and preserve strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.0, "repeat_penalty": 1.0},
        )

    if "qwen3.6" in tag:
        return PromptProfile(
            name="qwen3.6",
            guide="Qwen 3.6 Prompt Engineering Guide.md",
            system_suffix="""Qwen style: the system prompt is the behavioral anchor. Use explicit uncertainty permission, XML-like boundaries conceptually, and strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0},
        )

    if "qwen3.5" in tag or "qwen35" in tag:
        return PromptProfile(
            name="qwen3.5",
            guide="Qwen 3.5 Prompt Engineering Guide.md",
            system_suffix="""Qwen style: substantive system prompt, explicit uncertainty permission, no greedy decoding, and strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repeat_penalty": 1.5},
        )

    if "kimi" in tag:
        is_code = "code" in tag or "coder" in tag
        return PromptProfile(
            name="kimi-k2-code" if is_code else "kimi-k2",
            guide="Kimi K2.6 and K2.7 Code Prompt Engineering Guide.md",
            system_suffix=("""Kimi coding style: final answer only, strict repo/patch contract, no Markdown fences, no hidden reasoning in final content. Treat coding success as implementation-lane evidence only.""" if is_code else """Kimi instant-mode style: final answer only, strong tool/agent discipline, no Markdown fences, no hidden reasoning in final content. Use the task facts and approval boundaries exactly."""),
            top_level={"think": False},
            options={"temperature": 0.6, "top_p": 0.95},
        )

    if "deepseek-r1" in tag:
        return PromptProfile(
            name="deepseek-r1",
            guide="DeepSeek Prompt Engineering Guide.md",
            system_suffix="""DeepSeek R1 caveat: distilled reasoning models prefer concise user instructions and can degrade with heavy system prompts. This benchmark still uses a minimal contract because PA safety requires it. No few-shot examples.""",
            top_level={"think": False},
            options={"temperature": 0.6, "top_p": 0.95},
        )

    if "deepseek" in tag:
        return PromptProfile(
            name="deepseek-v3",
            guide="DeepSeek Prompt Engineering Guide.md",
            system_suffix="""DeepSeek chat style: standard system/user prompting, explicit JSON/schema wording, and low temperature for deterministic extraction/classification tasks.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )

    if "minimax" in tag:
        return PromptProfile(
            name="minimax-m3",
            guide="MiniMax M3 Prompt Engineering Guide.md",
            system_suffix="""MiniMax M3 style: concise final-answer contract, low-creativity structured output, exact schema/section adherence, and no invented facts. For JSON, return raw valid JSON only with no fences or prose.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )

    if "gemini" in tag:
        return PromptProfile(
            name="gemini-3",
            guide="Gemini 3 Prompt Engineering Guide.md",
            system_suffix="""Gemini 3 style: direct clear instructions, explicit completion criteria, structured-output discipline, and visual/source uncertainty when evidence is missing. Native schema/thinking controls are not assumed through Ollama Cloud; enforce format in the prompt and validators.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )

    if "nemotron" in tag:
        return PromptProfile(
            name="nemotron",
            guide="Nemotron Prompt Engineering Guide.md",
            system_suffix="""Nemotron structured-output style: treat schema validity as the task; validate mentally before returning; use null/uncertainty fields for unsupported values; preserve German/language constraints exactly.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )

    if "gemma" in tag:
        return PromptProfile(
            name="gemma4",
            guide="Gemma 4 Prompt Engineering Guide.md",
            system_suffix="""Gemma style: consolidate all behavior in the system turn. Thinking/tool modes are not used in this final-answer benchmark. Return the final answer only, with no fences around JSON.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )

    if "devstral" in tag:
        return PromptProfile(
            name="devstral",
            guide="Devstral Prompt Engineering Guide.md",
            system_suffix="""Devstral style: Mistral/code-agent-family prompt with clear objective, constraints, allowed changes, and exact output format. Use low temperature and final-answer-only behavior for deterministic PA/coding benchmarks.""",
            top_level={"think": False},
            options={"temperature": 0.15, "top_p": 0.95},
        )

    if "mistral" in tag:
        return PromptProfile(
            name="mistral",
            guide="Mistral Prompt Engineering Guide.md",
            system_suffix="""Mistral style: clear complete hierarchical instructions; exact objective criteria; explicit response format; silently check schema before final output. No fences around JSON.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )

    if "glm" in tag:
        return PromptProfile(
            name="glm-5.2",
            guide="GLM 5.2 Prompt Engineering Guide.md",
            system_suffix="""GLM style: long-horizon/coding strengths but fragile final-answer hygiene in PA tests. Thinking is disabled for automation benchmarks. Return final answer only. For JSON, raw valid JSON only: no fences, no analysis, no requirement parsing.""",
            top_level={"think": False},
            options={"temperature": 1.0, "top_p": 0.95},
        )

    if "ornith" in tag:
        return PromptProfile(
            name="ornith",
            guide="Ornith Prompt Engineering Guide.md",
            system_suffix="""Ornith style: agentic coding model with self-improving RL training. Non-thinking mode for benchmark. Return final answer only; no Markdown fences, no hidden reasoning in content. For JSON, raw valid JSON only with exact requested keys. For coding, modify only allowed files and include verification.""",
            top_level={"think": False},
            options={"temperature": 0.3, "top_p": 0.95},
        )

    if "laguna" in tag:
        return PromptProfile(
            name="laguna-s-2.1",
            guide="Laguna S 2.1 Prompt Engineering Guide.md",
            system_suffix="""Laguna S 2.1 style: agentic coding model with native reasoning. Stage A drop-in uses non-thinking mode for fair contract comparison. Return final answer only; no Markdown fences, no hidden reasoning in content. For JSON, raw valid JSON only with exact requested keys. For coding, modify only allowed files and include verification. If thinking is enabled, keep reasoning in the thinking field, not content.""",
            top_level={"think": False},
            options={"temperature": 0.3, "top_p": 0.95},
        )

    return PromptProfile(
        name="generic",
        guide="No model-specific guide found",
        system_suffix="Generic benchmark contract. If this model becomes a recurring candidate, create a guide under LLM Prompt Guides and add a profile here.",
        top_level={"think": False},
        options={"temperature": 0.3, "top_p": 0.95},
    )


def require_profile_coverage(model_tags: list[str]) -> None:
    """Fail closed when a benchmark candidate lacks governed prompt coverage."""
    missing = [tag for tag in model_tags if profile_for_model(tag).name == "generic"]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            "Missing model-specific prompt profile for: "
            f"{joined}. Add a current guide under LLM Prompt Guides and map it in "
            "scripts/model_prompt_profiles.py before running benchmark evidence."
        )
    missing_guides = [
        str(guide_path(profile_for_model(tag)))
        for tag in model_tags
        if not guide_path(profile_for_model(tag)).is_file()
    ]
    if missing_guides:
        raise FileNotFoundError(f"Repository-owned prompt guides missing: {missing_guides}")


def request_payload(model_tag: str, user_prompt: str, *, num_predict: int = 1200) -> dict[str, Any]:
    """Build an Ollama /api/chat payload using the model-specific profile."""
    profile = profile_for_model(model_tag)
    payload: dict[str, Any] = {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": profile.system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": num_predict, **profile.options},
    }
    payload.update(profile.top_level)
    return payload
