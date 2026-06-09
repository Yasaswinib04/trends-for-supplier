import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from openai import OpenAI
from pathlib import Path
from .prompts import DISAGREEMENT_ENGINE_PROMPT, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

ROOT_DIR = Path(__file__).parent.parent
DB_PATH = ROOT_DIR / "data" / "telemetry.db"


def _get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def _clean_json(raw: str) -> str:
    stripped = raw.strip()
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    return match.group(0) if match else stripped


def synthesize(trend, nykaa_data, myntra_data, meesho_data):
    client = _get_client()

    user_prompt = f"""## Trend Under Evaluation
{json.dumps({"name": trend["name"], "price_band": trend.get("price_band", ""), "season": trend.get("season", ""), "silhouette": trend.get("silhouette", ""), "fabric": trend.get("fabric", "")}, indent=2)}

## Source 1: Nykaa Fashion — Premium D2C Demand
{json.dumps(nykaa_data, indent=2)}

## Source 2: Myntra/Ajio — Organized Mass Retail
{json.dumps(myntra_data, indent=2)}

## Source 3: Meesho — Price-Sensitive Mass Market
{json.dumps(meesho_data, indent=2)}

Analyze the evidence using the Disagreement Engine rules. Detect all conflicts. Output the structured JSON as specified."""

    if not client:
        return {
            "headline": f"Analysis of {trend['name']}: No API key configured. Set DEEPSEEK_API_KEY.",
            "reasoning_trace": [],
            "conflicts": [],
            "convergences": [],
            "upside_summary": "No API key configured.",
            "catch_summary": "Set DEEPSEEK_API_KEY to enable analysis.",
            "bet_lean": "SKIP",
            "bet_rationale": "Cannot analyze without API key.",
            "watch_triggers": [],
            "missing_evidence": [],
            "_mode": "no_api_key"
        }

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": DISAGREEMENT_ENGINE_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=2500,
        )
        content = response.choices[0].message.content
        result = json.loads(_clean_json(content))
        result["_mode"] = "disagreement_engine"

        # Validate Chain-of-Thought reasoning trace
        trace = result.get("reasoning_trace")
        if not trace or not isinstance(trace, list) or len(trace) < 3:
            result["_missing_trace"] = True
            result["_mode"] = "disagreement_engine (no CoT)"
        else:
            result["_has_trace"] = len(trace)

        return result
    except Exception as e:
        return {
            "headline": f"Error analyzing {trend['name']}: {str(e)[:100]}",
            "reasoning_trace": [],
            "conflicts": [],
            "convergences": [],
            "upside_summary": f"Synthesis failed: {str(e)[:80]}",
            "catch_summary": "Try again or check API key.",
            "bet_lean": "SKIP",
            "bet_rationale": "Synthesis error.",
            "watch_triggers": [],
            "missing_evidence": [],
            "_mode": "error",
            "_error": str(e)
        }


# ---- TELEMETRY ----

def init_telemetry():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            trend_id TEXT NOT NULL,
            trend_name TEXT,
            system_bet_lean TEXT,
            override_reason TEXT NOT NULL,
            override_bet_lean TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_override(trend_id, trend_name, system_bet, override_reason, override_bet=None, notes=""):
    init_telemetry()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO overrides (timestamp, trend_id, trend_name, system_bet_lean, override_reason, override_bet_lean, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), trend_id, trend_name, system_bet, override_reason, override_bet, notes)
    )
    conn.commit()
    conn.close()


def get_override_stats():
    init_telemetry()
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT override_reason, COUNT(*) as cnt FROM overrides GROUP BY override_reason ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return rows


def clear_telemetry():
    init_telemetry()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM overrides")
    conn.commit()
    conn.close()
