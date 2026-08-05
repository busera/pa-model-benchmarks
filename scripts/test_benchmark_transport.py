from __future__ import annotations

import ast
import json
import hashlib
import subprocess
import urllib.error
from pathlib import Path

import pytest


def test_call_identity_is_unique_deterministic_and_round_trips():
    from benchmark_transport import ProviderCallIdentity

    identity = ProviderCallIdentity(
        run_id="night-T", lane="T", task_id="T07", trial_index=2,
        part="t7_multiturn", call_ordinal=1,
    )

    assert identity.as_dict() == {
        "run_id": "night-T", "lane": "T", "task_id": "T07",
        "trial_index": 2, "part": "t7_multiturn", "call_ordinal": 1,
    }
    assert ProviderCallIdentity.from_dict(identity.as_dict()) == identity
    assert identity.key == ("night-T", "T", "T07", 2, "t7_multiturn", 1)


def test_complete_effective_request_substitution_changes_fingerprint():
    from benchmark_transport import canonical_json_bytes, sha256_bytes

    request = {
        "model": "model:cloud", "stream": False, "keep_alive": "30m",
        "messages": [
            {"role": "system", "content": "system-v1"},
            {"role": "user", "content": "fixture"},
        ],
        "options": {"num_predict": 80, "temperature": 1.0},
        "think": True,
    }
    substituted = json.loads(json.dumps(request))
    substituted["messages"][0]["content"] = "system-v2"

    assert canonical_json_bytes(request) == canonical_json_bytes(dict(reversed(list(request.items()))))
    assert sha256_bytes(canonical_json_bytes(request)) != sha256_bytes(canonical_json_bytes(substituted))
    assert not canonical_json_bytes(request).endswith(b"\n")


def test_raw_response_tampering_changes_fingerprint():
    from benchmark_transport import sha256_bytes

    assert sha256_bytes(b'{"done":true}') != sha256_bytes(b'{"done":false}')


@pytest.mark.parametrize(
    "payload",
    [
        {"run_id": "", "lane": "T", "task_id": "T01", "trial_index": 1, "part": "t1", "call_ordinal": 1},
        {"run_id": "run", "lane": "T", "task_id": "T01", "trial_index": 0, "part": "t1", "call_ordinal": 1},
        {"run_id": "run", "lane": "T", "task_id": "T01", "trial_index": 1, "part": "t1", "call_ordinal": 0},
    ],
)
def test_call_identity_rejects_malformed_fields(payload):
    from benchmark_transport import ProviderCallIdentity

    with pytest.raises((TypeError, ValueError)):
        ProviderCallIdentity.from_dict(payload)


def test_call_schedule_rejects_duplicate_identity():
    from benchmark_transport import ProviderCallIdentity, validate_call_schedule

    identity = ProviderCallIdentity("run", "T", "T01", 1, "t1_brief", 1)
    with pytest.raises(ValueError, match="duplicate"):
        validate_call_schedule([identity, identity])


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

    registration = {
        "name": "glm-5.2:cloud",
        "remote_model": "glm-5.2",
        "digest": "abc123",
    }
    result = parse_ollama_response(
        "glm-5.2:cloud", data, payload=payload, registered_identity=registration,
    )

    assert result.content == '{"ok":true}'
    assert result.requested_model == "glm-5.2:cloud"
    assert result.returned_model == "glm-5.2"
    assert result.done_reason == "stop"
    assert result.prompt_tokens == 19
    assert result.response_tokens == 42
    assert result.incomplete_reason is None
    assert result.provider_metadata == {
        "returned_model": "glm-5.2",
        "identity_evidence": "ollama_registered_remote_alias",
        "done": True,
        "done_reason": "stop",
        "prompt_tokens": 19,
        "response_tokens": 42,
        "registered_identity": registration,
        "thinking_chars": 0,
        "thinking_sha256": hashlib.sha256(b"").hexdigest(),
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


def test_ollama_registry_identity_requires_exact_registered_alias():
    from benchmark_transport import ollama_registry_identity

    data = {"models": [{
        "name": "gemma4:31b-cloud",
        "model": "gemma4:31b-cloud",
        "remote_model": "gemma4:31b",
        "digest": "abc123",
    }]}
    assert ollama_registry_identity("gemma4:31b-cloud", data) == {
        "name": "gemma4:31b-cloud",
        "remote_model": "gemma4:31b",
        "digest": "abc123",
    }
    assert ollama_registry_identity("gemma4:12b-cloud", data) is None


def test_suffix_only_cloud_alias_is_rejected_without_registry_evidence():
    from benchmark_transport import ModelIdentityMismatch, parse_ollama_response

    with pytest.raises(ModelIdentityMismatch):
        parse_ollama_response(
            "gemma4:31b-cloud",
            {"model": "gemma4:31b", "done": True, "message": {"content": "{}"}},
            payload={"model": "gemma4:31b-cloud", "stream": False},
        )


def test_live_registry_resolution_is_same_origin_and_lazy(monkeypatch):
    from benchmark_transport import resolve_ollama_registered_identity

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"models": [{
                "name": "gemma4:31b-cloud",
                "model": "gemma4:31b-cloud",
                "remote_model": "gemma4:31b",
                "digest": "abc123",
            }]}).encode()

    calls = []

    def fake_urlopen(request, *, timeout):
        calls.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr("benchmark_transport.urllib.request.urlopen", fake_urlopen)
    assert resolve_ollama_registered_identity(
        "gemma4:31b-cloud", {"model": "gemma4:31b"},
        chat_url="http://localhost:11434/api/chat", timeout_s=12,
    ) == {
        "name": "gemma4:31b-cloud",
        "remote_model": "gemma4:31b",
        "digest": "abc123",
    }
    assert calls == [("http://localhost:11434/api/tags", 12)]
    assert resolve_ollama_registered_identity(
        "local:tag", {"model": "local:tag"},
        chat_url="http://localhost:11434/api/chat", timeout_s=12,
    ) is None
    assert len(calls) == 1


def test_live_registry_resolution_rejects_cross_origin_before_io(monkeypatch):
    from benchmark_transport import ProviderContractError, resolve_ollama_registered_identity

    monkeypatch.setattr(
        "benchmark_transport.urllib.request.urlopen",
        lambda *_args, **_kwargs: pytest.fail("network should not be called"),
    )
    with pytest.raises(ProviderContractError, match="governed localhost"):
        resolve_ollama_registered_identity(
            "gemma4:31b-cloud", {"model": "gemma4:31b"},
            chat_url="https://ollama.example/api/chat", timeout_s=12,
        )


@pytest.mark.parametrize(
    "body",
    [b"not-json", json.dumps({"models": []}).encode()],
)
def test_live_registry_failure_preserves_requested_and_returned_identity(monkeypatch, body):
    from benchmark_transport import ModelIdentityMismatch, resolve_ollama_registered_identity

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return body

    monkeypatch.setattr(
        "benchmark_transport.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )
    with pytest.raises(ModelIdentityMismatch) as caught:
        resolve_ollama_registered_identity(
            "gemma4:31b-cloud", {"model": "gemma4:31b"},
            chat_url="http://127.0.0.1:11434/api/chat", timeout_s=12,
        )
    assert caught.value.requested_model == "gemma4:31b-cloud"
    assert caught.value.returned_model == "gemma4:31b"


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


def test_exception_checks_retains_identity_mismatch_evidence():
    from benchmark_transport import ModelIdentityMismatch, exception_checks

    exc = ModelIdentityMismatch(
        "bad route",
        requested_model="gemma4:31b-cloud",
        returned_model="gemma4:31b",
        registered_identity={
            "name": "gemma4:31b-cloud",
            "remote_model": "other",
            "digest": "abc123",
        },
    )
    assert exception_checks(exc) == {
        "failure_class": "provider_model_mismatch",
        "requested_model": "gemma4:31b-cloud",
        "actual_model": "gemma4:31b",
        "provider_response": {
            "identity_evidence": "mismatch",
            "requested_model": "gemma4:31b-cloud",
            "returned_model": "gemma4:31b",
            "registered_identity": {
                "name": "gemma4:31b-cloud",
                "remote_model": "other",
                "digest": "abc123",
            },
        },
    }


@pytest.mark.parametrize(
    ("filename", "consumer_functions"),
    [
        ("pa_daily_use_benchmark.py", ("preflight_model", "run_cell")),
        ("pa_held_out_benchmark.py", ("preflight_model", "run_cell")),
        ("pa_real_life_pack_benchmark.py", ("run_cell",)),
        ("pa_typical_workload_benchmark.py", ("run_cell",)),
        ("pa_conflict_retrieval_benchmark.py", ("run_cell",)),
        ("pa_extended_capability_benchmark.py", ("run_cell",)),
        ("run_t01_t12_full_matrix_profiled.py", ("run_part",)),
    ],
)
def test_every_native_runner_persists_structured_exception_checks(filename, consumer_functions):
    """Bind duplicated provider-error consumers to the shared identity evidence helper."""
    path = Path(__file__).parent / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "benchmark_transport"
        and any(alias.name == "exception_checks" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imported, f"{filename} must import exception_checks"

    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for function_name in consumer_functions:
        function = functions[function_name]
        exception_handlers = [
            node for node in ast.walk(function) if isinstance(node, ast.ExceptHandler)
        ]
        assert any(
            isinstance(call.func, ast.Name) and call.func.id == "exception_checks"
            for handler in exception_handlers
            for call in ast.walk(handler)
            if isinstance(call, ast.Call)
        ), f"{filename}:{function_name} must persist exception_checks from its error path"


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
