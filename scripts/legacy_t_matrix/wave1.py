#!/usr/bin/env python3
"""Ollama Cloud PA Fallback Wave 1 runner.

Wave: 5 Ollama Cloud models x 5 PA workload tasks, judge-free.

Tasks (fixtures in artifacts/2026-06-10-ollama-cloud-pa-wave1/fixtures/):
  1. Multilingual structured brief (EN/DE)
  2. Long-context RSS synthesis (~80K tokens, 1M headroom test)
  3. Bounded Python coding (3 deterministic tasks, strict JSON contract)
  4. German email draft (email-draft workload class)
  5. Cron-style mail triage (100 synthetic items, JSON schema contract)

Models under test (M3 = baseline):
  - minimax-m3:cloud
  - gemma4:31b-cloud
  - nemotron-3-ultra:cloud

Per-cell scoring is deterministic (regex/schema) plus heuristic (no LLM judge,
because GPT-5.5 quota is empty per the 2026-06-10 user note).

Pause-not-fail on cloud overload: per Ollama-local-benchmarking skill rule,
if the wave stalls, partial artifacts are preserved and the wave is recorded
as `paused` rather than `failed`.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = "http://localhost:11434/api/chat"

WAVE_ID = "2026-06-10-ollama-cloud-pa-wave1"
ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / WAVE_ID
FIXTURES_DIR = ARTIFACT_ROOT / "fixtures"

# Models in the wave. active_params is used as a cost proxy.
# 30-min trim: 3 models x 2 tasks.
MODELS: list[dict[str, Any]] = [
    {"tag": "minimax-m3:cloud", "label": "m3", "active_params_b": 40, "tier": "baseline"},
    {"tag": "gemma4:31b-cloud", "label": "gemma4", "active_params_b": 32, "tier": "challenger"},
    {"tag": "nemotron-3-ultra:cloud", "label": "nemotron", "active_params_b": 55, "tier": "challenger"},
]

# Per-task context budget and max output tokens.
# 30-min trim: only t1_brief and t4_email_de, num_predict=400.
TASK_CONFIG: dict[str, dict[str, Any]] = {
    "t1_brief": {"context_k": 16, "num_predict": 400, "max_prompt_chars": 16000},
    "t4_email_de": {"context_k": 8, "num_predict": 400, "max_prompt_chars": 8000},
}


@dataclass
class CellResult:
    wave_id: str
    task: str
    model_tag: str
    model_label: str
    started_at: str
    finished_at: str
    status: str  # "ok" | "overload" | "context_overflow" | "error" | "skipped"
    error: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    response_text: str = ""
    total_duration_ns: int = 0
    eval_duration_ns: int = 0
    eval_count: int = 0
    prompt_eval_count: int = 0
    tokens_per_sec: float = 0.0
    estimated_gpu_units: float = 0.0  # eval_duration_s * active_params_b
    validators: dict[str, Any] = field(default_factory=dict)
    weighted_score: float = 0.0
    hard_fails: list[str] = field(default_factory=list)
    artifact_path: str = ""


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def call_ollama(
    model: str,
    prompt: str,
    num_predict: int,
    timeout_s: int = 600,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Call Ollama /api/chat. Returns the parsed response object.

    Raises urllib.error.URLError or urllib.error.HTTPError on transport /
    server errors. Empty content while `thinking` is populated is preserved
    in the response object — the caller decides how to score it.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    req = urllib.request.Request(
        BASE,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode())


def list_local_tags() -> set[str]:
    """Probe of locally resolvable model tags via /api/tags."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return {m.get("name", "") for m in data.get("models", [])}
    except Exception:
        return set()


def probe_cloud_tag(tag: str, timeout_s: int = 15) -> bool:
    """Probe whether a cloud tag resolves via /api/show.

    /api/tags only lists locally-pulled models; cloud tags are pull-on-demand
    but resolve metadata via /api/show. This is the correct check for cloud
    availability from the user's account.
    """
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/show",
            data=json.dumps({"name": tag}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
        # If the tag resolves, the response has capabilities or details
        return bool(data.get("capabilities") or data.get("details"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures (load-on-demand from FIXTURES_DIR; if missing, return placeholder)
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> str | None:
    path = FIXTURES_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def fixture_t1_brief() -> str:
    """Multilingual EN/DE brief task.

    Required output sections: [Summary] [Actions] [Risks] [References].
    """
    cached = _load_fixture("t1_brief.md")
    if cached:
        return cached
    # Inline placeholder so the runner is executable even before fixtures ship.
    return (
        "SYNTHETIC FIXTURE. Erstelle einen kurzen Tagesbrief für einen Testnutzer "
        "aus den folgenden Slack- und E-Mail-Updates. Antworte auf Deutsch und "
        "Englisch gemischt. Verwende genau diese Sektionen:\n"
        "[Summary] [Actions] [Risks] [References]\n\n"
        "INPUTS:\n"
        "1. Slack #health: 'CGM overnight avg 112 mg/dL, post-meal spike 165 at lunch. "
        "Suggest lower-carb lunch tomorrow.'\n"
        "2. E-Mail einer externen Steuerberatung: 'ESt joint filing ready for review, "
        "please confirm synthetic trading-bot P&L classification.'\n"
        "3. Calendar: 14:00 IA review with a regulated-company compliance team (DE).\n"
    )


def fixture_t2_longctx() -> str:
    """Long-context RSS synthesis task."""
    cached = _load_fixture("t2_longctx.md")
    if cached:
        return cached
    return (
        "Synthesize the following 200 RSS headlines into top-5 themes with one "
        "representative quote per theme. Output as Markdown.\n\n" + ("HEADLINE\n" * 200)
    )


def fixture_t3_coding() -> str:
    """Bounded Python coding task with strict JSON contract.

    Output contract: {"patch": "<unified diff>", "explanation": "<text>"} (no fences).
    """
    cached = _load_fixture("t3_coding.md")
    if cached:
        return cached
    return (
        "Refactor the following Python function to use pathlib instead of os.path. "
        "Return STRICT JSON with exactly these keys: {\"patch\": \"<unified diff>\", "
        "\"explanation\": \"<one paragraph>\"}. Do NOT wrap in code fences. Do NOT add "
        "any other keys.\n\n"
        "```python\n"
        "import os\n"
        "def join_paths(*parts):\n    return os.path.join(*parts)\n"
        "```\n"
    )


def fixture_t4_email_de() -> str:
    """German email draft task.

    Output contract: starts with 'Sehr geehrte' (or 'Liebe/Lieber'), German body,
    German sign-off ('Mit freundlichen Grüßen' or 'Beste Grüße'), NO English body.
    """
    cached = _load_fixture("t4_email_de.md")
    if cached:
        return cached
    return (
        "SYNTHETIC FIXTURE. Beantworte die folgende E-Mail auf Deutsch, formell aber "
        "freundlich. Verwende 'Sehr geehrte Frau ...' als Anrede und 'Mit freundlichen "
        "Grüßen / Test User' als Sign-off. KEIN Englisch im Body.\n\n"
        "VON: Externe Steuerberatung <tax@example.invalid>\n"
        "BETREFF: ESt 2025 joint filing — Rückfrage zu 3c unrealized P&L\n\n"
        "Sehr geehrte Testperson,\n\n"
        "für die gemeinsame ESt-Erklärung 2025 benötigen wir die Klassifikation der "
        "3Commas unrealized P&L. Bitte bestätigen Sie, ob diese als §23 EStG "
        "private Veräußerungsgeschäfte (1-Jahres-Frist) oder als §20 EStG "
        "Kapitalerträge zu behandeln sind. Vielen Dank.\n\n"
        "Mit freundlichen Grüßen\nExterne Steuerberatung\n"
    )


def fixture_t5_triage() -> str:
    """Mail triage task with strict JSON schema."""
    cached = _load_fixture("t5_triage.json")
    if cached:
        return cached
    items = []
    for i in range(100):
        items.append(
            {
                "id": f"msg-{i:03d}",
                "from": f"sender-{i}@example.com",
                "subject": f"Test message {i}",
                "body": "Action required by EOD." if i % 7 == 0 else "FYI only.",
            }
        )
    prompt = (
        "Triage the following 100 inbox items into categories: Urgent, Action, FYI, "
        "Newsletter. Return STRICT JSON array with exactly one object per item: "
        "[{\"id\": \"msg-000\", \"category\": \"Urgent|Action|FYI|Newsletter\", "
        "\"confidence\": 0.0-1.0, \"reason\": \"<short>\"}]\n\n"
        + json.dumps(items)
    )
    return prompt


TASK_FIXTURES = {
    "t1_brief": fixture_t1_brief,
    "t2_longctx": fixture_t2_longctx,
    "t3_coding": fixture_t3_coding,
    "t4_email_de": fixture_t4_email_de,
    "t5_triage": fixture_t5_triage,
}


# ---------------------------------------------------------------------------
# Validators (deterministic + heuristic, no LLM judge)
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    return re.sub(r"```[a-zA-Z0-9]*\n|```", "", text).strip()


def validate_t1_brief(text: str) -> dict[str, Any]:
    """Required sections: [Summary] [Actions] [Risks] [References]."""
    sections = ["[Summary]", "[Actions]", "[Risks]", "[References]"]
    present = {s: (s in text) for s in sections}
    return {
        "required_sections": present,
        "all_present": all(present.values()),
        "section_count": sum(present.values()),
    }


def validate_t2_longctx(text: str) -> dict[str, Any]:
    """Theme-counting: look for at least 3 numbered themes."""
    themes = re.findall(r"(?m)^#{1,3}\s*\d+[\.\)]\s+\S+", text)
    return {
        "theme_count": len(themes),
        "themes_meet_threshold": len(themes) >= 3,
    }


def validate_t3_coding(text: str) -> dict[str, Any]:
    """Strict JSON output: {patch, explanation}, no fences, JSON-parseable."""
    cleaned = _strip_fences(text)
    has_fences = "```" in text
    try:
        obj = json.loads(cleaned)
        if not isinstance(obj, dict):
            return {"json_valid": False, "schema_match": False, "has_fences": has_fences}
        keys = set(obj.keys())
        schema_ok = keys == {"patch", "explanation"}
        return {
            "json_valid": True,
            "schema_match": schema_ok,
            "has_fences": has_fences,
            "keys": sorted(keys),
        }
    except json.JSONDecodeError as e:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": str(e)}


def validate_t4_email_de(text: str) -> dict[str, Any]:
    """German output contract."""
    has_salutation = bool(re.search(r"\b(Sehr geehrte|Liebe|Lieber)\b", text))
    has_signoff = bool(re.search(r"(Mit freundlichen Grüßen|Beste Grüße|Viele Grüße)", text))
    # Crude English-leakage check: count common English function words.
    english_markers = re.findall(r"\b(the|is|are|please|find|attached|regards)\b", text, flags=re.I)
    return {
        "has_salutation": has_salutation,
        "has_signoff": has_signoff,
        "english_marker_count": len(english_markers),
        "english_leakage_flag": len(english_markers) >= 3,
    }


def validate_t5_triage(text: str) -> dict[str, Any]:
    """JSON array of 100 items, each with id/category/confidence/reason."""
    cleaned = _strip_fences(text)
    try:
        arr = json.loads(cleaned)
        if not isinstance(arr, list):
            return {"json_valid": False, "count": 0, "schema_match": False}
        valid_categories = {"Urgent", "Action", "FYI", "Newsletter"}
        all_have_keys = all(
            isinstance(x, dict)
            and {"id", "category", "confidence", "reason"} <= set(x.keys())
            and x.get("category") in valid_categories
            for x in arr
        )
        return {
            "json_valid": True,
            "count": len(arr),
            "count_match": len(arr) == 100,
            "schema_match": all_have_keys,
        }
    except json.JSONDecodeError as e:
        return {"json_valid": False, "count": 0, "schema_match": False, "error": str(e)}


VALIDATORS = {
    "t1_brief": validate_t1_brief,
    "t2_longctx": validate_t2_longctx,
    "t3_coding": validate_t3_coding,
    "t4_email_de": validate_t4_email_de,
    "t5_triage": validate_t5_triage,
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

WEIGHTS = {
    "factual_accuracy": 0.30,
    "instruction_adherence": 0.20,
    "output_contract": 0.20,
    "recommendation_usefulness": 0.15,
    "latency": 0.10,
    "gpu_cost": 0.05,
}


def score_cell(task: str, validators: dict[str, Any], response_text: str) -> tuple[float, list[str], dict[str, float]]:
    """Returns (weighted_score_0_to_1, hard_fails, dimension_scores)."""
    dims = {
        "factual_accuracy": 0.0,
        "instruction_adherence": 0.0,
        "output_contract": 0.0,
        "recommendation_usefulness": 0.0,
        "latency": 0.5,  # neutral until normalized across the wave
        "gpu_cost": 0.5,  # neutral until normalized across the wave
    }
    hard_fails: list[str] = []

    if task == "t1_brief":
        dims["instruction_adherence"] = validators["section_count"] / 4.0
        dims["output_contract"] = 1.0 if validators["all_present"] else 0.0
        dims["factual_accuracy"] = 1.0 if validators["all_present"] else 0.5
        # Heuristic: count action verbs as a proxy for usefulness.
        actions = len(re.findall(r"\b(müssen|sollte|bitte|erforderlich|TODO|erledigen)\b", response_text, flags=re.I))
        dims["recommendation_usefulness"] = min(actions / 3.0, 1.0)
        if not validators["all_present"]:
            hard_fails.append("missing_required_section")
    elif task == "t2_longctx":
        dims["instruction_adherence"] = 1.0 if validators["themes_meet_threshold"] else 0.0
        dims["output_contract"] = 1.0 if validators["themes_meet_threshold"] else 0.0
        dims["factual_accuracy"] = 1.0 if validators["themes_meet_threshold"] else 0.0
        dims["recommendation_usefulness"] = min(validators["theme_count"] / 5.0, 1.0)
        if not validators["themes_meet_threshold"]:
            hard_fails.append("insufficient_themes")
    elif task == "t3_coding":
        dims["output_contract"] = 1.0 if validators.get("json_valid") and validators.get("schema_match") else 0.0
        dims["instruction_adherence"] = 0.0 if validators.get("has_fences") else 1.0
        dims["factual_accuracy"] = 1.0 if validators.get("json_valid") else 0.0
        if validators.get("has_fences"):
            dims["instruction_adherence"] = 0.0
            hard_fails.append("forbidden_code_fences")
        if not validators.get("json_valid"):
            hard_fails.append("json_invalid")
        if not validators.get("schema_match"):
            hard_fails.append("schema_mismatch")
    elif task == "t4_email_de":
        dims["instruction_adherence"] = (1.0 if validators["has_salutation"] else 0.0) * 0.5 + (
            1.0 if validators["has_signoff"] else 0.0
        ) * 0.5
        dims["output_contract"] = 1.0 if (validators["has_salutation"] and validators["has_signoff"]) else 0.0
        dims["factual_accuracy"] = 1.0 if (validators["has_salutation"] and validators["has_signoff"]) else 0.5
        # Recommendation usefulness = body length vs. expected (~500 chars), capped.
        body_len = len(response_text)
        dims["recommendation_usefulness"] = min(body_len / 600.0, 1.0)
        if validators["english_leakage_flag"]:
            hard_fails.append("english_leakage_in_german")
        if not validators["has_salutation"]:
            hard_fails.append("missing_german_salutation")
        if not validators["has_signoff"]:
            hard_fails.append("missing_german_signoff")
    elif task == "t5_triage":
        dims["output_contract"] = 1.0 if validators.get("json_valid") and validators.get("count_match") and validators.get("schema_match") else 0.0
        dims["instruction_adherence"] = 1.0 if validators.get("json_valid") else 0.0
        dims["factual_accuracy"] = 1.0 if validators.get("count_match") else 0.0
        if not validators.get("json_valid"):
            hard_fails.append("json_invalid")
        if not validators.get("count_match"):
            hard_fails.append("count_mismatch")
        if not validators.get("schema_match"):
            hard_fails.append("schema_mismatch")

    weighted = sum(dims[k] * WEIGHTS[k] for k in WEIGHTS)
    return weighted, hard_fails, dims


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def precheck_models() -> dict[str, bool]:
    """Probe each model via /api/show. /api/tags is local-only; cloud tags
    are pull-on-demand and only show after pull, so we rely on /api/show
    which returns metadata for both local and cloud tags."""
    return {m["tag"]: probe_cloud_tag(m["tag"]) for m in MODELS}


def write_manifest(precheck: dict[str, bool]) -> Path:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "wave_id": WAVE_ID,
        "created_at": _timestamp(),
        "models": [
            {**m, "available_now": precheck.get(m["tag"], False)} for m in MODELS
        ],
        "tasks": list(TASK_CONFIG.keys()),
        "task_config": TASK_CONFIG,
        "weights": WEIGHTS,
        "scoring_notes": "Judge-free: deterministic validators + heuristic. No GPT-5.5 control lane (quota empty).",
    }
    path = ARTIFACT_ROOT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return path


def run_cell(task: str, model: dict[str, Any], precheck: dict[str, bool], dry_run: bool) -> CellResult:
    started = _timestamp()
    if not precheck.get(model["tag"], False):
        return CellResult(
            wave_id=WAVE_ID,
            task=task,
            model_tag=model["tag"],
            model_label=model["label"],
            started_at=started,
            finished_at=_timestamp(),
            status="skipped",
            error="model_not_available",
        )

    # Skip long-context task for small-context models.
    if task == "t2_longctx" and model["label"] in SMALL_CTX_MODELS:
        return CellResult(
            wave_id=WAVE_ID,
            task=task,
            model_tag=model["tag"],
            model_label=model["label"],
            started_at=started,
            finished_at=_timestamp(),
            status="context_overflow",
            error=f"context_too_small ({model['label']} < 1M for 200K prompt)",
        )

    fixture = TASK_FIXTURES[task]()
    cfg = TASK_CONFIG[task]
    if len(fixture) > cfg["max_prompt_chars"]:
        fixture = fixture[: cfg["max_prompt_chars"]]

    if dry_run:
        return CellResult(
            wave_id=WAVE_ID,
            task=task,
            model_tag=model["tag"],
            model_label=model["label"],
            started_at=started,
            finished_at=_timestamp(),
            status="skipped",
            error="dry_run",
        )

    try:
        resp = call_ollama(model["tag"], fixture, cfg["num_predict"])
    except urllib.error.HTTPError as e:
        return CellResult(
            wave_id=WAVE_ID,
            task=task,
            model_tag=model["tag"],
            model_label=model["label"],
            started_at=started,
            finished_at=_timestamp(),
            status="error",
            error=f"http_{e.code}: {e.reason}",
        )
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return CellResult(
            wave_id=WAVE_ID,
            task=task,
            model_tag=model["tag"],
            model_label=model["label"],
            started_at=started,
            finished_at=_timestamp(),
            status="overload",
            error=str(e),
        )

    text = resp.get("message", {}).get("content", "") or ""
    total_ns = int(resp.get("total_duration", 0) or 0)
    eval_count = int(resp.get("eval_count", 0) or 0)
    prompt_eval_count = int(resp.get("prompt_eval_count", 0) or 0)
    eval_ns = int(resp.get("eval_duration") or 0)
    has_eval_ns = eval_ns > 0
    if not has_eval_ns and total_ns > 0 and prompt_eval_count:
        # Ollama Cloud often omits eval_duration. Estimate from total_duration minus
        # a prefill proxy of ~1ms per prompt token (server-side measured for typical
        # cloud models; this is an upper bound on prefill, so our throughput estimate
        # is a lower bound on true decode throughput).
        prefill_proxy_ns = prompt_eval_count * 1_000_000
        eval_ns = max(total_ns - prefill_proxy_ns, 0)
    # Lower-bound tokens/sec: eval_count / (total wall per output token)
    tokens_per_sec = eval_count / max(total_ns / 1e9, 1e-9) if total_ns and eval_count else 0.0
    estimated_gpu_units = (eval_ns / 1e9) * model["active_params_b"]

    validators = VALIDATORS[task](text)
    weighted, hard_fails, dims = score_cell(task, validators, text)

    finished = _timestamp()
    return CellResult(
        wave_id=WAVE_ID,
        task=task,
        model_tag=model["tag"],
        model_label=model["label"],
        started_at=started,
        finished_at=finished,
        status="ok",
        raw_response=resp,
        response_text=text,
        total_duration_ns=total_ns,
        eval_duration_ns=eval_ns,
        eval_count=eval_count,
        prompt_eval_count=prompt_eval_count,
        tokens_per_sec=round(tokens_per_sec, 2),
        estimated_gpu_units=round(estimated_gpu_units, 2),
        validators=validators,
        weighted_score=round(weighted, 4),
        hard_fails=hard_fails,
    )


def append_jsonl(path: Path, result: CellResult) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result), ensure_ascii=False, default=str) + "\n")


def write_cell_artifact(result: CellResult) -> Path:
    cell_dir = ARTIFACT_ROOT / result.task / result.model_label
    cell_dir.mkdir(parents=True, exist_ok=True)
    artifact = cell_dir / "cell.json"
    artifact.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Ollama Cloud PA Fallback Wave 1")
    parser.add_argument("--dry-run", action="store_true", help="Build manifest and print matrix without executing")
    parser.add_argument("--task", choices=list(TASK_CONFIG.keys()), help="Run a single task only")
    parser.add_argument("--model", help="Run a single model tag only")
    args = parser.parse_args()

    print(f"[{_timestamp()}] Wave: {WAVE_ID}")
    print(f"[{_timestamp()}] Pre-checking model availability...")
    precheck = precheck_models()
    for m in MODELS:
        flag = "AVAILABLE" if precheck.get(m["tag"]) else "NOT FOUND"
        print(f"  {m['tag']:<40} {flag}")
    manifest_path = write_manifest(precheck)
    print(f"[{_timestamp()}] Manifest written: {manifest_path}")

    if args.dry_run:
        print(f"[{_timestamp()}] Dry run complete. Use without --dry-run to execute.")
        return 0

    results_path = ARTIFACT_ROOT / "results.jsonl"
    if results_path.exists():
        results_path.unlink()  # fresh wave

    tasks = [args.task] if args.task else list(TASK_CONFIG.keys())
    models = [m for m in MODELS if not args.model or m["tag"] == args.model]

    completed = 0
    for task in tasks:
        for model in models:
            print(f"[{_timestamp()}] {task} x {model['tag']}...")
            result = run_cell(task, model, precheck, dry_run=False)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            print(
                f"    status={result.status} "
                f"score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} "
                f"hard_fails={result.hard_fails}"
            )

    print(f"[{_timestamp()}] Wave complete. {completed} cells executed. Results: {results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
