#!/usr/bin/env python3
"""PA-derived coding benchmark goals.

Goals derived from real PA project coding patterns:
- C1-PG: Privacy-gated cloud authorization (PDF_Converter_Clean cloud_privacy.py)
- C2-MD: Markdown table extraction with regex (APM Creation state_manager.py)
- C3-AS: Async dependency-ordered orchestration (APM Creation orchestrator.py)
- C3-CT: Typed request/response contracts (ai-learning-coach contracts.py)

Each goal mirrors the complexity and pattern of the real project code
without copying it. The contracts and hidden tests are self-contained.
"""
from __future__ import annotations

from typing import Any


def pa_derived_goal_specs() -> list[dict[str, Any]]:
    return [

        # ── C1-PG: Privacy-gated authorization (from PDF_Converter_Clean) ──
        {
            "id": "C1-PG",
            "tier": 1,
            "name": "Privacy-gated authorization guard",
            "specification": (
                "Create auth_guard.py. Define ELIGIBLE_CLASSIFICATIONS as a frozenset of "
                "exact string values 'public' and 'nonpersonal'. Define "
                "ELIGIBLE_RESTRICTION as the exact string 'unrestricted'. Define "
                "AuthorizationDenied(ValueError) exception. Implement "
                "authorize(classification: str | None, *, allow_cloud: bool, "
                "restriction_status: str | None, operation: str = 'processing') -> str. "
                "The function must verify all three conditions independently: "
                "(1) classification is an exact member of ELIGIBLE_CLASSIFICATIONS; "
                "(2) restriction_status equals ELIGIBLE_RESTRICTION exactly; "
                "(3) allow_cloud is exactly True. No normalization of inputs. "
                "Raise AuthorizationDenied with a message containing the operation name "
                "and which condition failed. Return the classification on success. "
                "Do not mutate inputs or use dependencies."
            ),
            "allowed_files": ("auth_guard.py",),
            "objectives": (
                "Implement the fail-closed authorization guard with exact classification, "
                "restriction, and consent checks.",
            ),
            "hidden_tests": """import pytest
from auth_guard import authorize, AuthorizationDenied, ELIGIBLE_CLASSIFICATIONS

def test_authorizes_public():
    assert authorize('public', allow_cloud=True, restriction_status='unrestricted') == 'public'

def test_authorizes_nonpersonal():
    assert authorize('nonpersonal', allow_cloud=True, restriction_status='unrestricted') == 'nonpersonal'

def test_returns_classification_unchanged():
    result = authorize('public', allow_cloud=True, restriction_status='unrestricted', operation='vision')
    assert result == 'public'

@pytest.mark.parametrize('cls,allow,restrict', [
    (None, True, 'unrestricted'),
    ('PUBLIC', True, 'unrestricted'),
    ('public ', True, 'unrestricted'),
    ('confidential', True, 'unrestricted'),
    ('public', False, 'unrestricted'),
    ('public', 'yes', 'unrestricted'),
    ('public', True, 'restricted'),
    ('public', True, None),
    ('public', True, 'UNRESTRICTED'),
])
def test_denied(cls, allow, restrict):
    with pytest.raises(AuthorizationDenied):
        authorize(cls, allow_cloud=allow, restriction_status=restrict)

def test_operation_in_message():
    try:
        authorize('public', allow_cloud=False, restriction_status='unrestricted', operation='vision')
    except AuthorizationDenied as e:
        assert 'vision' in str(e)
    else:
        pytest.fail('should have raised')
""",
            "max_output_tokens": 1200,
        },

        # ── C2-MD: Markdown table extraction (from APM Creation state_manager) ──
        {
            "id": "C2-MD",
            "tier": 2,
            "name": "Markdown table risk-ID extractor",
            "specification": (
                "Create risk_extractor.py. Implement extract_scoped_risk_ids("
                "markdown: str, section_heading: str) -> list[str]. The function finds "
                "a markdown section starting with a heading line matching '### <section_heading>' "
                "(case-insensitive, leading # and whitespace trimmed). The section ends at the "
                "next heading of level 1-3 or end of text. Within the section, find the first "
                "markdown table row containing a column header (case-insensitive) containing "
                "'id' AND a column header containing 'scope'. Record the 0-based column index "
                "of each. Then iterate non-header, non-separator rows: a row is in-scope when "
                "its scope cell (trimmed, lowercased) starts with 'yes'. For in-scope rows, "
                "extract the first match of the pattern [A-Za-z]{2,}[A-Za-z0-9._-]*\\d+ from "
                "the id cell. Return unique IDs in first-seen order. Return [] when the section "
                "is not found, the table has no matching headers, or no rows are in-scope. "
                "Do not mutate inputs. Use only stdlib re and typing."
            ),
            "allowed_files": ("risk_extractor.py",),
            "objectives": (
                "Implement markdown section boundary detection, table header identification, "
                "scoped row filtering, and unique ID extraction with regex.",
            ),
            "hidden_tests": """import pytest
from risk_extractor import extract_scoped_risk_ids

SAMPLE = '''# Document

### 5.3 Risk Prioritization

| ID (New) | Severity | In Audit Scope | Owner |
|---|---|---|---|
| RISK001 | High | Yes | Audit |
| CTRL002 | Low | No | Ops |
| RISK003 | Medium | Yes | Audit |

### 6.0 Next Section

| ID | Scope |
|---|---|
| X001 | Yes |
'''

def test_extracts_scoped_ids():
    result = extract_scoped_risk_ids(SAMPLE, '5.3 Risk Prioritization')
    assert result == ['RISK001', 'RISK003']

def test_case_insensitive_heading():
    result = extract_scoped_risk_ids(SAMPLE, '5.3 RISK PRIORITIZATION')
    assert result == ['RISK001', 'RISK003']

def test_section_not_found():
    assert extract_scoped_risk_ids(SAMPLE, '7.0 Missing') == []

def test_no_matching_headers():
    text = '''### 5.3 Risks

| Name | Owner |
|---|---|
| RISK001 | Yes |
'''
    assert extract_scoped_risk_ids(text, '5.3 Risks') == []

def test_no_in_scope_rows():
    text = '''### 5.3 Risks

| ID | Scope |
|---|---|
| R001 | No |
| R002 | Maybe |
'''
    assert extract_scoped_risk_ids(text, '5.3 Risks') == []

def test_unique_first_seen_order():
    text = '''### Risks

| ID | Scope |
|---|---|
| RISK001 | Yes |
| RISK002 | Yes |
| RISK001 | Yes |
'''
    assert extract_scoped_risk_ids(text, 'Risks') == ['RISK001', 'RISK002']

def test_empty_input():
    assert extract_scoped_risk_ids('', 'Risks') == []

def test_no_mutation():
    original = SAMPLE
    extract_scoped_risk_ids(SAMPLE, '5.3 Risk Prioritization')
    assert SAMPLE == original
""",
            "max_output_tokens": 2000,
        },

        # ── C3-AS: Async dependency-ordered orchestration (from APM Creation) ──
        {
            "id": "C3-AS",
            "tier": 3,
            "name": "Async dependency-ordered task runner",
            "specification": (
                "Create dep_model.py and dep_runner.py. dep_model.py defines "
                "normalize_id(value: str) -> str: strip whitespace; if the value starts "
                "with 'task_' remove that prefix; if the remaining value is all digits, "
                "zero-pad to 2 digits; return the result. Reject empty or non-string "
                "input with ValueError or TypeError. dep_runner.py defines "
                "build_dependency_map(task_ids: list[str], dependencies: dict[str, list[str]]) "
                "-> dict[str, set[str]]. For each task_id in task_ids, normalize it and create "
                "an entry with an empty set. For each key in dependencies, normalize the key; "
                "if it is 'ALL' or '*', add all other normalized task_ids as dependencies for "
                "every task. Otherwise, for each dependency string in the list, normalize it; "
                "skip self-dependencies and unknown IDs. Return the map. Also define "
                "async run_with_dependencies(task_ids: list[str], dep_map: dict[str, set[str]], "
                "worker: callable, concurrency: int = 5) -> dict[str, bool]. Use asyncio. "
                "Run tasks concurrently up to concurrency with a Semaphore. A task may only "
                "start when all its dependencies are done (use asyncio.Event per task). "
                "Call worker(normalized_id) and catch Exception as failure. Return a dict "
                "of normalized_id -> bool (True if worker succeeded). Use only stdlib asyncio, "
                "typing, and collections."
            ),
            "allowed_files": ("dep_model.py", "dep_runner.py"),
            "objectives": (
                "Implement task ID normalization with validation and dependency map construction with ALL/wildcard support.",
                "Implement async semaphore-bounded execution with dependency ordering and failure capture.",
            ),
            "hidden_tests": """import asyncio
import pytest
from dep_model import normalize_id
from dep_runner import build_dependency_map, run_with_dependencies

def test_normalize():
    assert normalize_id('task_01') == '01'
    assert normalize_id(' task_5 ') == '05'
    assert normalize_id('custom_name') == 'custom_name'

def test_normalize_rejects():
    with pytest.raises(ValueError): normalize_id('')
    with pytest.raises(TypeError): normalize_id(None)

def test_build_dep_map():
    ids = ['01', '02', '03']
    deps = {'03': ['01', '02']}
    dm = build_dependency_map(ids, deps)
    assert dm == {'01': set(), '02': set(), '03': {'01', '02'}}

def test_build_dep_map_all():
    ids = ['01', '02', '03']
    deps = {'ALL': ['00']}
    dm = build_dependency_map(ids, deps)
    # '00' is not in task_ids, so it should be skipped
    assert dm == {'01': set(), '02': set(), '03': set()}

def test_build_dep_map_all_to_all():
    ids = ['01', '02', '03']
    deps = {'ALL': ['ALL']}
    dm = build_dependency_map(ids, deps)
    assert dm['01'] == {'02', '03'}
    assert dm['02'] == {'01', '03'}
    assert dm['03'] == {'01', '02'}

def test_run_with_deps():
    async def main():
        ids = ['01', '02', '03']
        deps = {'03': ['01', '02']}
        dm = build_dependency_map(ids, deps)
        order = []
        async def worker(tid):
            order.append(tid)
            await asyncio.sleep(0.01)
            return True
        result = await run_with_dependencies(ids, dm, worker, concurrency=2)
        assert result == {'01': True, '02': True, '03': True}
        assert order.index('01') < order.index('03')
        assert order.index('02') < order.index('03')
    asyncio.run(main())

def test_run_captures_failure():
    async def main():
        ids = ['01', '02']
        dm = {'01': set(), '02': set()}
        async def worker(tid):
            if tid == '01':
                raise RuntimeError('boom')
            return True
        result = await run_with_dependencies(ids, dm, worker, concurrency=2)
        assert result == {'01': False, '02': True}
    asyncio.run(main())

def test_run_respects_concurrency():
    async def main():
        ids = ['01', '02', '03', '04']
        dm = {tid: set() for tid in ids}
        import threading
        lock = threading.Lock()
        active = 0
        peak = 0
        async def worker(tid):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.05)
            with lock:
                active -= 1
            return True
        await run_with_dependencies(ids, dm, worker, concurrency=2)
        assert 1 < peak <= 2
    asyncio.run(main())
""",
            "max_output_tokens": 3000,
        },

        # ── C3-CT: Typed contracts with enum validation (from ai-learning-coach) ──
        {
            "id": "C3-CT",
            "tier": 3,
            "name": "Typed request/response contract with enum validation",
            "specification": (
                "Create contract_model.py and contract_validator.py. "
                "contract_model.py defines: (1) Mode(str, Enum) with values QUIZ='quiz', "
                "TEACH='teach', SCENARIO='scenario'; (2) GroundingMode(str, Enum) with values "
                "VAULT='vault', COCKPIT='cockpit', WEB='web', NONE='none'; (3) frozen dataclass "
                "SourceRef(source_type: str, source_id: str, source_label: str, "
                "grounding_mode: GroundingMode) with a validate() method that raises ValueError "
                "if any field except grounding_mode is empty/whitespace-only, and raises "
                "ValueError if grounding_mode is GroundingMode.NONE; (4) frozen dataclass "
                "TurnRequest(session_id: str, mode: Mode, topic: str, transcript: str) with "
                "validate() that raises ValueError on empty session_id, topic, or transcript, "
                "and TypeError if mode is not a Mode enum. "
                "contract_validator.py defines validate_request(request: TurnRequest, "
                "sources: list[SourceRef]) -> dict[str, object]. It calls request.validate(), "
                "validates each source with source.validate(), and returns a dict with keys: "
                "'valid' (bool), 'mode' (str, the mode value), 'source_count' (int), "
                "'grounding_modes' (sorted list of unique grounding_mode values as strings). "
                "Use only stdlib dataclasses, enum, typing."
            ),
            "allowed_files": ("contract_model.py", "contract_validator.py"),
            "objectives": (
                "Define Mode and GroundingMode enums, immutable SourceRef with validation, "
                "and immutable TurnRequest with validation.",
                "Implement composite request+source validation returning a structured summary.",
            ),
            "hidden_tests": """import pytest
from contract_model import Mode, GroundingMode, SourceRef, TurnRequest
from contract_validator import validate_request

def test_valid_request():
    req = TurnRequest(session_id='s1', mode=Mode.QUIZ, topic='AI Audit', transcript='What is...')
    src = SourceRef(source_type='vault', source_id='n1', source_label='Note 1', grounding_mode=GroundingMode.VAULT)
    result = validate_request(req, [src])
    assert result == {'valid': True, 'mode': 'quiz', 'source_count': 1, 'grounding_modes': ['vault']}

def test_multiple_grounding_modes_sorted():
    req = TurnRequest(session_id='s1', mode=Mode.TEACH, topic='T', transcript='X')
    srcs = [
        SourceRef('web', 'w1', 'Web 1', GroundingMode.WEB),
        SourceRef('vault', 'v1', 'Vault 1', GroundingMode.VAULT),
        SourceRef('cockpit', 'c1', 'Cockpit 1', GroundingMode.COCKPIT),
    ]
    result = validate_request(req, srcs)
    assert result['valid'] is True
    assert result['grounding_modes'] == ['cockpit', 'vault', 'web']

def test_invalid_source_empty_field():
    req = TurnRequest(session_id='s1', mode=Mode.QUIZ, topic='T', transcript='X')
    bad_src = SourceRef(source_type='', source_id='n1', source_label='L', grounding_mode=GroundingMode.VAULT)
    with pytest.raises(ValueError):
        validate_request(req, [bad_src])

def test_invalid_source_none_grounding():
    req = TurnRequest(session_id='s1', mode=Mode.QUIZ, topic='T', transcript='X')
    bad_src = SourceRef(source_type='vault', source_id='n1', source_label='L', grounding_mode=GroundingMode.NONE)
    with pytest.raises(ValueError):
        validate_request(req, [bad_src])

def test_invalid_request_empty_session():
    with pytest.raises(ValueError):
        TurnRequest(session_id='', mode=Mode.QUIZ, topic='T', transcript='X').validate()

def test_invalid_request_empty_transcript():
    with pytest.raises(ValueError):
        TurnRequest(session_id='s1', mode=Mode.QUIZ, topic='T', transcript='').validate()

def test_invalid_mode_type():
    with pytest.raises(TypeError):
        TurnRequest(session_id='s1', mode='quiz', topic='T', transcript='X').validate()

def test_empty_sources():
    req = TurnRequest(session_id='s1', mode=Mode.QUIZ, topic='T', transcript='X')
    result = validate_request(req, [])
    assert result == {'valid': True, 'mode': 'quiz', 'source_count': 0, 'grounding_modes': []}
""",
            "max_output_tokens": 2800,
        },
    ]