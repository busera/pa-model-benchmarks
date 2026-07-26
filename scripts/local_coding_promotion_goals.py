#!/usr/bin/env python3
"""Frozen S/R goal specifications for the local coding promotion benchmark."""
from __future__ import annotations

from typing import Any


def promotion_goal_specs() -> list[dict[str, Any]]:
    """Return independent state/idempotency and repository/standards goal specs."""
    return [
        {
            "id": "C0-S",
            "tier": 0,
            "name": "Deterministic idempotency key",
            "specification": "Create idempotency.py with idempotency_key(namespace: str, payload: str) -> str. Trim and lowercase namespace; require one or more ASCII letters, digits, dots, underscores, or hyphens; require payload to be a string; return '<namespace>:<digest>' where digest is the first 16 lowercase hexadecimal characters of SHA-256 over the exact UTF-8 payload. Reject booleans, non-strings, empty/invalid namespace, and never use process-random hashing.",
            "allowed_files": ("idempotency.py",),
            "objectives": ("Implement the typed deterministic idempotency-key helper and validation.",),
            "hidden_tests": """import pytest\nfrom idempotency import idempotency_key\n\ndef test_key_is_stable_and_exact():\n assert idempotency_key(' Jobs.API ', 'alpha') == 'jobs.api:8ed3f6ad685b959e'\n assert idempotency_key('jobs-api', '') == 'jobs-api:e3b0c44298fc1c14'\n@pytest.mark.parametrize('namespace,payload',[('', 'x'),('bad space','x'),(True,'x'),('ok',True),('ok',None)])\ndef test_rejects(namespace,payload):\n with pytest.raises((TypeError,ValueError)): idempotency_key(namespace,payload)\n""",
            "max_output_tokens": 900,
        },
        {
            "id": "C0-R",
            "tier": 0,
            "name": "Strict percentage normalizer",
            "specification": "Create percent.py with normalize_percent(value: int | float | str) -> float. Reject booleans. Accept finite numeric values or strings containing a numeric value with optional surrounding whitespace and one optional trailing percent sign. Values without a percent sign are already percentages. Return a float rounded to two decimal places. Reject empty, malformed, non-finite, negative, or above-100 values with ValueError; unsupported types raise TypeError.",
            "allowed_files": ("percent.py",),
            "objectives": ("Implement strict percentage parsing, bounds, and rounding.",),
            "hidden_tests": """import pytest\nfrom percent import normalize_percent\n\ndef test_values():\n assert normalize_percent(' 12.345% ') == 12.35\n assert normalize_percent(0) == 0.0\n assert normalize_percent('100') == 100.0\n@pytest.mark.parametrize('value',[True,'','nan','inf','-1','100.1','1%%',None])\ndef test_rejects(value):\n with pytest.raises((TypeError,ValueError)): normalize_percent(value)\n""",
            "max_output_tokens": 900,
        },
        {
            "id": "C1-S",
            "tier": 1,
            "name": "Checkpoint merge",
            "specification": "Create checkpoint.py with merge_completed(existing: list[str], observed: list[str]) -> list[str]. Return unique trimmed non-empty IDs in first-seen order, processing existing before observed. Reject booleans, non-lists, non-string elements, or elements that become empty with TypeError or ValueError. Do not mutate either input and do not use unordered set iteration for output order.",
            "allowed_files": ("checkpoint.py",),
            "objectives": ("Implement validated stable checkpoint merging without input mutation.",),
            "hidden_tests": """import copy, pytest\nfrom checkpoint import merge_completed\n\ndef test_merge_stable_and_no_mutation():\n a=[' a ','b','a']; b=['b',' c ']\n before=(copy.deepcopy(a),copy.deepcopy(b))\n assert merge_completed(a,b)==['a','b','c']\n assert (a,b)==before\n@pytest.mark.parametrize('a,b',[('a',[]),([],None),([True],[]),([' '],[])])\ndef test_rejects(a,b):\n with pytest.raises((TypeError,ValueError)): merge_completed(a,b)\n""",
            "max_output_tokens": 1100,
        },
        {
            "id": "C1-R",
            "tier": 1,
            "name": "Confined relative path",
            "specification": "Create paths.py with confined_path(root: Path, relative: str) -> Path. root must be a Path and relative a non-empty string naming a relative path. Resolve root and candidate without requiring the candidate to exist. Return the resolved candidate only when it is root itself or inside root. Reject absolute paths, traversal escapes, booleans, NUL bytes, and wrong types with TypeError or ValueError. Do not create files or directories.",
            "allowed_files": ("paths.py",),
            "objectives": ("Implement resolved-root path confinement with strict type and escape checks.",),
            "hidden_tests": """from pathlib import Path\nimport pytest\nfrom paths import confined_path\n\ndef test_inside(tmp_path):\n assert confined_path(tmp_path,'a/../b.txt') == (tmp_path/'b.txt').resolve()\n assert not (tmp_path/'b.txt').exists()\n@pytest.mark.parametrize('value',['../escape','/tmp/x','',True,'a\\x00b'])\ndef test_rejects(tmp_path,value):\n with pytest.raises((TypeError,ValueError)): confined_path(tmp_path,value)\ndef test_root_type():\n with pytest.raises(TypeError): confined_path('/tmp','x')\n""",
            "max_output_tokens": 1200,
        },
        {
            "id": "C2-S",
            "tier": 2,
            "name": "Idempotent event reducer",
            "specification": "Create reducer.py with reduce_events(events: list[dict[str, object]], completed: set[str], transform: callable) -> tuple[list[object], set[str], dict[str, str]]. Each event must have exactly id and payload; id is a trimmed non-empty string. Process in input order, skip IDs already completed or successfully seen earlier, call transform(payload), append successful values, and add successful IDs to a copied completed set. Capture Exception failures as '<ExceptionType>: <message>' by ID without completing them. Reject malformed inputs before calling transform, never mutate events or completed, and do not catch BaseException.",
            "allowed_files": ("reducer.py",),
            "objectives": ("Implement ordered idempotent reduction, copied state, validation, and typed failure capture.",),
            "hidden_tests": """import copy, pytest\nfrom reducer import reduce_events\n\ndef test_reduce_skip_fail_and_copy():\n events=[{'id':'a','payload':1},{'id':'b','payload':2},{'id':'a','payload':9}]\n done={'old'}; before=(copy.deepcopy(events),done.copy()); calls=[]\n def transform(x):\n  calls.append(x)\n  if x==2: raise KeyError('bad')\n  return x*10\n values,completed,failures=reduce_events(events,done,transform)\n assert values==[10] and completed=={'old','a'} and list(failures)==['b'] and 'KeyError' in failures['b']\n assert calls==[1,2] and (events,done)==before\ndef test_malformed_is_prevalidated():\n calls=[]\n with pytest.raises(ValueError): reduce_events([{'id':'a','payload':1},{'id':''}],set(),lambda x:calls.append(x))\n assert calls==[]\n""",
            "max_output_tokens": 1600,
        },
        {
            "id": "C2-R",
            "tier": 2,
            "name": "Layered typed configuration",
            "specification": "Create layered_config.py with resolve_config(defaults: dict[str, object], environment: dict[str, str], overrides: dict[str, object], schema: dict[str, type]) -> dict[str, object]. Require every schema key in defaults and reject unknown keys in any input. Precedence is overrides, then environment, then defaults. Convert environment strings only for exact schema types str, int, float, bool; bool accepts case-insensitive true/false/1/0 only and numeric conversions reject booleans and non-finite floats. Direct default/override values must already have the exact declared type, except int is not accepted as float. Return a new dict and never mutate inputs.",
            "allowed_files": ("layered_config.py",),
            "objectives": ("Implement strict schema validation, environment conversion, precedence, and immutable inputs.",),
            "hidden_tests": """import copy, pytest\nfrom layered_config import resolve_config\n\ndef test_precedence_and_types():\n d={'workers':1,'enabled':False,'name':'x','ratio':1.5}; e={'workers':'2','enabled':'TRUE'}; o={'name':'y'}; s={'workers':int,'enabled':bool,'name':str,'ratio':float}\n before=copy.deepcopy((d,e,o,s)); got=resolve_config(d,e,o,s)\n assert got=={'workers':2,'enabled':True,'name':'y','ratio':1.5} and (d,e,o,s)==before\n@pytest.mark.parametrize('e,o',[({'enabled':'yes'},{}),({'ratio':'nan'},{}),({}, {'workers':True}),({'extra':'1'}, {})])\ndef test_rejects(e,o):\n with pytest.raises((TypeError,ValueError,KeyError)): resolve_config({'workers':1,'enabled':False,'ratio':1.0},e,o,{'workers':int,'enabled':bool,'ratio':float})\n""",
            "max_output_tokens": 1800,
        },
        {
            "id": "C3-S",
            "tier": 3,
            "name": "Three-file durable job runner",
            "specification": "Create job_model.py, job_store.py, and job_runner.py. job_model.py defines frozen Job(id: str, payload: object) validating a trimmed non-empty string ID. job_store.py defines load_checkpoint(path: Path) -> dict with exact keys completed(list[str]) and failures(dict[str,str]); missing returns empty state; invalid JSON/shape raises ValueError. save_checkpoint(path,state) validates, writes UTF-8 JSON through a same-directory temporary file, flushes and os.fsync, then os.replace, cleaning temp files on failure. job_runner.py defines run_jobs(jobs, handler, path) -> list[object]: preserve order, skip completed IDs, reject duplicate IDs in the supplied batch before handler calls, capture Exception failures, persist after every attempted job, clear a prior failure after success, and never complete failures.",
            "allowed_files": ("job_model.py", "job_store.py", "job_runner.py"),
            "objectives": ("Define the immutable validated Job model.", "Implement validated atomic checkpoint loading and saving.", "Implement resumable ordered job execution with durable per-job state."),
            "hidden_tests": """from pathlib import Path\nimport pytest\nfrom job_model import Job\nfrom job_store import load_checkpoint\nfrom job_runner import run_jobs\n\ndef test_resume_failure_and_atomic(tmp_path):\n p=tmp_path/'state.json'; calls=[]\n def handler(x):\n  calls.append(x)\n  if x==2: raise RuntimeError('boom')\n  return x*10\n assert run_jobs([Job('a',1),Job('b',2),Job('c',3)],handler,p)==[10,30]\n state=load_checkpoint(p); assert state['completed']==['a','c'] and 'b' in state['failures']; assert not list(tmp_path.glob('*.tmp'))\n calls.clear(); assert run_jobs([Job('a',1),Job('b',4),Job('c',3)],handler,p)==[40]\n assert calls==[4] and load_checkpoint(p)=={'completed':['a','c','b'],'failures':{}}\ndef test_duplicate_preflight(tmp_path):\n calls=[]\n with pytest.raises(ValueError): run_jobs([Job('a',1),Job('a',2)],lambda x:calls.append(x),tmp_path/'s.json')\n assert calls==[]\n""",
            "max_output_tokens": 2800,
        },
        {
            "id": "C3-R",
            "tier": 3,
            "name": "Configuration-driven route service",
            "specification": "Create route_model.py, route_config.py, and route_service.py. route_model.py defines frozen Route(name: str, timeout_s: float, enabled: bool) with non-empty trimmed name and finite timeout in (0,300]. route_config.py defines parse_routes(data: dict[str, object]) -> tuple[Route,...], requiring top-level exact key routes, each row exact keys name/timeout_s/enabled, rejecting duplicate names case-insensitively and preserving order. route_service.py defines choose_route(routes, requested: str | None) -> Route: only enabled routes qualify; a requested name matches case-insensitively or raises LookupError; without a request choose the first enabled route; raise LookupError when none. Do not mutate inputs or use dependencies.",
            "allowed_files": ("route_model.py", "route_config.py", "route_service.py"),
            "objectives": ("Define strict immutable Route validation.", "Parse ordered route configuration with exact shape and duplicate protection.", "Implement deterministic enabled-route selection and explicit lookup failures."),
            "hidden_tests": """import copy, pytest\nfrom route_config import parse_routes\nfrom route_service import choose_route\n\ndef test_parse_and_choose():\n data={'routes':[{'name':'Local','timeout_s':10,'enabled':False},{'name':'Frontier','timeout_s':20.5,'enabled':True}]}; before=copy.deepcopy(data)\n routes=parse_routes(data); assert choose_route(routes,None).name=='Frontier'; assert choose_route(routes,'frontier').timeout_s==20.5; assert data==before\ndef test_duplicate_and_exact_shape():\n with pytest.raises(ValueError): parse_routes({'routes':[{'name':'A','timeout_s':1,'enabled':True},{'name':'a','timeout_s':2,'enabled':True}]})\n with pytest.raises(ValueError): parse_routes({'routes':[],'extra':1})\ndef test_lookup():\n routes=parse_routes({'routes':[{'name':'A','timeout_s':1,'enabled':False}]})\n with pytest.raises(LookupError): choose_route(routes,None)\n""",
            "max_output_tokens": 2600,
        },
        {
            "id": "C4-S",
            "tier": 4,
            "name": "Rollback-safe file batch",
            "specification": "Create batch_model.py, batch_stage.py, and batch_commit.py. batch_model.py defines frozen Change(relative_path: str, content: str), rejecting absolute/traversal paths, empty paths, NULs, and non-strings. batch_stage.py defines stage_changes(root: Path, changes: list[Change]) -> Path: reject duplicate resolved destinations, create a unique staging directory inside root, and write each content under matching relative paths without touching destinations. batch_commit.py defines commit_staged(root: Path, staging: Path, changes: list[Change]) -> None: staging must resolve inside root; before replacing each destination, copy any existing destination into a unique backup directory inside root; use os.replace from staged files to destinations. If any replacement fails, restore every already-replaced destination exactly, remove destinations that did not previously exist, re-raise, and leave no staging/backup directory. On success also remove staging/backup directories. No writes may escape root.",
            "allowed_files": ("batch_model.py", "batch_stage.py", "batch_commit.py"),
            "objectives": ("Define confined immutable file changes.", "Stage a validated batch without touching destinations.", "Commit with same-root replacements, exact rollback, and cleanup."),
            "hidden_tests": """from pathlib import Path\nimport os, pytest\nfrom batch_model import Change\nfrom batch_stage import stage_changes\nfrom batch_commit import commit_staged\n\ndef test_success(tmp_path):\n (tmp_path/'a.txt').write_text('old'); changes=[Change('a.txt','new'),Change('d/b.txt','bee')]\n staging=stage_changes(tmp_path,changes); assert (tmp_path/'a.txt').read_text()=='old'\n commit_staged(tmp_path,staging,changes)\n assert (tmp_path/'a.txt').read_text()=='new' and (tmp_path/'d/b.txt').read_text()=='bee'\n assert not [p for p in tmp_path.iterdir() if p.name.startswith(('.stage-','.backup-'))]\ndef test_rollback_on_second_replace(tmp_path,monkeypatch):\n import batch_commit\n (tmp_path/'a.txt').write_text('old-a'); changes=[Change('a.txt','new-a'),Change('b.txt','new-b')]; staging=stage_changes(tmp_path,changes)\n real=batch_commit.os.replace; calls=0\n def flaky(src,dst):\n  nonlocal calls; calls+=1\n  if calls==2: raise OSError('boom')\n  return real(src,dst)\n monkeypatch.setattr(batch_commit.os,'replace',flaky)
 with pytest.raises(OSError): commit_staged(tmp_path,staging,changes)\n assert (tmp_path/'a.txt').read_text()=='old-a' and not (tmp_path/'b.txt').exists()\n assert not [p for p in tmp_path.iterdir() if p.name.startswith(('.stage-','.backup-'))]\ndef test_escape_rejected(tmp_path):\n with pytest.raises(ValueError): Change('../x','bad')\n""",
            "max_output_tokens": 3600,
        },
        {
            "id": "C4-R",
            "tier": 4,
            "name": "Cross-layer command resolution",
            "specification": "Create command_model.py, command_config.py, command_app.py, and command_audit.py. command_model.py defines frozen Command(name: str, executable: Path, args: tuple[str,...], timeout_s: float), validating a simple ASCII command name, absolute executable, string args, and finite timeout in (0,120]. command_config.py defines load_commands(data: dict[str,object], allowed_executables: set[Path]) -> tuple[Command,...], requiring exact JSON-like shapes, resolved executable membership, and case-insensitive unique names. command_app.py defines build_invocation(commands, requested: str) -> tuple[list[str],float], matching name case-insensitively and returning list-form executable+args plus timeout, with LookupError when absent. command_audit.py defines audit_commands(commands)->dict with total, executable_counts keyed by resolved executable string, and duplicate_executables sorted. Never execute commands, inspect the filesystem, use shell strings, or mutate inputs.",
            "allowed_files": ("command_model.py", "command_config.py", "command_app.py", "command_audit.py"),
            "objectives": ("Define strict immutable command boundaries.", "Load exact command configuration against an executable allowlist.", "Build deterministic list-form invocations without execution.", "Summarize executable reuse deterministically."),
            "hidden_tests": """from pathlib import Path\nimport copy, pytest\nfrom command_config import load_commands\nfrom command_app import build_invocation\nfrom command_audit import audit_commands\n\ndef test_flow_and_no_mutation():\n allowed={Path('/usr/bin/python3')}; data={'commands':[{'name':'Check','executable':'/usr/bin/python3','args':['-V'],'timeout_s':5},{'name':'Lint','executable':'/usr/bin/python3','args':['-m','compileall'],'timeout_s':10}]}; before=copy.deepcopy(data)\n commands=load_commands(data,allowed); assert build_invocation(commands,'check')==(['/usr/bin/python3','-V'],5.0); assert data==before\n assert audit_commands(commands)=={'total':2,'executable_counts':{'/usr/bin/python3':2},'duplicate_executables':['/usr/bin/python3']}\ndef test_allowlist_and_shape():\n with pytest.raises(ValueError): load_commands({'commands':[{'name':'x','executable':'/bin/sh','args':[],'timeout_s':1}]},{Path('/usr/bin/python3')})\n with pytest.raises(ValueError): load_commands({'commands':[],'extra':1},set())\ndef test_missing():\n with pytest.raises(LookupError): build_invocation((), 'x')\n""",
            "max_output_tokens": 3400,
        },
        {
            "id": "C5-S",
            "tier": 5,
            "name": "Resumable bounded scheduler",
            "specification": "Create scheduler_config.py, scheduler_state.py, scheduler.py, and scheduler_report.py. scheduler_config.py defines frozen SchedulerConfig(max_workers:int, timeout_s:float) rejecting booleans, workers outside 1..6, and nonpositive/nonfinite timeout. scheduler_state.py atomically loads/saves exact state {'completed': list[str], 'failures': dict[str,str]} using same-directory temp, fsync, os.replace. scheduler.py defines run_tasks(tasks: list[dict[str,object]], worker, config, state_path) -> list[dict[str,object]]: prevalidate exact id/payload rows and unique trimmed IDs; skip completed; run remaining tasks concurrently with at most max_workers and one overall timeout; preserve input order among attempted tasks; success row exact {'id','ok':True,'value'}, failure exact {'id','ok':False,'error'}; timeout errors contain TimeoutError; update and atomically save state once after results are assembled, completing only successes and replacing prior failure for retried success; cancel pending futures and return promptly without waiting for timed-out workers. scheduler_report.py summarizes rows with total, succeeded, failed, failure_ids. No shell/network/dependencies.",
            "allowed_files": ("scheduler_config.py", "scheduler_state.py", "scheduler.py", "scheduler_report.py"),
            "objectives": ("Implement strict immutable scheduler configuration.", "Implement validated atomic scheduler state persistence.", "Implement bounded ordered concurrent execution, timeout cancellation, and resumability.", "Implement deterministic result reporting."),
            "hidden_tests": """import threading,time\nfrom scheduler_config import SchedulerConfig\nfrom scheduler import run_tasks\nfrom scheduler_report import summarize\n\ndef test_concurrency_order_resume(tmp_path):\n lock=threading.Lock(); active=0; peak=0\n def worker(x):\n  nonlocal active,peak\n  with lock: active+=1; peak=max(peak,active)\n  time.sleep(.04)\n  with lock: active-=1\n  if x==2: raise KeyError('bad')\n  return x*10\n p=tmp_path/'state.json'; tasks=[{'id':'a','payload':1},{'id':'b','payload':2},{'id':'c','payload':3}]\n rows=run_tasks(tasks,worker,SchedulerConfig(2,1),p)\n assert [r['id'] for r in rows]==['a','b','c'] and 1 < peak <= 2\n assert summarize(rows)=={'total':3,'succeeded':2,'failed':1,'failure_ids':['b']}\n retried=run_tasks(tasks,lambda x:x*100,SchedulerConfig(2,1),p); assert retried==[{'id':'b','ok':True,'value':200}]\ndef test_overall_timeout_prompt(tmp_path):\n start=time.monotonic(); rows=run_tasks([{'id':'a','payload':1},{'id':'b','payload':2}],lambda x:(time.sleep(.5),x)[1],SchedulerConfig(2,.05),tmp_path/'s.json'); elapsed=time.monotonic()-start\n assert elapsed < .25 and len(rows)==2 and all(not r['ok'] and 'TimeoutError' in r['error'] for r in rows)\n""",
            "max_output_tokens": 4200,
        },
        {
            "id": "C5-R",
            "tier": 5,
            "name": "Versioned additive migration contract",
            "specification": "Create schema_model.py, compatibility.py, migration_plan.py, and migration_cli.py. schema_model.py defines frozen Field(name:str, kind:str, required:bool=False) and Schema(version:int, fields:tuple[Field,...]), validating positive non-bool versions, identifier names, unique names, and kinds TEXT/INTEGER/DOUBLE/BOOLEAN. compatibility.py defines compare(old,new)->dict with exact keys added, removed, changed mapping to lists of field-name strings; versions must increase exactly by one; changed includes names whose kind or required value changed. migration_plan.py defines build_migration(db_path:Path, table:str, old:Schema, new:Schema)->dict with exact keys sql_statements, backup_path, from_version, to_version: allow table prefixes pa_ or bridge_; reject removed/changed fields and reject newly added required fields; sql_statements is a list of additive ALTER TABLE ADD COLUMN IF NOT EXISTS strings for added fields, backup_path is a timestamped string, and versions are integers; never execute SQL or access DB. migration_cli.py defines render_plan(plan)->str as deterministic JSON with sorted keys after validating those exact plan keys. No SQL interpolation beyond validated identifiers/types and no destructive verbs.",
            "allowed_files": ("schema_model.py", "compatibility.py", "migration_plan.py", "migration_cli.py"),
            "objectives": ("Define strict immutable versioned schema models.", "Compare adjacent schema versions deterministically.", "Build a validated additive-only migration plan with backup metadata.", "Render the exact plan deterministically without execution."),
            "hidden_tests": """import json,re\nfrom pathlib import Path\nimport pytest\nfrom schema_model import Field,Schema\nfrom compatibility import compare\nfrom migration_plan import build_migration\nfrom migration_cli import render_plan\n\ndef test_additive_plan(tmp_path):\n old=Schema(1,(Field('id','TEXT',True),)); new=Schema(2,(Field('id','TEXT',True),Field('score','DOUBLE')))
 assert compare(old,new)=={'added':['score'],'removed':[],'changed':[]}\n plan=build_migration(tmp_path/'x.duckdb','pa_scores',old,new); sql=' '.join(plan['sql_statements']).upper()\n assert plan['from_version']==1 and plan['to_version']==2 and plan['backup_path'].startswith(str(tmp_path/'x.duckdb')+'.bak-')\n assert 'ADD COLUMN IF NOT EXISTS SCORE DOUBLE' in sql and not re.search(r'\\b(DROP|DELETE|UPDATE|INSERT|TRUNCATE)\\b',sql)\n assert json.loads(render_plan(plan))==plan\ndef test_breaking_changes_rejected(tmp_path):\n old=Schema(1,(Field('id','TEXT'),Field('x','INTEGER')))
 for new in [Schema(2,(Field('id','TEXT'),)),Schema(2,(Field('id','INTEGER'),Field('x','INTEGER'))),Schema(2,(Field('id','TEXT'),Field('x','INTEGER'),Field('must','TEXT',True)))]:\n  with pytest.raises(ValueError): build_migration(tmp_path/'x','pa_x',old,new)\ndef test_versions_and_table(tmp_path):\n with pytest.raises(ValueError): compare(Schema(1,()),Schema(3,()))\n with pytest.raises(ValueError): build_migration(tmp_path/'x','records',Schema(1,()),Schema(2,()))\n""",
            "max_output_tokens": 4200,
        },
    ]
