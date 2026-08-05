"""Shared, auditable provider-response handling for PA model benchmarks."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable


class ProviderContractError(RuntimeError):
    """Provider returned an envelope that cannot support benchmark evidence."""


class ModelIdentityMismatch(ProviderContractError):
    """Provider returned a model other than the explicitly requested route."""

    def __init__(
        self,
        message: str,
        *,
        requested_model: str | None = None,
        returned_model: str | None = None,
        registered_identity: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.requested_model = requested_model
        self.returned_model = returned_model
        self.registered_identity = (
            dict(registered_identity) if registered_identity is not None else None
        )


class ProviderProcessError(RuntimeError):
    """Provider CLI exited unsuccessfully after it was invoked."""


class UnsupportedRouteError(RuntimeError):
    """Requested modality or route is deliberately unsupported."""


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize complete evidence payloads with one reproducible JSON encoding."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class ProviderCallIdentity:
    run_id: str
    lane: str
    task_id: str
    trial_index: int
    part: str
    call_ordinal: int

    def __post_init__(self) -> None:
        for name in ("run_id", "lane", "task_id", "part"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"invalid provider call identity {name}")
        for name in ("trial_index", "call_ordinal"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"invalid provider call identity {name}")

    @property
    def key(self) -> tuple[str, str, str, int, str, int]:
        return (
            self.run_id, self.lane, self.task_id, self.trial_index,
            self.part, self.call_ordinal,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "lane": self.lane,
            "task_id": self.task_id,
            "trial_index": self.trial_index,
            "part": self.part,
            "call_ordinal": self.call_ordinal,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderCallIdentity":
        if not isinstance(value, dict):
            raise TypeError("provider call identity must be an object")
        expected = {
            "run_id", "lane", "task_id", "trial_index", "part", "call_ordinal",
        }
        if set(value) != expected:
            raise ValueError("provider call identity fields do not match the contract")
        return cls(**value)


def validate_call_schedule(
    identities: Iterable[ProviderCallIdentity], *, expected_count: int | None = None,
) -> tuple[ProviderCallIdentity, ...]:
    frozen = tuple(identities)
    if any(not isinstance(identity, ProviderCallIdentity) for identity in frozen):
        raise TypeError("call schedule contains a malformed identity")
    keys = [identity.key for identity in frozen]
    if len(keys) != len(set(keys)):
        raise ValueError("call schedule contains a duplicate identity")
    if expected_count is not None and len(frozen) != expected_count:
        raise ValueError(
            f"call schedule contains {len(frozen)} identities; expected {expected_count}",
        )
    return frozen


CALL_EVENT_STATES = frozenset({
    "started", "completed", "failed_transport", "failed_parse",
    "failed_identity", "failed_contract",
})
TERMINAL_CALL_EVENT_STATES = CALL_EVENT_STATES - {"started"}


def _valid_sha256(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class ProviderCallEvent:
    identity: ProviderCallIdentity
    state: str
    request_sha256: str
    requested_model: str
    effective_controls: dict[str, Any]
    raw_response_sha256: str | None = None
    actual_model: str | None = None
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    done: bool | None = None
    done_reason: str | None = None
    elapsed_s: float | None = None
    route_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ProviderCallIdentity):
            raise TypeError("provider call event has invalid identity")
        if self.state not in CALL_EVENT_STATES:
            raise ValueError(f"invalid provider call event state: {self.state}")
        if not _valid_sha256(self.request_sha256):
            raise ValueError("provider call event has invalid request fingerprint")
        if (
            not isinstance(self.requested_model, str)
            or not self.requested_model
            or self.requested_model != self.requested_model.strip()
        ):
            raise ValueError("provider call event has invalid requested model")
        if not isinstance(self.effective_controls, dict):
            raise TypeError("provider call event controls must be an object")
        if not isinstance(self.route_metadata, dict):
            raise TypeError("provider call event route metadata must be an object")
        if self.raw_response_sha256 is not None and not _valid_sha256(self.raw_response_sha256):
            raise ValueError("provider call event has invalid raw-response fingerprint")
        if self.state in {"completed", "failed_parse", "failed_identity", "failed_contract"} and self.raw_response_sha256 is None:
            raise ValueError(f"{self.state} requires raw response evidence")
        if self.state in {"started", "failed_transport"} and self.raw_response_sha256 is not None:
            raise ValueError(f"{self.state} cannot claim raw response evidence")
        for name in ("prompt_tokens", "response_tokens"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"provider call event has invalid {name}")
        if self.elapsed_s is not None and (
            not isinstance(self.elapsed_s, (int, float)) or self.elapsed_s < 0
        ):
            raise ValueError("provider call event has invalid elapsed time")

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.as_dict(),
            "state": self.state,
            "request_sha256": self.request_sha256,
            "raw_response_sha256": self.raw_response_sha256,
            "requested_model": self.requested_model,
            "actual_model": self.actual_model,
            "effective_controls": self.effective_controls,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "done": self.done,
            "done_reason": self.done_reason,
            "elapsed_s": self.elapsed_s,
            "route_metadata": self.route_metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProviderCallEvent":
        if not isinstance(value, dict):
            raise TypeError("provider call event must be an object")
        expected = {
            "identity", "state", "request_sha256", "raw_response_sha256",
            "requested_model", "actual_model", "effective_controls",
            "prompt_tokens", "response_tokens", "done", "done_reason", "elapsed_s",
            "route_metadata",
        }
        if set(value) != expected:
            raise ValueError("provider call event fields do not match the contract")
        fields = dict(value)
        fields["identity"] = ProviderCallIdentity.from_dict(fields["identity"])
        return cls(**fields)


class ProviderCallLifecycleError(RuntimeError):
    """A post-start provider call exit with one constructed terminal event."""

    def __init__(
        self,
        message: str,
        *,
        events: tuple[ProviderCallEvent, ...],
        original_error: BaseException | None = None,
        terminal_persistence_error: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        if len(events) != 2 or events[0].state != "started" or events[1].state not in TERMINAL_CALL_EVENT_STATES:
            raise ValueError("provider lifecycle exception requires one started and one terminal event")
        self.events = events
        self.original_error = original_error
        self.terminal_persistence_error = terminal_persistence_error


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


def ollama_registry_identity(requested_model: str, data: dict[str, Any]) -> dict[str, str] | None:
    """Return one exact, allow-listed Ollama remote-alias registration."""
    if (
        not isinstance(requested_model, str)
        or not requested_model
        or requested_model != requested_model.strip()
    ):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise ProviderContractError("Ollama tags response has invalid models list")
    matches = [
        record
        for record in data["models"]
        if isinstance(record, dict)
        and record.get("name") == requested_model
        and record.get("model") == requested_model
    ]
    if len(matches) > 1:
        raise ProviderContractError(f"ambiguous Ollama registry identity for {requested_model!r}")
    if not matches:
        return None
    remote_model = matches[0].get("remote_model")
    digest = matches[0].get("digest")
    if (
        not isinstance(remote_model, str)
        or not remote_model
        or remote_model != remote_model.strip()
        or not isinstance(digest, str)
        or not digest
        or digest != digest.strip()
    ):
        return None
    return {
        "name": requested_model,
        "remote_model": remote_model,
        "digest": digest,
    }


def resolve_ollama_registered_identity(
    requested_model: str,
    response_data: dict[str, Any],
    *,
    chat_url: str,
    timeout_s: int,
) -> dict[str, str] | None:
    """Fetch fresh same-origin alias evidence only when returned identity differs."""
    returned_model = response_data.get("model") if isinstance(response_data, dict) else None
    if returned_model == requested_model:
        return None
    parsed = urllib.parse.urlsplit(chat_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/api/chat"
        or parsed.query
        or parsed.fragment
    ):
        raise ProviderContractError("Ollama chat URL is not the governed localhost /api/chat origin")
    tags_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/api/tags", "", ""))
    request = urllib.request.Request(tags_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            registry_data = json.loads(response.read().decode())
        registered_identity = ollama_registry_identity(requested_model, registry_data)
    except Exception as exc:
        raise ModelIdentityMismatch(
            "remote alias evidence unavailable: "
            f"requested={requested_model!r}, returned={returned_model!r}; "
            f"registry_error={type(exc).__name__}",
            requested_model=requested_model,
            returned_model=returned_model if isinstance(returned_model, str) else None,
        ) from exc
    if registered_identity is None:
        raise ModelIdentityMismatch(
            f"remote alias not registered: requested={requested_model!r}, returned={returned_model!r}",
            requested_model=requested_model,
            returned_model=returned_model if isinstance(returned_model, str) else None,
        )
    return registered_identity


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


def parse_ollama_response(
    requested_model: str,
    data: dict[str, Any],
    *,
    payload: dict[str, Any],
    registered_identity: dict[str, str] | None = None,
) -> ProviderResult:
    if (
        not isinstance(requested_model, str)
        or not requested_model
        or requested_model != requested_model.strip()
    ):
        raise ProviderContractError("invalid requested model identity")
    if not isinstance(data, dict):
        raise ProviderContractError("Ollama response is not an object")
    returned_model = data.get("model")
    if (
        not isinstance(returned_model, str)
        or not returned_model
        or returned_model != returned_model.strip()
    ):
        raise ProviderContractError("Ollama response has invalid model identity")
    registered_remote_model: str | None = None
    if registered_identity is not None:
        if (
            registered_identity.get("name") != requested_model
            or not isinstance(registered_identity.get("remote_model"), str)
            or not registered_identity["remote_model"]
            or registered_identity["remote_model"] != registered_identity["remote_model"].strip()
            or not isinstance(registered_identity.get("digest"), str)
            or not registered_identity["digest"]
            or registered_identity["digest"] != registered_identity["digest"].strip()
        ):
            raise ProviderContractError("invalid Ollama registered identity evidence")
        registered_remote_model = registered_identity["remote_model"]
    if returned_model != requested_model and returned_model != registered_remote_model:
        raise ModelIdentityMismatch(
            f"model identity mismatch: requested={requested_model!r}, returned={returned_model!r}",
            requested_model=requested_model,
            returned_model=returned_model,
            registered_identity=registered_identity,
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
    if done is False:
        incomplete_reason = "provider_not_done"
    elif done is None:
        incomplete_reason = "completion_unverified"
    elif normalized_reason in {"length", "max_tokens", "token_limit", "context_length"}:
        incomplete_reason = "output_truncated"
    elif not content.strip() and response_tokens == 0:
        incomplete_reason = "empty_response"
    else:
        incomplete_reason = None
    if returned_model == requested_model:
        identity_evidence = "exact"
    else:
        identity_evidence = "ollama_registered_remote_alias"
    provider_metadata = {
        "returned_model": returned_model,
        "identity_evidence": identity_evidence,
        "done": done,
        "done_reason": done_reason,
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
    }
    if identity_evidence == "ollama_registered_remote_alias":
        provider_metadata["registered_identity"] = dict(registered_identity or {})
    thinking = str((message or {}).get("thinking") or "")
    provider_metadata.update(
        thinking_chars=len(thinking),
        thinking_sha256=hashlib.sha256(thinking.encode()).hexdigest(),
    )
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
    for line in (stdout or "").splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("session_id:"):
            continue
        if re.search(
            r"(?:reached\s+maximum\s+(?:iterations|turns)|maximum\s+(?:iterations|turns)\s+reached)",
            stripped,
            flags=re.IGNORECASE,
        ):
            reached_max_turns = True
            continue
        kept.append(line)
    content = "".join(kept).strip()
    if reached_max_turns:
        incomplete_reason = "max_iterations_reached"
        completion_evidence = "max_iterations_warning"
    elif not content.strip():
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
    if isinstance(exc, ProviderCallLifecycleError):
        return {
            "completed": "runtime_error",
            "failed_transport": "transport_unavailable",
            "failed_parse": "provider_contract_error",
            "failed_identity": "provider_model_mismatch",
            "failed_contract": "provider_contract_error",
        }[exc.events[-1].state]
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


def exception_checks(exc: BaseException) -> dict[str, Any]:
    """Retain auditable identity evidence for fail-closed provider errors."""
    failure = classify_exception(exc)
    checks: dict[str, Any] = {"failure_class": failure}
    if isinstance(exc, ProviderCallLifecycleError):
        checks["provider_call_lifecycle"] = [event.as_dict() for event in exc.events]
        if exc.terminal_persistence_error is not None:
            checks["terminal_persistence_error"] = {
                "type": type(exc.terminal_persistence_error).__name__,
                "message": str(exc.terminal_persistence_error)[-1000:],
            }
    if isinstance(exc, ModelIdentityMismatch):
        checks.update({
            "requested_model": exc.requested_model,
            "actual_model": exc.returned_model,
            "provider_response": {
                "identity_evidence": "mismatch",
                "requested_model": exc.requested_model,
                "returned_model": exc.returned_model,
                "registered_identity": (
                    dict(exc.registered_identity)
                    if exc.registered_identity is not None
                    else None
                ),
            },
        })
    return checks
