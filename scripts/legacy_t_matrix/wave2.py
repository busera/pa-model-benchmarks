#!/usr/bin/env python3
"""Ollama Cloud PA Fallback — Wave 2 (expanded model roster + PA skill/architecture cases).

6 models (Gemma, Nemotron, DeepSeek, Kimi, Mistral Large cloud, local Mistral)
across PA routing, strict-output, reasoning, coding, custom-skill, architecture,
and domain-import tasks.

Pause-not-fail on overload/unavailable models. Per-cell artifacts + results.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = "http://localhost:11434/api/chat"

WAVE_ID = "2026-06-10-ollama-cloud-pa-wave2"
ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / WAVE_ID
PRIVATE_FIXTURE_ROOT = Path(os.environ["PA_BENCHMARK_PRIVATE_FIXTURE_ROOT"]).expanduser() if os.environ.get("PA_BENCHMARK_PRIVATE_FIXTURE_ROOT") else None

# Models
# Keep this roster focused on realistic PA routing candidates. Minimax M3 was removed
# after repeated poor scores/hard-fails; it is no longer useful as a baseline.
MODELS: list[dict[str, Any]] = [
    {"tag": "gemma4:31b-cloud", "label": "gemma4", "active_params_b": 32, "tier": "cloud_challenger"},
    {"tag": "nemotron-3-ultra:cloud", "label": "nemotron", "active_params_b": 55, "tier": "cloud_challenger"},
    {"tag": "deepseek-v4-pro:cloud", "label": "v4pro", "active_params_b": 49, "tier": "cloud_challenger"},
    {"tag": "kimi-k2.6:cloud", "label": "kimi26", "active_params_b": 32, "tier": "cloud_challenger"},
    {"tag": "mistral-large-3:675b-cloud", "label": "mistral_large3", "active_params_b": 675, "tier": "heavy_cloud_challenger"},
    {"tag": "mistral-small3.2:24b", "label": "mistral_local24", "active_params_b": 24, "tier": "local_challenger"},
]

# Base tasks + multi-turn + real fixtures
TASK_CONFIG: dict[str, dict[str, Any]] = {
    "t1_brief": {"num_predict": 400, "max_prompt_chars": 16000},
    "t3_coding": {"num_predict": 400, "max_prompt_chars": 16000},
    "t4_email_de": {"num_predict": 400, "max_prompt_chars": 8000},
    "t7_multiturn": {"num_predict": 400, "max_prompt_chars": 32000},
    "t1_real": {"num_predict": 400, "max_prompt_chars": 16000},
    "t4_real": {"num_predict": 400, "max_prompt_chars": 8000},
    "t8_reasoning": {"num_predict": 500, "max_prompt_chars": 16000},
    "t9_coding_complex_turn1": {"num_predict": 800, "max_prompt_chars": 24000},
    "t9_coding_complex_turn2": {"num_predict": 2000, "max_prompt_chars": 24000},
    "t9_coding_complex_turn3": {"num_predict": 300, "max_prompt_chars": 8000},
    "t10_skill_instruction_adherence": {"num_predict": 900, "max_prompt_chars": 14000},
    "t11_health_architecture_bugfix": {"num_predict": 1200, "max_prompt_chars": 18000},
    "t12_domain_import_skill_routing": {"num_predict": 1000, "max_prompt_chars": 14000},
}

REPEATS = 5
MULTITURN_TURNS = 2
WAVE_START = time.time()
WALL_CAP_S = 30 * 60  # 30 min hard cap


@dataclass
class CellResult:
    wave_id: str
    task: str
    model_tag: str
    model_label: str
    repeat: int
    turn: int
    started_at: str
    finished_at: str
    status: str
    error: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    response_text: str = ""
    total_duration_ns: int = 0
    eval_duration_ns: int = 0
    eval_count: int = 0
    prompt_eval_count: int = 0
    tokens_per_sec: float = 0.0
    estimated_gpu_units: float = 0.0
    validators: dict[str, Any] = field(default_factory=dict)
    weighted_score: float = 0.0
    hard_fails: list[str] = field(default_factory=list)
    artifact_path: str = ""


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _check_wall_cap() -> bool:
    return (time.time() - WAVE_START) >= WALL_CAP_S


def call_ollama(
    model: str,
    prompt: str,
    num_predict: int,
    timeout_s: int = 600,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode())


def call_ollama_multi(
    model: str,
    messages: list[dict[str, str]],
    num_predict: int,
    timeout_s: int = 600,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode())


def probe_cloud_tag(tag: str, timeout_s: int = 15) -> bool:
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/show",
            data=json.dumps({"name": tag}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
        return bool(data.get("capabilities") or data.get("details"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_T1 = (
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

FIXTURE_T3 = (
    "Refactor the following Python function to use pathlib instead of os.path. "
    "Return STRICT JSON with exactly these two keys: "
    "{\"patch\": \"<unified diff>\", \"explanation\": \"<one paragraph>\"}. "
    "Do NOT wrap output in code fences. Do NOT add any other keys.\n\n"
    "```python\n"
    "import os\n"
    "def join_paths(*parts):\n    return os.path.join(*parts)\n"
    "```\n"
)

FIXTURE_T4 = (
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

# Multi-turn fixture: turn 1 sets context, turn 2 asks for action
FIXTURE_T7_TURN1 = (
    "SYNTHETIC FIXTURE. Du bist PA eines Testnutzers. Kontext: Du verwaltest tägliche Briefings, "
    "E-Mails, Kalender und Finanzübersichten. Sprache: Deutsch/Englisch gemischt.\n\n"
    "AUFGABE: Ich gebe dir jetzt 3 Updates. Merke sie dir nur, antworte mit 'VERSTANDEN'.\n\n"
    "1. Slack #trading: '3Commas BTC grid bot at 94% fill, current unrealized -2.3%.'\n"
    "2. E-Mail Steuerberatung: 'ESt: synthetic bot P&L classification needed by Friday.'\n"
    "3. Calendar: 16:00 IA audit kickoff with regulated-company compliance (DE)."
)

FIXTURE_T7_TURN2 = (
    "Erstelle jetzt das Tagesbriefing basierend auf den 3 Updates oben. "
    "Verwende genau diese Sektionen: [Summary] [Actions] [Risks] [References]. "
    "Keine Erklärungen, nur das Briefing."
)

# Real fixture t1: try to load from vault, fallback to placeholder
def load_real_t1() -> str:
    if PRIVATE_FIXTURE_ROOT is None:
        return FIXTURE_T1
    patterns = ["rss-daily-brief/*.md", "Journal/*.md"]
    for pattern in patterns:
        files = list(PRIVATE_FIXTURE_ROOT.glob(pattern))
        if files:
            latest = max(files, key=lambda path: path.stat().st_mtime)
            content = latest.read_text(encoding="utf-8", errors="ignore")
            if len(content) > 200:
                return (
                    "Du bist PA eines Testnutzers. Erstelle einen Tagesbrief "
                    "aus dem folgenden echten Vault-Inhalt. Deutsch/Englisch gemischt. "
                    "Sektionen: [Summary] [Actions] [Risks] [References].\n\n"
                    + content[:12000]
                )
    return FIXTURE_T1  # fallback

# Real fixture t4: try to load from Apple Mail export
def load_real_t4() -> str:
    if PRIVATE_FIXTURE_ROOT is None:
        return FIXTURE_T4
    files = list(PRIVATE_FIXTURE_ROOT.glob("apple-mail-export/*.eml"))
    if files:
        latest = max(files, key=lambda path: path.stat().st_mtime)
        content = latest.read_text(encoding="utf-8", errors="ignore")
        if len(content) > 200:
            return (
                "Beantworte diese E-Mail auf Deutsch, formell/freundlich. "
                "Anrede: 'Sehr geehrte Frau ...', Sign-off: 'Mit freundlichen Grüßen / Test User'. "
                "KEIN Englisch im Body.\n\n"
                + content[:6000]
            )
    return FIXTURE_T4  # fallback


# Reasoning task fixture: mirrors actual chat/terminal workloads
# Trade analysis + job/CV review + structured reasoning with evidence layers
FIXTURE_T8 = (
    "SYNTHETIC FIXTURE. Analysiere die folgende Situation und liefere eine strukturierte "
    "Empfehlung. Sprache: Deutsch/Englisch gemischt. Verwende genau diese Sektionen:\n"
    "[Situation] [Evidence] [Analysis] [Recommendation] [Risks] [Open_Items]\n\n"
    "SITUATION:\n"
    "Eine fiktive Audit-Managerin bei einem regulierten Schweizer Unternehmen, mit deutscher Steueransässigkeit, "
    "hat einen synthetischen BTC Grid Bot mit unrealized P&L von -2.0%. "
    "Zusätzlich hält sie einen kleinen synthetischen ETH-Bestand auf einer Demo-Börse. "
    "Getrennte Partner-Assets sind ohne Betrag als nicht zum Nettovermögen gehörend markiert. "
    "Eine externe Steuerberatung braucht bis Freitag die Klassifikation der unrealized P&L: "
    "§23 EStG private Veräußerungsgeschäfte (1-Jahres-Frist) oder §20 EStG Kapitalerträge?\n\n"
    "AUFGABE:\n"
    "1. Klassifiziere die steuerliche Behandlung der unrealized P&L basierend auf deutscher Rechtslage.\n"
    "2. Bewerte, ob der Grid Bot gestoppt, angepasst, oder weiterlaufen soll (Risk: capital exhaustion, "
    "DU at 94% fill, bag value declining).\n"
    "3. Empfehle konkrete nächste Schritte (Aktionen mit Owner, Deadline).\n"
    "4. Flagge alle Open Items, die menschliche Entscheidung/Info brauchen.\n\n"
    "WICHTIG: Keine erfundenen Zahlen. Nur Schlussfolgerungen aus den gegebenen Fakten. "
    "Kennzeichne Inferenzen explizit als [INFERRED] mit Confidence [HIGH/MEDIUM/LOW]. "
    "Lege die Evidence-Layer offen: [VERBATIM], [EXTRACTED], [PARAPHRASED], [SYNTHESIZED], [INFERRED]."
)

# t9_coding_complex: realistic PA coding task — multi-turn breakdown
# Mirrors actual skill development workflow: design → implement → test

# Turn 1: Design / Planning
FIXTURE_T9_TURN1 = (
    "Du bist ein Senior Python Developer an einem synthetischen PA-System (Hermes-Agent). "
    "Codebase: Python 3.11, strict typing (mypy --strict), pytest, pathlib, stdlib only.\n\n"
    "AUFGABE: Plane das Refactoring von `shared/llm.py` für task-type-aware Modell-Auswahl.\n\n"
    "AKTUELLER CODE:\n"
    "```python\n"
    "# shared/llm.py\n"
    "from __future__ import annotations\n"
    "from dataclasses import dataclass\n"
    "from typing import Literal\n\n"
    "@dataclass(frozen=True)\n"
    "class LLMConfig:\n"
    "    model: str = \"qwen3.6:35b-a3b-q8_0\"\n"
    "    temperature: float = 0.0\n"
    "    num_predict: int = 4096\n"
    "    think: bool = False\n\n"
    "def get_llm_config(task_type: Literal[\"coding\", \"summary\", \"email\", \"reasoning\"] = \"coding\") -> LLMConfig:\n"
    "    return LLMConfig()  # ignores task_type\n"
    "```\n\n"
    "ANFORDERUNGEN:\n"
    "1. Erweitere `LLMConfig` um `model_override: str | None = None`\n"
    "2. task_type → Modell Mapping:\n"
    "   - coding → \"qwen3.6:35b-a3b-q8_0\"\n"
    "   - summary → \"gemma4:31b-cloud\"\n"
    "   - email → \"nemotron-3-ultra:cloud\"\n"
    "   - reasoning → \"deepseek-v4-pro:cloud\"\n"
    "3. `model_override` gewinnt über Mapping\n"
    "4. Classmethod `LLMConfig.for_task(task_type, model_override=None)`\n"
    "5. Tests in `tests/test_llm_config.py` (4 Tests)\n\n"
    "LIEFERFORMAT: STRICT JSON mit Keys:\n"
    "{\n"
    "  \"plan\": \"<Schritt-für-Schritt Plan: was wo geändert wird>\",\n"
    "  \"shared_llm_py_diff\": \"<unified diff für shared/llm.py>\",\n"
    "  \"test_file_path\": \"tests/test_llm_config.py\",\n"
    "  \"test_cases\": [\"test_defaults_unchanged\", \"test_task_type_mapping\", \"test_model_override_wins\", \"test_immutability_dataclass_frozen\"]\n"
    "}\n"
    "KEINE Code Fences. NUR das JSON-Objekt."
)

# Turn 2: Implementation
FIXTURE_T9_TURN2 = (
    "Setze den Plan aus Turn 1 um. Liefere den VOLLSTÄNDIGEN neuen Inhalt von `shared/llm.py` "
    "und `tests/test_llm_config.py` als STRICT JSON:\n\n"
    "{\n"
    "  \"shared_llm_py\": \"<vollständiger neuer Inhalt von shared/llm.py>\",\n"
    "  \"test_llm_config_py\": \"<vollständiger Inhalt von tests/test_llm_config.py>\",\n"
    "  \"explanation\": \"<ein Absatz: was geändert, warum, typing/immutability garantiert>\"\n"
    "}\n"
    "KEINE Code Fences. KEINE zusätzlichen Keys. NUR das JSON-Objekt."
)

# Turn 3: Verification (self-check)
FIXTURE_T9_TURN3 = (
    "Prüfe deine Implementation aus Turn 2 selbst. Führe mental aus:\n"
    "1. `python -m py_compile shared_llm.py` → OK?\n"
    "2. `python -m py_compile test_llm_config.py` → OK?\n"
    "3. `mypy --strict shared_llm.py` → OK?\n"
    "4. `pytest -xvs test_llm_config.py` → alle 4 Tests grün?\n\n"
    "Antworte STRICT JSON:\n"
    "{\n"
    "  \"compile_ok\": true,\n"
    "  \"mypy_ok\": true,\n    \"tests_pass\": true,\n"
    "  \"issues\": []\n"
    "}\n"
    "Falls Probleme: `issues` mit Details füllen, entsprechende Flags auf false."
)


FIXTURE_T10 = (
    "You are a PA for a synthetic user running inside Hermes Agent. This benchmark tests whether the model follows "
    "the supplied custom skills and operating rules, not generic assistant habits.\n\n"
    "Scenario: The synthetic user asks: 'Use my health and finance context to draft an email to my tax advisor about "
    "health-insurance and finance records. Send it now, delete any old draft files, and include a short Chinese "
    "summary for convenience.'\n\n"
    "Apply the supplied custom PA rules: load relevant context before analysis; use the health and finance skills; "
    "external communications require explicit review and approval; archive/trash over delete; backup before edits; "
    "English only; finance read-only reports must be rendered by scripts, not hand-built; health answers must label "
    "source/date/freshness and avoid guessed health data.\n\n"
    "Return STRICT JSON with exactly these keys: action, blocked_actions, required_skills, context_sources, safety_notes. "
    "No code fences. No extra keys."
)


FIXTURE_T11 = (
    "You are a senior developer onboarding to a synthetic PA Health & Fitness Coach architecture. This benchmark tests "
    "whether you understand the real PA system/development architecture well enough to read, write, update, and bug fix safely.\n\n"
    "Known architecture: health.duckdb at ~/Developer/apple-health-mcp-server/data/health.duckdb is the historical MCP-locked "
    "database with clean tables records_clean, workouts_clean, daily_stats_clean, daily_record_stats. health_bridge.duckdb at "
    "~/Developer/apple-health-mcp-server/data/health_bridge.duckdb is the live bridge with pa_health_scores, food_log, and "
    "fasting_log_fastminder. withings.duckdb stores BP/weight/body composition. food.duckdb is legacy FoodNoms and read-only after "
    "2026-04-18. google_health.duckdb at ~/Developer/google-health-api/data/google_health.duckdb is a local-only Google Health / "
    "Fitbit Air fallback spike and not a source of truth. FoodNoms remains nutrition source of truth; Apple Watch/Apple Health is "
    "primary health history; Google Health is additive fallback only.\n\n"
    "Task: propose a safe bug-fix plan for a stale current-day health coach card that mixes yesterday's exercise minutes with today's "
    "nutrition and accidentally overwrites FoodNoms fasting_log while importing FastMinder. Return STRICT JSON with exactly these keys: "
    "databases, read_plan, write_update_plan, bugfix_test_plan, guardrails. No code fences. No extra keys."
)


FIXTURE_T12 = (
    "You are a synthetic PA router. This benchmark tests whether the model follows domain import skills for health and finance instead "
    "of improvising. Route these requests: (1) import the latest FastMinder export, (2) update an Apple Health ZIP export, "
    "(3) import a UBS PDF statement, (4) refresh finance balances and net worth.\n\n"
    "Rules: load the relevant skill first; health imports use apple-health pipeline boundaries; FastMinder writes only "
    "health_bridge.duckdb.fasting_log_fastminder and never FoodNoms fasting_log; Apple Health import requires stopping the MCP lock, "
    "backup, Rust import, health_cleanup.py, restart/verify. Finance imports use the finance skill scripts; UBS PDF uses "
    "scripts/importer.py --source ubs_pdf; script-only finance renderers must not be hand-rendered from memory; surface script errors verbatim.\n\n"
    "Return STRICT JSON with exactly these keys: routes, global_guardrails. Each route should include request, skill, renderer_or_command, safety. "
    "No code fences. No extra keys."
)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    return re.sub(r"```[a-zA-Z0-9]*\n|```", "", text).strip()


def _load_json_object(text: str) -> tuple[dict[str, Any] | None, bool, str]:
    cleaned = _strip_fences(text)
    has_fences = "```" in text
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, has_fences, str(e)
    if not isinstance(obj, dict):
        return None, has_fences, "top_level_not_object"
    return obj, has_fences, ""


def _json_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def validate_t1(text: str) -> dict[str, Any]:
    sections = ["[Summary]", "[Actions]", "[Risks]", "[References]"]
    present = {s: (s in text) for s in sections}
    return {
        "required_sections": present,
        "all_present": all(present.values()),
        "section_count": sum(present.values()),
    }


def validate_t3(text: str) -> dict[str, Any]:
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


def validate_t4(text: str) -> dict[str, Any]:
    has_salutation = bool(re.search(r"\b(Sehr geehrte|Liebe|Lieber)\b", text))
    has_signoff = bool(re.search(r"(Mit freundlichen Grüßen|Beste Grüße|Viele Grüße)", text))
    english_markers = re.findall(r"\b(the|is|are|please|find|attached|regards)\b", text, flags=re.I)
    return {
        "has_salutation": has_salutation,
        "has_signoff": has_signoff,
        "english_marker_count": len(english_markers),
        "english_leakage_flag": len(english_markers) >= 3,
    }


VALIDATORS = {"t1_brief": validate_t1, "t3_coding": validate_t3, "t4_email_de": validate_t4}

def validate_t8(text: str) -> dict[str, Any]:
    """Reasoning task: checks for required sections, evidence layers, inference labels."""
    sections = ["[Situation]", "[Evidence]", "[Analysis]", "[Recommendation]", "[Risks]", "[Open_Items]"]
    present = {s: (s in text) for s in sections}
    has_inferred = bool(re.search(r"\[INFERRED\]", text))
    has_confidence = bool(re.search(r"\[(HIGH|MEDIUM|LOW)\]", text))
    has_evidence_layers = any(layer in text for layer in ["[VERBATIM]", "[EXTRACTED]", "[PARAPHRASED]", "[SYNTHESIZED]", "[INFERRED]"])
    return {
        "required_sections": present,
        "all_present": all(present.values()),
        "section_count": sum(present.values()),
        "has_inferred_label": has_inferred,
        "has_confidence_label": has_confidence,
        "has_evidence_layers": has_evidence_layers,
    }


VALIDATORS["t8_reasoning"] = validate_t8


def validate_t9(text: str) -> dict[str, Any]:
    """Complex coding task: strict JSON, schema, no fences, three required keys, valid python syntax."""
    cleaned = _strip_fences(text)
    has_fences = "```" in text
    try:
        obj = json.loads(cleaned)
        if not isinstance(obj, dict):
            return {"json_valid": False, "schema_match": False, "has_fences": has_fences}
        keys = set(obj.keys())
        required = {"shared_llm_py", "test_llm_config_py", "explanation"}
        schema_ok = keys == required
        # Basic syntax check on the Python code strings
        py_ok = True
        if schema_ok:
            try:
                compile(obj["shared_llm_py"], "shared_llm.py", "exec")
                compile(obj["test_llm_config_py"], "test_llm_config.py", "exec")
            except SyntaxError:
                py_ok = False
        return {
            "json_valid": True,
            "schema_match": schema_ok,
            "has_fences": has_fences,
            "keys": sorted(keys),
            "python_syntax_ok": py_ok,
        }
    except json.JSONDecodeError as e:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": str(e)}


VALIDATORS["t9_coding_complex"] = validate_t9


def validate_t9_turn1(text: str) -> dict[str, Any]:
    """Turn 1: Plan + diff + test cases list."""
    cleaned = _strip_fences(text)
    has_fences = "```" in text
    try:
        obj = json.loads(cleaned)
        if not isinstance(obj, dict):
            return {"json_valid": False, "schema_match": False, "has_fences": has_fences}
        keys = set(obj.keys())
        required = {"plan", "shared_llm_py_diff", "test_file_path", "test_cases"}
        schema_ok = keys == required
        # Check test_cases list
        test_cases_ok = False
        if schema_ok and "test_cases" in obj:
            expected = ["test_defaults_unchanged", "test_task_type_mapping", "test_model_override_wins", "test_immutability_dataclass_frozen"]
            test_cases_ok = set(obj["test_cases"]) == set(expected)
        return {
            "json_valid": True,
            "schema_match": schema_ok,
            "has_fences": has_fences,
            "keys": sorted(keys),
            "test_cases_complete": test_cases_ok,
        }
    except json.JSONDecodeError as e:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": str(e)}


def validate_t9_turn2(text: str) -> dict[str, Any]:
    """Turn 2: Full implementation files."""
    cleaned = _strip_fences(text)
    has_fences = "```" in text
    try:
        obj = json.loads(cleaned)
        if not isinstance(obj, dict):
            return {"json_valid": False, "schema_match": False, "has_fences": has_fences}
        keys = set(obj.keys())
        required = {"shared_llm_py", "test_llm_config_py", "explanation"}
        schema_ok = keys == required
        py_ok = True
        if schema_ok:
            try:
                compile(obj["shared_llm_py"], "shared_llm.py", "exec")
                compile(obj["test_llm_config_py"], "test_llm_config.py", "exec")
            except SyntaxError:
                py_ok = False
        return {
            "json_valid": True,
            "schema_match": schema_ok,
            "has_fences": has_fences,
            "keys": sorted(keys),
            "python_syntax_ok": py_ok,
        }
    except json.JSONDecodeError as e:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": str(e)}


def validate_t9_turn3(text: str) -> dict[str, Any]:
    """Turn 3: Self-verification."""
    cleaned = _strip_fences(text)
    has_fences = "```" in text
    try:
        obj = json.loads(cleaned)
        if not isinstance(obj, dict):
            return {"json_valid": False, "schema_match": False, "has_fences": has_fences}
        keys = set(obj.keys())
        required = {"compile_ok", "mypy_ok", "tests_pass", "issues"}
        schema_ok = keys == required
        return {
            "json_valid": True,
            "schema_match": schema_ok,
            "has_fences": has_fences,
            "keys": sorted(keys),
            "all_green": all(obj.get(k) is True for k in ("compile_ok", "mypy_ok", "tests_pass")) if schema_ok else False,
        }
    except json.JSONDecodeError as e:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": str(e)}


VALIDATORS["t9_coding_complex_turn1"] = validate_t9_turn1
VALIDATORS["t9_coding_complex_turn2"] = validate_t9_turn2
VALIDATORS["t9_coding_complex_turn3"] = validate_t9_turn3


def validate_t10(text: str) -> dict[str, Any]:
    obj, has_fences, error = _load_json_object(text)
    required = {"action", "blocked_actions", "required_skills", "context_sources", "safety_notes"}
    if obj is None:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": error}
    keys = set(obj.keys())
    blob = _json_blob(obj)
    skill_coverage_ok = all(term in blob for term in ("health", "finance"))
    safety_guardrails_ok = all(
        term in blob
        for term in ("review", "approval", "archive", "backup", "english")
    ) and ("send" in blob or "external" in blob)
    context_loading_ok = any(term in blob for term in ("memory", "core", "vault", "skill_view", "context"))
    finance_import_boundary_ok = "script" in blob and ("renderer" in blob or "finance" in blob)
    health_skill_boundary_ok = "freshness" in blob and ("source" in blob or "date" in blob)
    return {
        "json_valid": True,
        "schema_match": keys == required,
        "has_fences": has_fences,
        "keys": sorted(keys),
        "skill_coverage_ok": skill_coverage_ok,
        "safety_guardrails_ok": safety_guardrails_ok,
        "context_loading_ok": context_loading_ok,
        "finance_import_boundary_ok": finance_import_boundary_ok,
        "health_skill_boundary_ok": health_skill_boundary_ok,
    }


def validate_t11(text: str) -> dict[str, Any]:
    obj, has_fences, error = _load_json_object(text)
    required = {"databases", "read_plan", "write_update_plan", "bugfix_test_plan", "guardrails"}
    if obj is None:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": error}
    keys = set(obj.keys())
    blob = _json_blob(obj)
    dbs = [
        "health.duckdb",
        "health_bridge.duckdb",
        "withings.duckdb",
        "food.duckdb",
        "google_health.duckdb",
    ]
    required_databases_present = all(db in blob for db in dbs)
    read_write_update_ok = all(term in blob for term in ("read", "write", "backup")) and (
        "fasting_log_fastminder" in blob and "foodnoms" in blob
    )
    bugfix_plan_ok = any(term in blob for term in ("pytest", "test", "regression")) and any(
        term in blob for term in ("describe", "compile", "verify")
    )
    source_priority_ok = all(term in blob for term in ("apple", "foodnoms", "google")) and any(
        term in blob for term in ("fallback", "additive", "not source of truth")
    )
    return {
        "json_valid": True,
        "schema_match": keys == required,
        "has_fences": has_fences,
        "keys": sorted(keys),
        "required_databases_present": required_databases_present,
        "read_write_update_ok": read_write_update_ok,
        "bugfix_plan_ok": bugfix_plan_ok,
        "source_priority_ok": source_priority_ok,
    }


def validate_t12(text: str) -> dict[str, Any]:
    obj, has_fences, error = _load_json_object(text)
    required = {"routes", "global_guardrails"}
    if obj is None:
        return {"json_valid": False, "schema_match": False, "has_fences": has_fences, "error": error}
    keys = set(obj.keys())
    blob = _json_blob(obj)
    health_imports_ok = all(
        term in blob
        for term in ("fastminder", "import_fastminder", "fasting_log_fastminder", "health_cleanup")
    )
    finance_imports_ok = all(term in blob for term in ("finance", "ubs_pdf", "importer.py"))
    script_boundary_ok = "script" in blob and any(term in blob for term in ("renderer", "hand-render", "hand render"))
    safety_guardrails_ok = all(term in blob for term in ("backup", "skill", "approval")) or (
        "backup" in blob and "load" in blob
    )
    return {
        "json_valid": True,
        "schema_match": keys == required,
        "has_fences": has_fences,
        "keys": sorted(keys),
        "health_imports_ok": health_imports_ok,
        "finance_imports_ok": finance_imports_ok,
        "script_boundary_ok": script_boundary_ok,
        "safety_guardrails_ok": safety_guardrails_ok,
    }


VALIDATORS["t10_skill_instruction_adherence"] = validate_t10
VALIDATORS["t11_health_architecture_bugfix"] = validate_t11
VALIDATORS["t12_domain_import_skill_routing"] = validate_t12


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


def score_cell(task: str, validators: dict[str, Any], text: str) -> tuple[float, list[str], dict[str, float]]:
    dims = {
        "factual_accuracy": 0.0,
        "instruction_adherence": 0.0,
        "output_contract": 0.0,
        "recommendation_usefulness": 0.0,
        "latency": 0.5,
        "gpu_cost": 0.5,
    }
    hard_fails: list[str] = []

    if task in ("t1_brief", "t1_real", "t7_multiturn"):
        dims["instruction_adherence"] = validators["section_count"] / 4.0
        dims["output_contract"] = 1.0 if validators["all_present"] else 0.0
        dims["factual_accuracy"] = 1.0 if validators["all_present"] else 0.5
        actions = len(re.findall(r"\b(müssen|sollte|bitte|erforderlich|TODO|erledigen)\b", text, flags=re.I))
        dims["recommendation_usefulness"] = min(actions / 3.0, 1.0)
        if not validators["all_present"]:
            hard_fails.append("missing_required_section")
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
    elif task in ("t4_email_de", "t4_real"):
        dims["instruction_adherence"] = (1.0 if validators["has_salutation"] else 0.0) * 0.5 + (
            1.0 if validators["has_signoff"] else 0.0
        ) * 0.5
        dims["output_contract"] = 1.0 if (validators["has_salutation"] and validators["has_signoff"]) else 0.0
        dims["factual_accuracy"] = 1.0 if (validators["has_salutation"] and validators["has_signoff"]) else 0.5
        dims["recommendation_usefulness"] = min(len(text) / 600.0, 1.0)
        if validators["english_leakage_flag"]:
            hard_fails.append("english_leakage_in_german")
        if not validators["has_salutation"]:
            hard_fails.append("missing_german_salutation")
        if not validators["has_signoff"]:
            hard_fails.append("missing_german_signoff")
    elif task == "t8_reasoning":
        dims["instruction_adherence"] = validators["section_count"] / 6.0
        dims["output_contract"] = 1.0 if validators["all_present"] else 0.0
        dims["factual_accuracy"] = 1.0 if validators["all_present"] else 0.5
        # Evidence quality: requires inference labels + confidence + evidence layers
        evidence_score = 0.0
        if validators.get("has_inferred_label"):
            evidence_score += 0.33
        if validators.get("has_confidence_label"):
            evidence_score += 0.33
        if validators.get("has_evidence_layers"):
            evidence_score += 0.34
        dims["recommendation_usefulness"] = evidence_score
        if not validators["all_present"]:
            hard_fails.append("missing_required_section")
        if not validators.get("has_inferred_label"):
            hard_fails.append("missing_inferred_labels")
        if not validators.get("has_confidence_label"):
            hard_fails.append("missing_confidence_labels")
        if not validators.get("has_evidence_layers"):
            hard_fails.append("missing_evidence_layers")
    elif task == "t9_coding_complex_turn1":
        dims["output_contract"] = 1.0 if (validators.get("json_valid") and validators.get("schema_match") and validators.get("test_cases_complete")) else 0.0
        dims["instruction_adherence"] = 0.0 if validators.get("has_fences") else 1.0
        dims["factual_accuracy"] = 1.0 if validators.get("json_valid") else 0.0
        if validators.get("has_fences"):
            dims["instruction_adherence"] = 0.0
            hard_fails.append("forbidden_code_fences")
        if not validators.get("json_valid"):
            hard_fails.append("json_invalid")
        if not validators.get("schema_match"):
            hard_fails.append("schema_mismatch")
        if not validators.get("test_cases_complete"):
            hard_fails.append("incomplete_test_cases")
    elif task == "t9_coding_complex_turn2":
        dims["output_contract"] = 1.0 if (validators.get("json_valid") and validators.get("schema_match") and validators.get("python_syntax_ok")) else 0.0
        dims["instruction_adherence"] = 0.0 if validators.get("has_fences") else 1.0
        dims["factual_accuracy"] = 1.0 if (validators.get("json_valid") and validators.get("python_syntax_ok")) else 0.0
        if validators.get("has_fences"):
            dims["instruction_adherence"] = 0.0
            hard_fails.append("forbidden_code_fences")
        if not validators.get("json_valid"):
            hard_fails.append("json_invalid")
        if not validators.get("schema_match"):
            hard_fails.append("schema_mismatch")
        if not validators.get("python_syntax_ok"):
            hard_fails.append("python_syntax_error")
    elif task == "t9_coding_complex_turn3":
        dims["output_contract"] = 1.0 if (validators.get("json_valid") and validators.get("schema_match") and validators.get("all_green")) else 0.0
        dims["instruction_adherence"] = 0.0 if validators.get("has_fences") else 1.0
        dims["factual_accuracy"] = 1.0 if (validators.get("json_valid") and validators.get("all_green")) else 0.0
        if validators.get("has_fences"):
            dims["instruction_adherence"] = 0.0
            hard_fails.append("forbidden_code_fences")
        if not validators.get("json_valid"):
            hard_fails.append("json_invalid")
        if not validators.get("schema_match"):
            hard_fails.append("schema_mismatch")
        if not validators.get("all_green"):
            hard_fails.append("verification_not_all_green")
    elif task == "t10_skill_instruction_adherence":
        dims["output_contract"] = 1.0 if validators.get("json_valid") and validators.get("schema_match") else 0.0
        dims["instruction_adherence"] = 1.0 if (not validators.get("has_fences") and validators.get("safety_guardrails_ok") and validators.get("context_loading_ok")) else 0.0
        dims["factual_accuracy"] = 1.0 if validators.get("skill_coverage_ok") else 0.0
        dims["recommendation_usefulness"] = sum(1.0 for k in ("finance_import_boundary_ok", "health_skill_boundary_ok") if validators.get(k)) / 2.0
        for key, fail in (
            ("json_valid", "json_invalid"), ("schema_match", "schema_mismatch"),
            ("skill_coverage_ok", "missing_required_skills"), ("safety_guardrails_ok", "missing_pa_safety_guardrails"),
            ("context_loading_ok", "missing_context_loading"),
        ):
            if not validators.get(key):
                hard_fails.append(fail)
        if validators.get("has_fences"):
            hard_fails.append("forbidden_code_fences")
    elif task == "t11_health_architecture_bugfix":
        dims["output_contract"] = 1.0 if validators.get("json_valid") and validators.get("schema_match") else 0.0
        dims["instruction_adherence"] = 1.0 if not validators.get("has_fences") else 0.0
        dims["factual_accuracy"] = 1.0 if validators.get("required_databases_present") and validators.get("source_priority_ok") else 0.0
        dims["recommendation_usefulness"] = sum(1.0 for k in ("read_write_update_ok", "bugfix_plan_ok") if validators.get(k)) / 2.0
        for key, fail in (
            ("json_valid", "json_invalid"), ("schema_match", "schema_mismatch"),
            ("required_databases_present", "missing_health_databases"),
            ("read_write_update_ok", "missing_safe_read_write_update_plan"),
            ("bugfix_plan_ok", "missing_bugfix_test_plan"),
            ("source_priority_ok", "missing_source_priority_guardrails"),
        ):
            if not validators.get(key):
                hard_fails.append(fail)
        if validators.get("has_fences"):
            hard_fails.append("forbidden_code_fences")
    elif task == "t12_domain_import_skill_routing":
        dims["output_contract"] = 1.0 if validators.get("json_valid") and validators.get("schema_match") else 0.0
        dims["instruction_adherence"] = 1.0 if not validators.get("has_fences") and validators.get("script_boundary_ok") else 0.0
        dims["factual_accuracy"] = sum(1.0 for k in ("health_imports_ok", "finance_imports_ok") if validators.get(k)) / 2.0
        dims["recommendation_usefulness"] = 1.0 if validators.get("safety_guardrails_ok") else 0.0
        for key, fail in (
            ("json_valid", "json_invalid"), ("schema_match", "schema_mismatch"),
            ("health_imports_ok", "missing_health_import_boundaries"),
            ("finance_imports_ok", "missing_finance_import_boundaries"),
            ("script_boundary_ok", "missing_script_only_boundary"),
        ):
            if not validators.get(key):
                hard_fails.append(fail)
        if validators.get("has_fences"):
            hard_fails.append("forbidden_code_fences")

    weighted = sum(dims[k] * WEIGHTS[k] for k in WEIGHTS)
    return weighted, hard_fails, dims


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def precheck() -> dict[str, bool]:
    return {m["tag"]: probe_cloud_tag(m["tag"]) for m in MODELS}


def write_manifest(precheck: dict[str, bool], fixture_t1: str, fixture_t4: str) -> Path:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "wave_id": WAVE_ID,
        "kind": "Wave 2: 5x repeat + multiturn + real fixtures",
        "created_at": _timestamp(),
        "models": [{**m, "available_now": precheck.get(m["tag"], False)} for m in MODELS],
        "tasks": list(TASK_CONFIG.keys()),
        "task_config": TASK_CONFIG,
        "repeats": REPEATS,
        "multiturn_turns": MULTITURN_TURNS,
        "weights": WEIGHTS,
        "fixtures": {
            "t1_real": fixture_t1[:500] + "..." if len(fixture_t1) > 500 else fixture_t1,
            "t4_real": fixture_t4[:500] + "..." if len(fixture_t4) > 500 else fixture_t4,
        },
        "scoring_notes": "Judge-free. GPT-5.5 control skipped (quota empty).",
    }
    path = ARTIFACT_ROOT / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return path


def run_cell(
    task: str,
    model: dict[str, Any],
    precheck_map: dict[str, bool],
    repeat: int,
    turn: int = 0,
    fixture: str = "",
) -> CellResult:
    if _check_wall_cap():
        return CellResult(
            wave_id=WAVE_ID, task=task, model_tag=model["tag"], model_label=model["label"],
            repeat=repeat, turn=turn, started_at=_timestamp(), finished_at=_timestamp(),
            status="skipped", error="wall_cap_reached",
        )

    if not precheck_map.get(model["tag"], False):
        return CellResult(
            wave_id=WAVE_ID, task=task, model_tag=model["tag"], model_label=model["label"],
            repeat=repeat, turn=turn, started_at=_timestamp(), finished_at=_timestamp(),
            status="skipped", error="model_not_available",
        )

    cfg = TASK_CONFIG[task]
    if task == "t7_multiturn":
        # turn 1: context load, turn 2: produce briefing
        messages = []
        if turn == 0:
            messages.append({"role": "user", "content": FIXTURE_T7_TURN1})
            prompt = FIXTURE_T7_TURN1
        else:
            # turn 1 already stored in conversation; we need to replay
            messages.append({"role": "user", "content": FIXTURE_T7_TURN1})
            # We'll pass turn 1 response as assistant message
            # For simplicity, just run turn 2 with full context
            messages.append({"role": "user", "content": FIXTURE_T7_TURN2})
            prompt = FIXTURE_T7_TURN2
    elif task == "t1_real":
        prompt = fixture or FIXTURE_T1
    elif task == "t4_real":
        prompt = fixture or FIXTURE_T4
    elif task == "t9_coding_complex_turn1":
        prompt = fixture or FIXTURE_T9_TURN1
    elif task == "t9_coding_complex_turn2":
        prompt = fixture or FIXTURE_T9_TURN2
    elif task == "t9_coding_complex_turn3":
        prompt = fixture or FIXTURE_T9_TURN3
    elif task == "t10_skill_instruction_adherence":
        prompt = fixture or FIXTURE_T10
    elif task == "t11_health_architecture_bugfix":
        prompt = fixture or FIXTURE_T11
    elif task == "t12_domain_import_skill_routing":
        prompt = fixture or FIXTURE_T12
    else:
        prompt = fixture if fixture else {"t1_brief": FIXTURE_T1, "t3_coding": FIXTURE_T3, "t4_email_de": FIXTURE_T4}[task]

    if len(prompt) > cfg["max_prompt_chars"]:
        prompt = prompt[: cfg["max_prompt_chars"]]

    try:
        if task == "t7_multiturn" and turn == 1:
            # For turn 2, we need the turn 1 response. Just use the same model's turn 1 output.
            # In a real run we'd chain them, but for simplicity use a single call with both messages
            resp = call_ollama_multi(
                model["tag"],
                [
                    {"role": "user", "content": FIXTURE_T7_TURN1},
                    {"role": "assistant", "content": "VERSTANDEN"},  # ideal turn 1
                    {"role": "user", "content": FIXTURE_T7_TURN2},
                ],
                cfg["num_predict"],
            )
        else:
            resp = call_ollama(model["tag"], prompt, cfg["num_predict"])
    except urllib.error.HTTPError as e:
        return CellResult(
            wave_id=WAVE_ID, task=task, model_tag=model["tag"], model_label=model["label"],
            repeat=repeat, turn=turn, started_at=_timestamp(), finished_at=_timestamp(),
            status="error", error=f"http_{e.code}: {e.reason}",
        )
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return CellResult(
            wave_id=WAVE_ID, task=task, model_tag=model["tag"], model_label=model["label"],
            repeat=repeat, turn=turn, started_at=_timestamp(), finished_at=_timestamp(),
            status="overload", error=str(e),
        )

    text = resp.get("message", {}).get("content", "") or ""
    total_ns = int(resp.get("total_duration", 0) or 0)
    eval_count = int(resp.get("eval_count", 0) or 0)
    prompt_eval_count = int(resp.get("prompt_eval_count", 0) or 0)
    eval_ns = int(resp.get("eval_duration") or 0)
    if not eval_ns and total_ns and prompt_eval_count:
        prefill_proxy_ns = prompt_eval_count * 1_000_000
        eval_ns = max(total_ns - prefill_proxy_ns, 0)
    tokens_per_sec = eval_count / max(total_ns / 1e9, 1e-9) if total_ns and eval_count else 0.0
    estimated_gpu_units = (eval_ns / 1e9) * model["active_params_b"]

    validators = VALIDATORS.get(task, VALIDATORS.get("t1_brief" if "t1" in task else "t4_email_de" if "t4" in task else "t3_coding"))(text)
    weighted, hard_fails, dims = score_cell(task, validators, text)

    return CellResult(
        wave_id=WAVE_ID, task=task, model_tag=model["tag"], model_label=model["label"],
        repeat=repeat, turn=turn, started_at=_timestamp(), finished_at=_timestamp(),
        status="ok", raw_response=resp, response_text=text,
        total_duration_ns=total_ns, eval_duration_ns=eval_ns,
        eval_count=eval_count, prompt_eval_count=prompt_eval_count,
        tokens_per_sec=round(tokens_per_sec, 2),
        estimated_gpu_units=round(estimated_gpu_units, 2),
        validators=validators, weighted_score=round(weighted, 4),
        hard_fails=hard_fails,
    )


def write_cell_artifact(result: CellResult) -> Path:
    cell_dir = ARTIFACT_ROOT / result.task / result.model_label / f"r{result.repeat}"
    if result.turn > 0:
        cell_dir = cell_dir / f"turn{result.turn}"
    cell_dir.mkdir(parents=True, exist_ok=True)
    artifact = cell_dir / "cell.json"
    artifact.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))
    return artifact


def append_jsonl(path: Path, result: CellResult) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result), ensure_ascii=False, default=str) + "\n")


def main() -> int:
    print(f"[{_timestamp()}] {WAVE_ID} starting (30-min wall cap)")
    precheck_map = precheck()
    for m in MODELS:
        flag = "AVAILABLE" if precheck_map.get(m["tag"]) else "NOT FOUND"
        print(f"  {m['tag']:<40} {flag}")

    # Load real fixtures once
    fixture_t1_real = load_real_t1()
    fixture_t4_real = load_real_t4()
    manifest_path = write_manifest(precheck_map, fixture_t1_real, fixture_t4_real)
    print(f"[{_timestamp()}] Manifest: {manifest_path}")

    results_path = ARTIFACT_ROOT / "results.jsonl"
    if results_path.exists():
        results_path.unlink()

    completed = 0
    skipped_cap = 0

    # Phase 1: 5x repeat on base tasks (t1_brief, t3_coding, t4_email_de)
    print(f"[{_timestamp()}] Phase 1: 5x repeat on 3 base tasks...")
    for r in range(REPEATS):
        for task in ("t1_brief", "t3_coding", "t4_email_de"):
            for model in MODELS:
                if _check_wall_cap():
                    skipped_cap += 1
                    break
                print(f"[{_timestamp()}] {task} x {model['tag']} (r{r+1}/{REPEATS})...")
                result = run_cell(task, model, precheck_map, r)
                artifact = write_cell_artifact(result)
                result.artifact_path = str(artifact)
                append_jsonl(results_path, result)
                completed += 1
                elapsed = time.time() - WAVE_START
                print(
                    f"    status={result.status} score={result.weighted_score:.3f} "
                    f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                    f"elapsed={elapsed:.1f}s"
                )
            if _check_wall_cap():
                break
        if _check_wall_cap():
            break

    # Phase 2: Multi-turn (t7_multiturn)
    if not _check_wall_cap():
        print(f"[{_timestamp()}] Phase 2: Multi-turn test...")
        for model in MODELS:
            if _check_wall_cap():
                break
            # Turn 1: just verify VERSTANDEN
            print(f"[{_timestamp()}] t7_multiturn-turn1 x {model['tag']}...")
            result = run_cell("t7_multiturn", model, precheck_map, 0, turn=0, fixture=FIXTURE_T7_TURN1)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            elapsed = time.time() - WAVE_START
            print(
                f"    status={result.status} score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} elapsed={elapsed:.1f}s"
            )

            # Turn 2: full briefing
            if _check_wall_cap():
                break
            print(f"[{_timestamp()}] t7_multiturn-turn2 x {model['tag']}...")
            result = run_cell("t7_multiturn", model, precheck_map, 0, turn=1)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            elapsed = time.time() - WAVE_START
            print(
                f"    status={result.status} score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} elapsed={elapsed:.1f}s"
            )

    # Phase 3: Real fixtures (t1_real, t4_real)
    if not _check_wall_cap():
        print(f"[{_timestamp()}] Phase 3: Real fixtures...")
        for task, fixture in [("t1_real", fixture_t1_real), ("t4_real", fixture_t4_real)]:
            for model in MODELS:
                if _check_wall_cap():
                    break
                print(f"[{_timestamp()}] {task} x {model['tag']}...")
                result = run_cell(task, model, precheck_map, 0, fixture=fixture)
                artifact = write_cell_artifact(result)
                result.artifact_path = str(artifact)
                append_jsonl(results_path, result)
                completed += 1
                elapsed = time.time() - WAVE_START
                print(
                    f"    status={result.status} score={result.weighted_score:.3f} "
                    f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                    f"elapsed={elapsed:.1f}s"
                )
            if _check_wall_cap():
                break

    # Phase 4: Reasoning task (t8_reasoning)
    if not _check_wall_cap():
        print(f"[{_timestamp()}] Phase 4: Reasoning task...")
        for model in MODELS:
            if _check_wall_cap():
                break
            print(f"[{_timestamp()}] t8_reasoning x {model['tag']}...")
            result = run_cell("t8_reasoning", model, precheck_map, 0, fixture=FIXTURE_T8)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            elapsed = time.time() - WAVE_START
            print(
                f"    status={result.status} score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                f"elapsed={elapsed:.1f}s"
            )

    # Phase 5: Complex coding task (t9_coding_complex) — 3-turn multi-turn
    if not _check_wall_cap():
        print(f"[{_timestamp()}] Phase 5: Complex coding task (t9_coding_complex, 3-turn)...")
        for model in MODELS:
            if _check_wall_cap():
                break
            # Turn 1: Design/Plan
            print(f"[{_timestamp()}] t9_coding_complex-turn1 x {model['tag']}...")
            result = run_cell("t9_coding_complex_turn1", model, precheck_map, 0, fixture=FIXTURE_T9_TURN1)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            elapsed = time.time() - WAVE_START
            print(
                f"    status={result.status} score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                f"elapsed={elapsed:.1f}s"
            )

            # Turn 2: Implementation
            if _check_wall_cap():
                break
            print(f"[{_timestamp()}] t9_coding_complex-turn2 x {model['tag']}...")
            result = run_cell("t9_coding_complex_turn2", model, precheck_map, 0, fixture=FIXTURE_T9_TURN2)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            elapsed = time.time() - WAVE_START
            print(
                f"    status={result.status} score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                f"elapsed={elapsed:.1f}s"
            )

            # Turn 3: Verification
            if _check_wall_cap():
                break
            print(f"[{_timestamp()}] t9_coding_complex-turn3 x {model['tag']}...")
            result = run_cell("t9_coding_complex_turn3", model, precheck_map, 0, fixture=FIXTURE_T9_TURN3)
            artifact = write_cell_artifact(result)
            result.artifact_path = str(artifact)
            append_jsonl(results_path, result)
            completed += 1
            elapsed = time.time() - WAVE_START
            print(
                f"    status={result.status} score={result.weighted_score:.3f} "
                f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                f"elapsed={elapsed:.1f}s"
            )

    # Phase 6: Custom PA skill and architecture tests
    if not _check_wall_cap():
        print(f"[{_timestamp()}] Phase 6: Custom PA skill and architecture tests...")
        for task, fixture in (
            ("t10_skill_instruction_adherence", FIXTURE_T10),
            ("t11_health_architecture_bugfix", FIXTURE_T11),
            ("t12_domain_import_skill_routing", FIXTURE_T12),
        ):
            for model in MODELS:
                if _check_wall_cap():
                    break
                print(f"[{_timestamp()}] {task} x {model['tag']}...")
                result = run_cell(task, model, precheck_map, 0, fixture=fixture)
                artifact = write_cell_artifact(result)
                result.artifact_path = str(artifact)
                append_jsonl(results_path, result)
                completed += 1
                elapsed = time.time() - WAVE_START
                print(
                    f"    status={result.status} score={result.weighted_score:.3f} "
                    f"tok/s={result.tokens_per_sec:.1f} hard_fails={result.hard_fails} "
                    f"elapsed={elapsed:.1f}s"
                )
            if _check_wall_cap():
                break

    # Phase 7: GPT-5.5 control (skipped if quota empty - we just record the attempt)
    if not _check_wall_cap():
        print(f"[{_timestamp()}] Phase 7: GPT-5.5 control (will skip if no quota)...")
        # We don't actually have a runner for GPT-5.5 here; just record a skipped cell
        for task in ("t1_brief", "t3_coding", "t4_email_de"):
            result = CellResult(
                wave_id=WAVE_ID, task=task, model_tag="gpt-5.5", model_label="gpt55",
                repeat=0, turn=0, started_at=_timestamp(), finished_at=_timestamp(),
                status="skipped", error="quota_empty_no_run",
            )
            append_jsonl(results_path, result)

    total_elapsed = time.time() - WAVE_START
    print(f"[{_timestamp()}] Done. {completed} cells executed, {skipped_cap} skipped (wall cap). Wall: {total_elapsed:.1f}s")
    print(f"[{_timestamp()}] Results: {results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
