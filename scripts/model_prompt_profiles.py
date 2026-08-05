#!/usr/bin/env python3
"""Model-specific prompt and runtime profiles for PA model benchmarks.

Benchmark prompt-guide snapshots are repository-owned under ``prompts/guides``.
External documentation may hold working guidance, but benchmark evidence hashes the snapshot
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
    """Return only an exact-tag profile; family/substring inference is prohibited."""
    profiles = {
        "gpt-5.5": PromptProfile(
            name="openai-gpt",
            guide="OpenAI GPT-5.4 and 5.5 Prompt Engineering Guide.md",
            system_suffix="""OpenAI/GPT contract style: prioritize output contract, permission boundaries, completion criteria, grounding, and verification. Keep initiative bounded by the task; do not continue beyond the requested artifact.""",
            options={},
            notes="Hermes/OpenAI route handles model-specific runtime options outside Ollama.",
        ),
        "gpt-5.6-sol": PromptProfile(
            name="openai-gpt-5.6",
            guide="OpenAI GPT-5.6 Prompt Engineering Guide.md",
            system_suffix="""OpenAI/GPT contract style: prioritize output contract, permission boundaries, completion criteria, grounding, and verification. Keep initiative bounded by the task; do not continue beyond the requested artifact.""",
            options={},
            notes="Hermes/OpenAI route handles model-specific runtime options outside Ollama.",
        ),
        "qwen3-coder:480b-cloud": PromptProfile(
            name="qwen3-coder",
            guide="Qwen3-Coder Prompt Engineering Guide.md",
            system_suffix="""Qwen3-Coder style: non-thinking final answer; strict patch/schema contract; modify only allowed artifacts; output blockers instead of invented code. For JSON or patch payloads, no Markdown fences.""",
            top_level={"think": False},
            options={"temperature": 0.6, "top_p": 0.95, "top_k": 20, "repeat_penalty": 1.0},
        ),
        "qwen3-next:cloud": PromptProfile(
            name="qwen3-next",
            guide="Qwen3 Next and VL Prompt Engineering Guide.md",
            system_suffix="""Qwen3 Next style: use the system prompt as the behavioral anchor, preserve strict final-format constraints, label uncertainty, and disable thinking for clean benchmark content. Do not include hidden reasoning, scratchpads, or Markdown fences around JSON.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0},
        ),
        "qwen3-vl:latest": PromptProfile(
            name="qwen-vl",
            guide="Qwen3 Next and VL Prompt Engineering Guide.md",
            system_suffix="""Qwen VL style: treat visual evidence separately from assumptions, state uncertainty when image/chart details are unreadable or unavailable, and preserve strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.0, "repeat_penalty": 1.0},
        ),
        "qwen2.5vl:32b": PromptProfile(
            name="qwen-vl",
            guide="Qwen3 Next and VL Prompt Engineering Guide.md",
            system_suffix="""Qwen VL style: treat visual evidence separately from assumptions, state uncertainty when image/chart details are unreadable or unavailable, and preserve strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.0, "repeat_penalty": 1.0},
        ),
    }
    qwen36 = PromptProfile(
            name="qwen3.6",
            guide="Qwen 3.6 Prompt Engineering Guide.md",
            system_suffix="""Qwen style: the system prompt is the behavioral anchor. Use explicit uncertainty permission, XML-like boundaries conceptually, and strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0},
        )
    for tag in (
        "qwen3.6:27b-mlx-bf16",
        "qwen3.6:27b-mlx",
        "qwen3.6:35b-mlx",
        "qwen3.6:35b-a3b-coding-mxfp8",
    ):
        profiles[tag] = qwen36
    qwen35 = PromptProfile(
            name="qwen3.5",
            guide="Qwen 3.5 Prompt Engineering Guide.md",
            system_suffix="""Qwen style: substantive system prompt, explicit uncertainty permission, no greedy decoding, and strict final-format constraints. Thinking is disabled for clean benchmark content.""",
            top_level={"think": False},
            options={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repeat_penalty": 1.5},
        )
    for tag in ("qwen3.5:35b-a3b-coding-nvfp4", "qwen3.5:35b"):
        profiles[tag] = qwen35
    profiles["kimi-k3:cloud"] = PromptProfile(
        name="kimi-k3-thinking",
        guide="Kimi K3 Thinking-On Benchmark Guide.md",
        system_suffix="""Kimi K3 thinking-on benchmark style: use the common PA safety and output contract, keep reasoning separate from final content, use only supplied facts, and return the exact requested final format.""",
        top_level={"think": True},
        options={},
        notes="Exact Kimi K3 lane; no Kimi K2.x prompting facts are inherited.",
    )
    profiles["kimi-k2.6:cloud"] = PromptProfile(
            name="kimi-k2",
            guide="Kimi K2.6 and K2.7 Code Prompt Engineering Guide.md",
            system_suffix="""Kimi instant-mode style: final answer only, strong tool/agent discipline, no Markdown fences, no hidden reasoning in final content. Use the task facts and approval boundaries exactly.""",
            top_level={"think": False},
            options={"temperature": 0.6, "top_p": 0.95},
        )
    profiles["kimi-k2.7-code:cloud"] = PromptProfile(
            name="kimi-k2-code",
            guide="Kimi K2.6 and K2.7 Code Prompt Engineering Guide.md",
            system_suffix="""Kimi coding style: final answer only, strict repo/patch contract, no Markdown fences, no hidden reasoning in final content. Treat coding success as implementation-lane evidence only.""",
            top_level={"think": False},
            options={"temperature": 0.6, "top_p": 0.95},
        )
    profiles["deepseek-v4-flash:0731-cloud"] = PromptProfile(
        name="deepseek-v4-flash-0731-thinking",
        guide="DeepSeek V4 Flash 0731 PA Benchmark Guide.md",
        system_suffix="""DeepSeek V4 Flash 0731 agentic PA style: preserve approval and scope boundaries, use current supplied evidence, recover explicitly from tool failures, keep reasoning outside final content, and return the exact requested final format.""",
        top_level={"think": True},
        options={"temperature": 1.0, "top_p": 0.95},
        notes="Exact 2026-07-31 agentic route; no generic Flash, Pro, or V3.x inheritance.",
    )
    profiles["deepseek-v4-pro:cloud"] = PromptProfile(
        name="deepseek-v4-pro",
        guide="DeepSeek V4 Pro Benchmark Guide.md",
        system_suffix="""DeepSeek V4 Pro benchmark style: use the common PA contract, exact schema wording, explicit uncertainty, and final-answer-only output. Do not infer unsupported model capabilities from the tag.""",
        top_level={"think": False},
        options={"temperature": 0.2, "top_p": 0.95},
    )
    profiles["deepseek-v3.2:cloud"] = PromptProfile(
        name="deepseek-v3.2",
        guide="DeepSeek Prompt Engineering Guide.md",
        system_suffix="""DeepSeek chat style: standard system/user prompting, explicit JSON/schema wording, and low temperature for deterministic extraction/classification tasks.""",
        top_level={"think": False},
        options={"temperature": 0.2, "top_p": 0.95},
    )
    profiles["minimax-m3:cloud"] = PromptProfile(
            name="minimax-m3",
            guide="MiniMax M3 Prompt Engineering Guide.md",
            system_suffix="""MiniMax M3 style: concise final-answer contract, low-creativity structured output, exact schema/section adherence, and no invented facts. For JSON, return raw valid JSON only with no fences or prose.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )
    profiles["gemini-3-flash-preview:cloud"] = PromptProfile(
            name="gemini-3",
            guide="Gemini 3 Prompt Engineering Guide.md",
            system_suffix="""Gemini 3 style: direct clear instructions, explicit completion criteria, structured-output discipline, and visual/source uncertainty when evidence is missing. Native schema/thinking controls are not assumed through Ollama Cloud; enforce format in the prompt and validators.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )
    profiles["nemotron-3-ultra:cloud"] = PromptProfile(
            name="nemotron-agentic-thinking",
            guide="Nemotron Prompt Engineering Guide.md",
            system_suffix="""Nemotron agentic PA style: preserve approval and scope boundaries, plan and recover across tool calls, validate tool evidence before claiming success, use null/uncertainty fields for unsupported values, and preserve German/language constraints exactly.""",
            top_level={"think": True},
            options={"temperature": 0.2, "top_p": 0.95},
        )
    profiles["gemma4:31b-cloud"] = PromptProfile(
            name="gemma4",
            guide="Gemma 4 Prompt Engineering Guide.md",
            system_suffix="""Gemma style: consolidate all behavior in the system turn. Thinking/tool modes are not used in this final-answer benchmark. Return the final answer only, with no fences around JSON.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )
    profiles["devstral-2:123b-cloud"] = PromptProfile(
            name="devstral",
            guide="Devstral Prompt Engineering Guide.md",
            system_suffix="""Devstral style: Mistral/code-agent-family prompt with clear objective, constraints, allowed changes, and exact output format. Use low temperature and final-answer-only behavior for deterministic PA/coding benchmarks.""",
            top_level={"think": False},
            options={"temperature": 0.15, "top_p": 0.95},
        )
    mistral = PromptProfile(
            name="mistral",
            guide="Mistral Prompt Engineering Guide.md",
            system_suffix="""Mistral style: clear complete hierarchical instructions; exact objective criteria; explicit response format; silently check schema before final output. No fences around JSON.""",
            top_level={"think": False},
            options={"temperature": 0.2, "top_p": 0.95},
        )
    profiles["mistral-large-3:675b-cloud"] = mistral
    profiles["mistral-small3.2:24b"] = mistral
    profiles["glm-5.2:cloud"] = PromptProfile(
            name="glm-5.2",
            guide="GLM 5.2 Prompt Engineering Guide.md",
            system_suffix="""GLM style: long-horizon/coding strengths but fragile final-answer hygiene in PA tests. Thinking is disabled for automation benchmarks. Return final answer only.

CRITICAL FORMAT RULE: The first character of your response must be the first character of the requested output. For JSON tasks, the first character must be { or [ and the last must be } or ]. Do NOT wrap output in Markdown code fences (```). Do NOT include any text before or after the requested format. Do NOT include analysis, planning, requirement parsing, or commentary. If you are about to write ```json or ```, stop and write the JSON directly instead.

HEALTH SAFETY RULE: When health data is stale, partial, or missing, recommend recovery or light training — never hard intervals. If HRV is stale, sleep is under 6h, or resting HR is elevated, the answer is recovery or light, not hard training. Do not recommend hard training when evidence is incomplete.

Do not invent data, prices, health diagnoses, or evidence not supplied in the task.""",
            top_level={"think": False},
            options={"temperature": 1.0, "top_p": 0.95},
        )
    profiles["ornith:cloud"] = PromptProfile(
            name="ornith",
            guide="Ornith Prompt Engineering Guide.md",
            system_suffix="""Ornith style: agentic coding model with self-improving RL training. Non-thinking mode for benchmark. Return final answer only; no Markdown fences, no hidden reasoning in content. For JSON, raw valid JSON only with exact requested keys. For coding, modify only allowed files and include verification.""",
            top_level={"think": False},
            options={"temperature": 0.3, "top_p": 0.95},
        )
    profiles["laguna-s-2.1:cloud"] = PromptProfile(
            name="laguna-s-2.1",
            guide="Laguna S 2.1 Prompt Engineering Guide.md",
            system_suffix="""Laguna S 2.1 style: agentic coding model with native reasoning. Stage A drop-in uses non-thinking mode for fair contract comparison. Return final answer only; no Markdown fences, no hidden reasoning in content. For JSON, raw valid JSON only with exact requested keys. For coding, modify only allowed files and include verification. If thinking is enabled, keep reasoning in the thinking field, not content.""",
            top_level={"think": False},
            options={"temperature": 0.3, "top_p": 0.95},
        )
    return profiles.get(model_tag, PromptProfile(
        name="generic",
        guide="No model-specific guide found",
        system_suffix="Generic benchmark contract. If this model becomes a recurring candidate, create a guide under LLM Prompt Guides and add a profile here.",
        top_level={"think": False},
        options={"temperature": 0.3, "top_p": 0.95},
    ))


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
    """Build an Ollama /api/chat payload using the model-specific profile.

    Thinking-on models need a larger num_predict budget because the thinking
    phase consumes tokens from the same budget. Apply a 2x multiplier when the
    profile has think=True so the response has room after reasoning.
    """
    profile = profile_for_model(model_tag)
    effective_num_predict = num_predict
    if profile.top_level.get("think") is True:
        effective_num_predict = num_predict * 2
    payload: dict[str, Any] = {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": profile.system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": effective_num_predict, **profile.options},
    }
    payload.update(profile.top_level)
    return payload
