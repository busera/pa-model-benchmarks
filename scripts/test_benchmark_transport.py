from __future__ import annotations

import json
import subprocess
import urllib.error
from pathlib import Path

import pytest


def test_parse_ollama_response_retains_stop_identity_tokens_and_request_controls():
    from benchmark_transport import parse_ollama_response

    payload = {
        "model": "glm-5.2:cloud",
        "stream": False,
        "keep_alive": "30m",
        "think": False,
        "options": {"num_predict": 321, "temperature": 0.2},
        "messages": [{"role": "user", "content": "private prompt must not be retained"}],
    }
    data = {
        "model": "glm-5.2",
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 19,
        "eval_count": 42,
        "message": {"content": '{"ok":true}'},
        "context": [1, 2, 3],
    }

    result = parse_ollama_response("glm-5.2:cloud", data, payload=payload)

    assert result.content == '{"ok":true}'
    assert result.requested_model == "glm-5.2:cloud"
    assert result.returned_model == "glm-5.2"
    assert result.done_reason == "stop"
    assert result.prompt_tokens == 19
    assert result.response_tokens == 42
    assert result.incomplete_reason is None
    assert result.provider_metadata == {
        "returned_model": "glm-5.2",
        "done": True,
        "done_reason": "stop",
        "prompt_tokens": 19,
        "response_tokens": 42,
    }
    assert result.request_metadata == {
        "stream": False,
        "keep_alive": "30m",
        "think": False,
        "options": {"num_predict": 321, "temperature": 0.2},
    }
    assert "messages" not in json.dumps(result.request_metadata)
    assert "private prompt" not in json.dumps(result.request_metadata)


def test_parse_ollama_response_marks_token_limit_incomplete_before_validation():
    from benchmark_transport import parse_ollama_response

    result = parse_ollama_response(
        "model:tag",
        {
            "model": "model:tag",
            "done": True,
            "done_reason": "length",
            "eval_count": 1200,
            "message": {"content": '{"cut_off":'},
        },
        payload={"model": "model:tag", "stream": False, "options": {"num_predict": 1200}},
    )

    assert result.incomplete_reason == "output_truncated"
    assert result.done_reason == "length"
    assert result.response_tokens == 1200
    assert result.request_metadata["options"]["num_predict"] == 1200


def test_parse_ollama_response_marks_empty_zero_token_response_incomplete():
    from benchmark_transport import parse_ollama_response

    result = parse_ollama_response(
        "model:tag",
        {"model": "model:tag", "done": True, "done_reason": "stop", "eval_count": 0, "message": {"content": ""}},
        payload={"model": "model:tag", "stream": False, "options": {"num_predict": 100}},
    )

    assert result.incomplete_reason == "empty_response"


@pytest.mark.parametrize(
    ("done_value", "expected"),
    [(False, "provider_not_done"), (None, "completion_unverified")],
)
def test_parse_ollama_response_fails_closed_without_positive_completion(done_value, expected):
    from benchmark_transport import parse_ollama_response

    envelope = {"model": "model:tag", "done_reason": "stop", "message": {"content": "plausible complete text"}}
    if done_value is not None:
        envelope["done"] = done_value
    result = parse_ollama_response("model:tag", envelope, payload={"model": "model:tag", "stream": False})

    assert result.incomplete_reason == expected


def test_parse_hermes_response_retains_request_only_identity_and_rejects_max_iterations():
    from benchmark_transport import parse_hermes_response

    result = parse_hermes_response(
        "gpt-5.5",
        "session_id: abc\nDraft looks valid\n⚠️ Reached maximum iterations (3)",
        provider="openai-codex",
        max_turns=3,
    )

    assert result.content == "Draft looks valid"
    assert result.returned_model is None
    assert result.incomplete_reason == "max_iterations_reached"
    assert result.evidence_failure == "route_identity_unverified"
    assert result.provider_metadata["identity_evidence"] == "request_only"
    assert result.provider_metadata["completion_evidence"] == "max_iterations_warning"


def test_parse_ollama_response_fails_closed_on_returned_model_mismatch():
    from benchmark_transport import ModelIdentityMismatch, parse_ollama_response

    with pytest.raises(ModelIdentityMismatch, match="requested='glm-5.2:cloud'.*returned='other-model'"):
        parse_ollama_response(
            "glm-5.2:cloud",
            {"model": "other-model", "done": True, "message": {"content": "{}"}},
            payload={"model": "glm-5.2:cloud", "stream": False, "options": {"num_predict": 100}},
        )


def test_failure_classification_distinguishes_transport_timeout_identity_and_provider_contract():
    from benchmark_transport import ModelIdentityMismatch, ProviderContractError, ProviderProcessError, UnsupportedRouteError, classify_exception

    assert classify_exception(TimeoutError("slow")) == "transport_timeout"
    assert classify_exception(subprocess.TimeoutExpired(["hermes"], 10)) == "transport_timeout"
    assert classify_exception(urllib.error.HTTPError("http://localhost", 500, "boom", None, None)) == "transport_http_error"
    assert classify_exception(urllib.error.URLError("offline")) == "transport_unavailable"
    assert classify_exception(ConnectionError("reset")) == "transport_unavailable"
    assert classify_exception(FileNotFoundError("hermes")) == "transport_unavailable"
    assert classify_exception(ModelIdentityMismatch("bad route")) == "provider_model_mismatch"
    assert classify_exception(ProviderContractError("bad envelope")) == "provider_contract_error"
    assert classify_exception(json.JSONDecodeError("bad JSON", "{", 1)) == "provider_contract_error"
    assert classify_exception(ProviderProcessError("CLI failed")) == "provider_process_error"
    assert classify_exception(UnsupportedRouteError("no image route")) == "unsupported_route"
    assert classify_exception(RuntimeError("other")) == "runtime_error"


def test_manifest_hashes_shared_transport_source(tmp_path: Path):
    from benchmark_manifest import build_manifest

    runner = tmp_path / "runner.py"
    runner.write_text("print('safe')\n", encoding="utf-8")
    manifest = build_manifest(
        run_id="transport-source",
        models=["glm-5.2:cloud"],
        task_payload=[{"id": "D01"}],
        source_paths=[runner],
        repeats=1,
        seed=1,
        run_order="balanced",
        privacy_class="synthetic",
        argv=["runner.py"],
        model_routes={"glm-5.2:cloud": "ollama"},
        probe_commands=False,
    )

    transport_sources = {
        source_id: digest
        for source_id, digest in manifest["source_hashes"].items()
        if source_id.endswith("benchmark_transport.py")
    }
    assert len(transport_sources) == 1
    assert next(iter(transport_sources.values()))
