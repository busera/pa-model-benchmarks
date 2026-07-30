from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module():
    return importlib.import_module("coding_workspace_benchmark")


def test_raw_python_is_the_file_content_without_json_or_fence():
    module = load_module()
    source = "def add(a: int, b: int) -> int:\n    return a + b\n"
    assert module.extract_source_response(source) == source


def test_standard_python_fence_with_surrounding_prose_is_unwrapped():
    module = load_module()
    response = "Here is the implementation:\n```python\nVALUE = 1\n```\nThis is ready."
    assert module.extract_source_response(response) == "VALUE = 1\n"


def test_unlabelled_fence_is_accepted_for_normal_coding_responses():
    module = load_module()
    assert module.extract_source_response("```\nVALUE = 1\n```") == "VALUE = 1\n"


@pytest.mark.parametrize(
    "response,match",
    [
        ("", "empty"),
        ("```python\nVALUE = 1", "unterminated"),
        ("```python\nA = 1\n```\n```python\nB = 2\n```", "multiple"),
        ("```json\n{}\n```", "language"),
    ],
)
def test_ambiguous_or_non_code_responses_fail_before_execution(response: str, match: str):
    module = load_module()
    with pytest.raises(module.ResponseContractError, match=match):
        module.extract_source_response(response)


def test_prompt_assigns_one_host_selected_path_without_json_contract(tmp_path: Path):
    module = load_module()
    goal = module.goal_catalog()[3]
    card = goal.cards[1]
    prompt = module.build_file_prompt(goal, card=card, workspace=tmp_path, test_feedback="")
    assert card.write_path in prompt
    assert "complete contents" in prompt.lower()
    assert "JSON" not in prompt
    assert '"files"' not in prompt
    assert "path metadata" not in prompt.lower()


def test_effective_record_has_no_structured_response_format(tmp_path: Path):
    module = load_module()
    goal = module.goal_catalog()[0]
    prompt = module.build_file_prompt(goal, card=goal.cards[0], workspace=tmp_path, test_feedback="")
    record = module.effective_prompt_record("gemma4:31b-mlx", prompt, num_predict=goal.max_output_tokens)
    assert record["response_format"] is None


def test_sandbox_denies_file_data_outside_workspace(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = module.subprocess.run(
        [
            str(module.SANDBOX_EXEC), "-p", module._sandbox_profile(workspace),
            module.PYTHON, "-I", "-B", "-c",
            "from pathlib import Path\ntry: Path('/etc/hosts').read_text()\nexcept OSError: raise SystemExit(42)\nraise SystemExit(0)",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 42, result


def test_workspace_prompt_reader_rejects_generated_symlink(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = 'host'\n", encoding="utf-8")
    (workspace / "solution.py").symlink_to(outside)

    with pytest.raises(module.ScopeViolation, match="symlink"):
        module._workspace_files(workspace, ("solution.py",))


def test_hidden_harness_is_read_only_to_generated_code(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = module.Goal(
        "read-only-harness", 0, "read-only harness", "read-only harness",
        ("solution.py",), (),
        """from pathlib import Path
import pytest

def test_harness_cannot_be_mutated(request):
    with pytest.raises(OSError):
        Path(__file__).write_text('def test_bypass(): assert True')
    with pytest.raises(OSError):
        Path(request.config.inipath).write_text('[pytest]')
""",
        100,
    )

    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is True, (checks, hard_fails)
    assert checks["completion_marker"] is True
    assert checks["expected_test_count"] == 1
    assert hard_fails == []


def test_hidden_test_integrity_mutation_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = module.Goal("integrity", 0, "integrity", "integrity", ("solution.py",), (), "def test_ok(): assert True\n", 100)

    def fake_run(command, **kwargs):
        config_index = max(index for index, value in enumerate(command) if value == "-c")
        config = Path(command[config_index + 1])
        config.write_text("[pytest]\naddopts = -x\n", encoding="utf-8")
        (config.parent / "hidden_tests" / "test_bypass.py").write_text(
            "def test_bypass(): assert True\n", encoding="utf-8",
        )
        return module.subprocess.CompletedProcess(command, 0, stdout="1 passed", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is False
    assert "TEST_WEAKENING" in hard_fails
    assert checks["harness_integrity"] is False


def test_generated_file_mutation_and_extra_file_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = module.Goal("inventory", 0, "inventory", "inventory", ("solution.py",), (), "def test_ok(): assert True\n", 100)

    def fake_run(command, **kwargs):
        (workspace / "solution.py").write_text("VALUE = 2\n", encoding="utf-8")
        (workspace / "extra.py").write_text("BYPASS = True\n", encoding="utf-8")
        return module.subprocess.CompletedProcess(command, 0, stdout="1 passed", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is False
    assert {"TEST_WEAKENING", "FILE_SET_MISMATCH"} <= set(hard_fails)
    assert checks["generated_file_integrity"] is False
    assert checks["file_set_integrity"] is False


@pytest.mark.parametrize("run_id", ["", ".", "../escape", "name/child"])
def test_validated_run_root_rejects_invalid_resume_ids(tmp_path: Path, run_id: str):
    module = load_module()
    with pytest.raises(ValueError, match="run_id"):
        module.validated_run_root(tmp_path, run_id)


def test_hermes_cli_metadata_is_removed_from_fenced_code_response():
    module = load_module()
    raw = "session_id: example\n┌─ Reasoning ─┐\nworking\n```python\nVALUE = 1\n```"
    assert module.parse_hermes_cli_output(raw) == "```python\nVALUE = 1\n```"


def test_hermes_raw_source_preserves_docstring_comment_and_shebang():
    module = load_module()
    source = '#!/usr/bin/env python3\n"""module contract"""\n# preserve me\nVALUE = 1\n'
    assert module.parse_hermes_cli_output("session_id: example\n" + source) == source


def test_hermes_unfenced_reasoning_frame_fails_closed():
    module = load_module()
    raw = "session_id: example\n┌─ Reasoning ─┐\nworking\nVALUE = 1\n"
    with pytest.raises(module.ResponseContractError, match="reasoning"):
        module.parse_hermes_cli_output(raw)


@pytest.mark.parametrize(
    "data,exception",
    [
        ({"model": "wrong-model", "done": True, "message": {"content": "VALUE = 1"}}, "ModelIdentityMismatch"),
        ({"model": "test-model", "done": False, "message": {"content": "VALUE = 1"}}, "IncompleteProviderResponse"),
        ({"model": "test-model", "done_reason": "stop", "message": {"content": "VALUE = 1"}}, "IncompleteProviderResponse"),
        ({"model": "test-model", "done": True, "done_reason": "length", "message": {"content": "VALUE = 1"}}, "IncompleteProviderResponse"),
        ({"model": "test-model", "done": True, "message": "not-an-object"}, "ProviderContractError"),
    ],
)
def test_call_model_rejects_unverified_ollama_envelopes(
    monkeypatch: pytest.MonkeyPatch, data: dict, exception: str,
):
    module = load_module()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(data).encode()

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    with pytest.raises(getattr(module, exception)):
        module.call_model("test-model", "code", num_predict=100)


def test_call_model_rejects_hermes_maximum_iteration_warning(monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    stdout = "```python\nVALUE = 1\n```\nWarning: maximum iterations reached\n"
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=stdout, stderr=""),
    )
    with pytest.raises(module.IncompleteProviderResponse, match="max_iterations"):
        module.call_model("gpt-test", "code", num_predict=100)


def test_hermes_cli_multiple_fences_reach_contract_validation():
    module = load_module()
    raw = (
        "session_id: example\n┌─ Reasoning ─┐\nworking\n"
        "```python\nVALUE = 1\n```\n"
        "```python\nVALUE = 2\n```"
    )
    parsed = module.parse_hermes_cli_output(raw)
    with pytest.raises(module.ResponseContractError, match="multiple"):
        module.extract_source_response(parsed)


def test_hidden_tests_reject_zero_exit_without_pytest_completion(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("import os\nos._exit(0)\n", encoding="utf-8")
    goal = module.Goal(
        "zero-exit", 0, "zero exit", "zero exit", ("solution.py",), (),
        "from solution import VALUE\ndef test_value(): assert VALUE == 1\n", 100,
    )

    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is False
    assert "TEST_CENSUS_MISMATCH" in hard_fails
    assert checks["pytest_completion"] is False
    assert checks["completion_marker"] is False


def test_hidden_tests_reject_module_level_skip(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = module.Goal(
        "skip", 0, "skip", "skip", ("solution.py",), (),
        "import pytest\npytest.skip('bypass', allow_module_level=True)\n", 100,
    )

    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is False
    assert hard_fails == ["TEST_SKIPPED", "TEST_CENSUS_MISMATCH"]
    assert checks["pytest_completion"] is False
    assert checks["completion_marker"] is False


def test_completed_pytest_failure_is_not_a_census_mismatch(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = module.Goal(
        "assertion-failure", 0, "assertion failure", "assertion failure", ("solution.py",), (),
        "from solution import VALUE\ndef test_value(): assert VALUE == 2\n", 100,
    )

    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is False
    assert checks["pytest_completion"] is True
    assert checks["completion_marker"] is True
    assert hard_fails == ["HIDDEN_TEST_FAILURE"]


def test_generated_code_collection_error_is_a_hidden_test_failure(tmp_path: Path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text(
        "BROKEN = callable[[int], int]\n",
        encoding="utf-8",
    )
    goal = module.Goal(
        "collection-error", 0, "collection error", "collection error", ("solution.py",), (),
        "from solution import BROKEN\ndef test_value(): assert BROKEN\n", 100,
    )

    passed, checks, hard_fails = module._run_hidden_tests(workspace, goal)

    assert passed is False
    assert checks["collection_complete"] is False
    assert checks["collection_rc"] not in (0, None)
    assert hard_fails == ["GENERATED_CODE_COLLECTION_ERROR", "TEST_CENSUS_MISMATCH"]


def test_compile_retry_can_reach_the_file_that_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    goal = module.Goal(
        "compile-retry", 1, "compile retry", "write both files", ("first.py", "second.py"),
        (
            module.AtomicCard("first", "write first", "first.py"),
            module.AtomicCard("second", "write second", "second.py", ("first",)),
        ),
        "", 100,
    )
    responses = iter(("FIRST = 1\n", "def broken(:\n", "FIRST = 1\n", "SECOND = 2\n"))

    def fake_call(*args, **kwargs):
        return next(responses), {
            "prompt": 1, "response": 1, "done_reason": "test",
            **module.provider_capabilities("gemma4:31b-mlx"),
        }

    monkeypatch.setattr(module, "call_model", fake_call)
    monkeypatch.setattr(module, "_run_hidden_tests", lambda workspace, selected: (True, {"pytest_rc": 0}, []))
    root = tmp_path / "run"
    root.mkdir()

    cell = module.run_cell("run", root, goal, "gemma4:31b-mlx", "W", 1)

    assert cell.passed is True
    assert cell.model_calls == 4
    workspace = Path(cell.artifact_path).parent / "workspace"
    assert (workspace / "second.py").read_text(encoding="utf-8") == "SECOND = 2\n"


def test_resume_manifest_binds_run_id():
    module = load_module()
    retained = {"run_id": "other-run", "models": ["model"]}
    current = {"run_id": "requested-run", "models": ["model"]}

    with pytest.raises(ValueError, match="run_id"):
        module.validate_resume_manifest(retained, current, keys=("run_id", "models"))


def test_run_cell_marks_unverified_provider_identity_ineligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    module = load_module()
    goal = module.goal_catalog()[0]
    monkeypatch.setattr(
        module,
        "call_model",
        lambda *_args, **_kwargs: (
            "def normalize_id(raw: str) -> str:\n    return raw\n",
            {
                "prompt": None,
                "response": None,
                "done_reason": "unavailable",
                "evidence_failure": "route_identity_unverified",
                **module.provider_capabilities("gpt-test"),
            },
        ),
    )
    monkeypatch.setattr(module, "_run_hidden_tests", lambda *_args: (True, {"pytest_rc": 0}, []))
    root = tmp_path / "run"
    root.mkdir()

    cell = module.run_cell("run", root, goal, "gpt-test", "W", 1)

    assert cell.status == "unverified"
    assert cell.passed is False
    assert cell.hard_fails == ["route_identity_unverified"]


def test_run_cell_writes_raw_code_to_host_selected_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    goal = module.goal_catalog()[0]
    response = "```python\ndef normalize_id(raw: str) -> str:\n    return 'R-04'\n```"
    monkeypatch.setattr(
        module,
        "call_model",
        lambda *args, **kwargs: (
            response,
            {
                "prompt": 1,
                "response": 1,
                "done_reason": "test",
                **module.provider_capabilities("gemma4:31b-mlx"),
            },
        ),
    )
    monkeypatch.setattr(module, "_run_hidden_tests", lambda workspace, selected: (True, {"pytest_rc": 0}, []))
    root = tmp_path / "run"
    root.mkdir()
    cell = module.run_cell("run", root, goal, "gemma4:31b-mlx", "W", 1)
    written = Path(cell.artifact_path).parent / "workspace" / "solution.py"
    assert written.read_text(encoding="utf-8").startswith("def normalize_id")
    assert cell.passed is True
    assert cell.model_calls == 1


def test_run_cell_retries_with_hidden_test_feedback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    goal = module.goal_catalog()[0]
    prompts: list[str] = []
    test_runs = 0

    def fake_call(_model, prompt, **_kwargs):
        prompts.append(prompt)
        return (
            "def normalize_id(raw: str) -> str:\n    return 'R-04'\n",
            {"prompt": 1, "response": 1, "done_reason": "test", **module.provider_capabilities("gemma4:31b-mlx")},
        )

    def fake_tests(_workspace, _goal):
        nonlocal test_runs
        test_runs += 1
        if test_runs == 1:
            return False, {"pytest_rc": 1, "stdout": "assert R-05 == R-04", "stderr": ""}, ["HIDDEN_TEST_FAILURE"]
        return True, {"pytest_rc": 0, "stdout": "1 passed", "stderr": ""}, []

    monkeypatch.setattr(module, "call_model", fake_call)
    monkeypatch.setattr(module, "_run_hidden_tests", fake_tests)
    root = tmp_path / "run"
    root.mkdir()

    cell = module.run_cell("run", root, goal, "gemma4:31b-mlx", "W", 1)

    assert cell.passed is True
    assert cell.model_calls == 2
    assert test_runs == 2
    assert "TEST FEEDBACK" in prompts[1]
    assert "assert R-05 == R-04" in prompts[1]


def test_run_cell_does_not_retry_integrity_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    goal = module.goal_catalog()[0]
    calls = 0

    def fake_call(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return (
            "def normalize_id(raw: str) -> str:\n    return 'R-04'\n",
            {"prompt": 1, "response": 1, "done_reason": "test", **module.provider_capabilities("gemma4:31b-mlx")},
        )

    monkeypatch.setattr(module, "call_model", fake_call)
    monkeypatch.setattr(
        module, "_run_hidden_tests",
        lambda *_args: (False, {"pytest_rc": 0}, ["FILE_SET_MISMATCH"]),
    )
    root = tmp_path / "run"
    root.mkdir()

    cell = module.run_cell("run", root, goal, "gemma4:31b-mlx", "W", 1)

    assert cell.passed is False
    assert cell.hard_fails == ["FILE_SET_MISMATCH"]
    assert calls == 1


def test_multifile_goal_uses_one_ordinary_code_response_per_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_module()
    goal = module.goal_catalog()[3]
    responses = {
        "models.py": "VALUE = 'models'\n",
        "parser.py": "VALUE = 'parser'\n",
        "service.py": "VALUE = 'service'\n",
    }
    prompts: list[str] = []

    def fake_call(_model, prompt, **_kwargs):
        prompts.append(prompt)
        target = next(path for path in responses if f"TARGET FILE: {path}" in prompt)
        return responses[target], {
            "prompt": 1,
            "response": 1,
            "done_reason": "test",
            **module.provider_capabilities("gemma4:31b-mlx"),
        }

    monkeypatch.setattr(module, "call_model", fake_call)
    monkeypatch.setattr(module, "_run_hidden_tests", lambda workspace, selected: (True, {"pytest_rc": 0}, []))
    root = tmp_path / "run"
    root.mkdir()

    cell = module.run_cell("run", root, goal, "gemma4:31b-mlx", "W", 1)

    workspace = Path(cell.artifact_path).parent / "workspace"
    assert cell.passed is True and cell.model_calls == 3
    assert {path.name for path in workspace.glob("*.py")} == set(responses)
    assert all('"files"' not in prompt and "JSON" not in prompt for prompt in prompts)
