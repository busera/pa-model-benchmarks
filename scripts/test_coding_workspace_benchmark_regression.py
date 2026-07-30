#!/usr/bin/env python3
"""Regression tests retained for the coding workspace benchmark."""
from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from collections import Counter
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("coding_workspace_benchmark.py")


def load_module():
    spec = importlib.util.spec_from_file_location("coding_workspace_benchmark_regression", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_fixture(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_catalog_has_contiguous_complexity_ladder_and_atomic_cards():
    m = load_module()
    goals = m.goal_catalog()
    assert [goal.tier for goal in goals] == list(range(6))
    assert [goal.id for goal in goals] == [f"C{i}" for i in range(6)]
    assert all(goal.allowed_files for goal in goals)
    assert all(goal.hidden_tests.strip() for goal in goals)
    assert all(goal.cards for goal in goals)
    for goal in goals:
        assert {card.write_path for card in goal.cards} == set(goal.allowed_files)
        assert all(len(card.write_paths) == 1 for card in goal.cards)
        assert all(card.verification for card in goal.cards)


def test_promotion_catalog_has_three_independent_families_per_tier():
    m = load_module()
    goals = m.promotion_goal_catalog()
    assert len(goals) == 18
    assert len({goal.id for goal in goals}) == 18
    assert Counter(goal.tier for goal in goals) == Counter({tier: 3 for tier in range(6)})
    assert {goal.id for goal in goals} == {
        f"C{tier}-{family}" for tier in range(6) for family in ("P", "S", "R")
    }
    for goal in goals:
        assert {card.write_path for card in goal.cards} == set(goal.allowed_files)
        assert goal.hidden_tests.strip()


def test_promotion_breakpoint_requires_every_family_and_repeat():
    m = load_module()
    expected = {0: {"C0-P", "C0-S", "C0-R"}}
    cells = [
        m.Cell.synthetic(
            model="local", mode="M", tier=0, trial=trial, passed=True, goal_id=goal_id,
        )
        for goal_id in ("C0-P", "C0-S")
        for trial in (1, 2, 3)
    ]
    incomplete = m.breakpoint_for(
        cells, model="local", mode="M", expected_repeats=3, expected_goal_ids=expected,
    )
    assert incomplete["tiers"]["C0"]["state"] == "ineligible"
    assert incomplete["tiers"]["C0"]["expected_trials"] == 9

    cells.extend(
        m.Cell.synthetic(
            model="local", mode="M", tier=0, trial=trial, passed=True, goal_id="C0-R",
        )
        for trial in (1, 2, 3)
    )
    complete = m.breakpoint_for(
        cells, model="local", mode="M", expected_repeats=3, expected_goal_ids=expected,
    )
    assert complete["tiers"]["C0"]["state"] == "reliable"
    assert complete["tiers"]["C0"]["trials"] == 9


def test_promotion_cli_and_default_roster_cover_all_local_coding_candidates():
    m = load_module()
    assert m.DEFAULT_MODELS == [
        "qwen3.6:35b-a3b-coding-mxfp8",
        "qwen3.6:35b-mlx",
        "qwen3.6:27b-mlx",
        "qwen3.6:27b-mlx-bf16",
        "gemma4:31b-mlx",
        "nemotron3:33b",
    ]
    args = m.parse_args(["--suite", "promotion", "--families", "P,S,R"])
    assert args.suite == "promotion"
    assert args.families == "P,S,R"


def test_summary_counts_goals_not_only_tiers(tmp_path: Path):
    m = load_module()
    goals = m.promotion_goal_catalog()[:3]
    cells = [
        m.Cell.synthetic(
            model="local", mode="M", tier=goal.tier, trial=1, passed=True, goal_id=goal.id,
        )
        for goal in goals
    ]
    summary = m.summarize(
        "run", tmp_path, cells, ["local"], ["M"], 1, "promotion_screen",
        goals=goals,
    )
    assert summary["cells_planned"] == 3
    assert summary["cells_completed"] == 3


def test_breakpoint_renders_entirely_missing_expected_tier_as_ineligible():
    m = load_module()
    expected = {0: {"C0-P", "C0-S", "C0-R"}, 1: {"C1-P", "C1-S", "C1-R"}}
    cells = [
        m.Cell.synthetic(model="local", mode="M", tier=0, trial=1, passed=True, goal_id=goal_id)
        for goal_id in expected[0]
    ]
    result = m.breakpoint_for(
        cells, model="local", mode="M", expected_repeats=1, expected_goal_ids=expected,
    )
    assert result["tiers"]["C1"] == {
        "state": "ineligible", "pass_rate": None, "trials": 0,
        "expected_trials": 3, "expected_goals": ["C1-P", "C1-R", "C1-S"],
    }


def test_resume_loader_rejects_duplicate_cells_and_skips_completed(tmp_path: Path):
    m = load_module()
    goal = m.goal_catalog()[0]
    row = m.Cell.synthetic(model="local", mode="M", tier=0, trial=1, passed=True)
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps(m.asdict(row)) + "\n", encoding="utf-8")
    loaded = m.load_existing_cells(results)
    pending = m.pending_schedule(
        [("local", goal, "M", 1), ("local", goal, "A", 1)], loaded,
    )
    assert [(model, item.id, mode, trial) for model, item, mode, trial in pending] == [
        ("local", "C0", "A", 1),
    ]
    results.write_text(results.read_text() + json.dumps(m.asdict(row)) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        m.load_existing_cells(results)


def test_resume_reconciles_terminal_cell_and_archives_partial_workspace(tmp_path: Path):
    m = load_module()
    goal = m.goal_catalog()[0]
    schedule = [("local", goal, "M", 1), ("local", goal, "A", 1)]
    complete_dir = m.cell_trial_dir(tmp_path, goal, "local", "M", 1)
    complete_dir.mkdir(parents=True)
    terminal = m.Cell.synthetic(model="local", mode="M", tier=0, trial=1, passed=True)
    terminal.artifact_path = str(complete_dir / "cell.json")
    (complete_dir / "cell.json").write_text(json.dumps(m.asdict(terminal)), encoding="utf-8")
    partial_dir = m.cell_trial_dir(tmp_path, goal, "local", "A", 1)
    (partial_dir / "workspace").mkdir(parents=True)
    (partial_dir / "workspace" / "partial.py").write_text("partial", encoding="utf-8")

    cells = m.reconcile_resume(tmp_path, schedule)

    assert [m._cell_key(cell) for cell in cells] == [m._cell_key(terminal)]
    assert not partial_dir.exists()
    archived = list((tmp_path / "_Archive" / "incomplete-cells").glob("*"))
    assert len(archived) == 1 and (archived[0] / "workspace" / "partial.py").is_file()
    loaded = m.load_existing_cells(tmp_path / "results.jsonl")
    assert [m._cell_key(cell) for cell in loaded] == [m._cell_key(terminal)]


def test_resume_rejects_terminal_cell_from_wrong_schedule_slot(tmp_path: Path):
    m = load_module()
    c0, c1 = m.goal_catalog()[:2]
    schedule = [("local", c0, "W", 1), ("local", c1, "W", 1)]
    c0_dir = m.cell_trial_dir(tmp_path, c0, "local", "W", 1)
    c0_dir.mkdir(parents=True)
    wrong = m.Cell.synthetic(
        model="local", mode="W", tier=c1.tier, trial=1, passed=True, goal_id=c1.id,
    )
    wrong.artifact_path = str(c0_dir / "cell.json")
    (c0_dir / "cell.json").write_text(json.dumps(m.asdict(wrong)), encoding="utf-8")

    with pytest.raises(ValueError, match="schedule slot"):
        m.reconcile_resume(tmp_path, schedule)


def test_resume_rejects_terminal_artifact_path_mismatch(tmp_path: Path):
    m = load_module()
    goal = m.goal_catalog()[0]
    schedule = [("local", goal, "W", 1)]
    trial_dir = m.cell_trial_dir(tmp_path, goal, "local", "W", 1)
    trial_dir.mkdir(parents=True)
    terminal = m.Cell.synthetic(model="local", mode="W", tier=goal.tier, trial=1, passed=True)
    terminal.artifact_path = str(tmp_path / "elsewhere" / "cell.json")
    (trial_dir / "cell.json").write_text(json.dumps(m.asdict(terminal)), encoding="utf-8")

    with pytest.raises(ValueError, match="artifact_path"):
        m.reconcile_resume(tmp_path, schedule)


def test_resume_rejects_missing_canonical_terminal_artifact(tmp_path: Path):
    m = load_module()
    goal = m.goal_catalog()[0]
    schedule = [("local", goal, "W", 1)]
    trial_dir = m.cell_trial_dir(tmp_path, goal, "local", "W", 1)
    retained = m.Cell.synthetic(model="local", mode="W", tier=goal.tier, trial=1, passed=True)
    retained.artifact_path = str(trial_dir / "cell.json")
    (tmp_path / "results.jsonl").write_text(json.dumps(m.asdict(retained)) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing canonical terminal artifact"):
        m.reconcile_resume(tmp_path, schedule)


def test_resume_rejects_conflicting_duplicate_terminal(tmp_path: Path):
    m = load_module()
    goal = m.goal_catalog()[0]
    schedule = [("local", goal, "W", 1)]
    trial_dir = m.cell_trial_dir(tmp_path, goal, "local", "W", 1)
    trial_dir.mkdir(parents=True)
    retained = m.Cell.synthetic(model="local", mode="W", tier=goal.tier, trial=1, passed=True)
    retained.artifact_path = str(trial_dir / "cell.json")
    (tmp_path / "results.jsonl").write_text(json.dumps(m.asdict(retained)) + "\n", encoding="utf-8")
    conflicting = m.Cell(**{**m.asdict(retained), "score": 0.0})
    (trial_dir / "cell.json").write_text(json.dumps(m.asdict(conflicting)), encoding="utf-8")

    with pytest.raises(ValueError, match="conflicting duplicate"):
        m.reconcile_resume(tmp_path, schedule)


def test_resume_archives_torn_final_jsonl_row_and_rejects_unscheduled_cell(tmp_path: Path):
    m = load_module()
    goal = m.goal_catalog()[0]
    valid = m.Cell.synthetic(model="local", mode="M", tier=0, trial=1, passed=True)
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps(m.asdict(valid)) + "\n{\"run_id\":", encoding="utf-8")
    recovered = m.recover_torn_results(results, tmp_path / "_Archive")
    assert [m._cell_key(cell) for cell in recovered] == [m._cell_key(valid)]
    assert list((tmp_path / "_Archive").glob("torn-results-*.jsonl"))

    wrong = m.Cell.synthetic(model="other", mode="M", tier=0, trial=1, passed=True)
    with pytest.raises(ValueError, match="unscheduled"):
        m.validate_cells_against_schedule([wrong], [("local", goal, "M", 1)])


def test_c2_spec_explicitly_defines_fields_thresholds_and_activity_scope():
    m = load_module()
    spec = m.goal_catalog()[2].specification
    for phrase in (
        "measured_date",
        "fresh only when measured_date equals current_date",
        "stale when measured_date is a valid earlier date",
        "unknown when measured_date is missing or invalid",
        "every non-nutrition metric",
        "Google Health/Fitbit",
    ):
        assert phrase in spec


def test_all_routes_disable_structured_output_schema():
    m = load_module()
    for model in ("kimi-k2.7-code:cloud", "gemma4:31b-cloud", "qwen3.6:27b-mlx-bf16"):
        record = m.effective_prompt_record(model, "code", num_predict=100)
        assert record["response_format"] is None
    assert m.model_route("gpt-5.6-sol") == "openai-codex"
    assert m.model_route("kimi-k2.7-code:cloud") == "ollama"


def test_hermes_cli_output_strips_only_session_and_reasoning_metadata():
    m = load_module()
    raw = 'session_id: 20260719_example\n┌─ Reasoning ─┐\n**working**\n```python\nVALUE = 1\n```'
    assert m.parse_hermes_cli_output(raw) == '```python\nVALUE = 1\n```'
    with pytest.raises(m.ResponseContractError):
        m.parse_hermes_cli_output('session_id: only')



def test_new_run_root_rejects_path_escape_and_existing_evidence(tmp_path: Path):
    m = load_module()
    with pytest.raises(ValueError, match="run_id"):
        m.new_run_root(tmp_path, "../escape")
    root = m.new_run_root(tmp_path, "valid-run_01")
    assert root == (tmp_path / "valid-run_01").resolve()
    with pytest.raises(FileExistsError):
        m.new_run_root(tmp_path, "valid-run_01")


@pytest.mark.parametrize(
    "models,modes,tiers,match",
    [
        (["model"], [], ["C0"], "modes"),
        (["model"], ["W", "W"], ["C0"], "duplicate modes"),
        (["model", "model"], ["W"], ["C0"], "duplicate models"),
        (["model"], ["W"], ["C0", "C0"], "duplicate tiers"),
        (["a:b", "a-b"], ["W"], ["C0"], "workspace"),
        (["Model", "model"], ["W"], ["C0"], "workspace"),
        (["!!!"], ["W"], ["C0"], "workspace"),
        (["model"], ["S"], ["C0"], "modes"),
    ],
)
def test_dimension_preflight_rejects_empty_duplicate_or_colliding_inputs(models, modes, tiers, match):
    m = load_module()
    with pytest.raises(ValueError, match=match):
        m.validate_dimensions(models, modes, tiers, repeats=1)


def test_gpt_manifest_route_is_internally_consistent():
    m = load_module()
    assert m.manifest_route("gpt-5.6-sol") == "hermes"
    manifest = m.build_manifest(
        run_id="manifest-test", models=["gpt-5.6-sol"], task_payload=[],
        source_paths=[m.Path(m.__file__)], repeats=1, seed=19, run_order="model-major",
        privacy_class="synthetic", argv=["runner.py"],
        model_routes={"gpt-5.6-sol": m.manifest_route("gpt-5.6-sol")}, probe_commands=False,
    )
    identity = manifest["model_identity"]["gpt-5.6-sol"]
    assert identity["provider_route"] == "hermes"
    assert identity["api_mode"] == "openai-codex"


def test_invalid_dimensions_fail_before_artifact_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    monkeypatch.setattr(m, "ARTIFACTS_DIR", tmp_path)
    with pytest.raises(ValueError, match="modes"):
        m.main(["--models", "gemma4:31b-mlx", "--modes", ",", "--tiers", "C0", "--run-id", "invalid-run"])
    assert not (tmp_path / "invalid-run").exists()


def test_write_files_rejects_escape_and_undeclared_paths(tmp_path: Path):
    m = load_module()
    allowed = ("src/solution.py",)
    with pytest.raises(m.ScopeViolation):
        m.write_model_files(tmp_path, {"../escape.py": "x"}, allowed)
    with pytest.raises(m.ScopeViolation):
        m.write_model_files(tmp_path, {"tests/test_solution.py": "pass"}, allowed)
    m.write_model_files(tmp_path, {"src/solution.py": "VALUE = 1\n"}, allowed)
    assert (tmp_path / "src" / "solution.py").read_text() == "VALUE = 1\n"


def test_atomic_scheduler_rejects_stale_or_missing_dependencies():
    m = load_module()
    goal = m.goal_catalog()[3]
    order = m.atomic_order(goal.cards)
    assert [card.id for card in order] == [card.id for card in goal.cards]
    broken = list(goal.cards)
    broken[1] = m.AtomicCard(
        id=broken[1].id,
        objective=broken[1].objective,
        write_path=broken[1].write_path,
        depends_on=("missing-card",),
        verification=broken[1].verification,
    )
    with pytest.raises(ValueError, match="unknown dependency"):
        m.atomic_order(tuple(broken))


def test_breakpoint_summary_uses_contiguous_reliable_ceiling():
    m = load_module()
    cells = []
    for tier, passes in {0: [True, True, True], 1: [True, True, True], 2: [True, True, False], 3: [True, True, True]}.items():
        for trial, passed in enumerate(passes, 1):
            cells.append(m.Cell.synthetic(model="local", mode="A", tier=tier, trial=trial, passed=passed))
    result = m.breakpoint_for(cells, model="local", mode="A", expected_repeats=3)
    assert result["reliable_ceiling"] == 1
    assert result["breakpoint"] == 2
    assert result["tiers"]["C2"]["state"] == "conditional"
    assert result["tiers"]["C3"]["state"] == "reliable"
    assert result["non_monotonic"] is True


def test_missing_repeat_is_ineligible_not_silently_averaged():
    m = load_module()
    cells = [m.Cell.synthetic(model="local", mode="M", tier=0, trial=1, passed=True)]
    result = m.breakpoint_for(cells, model="local", mode="M", expected_repeats=3)
    assert result["tiers"]["C0"]["state"] == "ineligible"
    assert result["reliable_ceiling"] is None
    assert result["breakpoint"] is None


def test_c2_r_hidden_tests_accept_keyerror_for_unknown_keys(tmp_path: Path):
    m = load_module()
    goal = next(goal for goal in m.promotion_goal_catalog() if goal.id == "C2-R")
    write_fixture(tmp_path, {
        "layered_config.py": """
            import math
            def resolve_config(defaults, environment, overrides, schema):
                for source in (defaults, environment, overrides):
                    unknown = set(source) - set(schema)
                    if unknown: raise KeyError(next(iter(unknown)))
                if set(defaults) != set(schema): raise KeyError('missing default')
                result = {}
                for key, expected in schema.items():
                    value = overrides[key] if key in overrides else environment.get(key, defaults[key])
                    if key in environment and key not in overrides:
                        if expected is bool:
                            lowered = value.lower()
                            if lowered not in {'true','false','1','0'}: raise ValueError('bool')
                            value = lowered in {'true','1'}
                        elif expected is int: value = int(value)
                        elif expected is float:
                            value = float(value)
                            if not math.isfinite(value): raise ValueError('finite')
                        elif expected is str: value = value
                        else: raise TypeError('schema')
                    elif type(value) is not expected:
                        raise TypeError('exact type')
                    result[key] = value
                return result
        """,
    })
    passed, checks, hard_fails = m._run_hidden_tests(tmp_path, goal)
    assert passed is True, (checks, hard_fails)


def test_run_cell_labels_empty_source_as_contract_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    monkeypatch.setattr(
        m,
        "call_model",
        lambda *a, **k: ("", {"prompt": 1, "response": 1, "done_reason": "test", **m.provider_capabilities("gemma4:31b-mlx")}),
    )
    root = tmp_path / "run"
    root.mkdir()
    cell = m.run_cell("run", root, m.goal_catalog()[0], "gemma4:31b-mlx", "W", 1)
    assert cell.hard_fails == ["CONTRACT_FORMAT"]
    assert "empty" in cell.error


def test_compile_failure_is_classified_and_retains_stdout_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    response = "def broken(:\n    pass\n"
    monkeypatch.setattr(
        m,
        "call_model",
        lambda *a, **k: (response, {"prompt": 1, "response": 1, "done_reason": "test", **m.provider_capabilities("gemma4:31b-mlx")}),
    )
    root = tmp_path / "run"
    root.mkdir()
    cell = m.run_cell("run", root, m.goal_catalog()[0], "gemma4:31b-mlx", "W", 1)
    assert cell.hard_fails == ["COMPILE_FAILURE"]
    assert "SyntaxError" in cell.error
    assert "solution.py" in cell.error


def test_promotion_goal_contracts_close_hidden_output_schemas():
    m = load_module()
    goals = {goal.id: goal for goal in m.promotion_goal_catalog()}
    assert "latest_by_metric(records: list[Record]) -> dict[str, Record]" in goals["C3-P"].specification
    assert "process_items(items, transform, state_path) -> list[object]" in goals["C4-P"].specification
    assert "successful transform values" in goals["C4-P"].specification
    assert "exact keys added, removed, changed mapping to lists of field-name strings" in goals["C5-R"].specification
    assert "exact keys sql_statements, backup_path, from_version, to_version" in goals["C5-R"].specification


def test_c4_hidden_tests_reject_non_atomic_direct_write(tmp_path: Path):
    m = load_module()
    write_fixture(tmp_path, {
        "state.py": """
            import json
            def load_state(path):
                if not path.exists(): return {'completed': [], 'failures': {}}
                value=json.loads(path.read_text())
                if not isinstance(value,dict): raise ValueError('shape')
                return value
            def save_state(path,state):
                path.write_text(json.dumps(state))
        """,
        "processor.py": """
            from state import load_state, save_state
            def process_items(items,transform,state_path):
                state=load_state(state_path); out=[]
                for item in items:
                    key=item['id']
                    if key in state['completed']: continue
                    try:
                        out.append(transform(item)); state['completed'].append(key); state['failures'].pop(key,None)
                    except Exception as exc:
                        state['failures'][key]=str(exc)
                    save_state(state_path,state)
                return out
        """,
        "cli.py": """
            from state import load_state
            def summarize_state(path):
                state=load_state(path)
                return {'completed_count':len(state['completed']),'failure_count':len(state['failures']),'retry_ids':list(state['failures'])}
        """,
    })
    passed, _, _ = m._run_hidden_tests(tmp_path, m.goal_catalog()[4])
    assert passed is False


def test_c5_hidden_tests_reject_serial_pipeline_without_timeout(tmp_path: Path):
    m = load_module()
    write_fixture(tmp_path, {
        "config.py": """
            import math
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class PipelineConfig:
                max_workers:int
                timeout_s:float
                def __post_init__(self):
                    if isinstance(self.max_workers,bool) or not 1 <= self.max_workers <= 8: raise ValueError('workers')
                    if isinstance(self.timeout_s,bool) or not math.isfinite(self.timeout_s) or self.timeout_s <= 0: raise ValueError('timeout')
        """,
        "pipeline.py": """
            def run_ordered(items,worker,config):
                rows=[]
                for item in items:
                    try: rows.append({'ok':True,'value':worker(item)})
                    except Exception as exc: rows.append({'ok':False,'error':f'{type(exc).__name__}: {exc}'})
                return rows
        """,
        "migration.py": """
            import re
            def build_plan(db_path,table,columns):
                if not re.fullmatch(r'(pa_|bridge_)[A-Za-z0-9_]*',table): raise ValueError('table')
                allowed={'TEXT','INTEGER','DOUBLE','BOOLEAN'}
                if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name) or kind not in allowed for name,kind in columns.items()): raise ValueError('column')
                sql=[f'CREATE TABLE IF NOT EXISTS {table} (id TEXT)']+[f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {kind}' for name,kind in columns.items()]
                return {'sql_statements':sql,'backup_path':str(db_path)+'.bak-20260719'}
        """,
        "cli.py": """
            def evaluate(results):
                failed=[i for i,row in enumerate(results) if not row['ok']]
                return {'total':len(results),'succeeded':len(results)-len(failed),'failed':len(failed),'failure_indexes':failed}
        """,
    })
    passed, _, _ = m._run_hidden_tests(tmp_path, m.goal_catalog()[5])
    assert passed is False


def test_c4_hidden_tests_accept_atomic_reference(tmp_path: Path):
    m = load_module()
    write_fixture(tmp_path, {
        "state.py": """
            import json, os, tempfile
            def _validate(value):
                if not isinstance(value,dict) or set(value)!={'completed','failures'}: raise ValueError('shape')
                if not isinstance(value['completed'],list) or not all(isinstance(x,str) for x in value['completed']): raise ValueError('completed')
                if not isinstance(value['failures'],dict): raise ValueError('failures')
                return value
            def load_state(path):
                if not path.exists(): return {'completed': [], 'failures': {}}
                return _validate(json.loads(path.read_text(encoding='utf-8')))
            def save_state(path,state):
                _validate(state); path.parent.mkdir(parents=True,exist_ok=True)
                fd,name=tempfile.mkstemp(dir=path.parent,prefix='state-',suffix='.tmp')
                try:
                    with os.fdopen(fd,'w',encoding='utf-8') as stream:
                        json.dump(state,stream); stream.flush(); os.fsync(stream.fileno())
                    os.replace(name,path)
                except Exception:
                    try: os.unlink(name)
                    except OSError: pass
                    raise
        """,
        "processor.py": """
            from state import load_state, save_state
            def process_items(items,transform,state_path):
                state=load_state(state_path); out=[]
                for item in items:
                    key=item['id']
                    if key in state['completed']: continue
                    try:
                        out.append(transform(item)); state['completed'].append(key); state['failures'].pop(key,None)
                    except Exception as exc:
                        state['failures'][key]=f'{type(exc).__name__}: {exc}'
                    save_state(state_path,state)
                return out
        """,
        "cli.py": """
            from state import load_state
            def summarize_state(path):
                state=load_state(path)
                return {'completed_count':len(state['completed']),'failure_count':len(state['failures']),'retry_ids':list(state['failures'])}
        """,
    })
    passed, checks, hard_fails = m._run_hidden_tests(tmp_path, m.goal_catalog()[4])
    assert passed is True, (checks, hard_fails)


def test_c5_hidden_tests_accept_bounded_concurrent_reference(tmp_path: Path):
    m = load_module()
    write_fixture(tmp_path, {
        "config.py": """
            import math
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class PipelineConfig:
                max_workers:int
                timeout_s:float
                def __post_init__(self):
                    if isinstance(self.max_workers,bool) or not isinstance(self.max_workers,int): raise TypeError('workers')
                    if not 1 <= self.max_workers <= 8: raise ValueError('workers')
                    if isinstance(self.timeout_s,bool) or not isinstance(self.timeout_s,(int,float)): raise TypeError('timeout')
                    if not math.isfinite(self.timeout_s) or self.timeout_s <= 0: raise ValueError('timeout')
        """,
        "pipeline.py": """
            from concurrent.futures import ThreadPoolExecutor, wait
            def run_ordered(items,worker,config):
                executor=ThreadPoolExecutor(max_workers=config.max_workers)
                futures=[executor.submit(worker,item) for item in items]
                done,pending=wait(futures,timeout=config.timeout_s)
                for future in pending: future.cancel()
                rows=[]
                for future in futures:
                    if future not in done:
                        rows.append({'ok':False,'error':'TimeoutError: overall timeout'})
                        continue
                    try: rows.append({'ok':True,'value':future.result()})
                    except Exception as exc: rows.append({'ok':False,'error':f'{type(exc).__name__}: {exc}'})
                executor.shutdown(wait=False,cancel_futures=True)
                return rows
        """,
        "migration.py": """
            import re
            def build_plan(db_path,table,columns):
                if not re.fullmatch(r'(?:pa_|bridge_)[A-Za-z0-9_]*',table): raise ValueError('table')
                allowed={'TEXT','INTEGER','DOUBLE','BOOLEAN'}
                if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name) or kind not in allowed for name,kind in columns.items()): raise ValueError('column')
                sql=[f'CREATE TABLE IF NOT EXISTS {table} (id TEXT)']+[f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {kind}' for name,kind in columns.items()]
                return {'sql_statements':sql,'backup_path':str(db_path)+'.bak-20260719T000000Z'}
        """,
        "cli.py": """
            def evaluate(results):
                failed=[index for index,row in enumerate(results) if not row['ok']]
                return {'total':len(results),'succeeded':len(results)-len(failed),'failed':len(failed),'failure_indexes':failed}
        """,
    })
    passed, checks, hard_fails = m._run_hidden_tests(tmp_path, m.goal_catalog()[5])
    assert passed is True, (checks, hard_fails)


def test_hidden_tests_execute_in_filesystem_and_network_sandbox(tmp_path: Path):
    m = load_module()
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = m.Goal(
        "sandbox", 0, "sandbox", "sandbox", ("solution.py",), (),
        f"""from pathlib import Path\nimport socket, subprocess\nimport pytest\ndef test_file_denied():\n with pytest.raises(OSError): Path({str(outside)!r}).read_text()\ndef test_network_denied():\n sock=socket.socket()\n try:\n  with pytest.raises(OSError): sock.bind(('127.0.0.1',0))\n finally:\n  sock.close()\ndef test_arbitrary_exec_denied():\n with pytest.raises(OSError): subprocess.run(['/bin/echo','no'],check=True)\n""",
        100,
    )
    passed, checks, hard_fails = m._run_hidden_tests(workspace, goal)
    assert passed is True, (checks, hard_fails)


def test_hidden_tests_do_not_discover_parent_pytest_configuration(tmp_path: Path):
    m = load_module()
    parent = tmp_path / "repository"
    parent.mkdir()
    (parent / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = '--definitely-invalid-option'\n",
        encoding="utf-8",
    )
    workspace = parent / "artifacts" / "run" / "cell" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "solution.py").write_text("VALUE = 1\n", encoding="utf-8")
    goal = m.Goal(
        "config-isolation", 0, "config isolation", "config isolation",
        ("solution.py",), (), "from solution import VALUE\ndef test_value(): assert VALUE == 1\n", 100,
    )

    passed, checks, hard_fails = m._run_hidden_tests(workspace, goal)

    assert passed is True, (checks, hard_fails)


def test_provider_metrics_and_effective_prompt_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    assert m.provider_capabilities("gpt-5.6-sol") == {"token_usage_available": False, "output_budget_enforced": False}
    assert m.provider_capabilities("gemma4:31b-mlx") == {"token_usage_available": True, "output_budget_enforced": True}
    captured: dict[str, object] = {}

    def fake_call(*args, **kwargs):
        captured.update(kwargs["effective_record"])
        return ("def normalize_id(raw): return 'R-04'\n", {"prompt": None, "response": None, "done_reason": "test", **m.provider_capabilities("gpt-5.6-sol")})
    monkeypatch.setattr(m, "call_model", fake_call)
    monkeypatch.setattr(m, "_run_hidden_tests", lambda *a, **k: (True, {}, []))
    root = tmp_path / "run"
    root.mkdir()
    cell = m.run_cell("run", root, m.goal_catalog()[0], "gpt-5.6-sol", "W", 1)
    assert cell.token_usage_available is False
    assert cell.output_budget_enforced is False
    assert len(cell.prompt_paths) == len(cell.prompt_hashes) == 1
    prompt_path = Path(cell.prompt_paths[0])
    assert m.hashlib.sha256(prompt_path.read_bytes()).hexdigest() == cell.prompt_hashes[0]
    payload = json.loads(prompt_path.read_text())
    assert payload == captured
    assert payload["route"] == "openai-codex" and payload["system"] and payload["user"]
    assert payload["output_budget_enforced"] is False


def test_call_model_dispatches_user_from_retained_record(monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    gpt_record = m.effective_prompt_record("gpt-5.6-sol", "retained-gpt-user", num_predict=100)
    captured_command = []

    def fake_run(command, **kwargs):
        captured_command.extend(command)
        return m.subprocess.CompletedProcess(command, 0, stdout="VALUE = 1\n", stderr="")

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    m.call_model("gpt-5.6-sol", "unretained-gpt-user", num_predict=100, effective_record=gpt_record)
    query = captured_command[-1]
    assert "retained-gpt-user" in query
    assert "unretained-gpt-user" not in query

    ollama_record = m.effective_prompt_record("gemma4:31b-mlx", "retained-ollama-user", num_predict=100)
    captured_payload = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"model":"gemma4:31b-mlx","done":true,"done_reason":"stop","message":{"content":"{\\"files\\": []}"},"prompt_eval_count":1,"eval_count":1}'

    def fake_urlopen(request, **kwargs):
        captured_payload.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    m.call_model("gemma4:31b-mlx", "unretained-ollama-user", num_predict=999, effective_record=ollama_record)
    assert captured_payload["messages"][1]["content"] == "retained-ollama-user"
    assert captured_payload["options"]["num_predict"] == 100

    mismatched = dict(ollama_record, route="openai-codex")
    with pytest.raises(ValueError, match="does not match"):
        m.call_model("gemma4:31b-mlx", "ignored", num_predict=100, effective_record=mismatched)


def test_ollama_dispatch_uses_complete_retained_request_envelope(monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    original = m.effective_prompt_record("gemma4:31b-mlx", "retained", num_predict=321)
    assert original["options"] and "temperature" in original["options"]
    assert "top_level" in original and original["timeout_s"] == 600
    captured = {}

    class DriftedProfile:
        options = {"temperature": 0.99, "top_p": 0.01}
        top_level = {"think": True}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return b'{"model":"gemma4:31b-mlx","done":true,"done_reason":"stop","message":{"content":"{\\"files\\": []}"},"prompt_eval_count":1,"eval_count":1}'

    def fake_urlopen(request, **kwargs):
        captured.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr(m, "profile_for_model", lambda _model: DriftedProfile())
    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    m.call_model("gemma4:31b-mlx", "ignored", num_predict=321, effective_record=original)
    assert captured["options"] == original["options"]
    assert captured["think"] == original["top_level"]["think"]


def test_runtime_preflight_fails_before_model_call_when_sandbox_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    missing = tmp_path / "missing-sandbox-exec"
    monkeypatch.setattr(m, "SANDBOX_EXEC", missing)
    with pytest.raises(RuntimeError, match="sandbox"):
        m.preflight_runtime(["gemma4:31b-mlx"], tmp_path)


def test_partial_boundary_slice_does_not_invent_non_monotonicity():
    m = load_module()
    cells = [
        m.Cell.synthetic(model="model", mode="M", tier=1, trial=1, passed=True),
        m.Cell.synthetic(model="model", mode="M", tier=2, trial=1, passed=False),
    ]
    result = m.breakpoint_for(cells, model="model", mode="M", expected_repeats=1)
    assert result["reliable_ceiling"] is None
    assert result["breakpoint"] is None
    assert result["non_monotonic"] is False


def test_schedule_is_model_major_to_avoid_repeated_model_reloads():
    m = load_module()
    goals = m.goal_catalog()[:2]
    schedule = m.make_schedule(["alpha", "beta"], goals, ["M", "A"], repeats=1)
    assert [(model, goal.id, mode, trial) for model, goal, mode, trial in schedule] == [
        ("alpha", "C0", "M", 1),
        ("alpha", "C0", "A", 1),
        ("alpha", "C1", "M", 1),
        ("alpha", "C1", "A", 1),
        ("beta", "C0", "M", 1),
        ("beta", "C0", "A", 1),
        ("beta", "C1", "M", 1),
        ("beta", "C1", "A", 1),
    ]


def test_schedule_rotates_models_across_repeats_and_declares_order_truthfully():
    m = load_module()
    goal = m.goal_catalog()[0]
    schedule = m.make_schedule(["alpha", "beta"], [goal], ["M", "A"], repeats=3)
    by_trial = {
        trial: [model for model, _, mode, seen_trial in schedule if seen_trial == trial and mode == "M"]
        for trial in (1, 2, 3)
    }
    assert by_trial == {1: ["alpha", "beta"], 2: ["beta", "alpha"], 3: ["alpha", "beta"]}
    assert m.RUN_ORDER == "model-major-rotating;mode-order=input"


def test_self_test_builds_report_without_model_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = load_module()
    monkeypatch.setattr(m, "call_model", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model call")))
    result = m.run_self_test(tmp_path)
    assert result["status"] == "pass"
    assert result["model_calls"] == 0
    assert (tmp_path / "report.md").is_file()
    assert (tmp_path / "report.html").is_file()
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["evidence_class"] == "offline_self_test"
