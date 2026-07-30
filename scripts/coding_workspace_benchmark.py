#!/usr/bin/env python3
"""Format-neutral coding workspace benchmark.

Each model call produces one host-selected Python file as ordinary raw or
fenced source. Multi-file goals are generated in dependency order and tested
inside filesystem/network-sandboxed workspaces. The model never serializes
source into a JSON file envelope or chooses destination paths.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
PYTHON = sys.executable
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
DEFAULT_MODELS = [
    "qwen3.6:35b-a3b-coding-mxfp8",
    "qwen3.6:35b-mlx",
    "qwen3.6:27b-mlx",
    "qwen3.6:27b-mlx-bf16",
    "gemma4:31b-mlx",
    "nemotron3:33b",
]
RUN_ORDER = "model-major-rotating;mode-order=input"

try:
    from benchmark_manifest import build_manifest, write_manifest
    from benchmark_transport import (
        ModelIdentityMismatch,
        ProviderContractError,
        parse_hermes_response,
        parse_ollama_response,
    )
    from local_coding_promotion_goals import promotion_goal_specs
    from model_prompt_profiles import profile_for_model, require_profile_coverage
except ImportError:  # pragma: no cover
    sys.path.append(str(BASE_DIR / "scripts"))
    from benchmark_manifest import build_manifest, write_manifest
    from benchmark_transport import (
        ModelIdentityMismatch,
        ProviderContractError,
        parse_hermes_response,
        parse_ollama_response,
    )
    from local_coding_promotion_goals import promotion_goal_specs
    from model_prompt_profiles import profile_for_model, require_profile_coverage

CODING_SYSTEM = """You are in a synthetic coding benchmark. Implement only the requested file.
Return its complete Python source. Raw source or one normal Python code fence is accepted.
Do not return path metadata, patches, multiple alternatives, hidden reasoning, dependencies, network calls, or test edits.
Use Python 3.12 stdlib, typed public signatures, pathlib for paths, specific exceptions,
context managers for resources, and list-form bounded subprocesses if needed."""


class ResponseContractError(ValueError):
    """Raised when a model response cannot identify one unambiguous source file."""


class IncompleteProviderResponse(RuntimeError):
    """Raised when provider telemetry cannot prove a complete response."""


class ScopeViolation(ValueError):
    """Raised when generated files escape the declared write scope."""


class CompileFailure(RuntimeError):
    """Raised when generated Python does not compile."""


@dataclass(frozen=True)
class AtomicCard:
    """One dependency-ordered implementation result."""

    id: str
    objective: str
    write_path: str
    depends_on: tuple[str, ...] = ()
    verification: str = "python -m py_compile {write_path}"

    @property
    def write_paths(self) -> tuple[str, ...]:
        return (self.write_path,)


@dataclass(frozen=True)
class Goal:
    """One calibrated coding goal."""

    id: str
    tier: int
    name: str
    specification: str
    allowed_files: tuple[str, ...]
    cards: tuple[AtomicCard, ...]
    hidden_tests: str
    max_output_tokens: int


@dataclass
class Cell:
    """One model, mode, tier, and trial result."""

    run_id: str
    model: str
    mode: str
    goal_id: str
    tier: int
    trial: int
    status: str
    passed: bool
    score: float
    hard_fails: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    model_calls: int = 0
    prompt_tokens: int = 0
    response_tokens: int = 0
    token_usage_available: bool = True
    output_budget_enforced: bool = True
    prompt_paths: list[str] = field(default_factory=list)
    prompt_hashes: list[str] = field(default_factory=list)
    response_texts: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    artifact_path: str = ""

    @classmethod
    def synthetic(
        cls, *, model: str, mode: str, tier: int, trial: int, passed: bool,
        goal_id: str | None = None,
    ) -> "Cell":
        return cls(
            run_id="synthetic", model=model, mode=mode, goal_id=goal_id or f"C{tier}", tier=tier,
            trial=trial, status="ok", passed=passed, score=1.0 if passed else 0.0,
        )


def _cards(goal: str, files: tuple[str, ...], objectives: tuple[str, ...]) -> tuple[AtomicCard, ...]:
    cards: list[AtomicCard] = []
    for index, (path, objective) in enumerate(zip(files, objectives, strict=True), 1):
        dependencies = (f"{goal}-{index - 1:02d}",) if index > 1 else ()
        cards.append(AtomicCard(f"{goal}-{index:02d}", objective, path, dependencies))
    return tuple(cards)


def goal_catalog() -> list[Goal]:
    """Return the frozen six-tier calibration ladder."""
    return [
        Goal(
            "C0", 0, "Pure identifier normalizer",
            "Create solution.py with normalize_id(raw: str) -> str. Trim whitespace; accept case-insensitive R followed by optional spaces/hyphen and 1-3 digits; return R-NN; reject booleans, empty input, zero, values above 99, and malformed text with ValueError.",
            ("solution.py",),
            _cards("C0", ("solution.py",), ("Implement the typed pure normalize_id function and its validation.",)),
            """import pytest\nfrom solution import normalize_id\n\ndef test_normalizes():\n assert normalize_id(' r-4 ') == 'R-04'\n assert normalize_id('R 09') == 'R-09'\n assert normalize_id('r99') == 'R-99'\n@pytest.mark.parametrize('value', ['', 'R0', 'R100', 'risk4', True, None])\ndef test_rejects(value):\n with pytest.raises((ValueError, TypeError)): normalize_id(value)\n""", 900,
        ),
        Goal(
            "C1", 1, "Delimited record parser",
            "Create line_parser.py. Define frozen dataclass Record(metric: str, value: float, unit: str, source: str). Implement parse_line(line: str) -> Record for metric|value|unit|source. Trim fields, preserve source text, reject wrong field count, empty fields, non-finite/non-numeric values, booleans, and non-string input with clear ValueError or TypeError.",
            ("line_parser.py",),
            _cards("C1", ("line_parser.py",), ("Implement the frozen record model and strict delimited parser.",)),
            """import math, pytest\nfrom line_parser import Record, parse_line\n\ndef test_parses_and_preserves():\n row=parse_line(' steps | 1234 | count | Google Health/Fitbit ')\n assert row == Record('steps',1234.0,'count','Google Health/Fitbit')\n@pytest.mark.parametrize('line', ['bad|line','x||u|s','x|nan|u|s','x|inf|u|s','x|abc|u|s'])\ndef test_rejects(line):\n with pytest.raises(ValueError): parse_line(line)\ndef test_type():\n with pytest.raises(TypeError): parse_line(None)\n""", 1200,
        ),
        Goal(
            "C2", 2, "Source-priority selector",
            "Create selector.py. Define choose_metric(candidates: list[dict[str, object]], metric: str, current_date: str) -> dict[str, object]. Each candidate uses the exact keys metric, value, source, and measured_date. Filter exact metric. For nutrition metrics protein/calories/carbs/fat, FoodNoms outranks all sources. For every non-nutrition metric, including steps, source priority is Apple Watch then Apple Health then Withings then the single combined source name Google Health/Fitbit. Prefer source priority before recency. Parse current_date as strict YYYY-MM-DD or raise ValueError. Freshness is fresh only when measured_date equals current_date, stale when measured_date is a valid earlier date, and unknown when measured_date is missing or invalid; an invalid candidate measured_date does not raise. Return a copy with freshness_label and reason. The reason must contain fallback whenever the selected source is not the highest-priority source for that metric family. Raise ValueError when no metric matches and never mutate inputs.",
            ("selector.py",),
            _cards("C2", ("selector.py",), ("Implement source priority, freshness, copying, validation, and fallback reasoning.",)),
            """import copy, pytest\nfrom selector import choose_metric\n\ndef test_foodnoms_and_copy():\n rows=[{'metric':'protein','value':1,'source':'Google Health/Fitbit','measured_date':'2026-07-19'},{'metric':'protein','value':2,'source':'FoodNoms','measured_date':'2026-07-18'}]\n original=copy.deepcopy(rows); got=choose_metric(rows,'protein','2026-07-19')\n assert got['source']=='FoodNoms' and got['freshness_label']=='stale' and rows==original\ndef test_activity_priority():\n rows=[{'metric':'steps','value':9,'source':'Google Health/Fitbit','measured_date':'2026-07-19'},{'metric':'steps','value':8,'source':'Apple Watch','measured_date':'2026-07-18'}]\n assert choose_metric(rows,'steps','2026-07-19')['source']=='Apple Watch'\ndef test_fallback():\n got=choose_metric([{'metric':'steps','value':9,'source':'Google Health/Fitbit','measured_date':'bad'}],'steps','2026-07-19')\n assert got['freshness_label']=='unknown' and 'fallback' in got['reason'].lower()\ndef test_missing():\n with pytest.raises(ValueError): choose_metric([], 'steps', '2026-07-19')\n""", 1500,
        ),
        Goal(
            "C3", 3, "Three-file ingestion service",
            "Create models.py, parser.py, and service.py. models.py defines frozen Record(metric,value,unit,source,measured_date). parser.py implements parse_lines(text: str) -> tuple[list[Record], list[dict[str, object]]], processing nonblank metric|value|unit|source|YYYY-MM-DD lines independently and recording 1-based line_number plus error for invalid rows. service.py implements latest_by_metric(records: list[Record]) -> dict[str, Record], mapping each metric to its newest valid measured_date record, preserving first input on date ties, without mutation. Use explicit local imports and no dependencies.",
            ("models.py", "parser.py", "service.py"),
            _cards("C3", ("models.py", "parser.py", "service.py"), (
                "Define the immutable Record boundary model.",
                "Implement independent line parsing and structured per-line errors using Record.",
                "Implement stable newest-record selection by metric without mutating records.",
            )),
            """from models import Record\nfrom parser import parse_lines\nfrom service import latest_by_metric\n\ndef test_parse_partial_and_lines():\n rows, errors=parse_lines('steps|1|count|Watch|2026-07-18\\nbad\\nsteps|2|count|Watch|2026-07-19')\n assert [r.value for r in rows]==[1.0,2.0]\n assert errors[0]['line_number']==2 and errors[0]['error']\ndef test_latest_stable():\n a=Record('steps',1,'count','A','2026-07-19'); b=Record('steps',2,'count','B','2026-07-19'); c=Record('protein',3,'g','F','2026-07-18')\n rows=[a,b,c]; got=latest_by_metric(rows)\n assert got=={'steps':a,'protein':c} and rows==[a,b,c]\n""", 2500,
        ),
        Goal(
            "C4", 4, "Resumable atomic processor",
            "Create state.py, processor.py, and cli.py. state.py provides load_state(path: Path)->dict and save_state(path: Path,state:dict)->None using UTF-8 JSON and same-directory temporary file plus os.replace; missing file returns {'completed': [], 'failures': {}} and malformed shapes raise ValueError. processor.py provides process_items(items, transform, state_path) -> list[object], returning successful transform values for attempted items in input order, skipping completed string IDs, capturing per-item exceptions in failures, saving after each item, and never marking failed items completed. cli.py provides summarize_state(path)->dict with completed_count, failure_count, retry_ids. No broad swallowed exceptions or writes outside the supplied path parent.",
            ("state.py", "processor.py", "cli.py"),
            _cards("C4", ("state.py", "processor.py", "cli.py"), (
                "Implement validated atomic JSON state load/save.",
                "Implement resumable per-item processing with per-item durable state.",
                "Implement deterministic state summary for operator use.",
            )),
            """import json\nfrom pathlib import Path\nimport pytest\nfrom state import load_state, save_state\nfrom processor import process_items\nfrom cli import summarize_state\n\ndef test_atomic_roundtrip(tmp_path):\n p=tmp_path/'s.json'; save_state(p,{'completed':['a'],'failures':{}}); assert load_state(p)['completed']==['a']; assert not list(tmp_path.glob('*.tmp'))\ndef test_resume_and_failure(tmp_path):\n p=tmp_path/'s.json'; calls=[]\n def transform(item):\n  calls.append(item['id'])\n  if item['id']=='b': raise RuntimeError('boom')\n  return item['id'].upper()\n first=process_items([{'id':'a'},{'id':'b'},{'id':'c'}],transform,p)\n assert first==['A','C']; state=load_state(p); assert state['completed']==['a','c'] and 'b' in state['failures']\n calls.clear(); second=process_items([{'id':'a'},{'id':'b'},{'id':'c'}],lambda x:x['id'],p)\n assert calls==[]; assert second==['b']; assert summarize_state(p)=={'completed_count':3,'failure_count':0,'retry_ids':[]}\ndef test_uses_same_directory_replace(tmp_path,monkeypatch):\n import state\n p=tmp_path/'s.json'; calls=[]; real=state.os.replace\n def replace(src,dst):\n  calls.append((Path(src),Path(dst))); return real(src,dst)\n monkeypatch.setattr(state.os,'replace',replace); save_state(p,{'completed':[],'failures':{}})\n assert len(calls)==1 and calls[0][0].parent==p.parent and calls[0][1]==p\ndef test_failed_replace_preserves_prior_state(tmp_path,monkeypatch):\n import state\n p=tmp_path/'s.json'; old={'completed':['old'],'failures':{}}; p.write_text(json.dumps(old))\n monkeypatch.setattr(state.os,'replace',lambda *a: (_ for _ in ()).throw(OSError('replace failed')))\n with pytest.raises(OSError): save_state(p,{'completed':['new'],'failures':{}})\n assert load_state(p)==old\ndef test_bad_shape(tmp_path):\n p=tmp_path/'s.json'; p.write_text('[]')\n with pytest.raises(ValueError): load_state(p)\n""", 3200,
        ),
        Goal(
            "C5", 5, "Bounded ordered pipeline and migration plan",
            "Create config.py, pipeline.py, migration.py, and cli.py. config.py defines frozen PipelineConfig(max_workers:int, timeout_s:float) rejecting bools, workers outside 1..8, and nonpositive/nonfinite timeout. pipeline.py defines run_ordered(items, worker, config)->list[dict] using ThreadPoolExecutor with at most max_workers; preserve input order; each row is {'ok':True,'value':...} or {'ok':False,'error': '<ExceptionType>: <message>'}; enforce a bounded overall wait and cancel unfinished futures. migration.py defines build_plan(db_path:Path,table:str,columns:dict[str,str])->dict allowing only pa_/bridge_ tables, identifier allowlists, TEXT/INTEGER/DOUBLE/BOOLEAN types, additive CREATE/ADD SQL only, and a timestamped backup_path; never execute SQL. cli.py defines evaluate(results)->dict with total, succeeded, failed, failure_indexes. No dependencies, shell, database access, or unsafe SQL verbs.",
            ("config.py", "pipeline.py", "migration.py", "cli.py"),
            _cards("C5", ("config.py", "pipeline.py", "migration.py", "cli.py"), (
                "Implement strict immutable pipeline configuration validation.",
                "Implement bounded concurrent execution with ordered typed result rows.",
                "Implement a validated additive-only migration plan without execution.",
                "Implement deterministic pipeline result evaluation.",
            )),
            """import re, threading, time\nfrom pathlib import Path\nimport pytest\nfrom config import PipelineConfig\nfrom pipeline import run_ordered\nfrom migration import build_plan\nfrom cli import evaluate\n\ndef test_config():\n assert PipelineConfig(2,1.0).max_workers==2\n for args in [(True,1),(0,1),(9,1),(1,float('inf'))]:\n  with pytest.raises((TypeError,ValueError)): PipelineConfig(*args)\ndef test_order_and_errors():\n def worker(x):\n  if x==2: raise KeyError('bad')\n  time.sleep((3-x)*.01); return x*10\n got=run_ordered([1,2,3],worker,PipelineConfig(2,2))\n assert got[0]=={'ok':True,'value':10} and got[2]=={'ok':True,'value':30}\n assert got[1]['ok'] is False and 'KeyError' in got[1]['error']\n assert evaluate(got)=={'total':3,'succeeded':2,'failed':1,'failure_indexes':[1]}\ndef test_concurrency_is_real_and_bounded():\n lock=threading.Lock(); active=0; peak=0\n def worker(x):\n  nonlocal active,peak\n  with lock: active+=1; peak=max(peak,active)\n  time.sleep(.05)\n  with lock: active-=1\n  return x\n assert all(row['ok'] for row in run_ordered([1,2,3,4],worker,PipelineConfig(2,1)))\n assert 1 < peak <= 2\ndef test_overall_timeout_returns_promptly():\n start=time.monotonic(); got=run_ordered([1,2],lambda x:(time.sleep(.5),x)[1],PipelineConfig(2,.05)); elapsed=time.monotonic()-start\n assert elapsed < .25\n assert len(got)==2 and all(not row['ok'] and 'Timeout' in row['error'] for row in got)\ndef test_plan(tmp_path):\n plan=build_plan(tmp_path/'x.duckdb','pa_scores',{'score':'DOUBLE','valid':'BOOLEAN'})\n sql=' '.join(plan['sql_statements']).upper(); assert plan['backup_path'].startswith(str(tmp_path/'x.duckdb')+'.bak-')\n assert 'CREATE TABLE IF NOT EXISTS' in sql and 'ADD COLUMN IF NOT EXISTS' in sql\n assert not re.search(r'\\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE)\\b',sql)\n@pytest.mark.parametrize('table,cols',[('records',{'x':'TEXT'}),('pa_x',{'bad-name':'TEXT'}),('pa_x',{'x':'DROP TABLE'})])\ndef test_plan_rejects(tmp_path,table,cols):\n with pytest.raises(ValueError): build_plan(tmp_path/'x',table,cols)\n""", 4200,
        ),
    ]


def promotion_goal_catalog() -> list[Goal]:
    """Return the frozen three-family promotion ladder."""
    goals: list[Goal] = []
    for source in goal_catalog():
        goal_id = f"C{source.tier}-P"
        cards = tuple(
            AtomicCard(
                id=card.id.replace(f"C{source.tier}", goal_id, 1),
                objective=card.objective,
                write_path=card.write_path,
                depends_on=tuple(
                    dependency.replace(f"C{source.tier}", goal_id, 1)
                    for dependency in card.depends_on
                ),
                verification=card.verification,
            )
            for card in source.cards
        )
        goals.append(Goal(
            goal_id, source.tier, source.name, source.specification,
            source.allowed_files, cards, source.hidden_tests, source.max_output_tokens,
        ))
    for spec in promotion_goal_specs():
        files = tuple(spec["allowed_files"])
        objectives = tuple(spec["objectives"])
        goals.append(Goal(
            spec["id"], spec["tier"], spec["name"], spec["specification"], files,
            _cards(spec["id"], files, objectives), spec["hidden_tests"], spec["max_output_tokens"],
        ))
    return sorted(goals, key=lambda goal: (goal.tier, goal.id))


def model_route(model: str) -> str:
    """Return the governed provider route for a model tag."""
    return "openai-codex" if model.lower().startswith("gpt-") else "ollama"


def manifest_route(model: str) -> str:
    """Map execution routes to the shared manifest vocabulary."""
    return "hermes" if model_route(model) == "openai-codex" else model_route(model)


def model_workspace_id(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", model).strip("_")


def cell_trial_dir(root: Path, goal: Goal, model: str, mode: str, trial: int) -> Path:
    return root / goal.id / model_workspace_id(model) / mode / f"trial-{trial:03d}"


def validate_dimensions(models: list[str], modes: list[str], tiers: list[str], *, repeats: int) -> None:
    """Reject empty, duplicate, invalid, or path-colliding dimensions before evidence creation."""
    if not models:
        raise ValueError("models required")
    if not modes or any(mode != "W" for mode in modes):
        raise ValueError("modes must be the workspace mode W")
    if not tiers or any(tier not in {f"C{i}" for i in range(6)} for tier in tiers):
        raise ValueError("tiers must be a non-empty C0-C5 selection")
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    for label, values in (("models", models), ("modes", modes), ("tiers", tiers)):
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label} are not allowed")
    workspace_ids = [model_workspace_id(model).casefold() for model in models]
    if any(not value for value in workspace_ids) or len(workspace_ids) != len(set(workspace_ids)):
        raise ValueError("model workspace identifiers must be non-empty and unique")


def parse_hermes_cli_output(text: str) -> str:
    """Remove only identified Hermes framing and preserve ordinary raw source."""
    response = text or ""
    if response.startswith("session_id:"):
        _session, separator, response = response.partition("\n")
        if not separator:
            response = ""
    if not response.strip():
        raise ResponseContractError("empty_hermes_response")
    fence_start = response.find("```")
    if fence_start >= 0:
        fenced = response[fence_start:]
        fence_lines = list(re.finditer(r"^```[^\n`]*\s*$", fenced, flags=re.MULTILINE))
        if len(fence_lines) < 2:
            raise ResponseContractError("unterminated_hermes_code_fence")
        return fenced.strip()
    if re.search(r"^[┌└│].*reasoning", response, flags=re.IGNORECASE | re.MULTILINE):
        raise ResponseContractError("unframed_hermes_reasoning_metadata")
    return response


def extract_source_response(text: str) -> str:
    """Extract one ordinary raw or fenced Python source response.

    Raw responses are preserved byte-for-byte. A single fenced block may have
    surrounding prose; only Python, ``py``, or an unlabelled fence is accepted.
    Multiple blocks are ambiguous and fail before generated code is executed.
    """
    if not text or not text.strip():
        raise ResponseContractError("empty response")
    fence_lines = list(re.finditer(r"^```([^\n`]*)\s*$", text, flags=re.MULTILINE))
    if not fence_lines:
        if "```" in text:
            raise ResponseContractError("unterminated fence")
        return text
    if len(fence_lines) < 2:
        raise ResponseContractError("unterminated fence")
    if len(fence_lines) != 2:
        raise ResponseContractError("multiple code blocks")
    opening, closing = fence_lines
    if closing.group(1).strip():
        raise ResponseContractError("unterminated fence")
    language = opening.group(1).strip().lower()
    source_start = opening.end()
    if source_start < len(text) and text[source_start] == "\n":
        source_start += 1
    source = text[source_start:closing.start()]
    if language not in {"", "py", "python", "python3"}:
        raise ResponseContractError(f"unsupported fence language: {language}")
    if not source.strip():
        raise ResponseContractError("empty code block")
    return source


def validated_run_root(base: Path, run_id: str) -> Path:
    """Resolve a confined evidence directory for a validated run ID."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ValueError("run_id must use 1-128 letters, digits, dots, underscores, or hyphens")
    base = base.resolve()
    root = (base / run_id).resolve()
    try:
        root.relative_to(base)
    except ValueError as exc:
        raise ValueError("run_id escapes artifact root") from exc
    if root == base:
        raise ValueError("run_id must select one child directory")
    return root


def new_run_root(base: Path, run_id: str) -> Path:
    """Create a fresh, confined evidence directory for a validated run ID."""
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=True)
    root = validated_run_root(base, run_id)
    root.mkdir(parents=False, exist_ok=False)
    return root


def write_model_files(root: Path, files: dict[str, str], allowed: Iterable[str]) -> None:
    """Write generated files while enforcing resolved-root and allow-list boundaries."""
    root = root.resolve()
    allowed_set = set(allowed)
    if set(files) - allowed_set:
        raise ScopeViolation(f"undeclared paths: {sorted(set(files) - allowed_set)}")
    for relative, content in files.items():
        destination = _confined_workspace_path(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def atomic_order(cards: tuple[AtomicCard, ...]) -> list[AtomicCard]:
    """Validate and return the declared dependency order."""
    known = {card.id for card in cards}
    completed: set[str] = set()
    result: list[AtomicCard] = []
    for card in cards:
        unknown = set(card.depends_on) - known
        if unknown:
            raise ValueError(f"unknown dependency: {sorted(unknown)}")
        if not set(card.depends_on) <= completed:
            raise ValueError(f"dependency order violation: {card.id}")
        completed.add(card.id)
        result.append(card)
    return result


def _confined_workspace_path(root: Path, relative: str) -> Path:
    """Return a non-symlinked path confined beneath the resolved workspace."""
    root = root.resolve()
    relative_path = Path(relative)
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        raise ScopeViolation("invalid workspace path")
    candidate = root / relative_path
    current = root
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise ScopeViolation(f"workspace symlink rejected: {relative}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ScopeViolation("path escape") from exc
    return candidate


def _workspace_files(root: Path, allowed: Iterable[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for relative in allowed:
        candidate = _confined_workspace_path(root, relative)
        if not candidate.exists():
            continue
        if not candidate.is_file():
            raise ScopeViolation(f"workspace path is not a regular file: {relative}")
        files[relative] = candidate.read_text(encoding="utf-8")
    return files


_RUNTIME_DIRS = {"__pycache__", "_tmp", "_pytest_cache", ".pytest_cache"}


def _directory_inventory(root: Path, *, ignored_dirs: set[str] | None = None) -> dict[str, str]:
    """Hash regular files below a root and reject symlinks/special files."""
    root = root.resolve()
    ignored_dirs = ignored_dirs or set()
    inventory: dict[str, str] = {}
    for candidate in root.rglob("*"):
        relative = candidate.relative_to(root)
        if any(part in ignored_dirs for part in relative.parts):
            continue
        if candidate.is_symlink():
            raise ScopeViolation(f"workspace symlink rejected: {relative}")
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ScopeViolation("path escape") from exc
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ScopeViolation(f"workspace special file rejected: {relative}")
        inventory[str(relative)] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return inventory


def _workspace_inventory(root: Path) -> dict[str, str]:
    return _directory_inventory(root, ignored_dirs=_RUNTIME_DIRS)


def build_file_prompt(
    goal: Goal, *, card: AtomicCard, workspace: Path, test_feedback: str = "",
) -> str:
    current = _workspace_files(workspace, goal.allowed_files)
    existing = "\n\n".join(
        f"CURRENT {path}:\n```python\n{content}\n```" for path, content in current.items()
    ) or "(workspace is empty)"
    feedback = f"\nTEST FEEDBACK:\n{test_feedback}\n" if test_feedback else ""
    return (
        f"GOAL {goal.id} / complexity C{goal.tier}: {goal.name}\n"
        f"SPECIFICATION:\n{goal.specification}\n\n"
        f"CURRENT CARD {card.id}: {card.objective}\n"
        f"TARGET FILE: {card.write_path}\n"
        f"CURRENT WORKSPACE:\n{existing}\n{feedback}"
        "Return the complete contents of the target file, not a diff. "
        "Raw Python or one standard Python code fence is accepted."
    )


def provider_capabilities(model: str) -> dict[str, bool]:
    """Declare metric comparability for the effective provider route."""
    supported = model_route(model) != "openai-codex"
    return {"token_usage_available": supported, "output_budget_enforced": supported}


def _system_prompt(model: str) -> str:
    return profile_for_model(model).system_prompt() + "\n\n" + CODING_SYSTEM


def effective_prompt_record(model: str, prompt: str, *, num_predict: int) -> dict[str, Any]:
    """Return the exact synthetic prompt envelope retained for replay/audit."""
    profile = profile_for_model(model)
    return {
        "model": model,
        "route": model_route(model),
        "system": _system_prompt(model),
        "user": prompt,
        "requested_output_tokens": num_predict,
        "stream": False,
        "options": {"num_predict": num_predict, **profile.options},
        "top_level": dict(profile.top_level),
        "response_format": None,
        "endpoint": OLLAMA_URL if model_route(model) == "ollama" else "hermes:openai-codex",
        "timeout_s": 600,
        **provider_capabilities(model),
    }


def call_model(
    model: str,
    prompt: str,
    *,
    num_predict: int,
    timeout: int = 900,
    effective_record: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Call a governed Ollama model and retain token metadata."""
    record = effective_record or effective_prompt_record(model, prompt, num_predict=num_predict)
    if record.get("model") != model or record.get("route") != model_route(model):
        raise ValueError("effective prompt record does not match requested model route")
    system_prompt = str(record["system"])
    user_prompt = str(record["user"])
    requested_output_tokens = int(record["requested_output_tokens"])
    timeout = int(record["timeout_s"])
    capabilities = {
        "token_usage_available": bool(record["token_usage_available"]),
        "output_budget_enforced": bool(record["output_budget_enforced"]),
    }
    if model_route(model) == "openai-codex":
        query = system_prompt + "\n\n" + user_prompt
        try:
            result = subprocess.run(
                ["hermes", "chat", "-Q", "--safe-mode", "--provider", "openai-codex", "-m", model,
                 "--max-turns", "1", "-q", query],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Hermes OpenAI-Codex transport timed out") from exc
        if result.returncode != 0:
            raise RuntimeError("Hermes OpenAI-Codex transport failed: " + result.stderr[-1000:])
        provider_result = parse_hermes_response(
            model, result.stdout, provider="openai-codex", max_turns=1,
        )
        if provider_result.incomplete_reason:
            raise IncompleteProviderResponse(provider_result.incomplete_reason)
        return parse_hermes_cli_output(result.stdout), {
            "prompt": None,
            "response": None,
            "done_reason": provider_result.done_reason,
            "evidence_failure": provider_result.evidence_failure,
            **capabilities,
        }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": bool(record["stream"]),
        "options": dict(record["options"]),
    }
    if int(payload["options"].get("num_predict", -1)) != requested_output_tokens:
        raise ValueError("effective prompt record has inconsistent output token controls")
    response_format = record["response_format"]
    if response_format is not None:
        payload["format"] = response_format
    payload.update(dict(record["top_level"]))
    request = urllib.request.Request(str(record["endpoint"]), data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"model transport failed: {type(exc).__name__}: {exc}") from exc
    provider_result = parse_ollama_response(model, data, payload=payload)
    if provider_result.incomplete_reason:
        raise IncompleteProviderResponse(provider_result.incomplete_reason)
    return provider_result.content, {
        "prompt": provider_result.prompt_tokens,
        "response": provider_result.response_tokens,
        "done_reason": provider_result.done_reason,
        "evidence_failure": provider_result.evidence_failure,
        **capabilities,
    }


def _seatbelt_path(path: Path | str) -> str:
    return str(Path(path).resolve()).replace("\\", "\\\\").replace('"', '\\"')


def _sandbox_profile(
    workspace: Path,
    *,
    read_only_roots: Iterable[Path] = (),
    writable_roots: Iterable[Path] | None = None,
    writable_files: Iterable[Path] = (),
) -> str:
    """Return a deny-by-default Seatbelt profile with separated read/write roots."""
    workspace_path = _seatbelt_path(workspace)
    runtime_root = _seatbelt_path(Path(PYTHON).resolve().parent.parent)
    readable_paths = (workspace_path, runtime_root, *(_seatbelt_path(path) for path in read_only_roots))
    writable_paths = tuple(
        _seatbelt_path(path) for path in (writable_roots if writable_roots is not None else (workspace,))
    )

    def deny_outside_allowed(root: str) -> str:
        exceptions = "".join(f'(require-not (subpath "{path}")) ' for path in readable_paths)
        return f'(deny file-read-data (require-all (subpath "{root}") {exceptions})) '

    sensitive_roots = ("/Users", "/Volumes", "/private", "/Applications", "/Network", "/Library", "/opt")
    deny_rules = "".join(deny_outside_allowed(root) for root in sensitive_roots)
    read_rules = " ".join(f'(subpath "{path}")' for path in readable_paths)
    write_rules = " ".join(f'(subpath "{path}")' for path in writable_paths)
    write_rules += " " + " ".join(
        f'(literal "{_seatbelt_path(path)}")' for path in writable_files
    )
    return (
        '(version 1) '
        '(deny default) '
        '(allow process*) '
        '(deny process-exec) '
        f'(allow process-exec (literal "{_seatbelt_path(PYTHON)}")) '
        '(allow file-read*) '
        f'{deny_rules}'
        '(deny file-read-data (subpath "/dev")) '
        '(allow file-read-data (literal "/dev/null") (literal "/dev/urandom")) '
        f'(allow file-read* {read_rules}) '
        f'(allow file-write* {write_rules} (literal "/dev/null"))'
    )


def preflight_runtime(models: list[str], artifact_root: Path) -> None:
    """Fail before model execution when required local runtime boundaries are absent."""
    if not SANDBOX_EXEC.is_file() or not os.access(SANDBOX_EXEC, os.X_OK):
        raise RuntimeError(f"sandbox executable unavailable: {SANDBOX_EXEC}")
    python_path = Path(PYTHON)
    if not python_path.is_file() or not os.access(python_path, os.X_OK):
        raise RuntimeError(f"benchmark Python unavailable: {PYTHON}")
    if not artifact_root.is_dir() or not os.access(artifact_root, os.W_OK):
        raise RuntimeError(f"artifact root is not writable: {artifact_root}")
    check = subprocess.run(
        [str(SANDBOX_EXEC), "-p", _sandbox_profile(artifact_root), PYTHON, "-I", "-B", "-c", "pass"],
        cwd=Path("/"), capture_output=True, text=True, timeout=15, check=False,
        env={"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "HOME": str(artifact_root)},
    )
    if check.returncode != 0:
        raise RuntimeError("sandbox preflight failed: " + check.stderr[-500:])
    if any(model_route(model) == "ollama" for model in models):
        ollama = shutil.which("ollama")
        if not ollama:
            raise RuntimeError("Ollama CLI unavailable")
        listing = subprocess.run([ollama, "list"], capture_output=True, text=True, timeout=15, check=False)
        installed = {line.split()[0] for line in listing.stdout.splitlines()[1:] if line.split()}
        missing = sorted(model for model in models if model_route(model) == "ollama" and model not in installed)
        if listing.returncode != 0 or missing:
            raise RuntimeError(f"local model preflight failed; missing={missing}")
    if any(model_route(model) == "openai-codex" for model in models) and not shutil.which("hermes"):
        raise RuntimeError("Hermes CLI unavailable")


def _run_hidden_tests(workspace: Path, goal: Goal) -> tuple[bool, dict[str, Any], list[str]]:
    workspace = workspace.resolve()
    try:
        generated_before = _workspace_inventory(workspace)
    except ScopeViolation as exc:
        return False, {"sandbox": "not_started", "integrity_error": str(exc)}, ["SAFETY_OR_SECURITY"]
    expected_files = set(goal.allowed_files)
    if set(generated_before) != expected_files:
        return False, {
            "sandbox": "not_started",
            "file_set_integrity": False,
            "expected_files": sorted(expected_files),
            "actual_files": sorted(generated_before),
        }, ["FILE_SET_MISMATCH"]

    harness_root = workspace.parent / f".{workspace.name}-test-harness"
    if harness_root.is_symlink():
        return False, {"sandbox": "not_started", "harness_integrity": False}, ["SAFETY_OR_SECURITY"]
    harness_root.mkdir(parents=True, exist_ok=True)
    test_dir = harness_root / "hidden_tests"
    test_dir.mkdir(exist_ok=True)
    test_path = test_dir / "test_goal.py"
    config_path = harness_root / "pytest.ini"
    test_path.write_text(goal.hidden_tests, encoding="utf-8")
    config_path.write_text("[pytest]\n", encoding="utf-8")
    harness_expected = {
        "pytest.ini": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "hidden_tests/test_goal.py": hashlib.sha256(test_path.read_bytes()).hexdigest(),
    }
    try:
        harness_before = _directory_inventory(harness_root)
    except ScopeViolation as exc:
        return False, {"sandbox": "not_started", "integrity_error": str(exc)}, ["SAFETY_OR_SECURITY"]
    if harness_before != harness_expected:
        return False, {
            "sandbox": "not_started", "harness_integrity": False,
            "expected_harness_files": sorted(harness_expected),
            "actual_harness_files": sorted(harness_before),
        }, ["TEST_WEAKENING"]

    temp_dir = workspace / "_tmp"
    cache_dir = workspace / "_pytest_cache"
    temp_dir.mkdir(exist_ok=True)
    cache_dir.mkdir(exist_ok=True)
    if not SANDBOX_EXEC.is_file():
        return False, {"sandbox": "unavailable"}, ["SAFETY_OR_SECURITY"]
    env = {
        "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
        "PYTHONPATH": str(workspace),
        "HOME": str(workspace),
        "TMPDIR": str(temp_dir),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completion_nonce = secrets.token_hex(32)
    completion_path = workspace.parent / f".pytest-completion-{secrets.token_hex(16)}"
    completion_path.write_text("", encoding="utf-8")
    profile = _sandbox_profile(
        workspace,
        read_only_roots=(harness_root,),
        writable_roots=(temp_dir, cache_dir),
        writable_files=(completion_path,),
    )
    command_prefix = [str(SANDBOX_EXEC), "-p", profile, PYTHON, "-I", "-B", "-c"]
    bootstrap = (
        "import sys, platform; platform.node = lambda: 'sandbox'; "
        "sys.path.insert(0, sys.argv[1]); import pytest; "
        "raise SystemExit(pytest.main(sys.argv[2:]))"
    )
    completion_bootstrap = (
        "import sys, platform; platform.node = lambda: 'sandbox'; "
        "sys.path.insert(0, sys.argv[1]); import pytest; "
        "rc = pytest.main(sys.argv[2:]); "
        f"open({str(completion_path)!r}, 'w', encoding='utf-8').write({completion_nonce!r} + ':' + str(int(rc))); "
        "raise SystemExit(rc)"
    )
    pytest_args = [
        str(workspace), "-q", "-c", str(config_path), str(test_dir),
        "-o", f"cache_dir={cache_dir}",
    ]
    command = [*command_prefix, completion_bootstrap, *pytest_args]
    hard_fails: list[str] = []
    collection_command = [*command_prefix, bootstrap, *pytest_args, "--collect-only"]
    collection_returncode: int | None = None
    try:
        collection = subprocess.run(
            collection_command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
        )
        collection_returncode = collection.returncode
        collection_stdout = collection.stdout[-4000:]
        collection_stderr = collection.stderr[-4000:]
        census_match = re.search(r"(\d+) tests? collected", collection.stdout)
        collected_nodeids = [
            line.strip() for line in collection.stdout.splitlines()
            if "::" in line and not line.lstrip().startswith(("=", "<"))
        ]
        expected_test_count = int(census_match.group(1)) if census_match else 0
        collection_complete = (
            collection.returncode == 0
            and expected_test_count > 0
            and len(collected_nodeids) == expected_test_count
        )
    except subprocess.TimeoutExpired as exc:
        collection_stdout = (exc.stdout or "")[-4000:]
        collection_stderr = (exc.stderr or "")[-4000:]
        expected_test_count = 0
        collected_nodeids = []
        collection_complete = False
        hard_fails.append("TEST_TIMEOUT")

    if collection_returncode not in (0, None):
        if collection_returncode == 5:
            hard_fails.append("TEST_SKIPPED")
        else:
            hard_fails.append("GENERATED_CODE_COLLECTION_ERROR")

    report_path = cache_dir / f"pytest-report-{time.time_ns()}.xml"
    returncode: int | None = None
    stdout = collection_stdout
    stderr = collection_stderr
    if collection_complete:
        try:
            result = subprocess.run(
                [*command, "--junitxml", str(report_path)],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                env=env,
            )
            returncode = result.returncode
            stdout = result.stdout[-4000:]
            stderr = result.stderr[-4000:]
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "")[-4000:]
            stderr = (exc.stderr or "")[-4000:]
            hard_fails.append("TEST_TIMEOUT")

    junit_counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if report_path.is_file() and not report_path.is_symlink():
        try:
            report_root = ET.parse(report_path).getroot()
            suites = [report_root] if report_root.tag == "testsuite" else report_root.findall("testsuite")
            junit_counts = {
                key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
                for key in junit_counts
            }
        except (ET.ParseError, OSError, ValueError):
            pass
    try:
        expected_marker = f"{completion_nonce}:{returncode}" if returncode is not None else ""
        completion_marker = (
            returncode is not None
            and completion_path.read_text(encoding="utf-8") == expected_marker
        )
    except OSError:
        completion_marker = False
    pytest_completion = (
        collection_complete
        and returncode is not None
        and completion_marker
        and junit_counts["tests"] == expected_test_count
        and junit_counts["skipped"] == 0
    )
    if not pytest_completion:
        hard_fails.append("TEST_CENSUS_MISMATCH")

    try:
        harness_after = _directory_inventory(harness_root)
        harness_integrity = harness_after == harness_expected
    except ScopeViolation:
        harness_after = {}
        harness_integrity = False
        hard_fails.append("SAFETY_OR_SECURITY")
    if not harness_integrity:
        hard_fails.append("TEST_WEAKENING")

    try:
        generated_after = _workspace_inventory(workspace)
        file_set_integrity = set(generated_after) == expected_files
        generated_file_integrity = all(
            generated_after.get(relative) == digest for relative, digest in generated_before.items()
        ) and file_set_integrity
    except ScopeViolation:
        generated_after = {}
        file_set_integrity = False
        generated_file_integrity = False
        hard_fails.append("SAFETY_OR_SECURITY")
    if not file_set_integrity:
        hard_fails.append("FILE_SET_MISMATCH")
    if not generated_file_integrity:
        hard_fails.append("TEST_WEAKENING")
    if returncode not in (0, None) or junit_counts["failures"] or junit_counts["errors"]:
        hard_fails.append("HIDDEN_TEST_FAILURE")

    hard_fails = list(dict.fromkeys(hard_fails))
    checks = {
        "sandbox": "seatbelt",
        "pytest_rc": returncode,
        "pytest_completion": pytest_completion,
        "completion_marker": completion_marker,
        "collection_complete": collection_complete,
        "collection_rc": collection_returncode,
        "expected_test_count": expected_test_count,
        "collected_nodeids": collected_nodeids,
        "junit_counts": junit_counts,
        "stdout": stdout,
        "stderr": stderr,
        "harness_integrity": harness_integrity,
        "generated_file_integrity": generated_file_integrity,
        "file_set_integrity": file_set_integrity,
        "expected_files": sorted(expected_files),
        "actual_files": sorted(generated_after),
    }
    passed = returncode == 0 and not hard_fails
    return passed, checks, hard_fails


def run_cell(run_id: str, root: Path, goal: Goal, model: str, mode: str, trial: int) -> Cell:
    """Execute one immutable benchmark cell."""
    started = time.monotonic()
    workspace = cell_trial_dir(root, goal, model, mode, trial) / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    responses: list[str] = []
    prompt_paths: list[str] = []
    prompt_hashes: list[str] = []
    calls = prompt_tokens = response_tokens = 0
    evidence_failures: set[str] = set()
    capabilities = provider_capabilities(model)
    token_usage_available = capabilities["token_usage_available"]
    output_budget_enforced = capabilities["output_budget_enforced"]
    try:
        if mode != "W":
            raise ValueError("workspace mode W required")
        cards = list(atomic_order(goal.cards))
        test_feedback = ""
        passed = False
        checks: dict[str, Any] = {}
        hard_fails: list[str] = []
        error = ""
        integrity_abort = False
        for attempt in range(1, 4):
            try:
                for card in cards:
                    prompt = build_file_prompt(
                        goal, card=card, workspace=workspace, test_feedback=test_feedback,
                    )
                    prompt_record = effective_prompt_record(model, prompt, num_predict=goal.max_output_tokens)
                    prompt_bytes = (json.dumps(prompt_record, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
                    prompt_path = workspace.parent / f"prompt-{calls + 1:03d}.json"
                    prompt_path.write_bytes(prompt_bytes)
                    prompt_paths.append(str(prompt_path))
                    prompt_hashes.append(hashlib.sha256(prompt_bytes).hexdigest())
                    text, usage = call_model(
                        model, prompt, num_predict=goal.max_output_tokens, effective_record=prompt_record,
                    )
                    responses.append(text)
                    calls += 1
                    prompt_count = usage.get("prompt")
                    response_count = usage.get("response")
                    if prompt_count is None or response_count is None:
                        token_usage_available = False
                    else:
                        prompt_tokens += int(prompt_count)
                        response_tokens += int(response_count)
                    output_budget_enforced = output_budget_enforced and bool(usage.get("output_budget_enforced", False))
                    token_usage_available = token_usage_available and bool(usage.get("token_usage_available", False))
                    if usage.get("evidence_failure"):
                        evidence_failures.add(str(usage["evidence_failure"]))
                    source = extract_source_response(text)
                    write_model_files(workspace, {card.write_path: source}, card.write_paths)
                    generated_path = _confined_workspace_path(workspace, card.write_path)
                    compile_result = subprocess.run(
                        [PYTHON, "-m", "compileall", "-q", str(generated_path)],
                        capture_output=True, text=True, timeout=30, check=False,
                    )
                    if compile_result.returncode != 0:
                        diagnostics = "\n".join(
                            part for part in (compile_result.stdout, compile_result.stderr) if part
                        ).strip()
                        raise CompileFailure("syntax_or_import_compile_failure: " + diagnostics[-2000:])
                passed, checks, hard_fails = _run_hidden_tests(workspace, goal)
                if passed:
                    break
                if set(hard_fails) & {
                    "SAFETY_OR_SECURITY", "SCOPE_CREEP", "TEST_WEAKENING", "FILE_SET_MISMATCH",
                }:
                    integrity_abort = True
                    break
                test_feedback = "\n".join(
                    part for part in (
                        str(checks.get("stdout", "")), str(checks.get("stderr", "")),
                    ) if part
                )[-4000:] or "Hidden tests failed; inspect the specification and current workspace."
            except (ResponseContractError, CompileFailure) as exc:
                if attempt == 3:
                    raise
                test_feedback = f"{type(exc).__name__}: {exc}"
        status = "ok" if passed else "failed"
        if not passed:
            error = (
                "workspace integrity failure; correction aborted"
                if integrity_abort else "hidden tests failed after 3 workspace passes"
            )
    except ScopeViolation as exc:
        passed, checks, hard_fails, status, error = False, {}, ["SCOPE_CREEP"], "failed", str(exc)
    except ResponseContractError as exc:
        passed, checks, hard_fails, status, error = False, {}, ["CONTRACT_FORMAT"], "failed", str(exc)
    except CompileFailure as exc:
        passed, checks, hard_fails, status, error = False, {}, ["COMPILE_FAILURE"], "failed", str(exc)
    except ModelIdentityMismatch as exc:
        passed, checks, hard_fails, status, error = False, {}, ["PROVIDER_MODEL_MISMATCH"], "error", str(exc)
    except ProviderContractError as exc:
        passed, checks, hard_fails, status, error = False, {}, ["PROVIDER_CONTRACT"], "error", str(exc)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        passed, checks, hard_fails, status, error = False, {}, ["TOOL_OR_RUNTIME"], "error", str(exc)
    if evidence_failures:
        passed = False
        status = "unverified"
        hard_fails = sorted(set([*hard_fails, *evidence_failures]))
        error = "provider route identity is unverified; cell is diagnostic only"
    cell = Cell(
        run_id=run_id, model=model, mode=mode, goal_id=goal.id, tier=goal.tier, trial=trial,
        status=status, passed=passed, score=1.0 if passed else 0.0, hard_fails=hard_fails,
        elapsed_s=round(time.monotonic() - started, 3), model_calls=calls,
        prompt_tokens=prompt_tokens, response_tokens=response_tokens,
        token_usage_available=token_usage_available, output_budget_enforced=output_budget_enforced,
        prompt_paths=prompt_paths, prompt_hashes=prompt_hashes, response_texts=responses,
        checks=checks, error=error,
    )
    cell_path = workspace.parent / "cell.json"
    cell.artifact_path = str(cell_path)
    cell_path.write_text(json.dumps(asdict(cell), indent=2, ensure_ascii=False), encoding="utf-8")
    return cell


def breakpoint_for(
    cells: list[Cell], *, model: str, mode: str, expected_repeats: int,
    expected_goal_ids: dict[int, set[str]] | None = None,
) -> dict[str, Any]:
    """Calculate a fail-closed contiguous reliable ceiling."""
    selected = [cell for cell in cells if cell.model == model and cell.mode == mode]
    tiers: dict[str, Any] = {}
    tier_numbers = (
        set(expected_goal_ids) | {cell.tier for cell in selected}
        if expected_goal_ids is not None else {cell.tier for cell in selected}
    )
    for tier in sorted(tier_numbers):
        rows = [cell for cell in selected if cell.tier == tier]
        expected_goals = (
            expected_goal_ids.get(tier, set()) if expected_goal_ids is not None
            else {cell.goal_id for cell in rows}
        )
        expected_pairs = {
            (goal_id, trial)
            for goal_id in expected_goals
            for trial in range(1, expected_repeats + 1)
        }
        actual_pairs = [(cell.goal_id, cell.trial) for cell in rows]
        complete = (
            bool(expected_goals)
            and set(actual_pairs) == expected_pairs
            and len(actual_pairs) == len(set(actual_pairs))
        )
        rate = sum(cell.passed for cell in rows) / len(rows) if rows else None
        critical = any(any(fail in {"FILE_SET_MISMATCH", "SCOPE_CREEP", "TEST_WEAKENING", "SAFETY_OR_SECURITY"} for fail in cell.hard_fails) for cell in rows)
        if not complete:
            state = "ineligible"
        elif critical or rate is None or rate < 2 / 3:
            state = "unreliable"
        elif rate >= 0.9:
            state = "reliable"
        else:
            state = "conditional"
        tiers[f"C{tier}"] = {
            "state": state,
            "pass_rate": round(rate, 4) if rate is not None else None,
            "trials": len(rows),
            "expected_trials": len(expected_pairs),
            "expected_goals": sorted(expected_goals),
        }
    ceiling: int | None = None
    for tier in range(6):
        row = tiers.get(f"C{tier}")
        if row and row["state"] == "reliable":
            ceiling = tier
        else:
            break
    breakpoint = None
    if ceiling is not None and f"C{ceiling + 1}" in tiers:
        breakpoint = ceiling + 1
    elif ceiling is None and tiers.get("C0", {}).get("state") == "unreliable":
        breakpoint = 0
    later_reliable = breakpoint is not None and any(
        row["state"] == "reliable" for key, row in tiers.items() if int(key[1:]) > breakpoint
    )
    return {"model": model, "mode": mode, "reliable_ceiling": ceiling, "breakpoint": breakpoint, "non_monotonic": later_reliable, "tiers": tiers}


def make_schedule(models: list[str], goals: list[Goal], modes: list[str], repeats: int) -> list[tuple[str, Goal, str, int]]:
    """Build a rotating model-major schedule while preserving supplied mode order."""
    schedule: list[tuple[str, Goal, str, int]] = []
    for trial in range(1, repeats + 1):
        offset = (trial - 1) % len(models)
        ordered_models = models[offset:] + models[:offset]
        for model in ordered_models:
            for goal in goals:
                for mode in modes:
                    schedule.append((model, goal, mode, trial))
    return schedule


def _cell_key(cell: Cell) -> tuple[str, str, str, int]:
    return cell.model, cell.goal_id, cell.mode, cell.trial


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            Path(temporary).unlink(missing_ok=True)
        finally:
            raise


def _write_results(results_path: Path, cells: list[Cell]) -> None:
    payload = "".join(json.dumps(asdict(cell), ensure_ascii=False) + "\n" for cell in cells)
    _atomic_write_bytes(results_path, payload.encode("utf-8"))


def recover_torn_results(results_path: Path, archive_root: Path) -> list[Cell]:
    """Preserve and remove only an invalid final JSONL fragment."""
    if not results_path.is_file():
        return []
    raw = results_path.read_bytes()
    lines = raw.splitlines(keepends=True)
    valid_lines: list[bytes] = []
    for index, line in enumerate(lines):
        try:
            json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if index != len(lines) - 1:
                raise ValueError(f"invalid results row {index + 1}") from exc
            archive_root.mkdir(parents=True, exist_ok=True)
            suffix = hashlib.sha256(raw).hexdigest()[:12]
            archived = archive_root / f"torn-results-{suffix}.jsonl"
            archived.write_bytes(raw)
            _atomic_write_bytes(results_path, b"".join(valid_lines))
            break
        valid_lines.append(line if line.endswith(b"\n") else line + b"\n")
    else:
        canonical = b"".join(valid_lines)
        if canonical != raw:
            _atomic_write_bytes(results_path, canonical)
    return load_existing_cells(results_path)


def validate_cells_against_schedule(
    cells: list[Cell], schedule: list[tuple[str, Goal, str, int]], *, run_id: str | None = None,
) -> None:
    expected = {
        (model, goal.id, mode, trial): goal
        for model, goal, mode, trial in schedule
    }
    if len(expected) != len(schedule):
        raise ValueError("schedule contains duplicate cell identities")
    for cell in cells:
        goal = expected.get(_cell_key(cell))
        if goal is None:
            raise ValueError(f"unscheduled result cell: {_cell_key(cell)}")
        if cell.tier != goal.tier:
            raise ValueError(f"result goal/tier mismatch: {_cell_key(cell)}")
        if run_id is not None and cell.run_id != run_id:
            raise ValueError(f"result run_id mismatch: {_cell_key(cell)}")


def reconcile_resume(
    root: Path, schedule: list[tuple[str, Goal, str, int]], *, run_id: str | None = None,
) -> list[Cell]:
    """Recover terminal cells and quarantine incomplete attempts before resume."""
    results_path = root / "results.jsonl"
    cells = recover_torn_results(results_path, root / "_Archive")
    validate_cells_against_schedule(cells, schedule, run_id=run_id)
    by_key = {_cell_key(cell): cell for cell in cells}
    for model, goal, mode, trial in schedule:
        key = (model, goal.id, mode, trial)
        trial_dir = cell_trial_dir(root, goal, model, mode, trial)
        cell_path = trial_dir / "cell.json"
        terminal: Cell | None = None
        if cell_path.is_file():
            try:
                terminal = Cell(**json.loads(cell_path.read_text(encoding="utf-8")))
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid terminal cell: {cell_path}") from exc
            validate_cells_against_schedule([terminal], schedule, run_id=run_id)
            if _cell_key(terminal) != key:
                raise ValueError(
                    f"terminal cell does not match schedule slot: expected={key}, actual={_cell_key(terminal)}"
                )
            if Path(terminal.artifact_path).resolve() != cell_path.resolve():
                raise ValueError(f"terminal artifact_path mismatch: {cell_path}")
        if key in by_key:
            retained = by_key[key]
            if Path(retained.artifact_path).resolve() != cell_path.resolve():
                raise ValueError(f"result artifact_path mismatch: {cell_path}")
            if terminal is None:
                raise ValueError(f"missing canonical terminal artifact: {cell_path}")
            if asdict(terminal) != asdict(retained):
                raise ValueError(f"conflicting duplicate terminal cell: {key}")
            continue
        if terminal is not None:
            by_key[key] = terminal
        elif trial_dir.exists():
            archive = root / "_Archive" / "incomplete-cells"
            archive.mkdir(parents=True, exist_ok=True)
            suffix = f"{goal.id}-{model_workspace_id(model)}-{mode}-{trial:03d}-{time.time_ns()}"
            trial_dir.replace(archive / suffix)
    ordered = [
        by_key[key] for model, goal, mode, trial in schedule
        if (key := (model, goal.id, mode, trial)) in by_key
    ]
    _write_results(results_path, ordered)
    return ordered


def load_existing_cells(results_path: Path) -> list[Cell]:
    """Load immutable JSONL cells and reject duplicate identities."""
    if not results_path.is_file():
        return []
    cells: list[Cell] = []
    seen: set[tuple[str, str, str, int]] = set()
    for line_number, line in enumerate(results_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cell = Cell(**json.loads(line))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid results row {line_number}") from exc
        key = _cell_key(cell)
        if key in seen:
            raise ValueError(f"duplicate results cell at row {line_number}: {key}")
        seen.add(key)
        cells.append(cell)
    return cells


def pending_schedule(
    schedule: list[tuple[str, Goal, str, int]], completed: list[Cell],
) -> list[tuple[str, Goal, str, int]]:
    """Return schedule entries not already represented by immutable cells."""
    completed_keys = {_cell_key(cell) for cell in completed}
    return [
        entry for entry in schedule
        if (entry[0], entry[1].id, entry[2], entry[3]) not in completed_keys
    ]


def summarize(
    run_id: str, root: Path, cells: list[Cell], models: list[str], modes: list[str],
    repeats: int, evidence_class: str, *, goals: list[Goal] | None = None,
) -> dict[str, Any]:
    selected_goals = goals or [
        Goal(f"C{tier}", tier, "synthetic", "synthetic", ("x.py",), (), "pass", 1)
        for tier in sorted({cell.tier for cell in cells})
    ]
    expected_goal_ids: dict[int, set[str]] = {}
    for goal in selected_goals:
        expected_goal_ids.setdefault(goal.tier, set()).add(goal.id)
    boundaries = [
        breakpoint_for(
            cells, model=model, mode=mode, expected_repeats=repeats,
            expected_goal_ids=expected_goal_ids,
        )
        for model in models for mode in modes
    ]
    data = {
        "schema_version": 1, "run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evidence_class": evidence_class, "models": models, "modes": modes, "repeats": repeats,
        "cells_planned": len(models) * len(modes) * len(selected_goals) * repeats,
        "cells_completed": len(cells), "boundaries": boundaries, "cells": [asdict(cell) for cell in cells],
    }
    (root / "summary.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    write_reports(root, data)
    return data


def write_reports(root: Path, summary: dict[str, Any]) -> None:
    """Render Markdown and HTML from one summary model."""
    lines = ["# Format-Neutral Coding Workspace Benchmark", "", f"Evidence class: **{summary['evidence_class']}**", "", "## Boundaries", "", "| Model | Mode | Reliable ceiling | Breakpoint | Non-monotonic |", "|---|---:|---:|---:|---:|"]
    for row in summary["boundaries"]:
        ceiling = "N/R" if row["reliable_ceiling"] is None else f"C{row['reliable_ceiling']}"
        point = "N/R" if row["breakpoint"] is None else f"C{row['breakpoint']}"
        lines.append(f"| {row['model']} | {row['mode']} | {ceiling} | {point} | {row['non_monotonic']} |")
    lines += [
        "", "## Cells", "",
        "| Goal | Model | Mode | Trial | Result | Seconds | Calls | Token usage | Output cap |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in summary["cells"]:
        usage = "available" if cell["token_usage_available"] else "unavailable"
        budget = "enforced" if cell["output_budget_enforced"] else "not enforced"
        lines.append(f"| {cell['goal_id']} | {cell['model']} | {cell['mode']} | {cell['trial']} | {'PASS' if cell['passed'] else 'FAIL'} | {cell['elapsed_s']} | {cell['model_calls']} | {usage} | {budget} |")
    markdown = "\n".join(lines) + "\n"
    (root / "report.md").write_text(markdown, encoding="utf-8")
    escaped = html.escape(markdown)
    (root / "report.html").write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>Coding Breakpoint</title><style>body{{font-family:-apple-system,sans-serif;margin:32px}}pre{{white-space:pre-wrap}}</style></head><body><pre>{escaped}</pre></body></html>", encoding="utf-8")


def run_self_test(root: Path) -> dict[str, Any]:
    """Exercise offline contracts and report generation without model calls."""
    root.mkdir(parents=True, exist_ok=True)
    goals = goal_catalog()
    assert [goal.tier for goal in goals] == list(range(6))
    for goal in goals:
        atomic_order(goal.cards)
        assert set(card.write_path for card in goal.cards) == set(goal.allowed_files)
    cells = [Cell.synthetic(model="offline-control", mode="W", tier=tier, trial=1, passed=True) for tier in range(6)]
    summary = summarize("offline-self-test", root, cells, ["offline-control"], ["W"], 1, "offline_self_test")
    return {"status": "pass", "model_calls": 0, "goals": len(goals), "summary": str(root / "summary.json"), "boundaries": summary["boundaries"]}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--suite", choices=("calibration", "promotion"), default="calibration")
    parser.add_argument("--families", default="P,S,R")
    parser.add_argument("--modes", default="W")
    parser.add_argument("--tiers", default="C0,C1,C2,C3,C4,C5")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d-%H%M%S-coding-workspace"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


RESUME_MANIFEST_KEYS = (
    "run_id", "models", "privacy_class", "repeats", "seed", "run_order", "task_hash",
    "prompt_profile_hashes", "source_hashes", "model_identity", "execution_modes",
    "suite", "goal_ids", "provider_capabilities", "evidence_class",
)


def validate_resume_manifest(
    retained: dict[str, Any], current: dict[str, Any], *, keys: Iterable[str] = RESUME_MANIFEST_KEYS,
) -> None:
    """Require retained provenance to match every immutable resume dimension."""
    for key in keys:
        if retained.get(key) != current.get(key):
            raise ValueError(f"resume manifest mismatch: {key}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        root = new_run_root(ARTIFACTS_DIR, args.run_id)
        print(json.dumps(run_self_test(root), indent=2))
        return 0
    models = [value.strip() for value in args.models.split(",") if value.strip()]
    modes = [value.strip().upper() for value in args.modes.split(",") if value.strip()]
    tier_ids = [value.strip().upper() for value in args.tiers.split(",") if value.strip()]
    validate_dimensions(models, modes, tier_ids, repeats=args.repeats)
    require_profile_coverage(models)
    if args.suite == "promotion":
        families = [value.strip().upper() for value in args.families.split(",") if value.strip()]
        if not families or len(families) != len(set(families)) or any(value not in {"P", "S", "R"} for value in families):
            raise ValueError("families must be a non-empty unique P/S/R selection")
        goals = [
            goal for goal in promotion_goal_catalog()
            if f"C{goal.tier}" in tier_ids and goal.id.rsplit("-", 1)[-1] in families
        ]
    else:
        goals_by_id = {goal.id: goal for goal in goal_catalog()}
        goals = [goals_by_id[value] for value in tier_ids]
    if not goals:
        raise ValueError("selected suite produced no goals")
    preflight_runtime(models, ARTIFACTS_DIR)
    if args.resume:
        root = validated_run_root(ARTIFACTS_DIR, args.run_id)
        if not root.is_dir():
            raise FileNotFoundError(f"resume root not found: {root}")
    else:
        root = new_run_root(ARTIFACTS_DIR, args.run_id)
    manifest = build_manifest(
        run_id=args.run_id, models=models, task_payload=[asdict(goal) for goal in goals],
        source_paths=[Path(__file__), Path(__file__).with_name("test_coding_workspace_benchmark.py"), Path(__file__).with_name("local_coding_promotion_goals.py")],
        repeats=args.repeats, seed=19, run_order=RUN_ORDER, privacy_class="synthetic", argv=[Path(__file__).name],
        model_routes={model: manifest_route(model) for model in models},
    )
    manifest["execution_modes"] = modes
    manifest["suite"] = args.suite
    manifest["goal_ids"] = [goal.id for goal in goals]
    manifest["provider_capabilities"] = {model: provider_capabilities(model) for model in models}
    manifest["evidence_class"] = (
        "multi_family_comparative_calibration" if args.suite == "promotion"
        else "single_family_calibration" if args.repeats == 1
        else "repeated_single_family_boundary"
    )
    manifest_path = root / "manifest.json"
    if args.resume:
        retained = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_resume_manifest(retained, manifest)
    else:
        write_manifest(root, manifest)
    results_path = root / "results.jsonl"
    full_schedule = make_schedule(models, goals, modes, args.repeats)
    cells = reconcile_resume(root, full_schedule, run_id=args.run_id) if args.resume else []
    validate_cells_against_schedule(cells, full_schedule, run_id=args.run_id)
    for model, goal, mode, trial in pending_schedule(full_schedule, cells):
        cell = run_cell(args.run_id, root, goal, model, mode, trial)
        cells.append(cell)
        _write_results(results_path, cells)
        print(f"{goal.id} {mode} {model}: {'PASS' if cell.passed else 'FAIL'} {cell.elapsed_s:.1f}s {cell.hard_fails}", flush=True)
    evidence = manifest["evidence_class"]
    summary = summarize(args.run_id, root, cells, models, modes, args.repeats, evidence, goals=goals)
    print(json.dumps({"artifact_root": str(root), "boundaries": summary["boundaries"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
