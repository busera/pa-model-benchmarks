"""Shared, auditable provider-response handling for PA model benchmarks."""
from __future__ import annotations

import json
import subprocess
import urllib.error
from dataclasses import dataclass
from typing import Any


class ProviderContractError(RuntimeError):
    """Provider returned an envelope that cannot support benchmark evidence."""


class ModelIdentityMismatch(ProviderContractError):
    """Provider returned a model other than the explicitly requested route."""


class ProviderProcessError(RuntimeError):
    """Provider CLI exited unsuccessfully after it was invoked."""


class UnsupportedRouteError(RuntimeError):
    """Requested modality or route is deliberately unsupported."""


@dataclass(frozen=True)
class ProviderResult:
    content: str
    requested_model: str
    returned_model: str | None
    done_reason: str
    prompt_tokens: int
    response_tokens: int
    incomplete_reason: str | None
    evidence_failure: str | None
    provider_metadata: dict[str, Any]
    request_metadata: dict[str, Any]


def _accepted_model_identities(requested: str) -> set[str]:
    accepted = {requested}
    if requested.endswith(":cloud"):
        accepted.add(requested.removesuffix(":cloud"))
    if requested.endswith("-cloud"):
        accepted.add(requested.removesuffix("-cloud"))
    return accepted


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def sanitized_request_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain runtime controls without prompts, images, credentials, or URLs."""
    metadata: dict[str, Any] = {
        "stream": bool(payload.get("stream", False)),
        "options": dict(payload.get("options") or {}),
    }
    for key in ("keep_alive", "think", "format"):
        if key in payload:
            metadata[key] = payload[key]
    return metadata


def parse_ollama_response(requested_model: str, data: dict[str, Any], *, payload: dict[str, Any]) -> ProviderResult:
    if not isinstance(data, dict):
        raise ProviderContractError("Ollama response is not an object")
    returned_model = str(data.get("model") or "").strip()
    if not returned_model:
        raise ProviderContractError("Ollama response omitted model identity")
    if returned_model not in _accepted_model_identities(requested_model):
        raise ModelIdentityMismatch(
            f"model identity mismatch: requested={requested_model!r}, returned={returned_model!r}"
        )
    message = data.get("message")
    if message is not None and not isinstance(message, dict):
        raise ProviderContractError("Ollama message field is not an object")
    content = str((message or {}).get("content") or data.get("response") or "")
    done_reason = str(data.get("done_reason") or "unknown")
    prompt_tokens = _safe_int(data.get("prompt_eval_count"))
    response_tokens = _safe_int(data.get("eval_count"))
    raw_done = data.get("done")
    done = raw_done if isinstance(raw_done, bool) else None
    normalized_reason = done_reason.strip().lower()
    if normalized_reason in {"length", "max_tokens", "token_limit", "context_length"}:
        incomplete_reason = "output_truncated"
    elif done is False:
        incomplete_reason = "provider_not_done"
    elif done is None:
        incomplete_reason = "completion_unverified"
    elif not content.strip() and response_tokens == 0:
        incomplete_reason = "empty_response"
    else:
        incomplete_reason = None
    provider_metadata = {
        "returned_model": returned_model,
        "done": done,
        "done_reason": done_reason,
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
    }
    return ProviderResult(
        content=content,
        requested_model=requested_model,
        returned_model=returned_model,
        done_reason=done_reason,
        prompt_tokens=prompt_tokens,
        response_tokens=response_tokens,
        incomplete_reason=incomplete_reason,
        evidence_failure=None,
        provider_metadata=provider_metadata,
        request_metadata=sanitized_request_metadata(payload),
    )


def parse_hermes_response(
    requested_model: str,
    stdout: str,
    *,
    provider: str,
    max_turns: int,
) -> ProviderResult:
    """Parse Hermes CLI text while preserving its explicit telemetry limits."""
    kept: list[str] = []
    reached_max_turns = False
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("session_id:"):
            continue
        if "Reached maximum iterations" in stripped:
            reached_max_turns = True
            continue
        kept.append(line)
    content = "\n".join(kept).strip()
    if reached_max_turns:
        incomplete_reason = "max_iterations_reached"
        completion_evidence = "max_iterations_warning"
    elif not content:
        incomplete_reason = "empty_response"
        completion_evidence = "process_exit_only"
    else:
        incomplete_reason = None
        completion_evidence = "process_exit_only"
    return ProviderResult(
        content=content,
        requested_model=requested_model,
        returned_model=None,
        done_reason="max_iterations" if reached_max_turns else "unavailable",
        prompt_tokens=0,
        response_tokens=0,
        incomplete_reason=incomplete_reason,
        evidence_failure="route_identity_unverified",
        provider_metadata={
            "returned_model": None,
            "identity_evidence": "request_only",
            "completion_evidence": completion_evidence,
            "provider": provider,
        },
        request_metadata={
            "interface": "hermes_cli",
            "provider": provider,
            "requested_model": requested_model,
            "max_turns": max_turns,
        },
    )


def result_checks(result: ProviderResult) -> dict[str, Any]:
    return {
        "requested_model": result.requested_model,
        "actual_model": result.returned_model,
        "provider_response": result.provider_metadata,
        "request_controls": result.request_metadata,
        "incomplete_reason": result.incomplete_reason,
        "evidence_failure": result.evidence_failure,
    }


def classify_exception(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)):
        return "transport_timeout"
    if isinstance(exc, urllib.error.HTTPError):
        return "transport_http_error"
    if isinstance(exc, urllib.error.URLError):
        return "transport_unavailable"
    if isinstance(exc, (ConnectionError, FileNotFoundError)):
        return "transport_unavailable"
    if isinstance(exc, ModelIdentityMismatch):
        return "provider_model_mismatch"
    if isinstance(exc, ProviderContractError):
        return "provider_contract_error"
    if isinstance(exc, json.JSONDecodeError):
        return "provider_contract_error"
    if isinstance(exc, ProviderProcessError):
        return "provider_process_error"
    if isinstance(exc, UnsupportedRouteError):
        return "unsupported_route"
    return "runtime_error"
