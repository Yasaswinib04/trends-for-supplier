import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from openai import OpenAI
from pathlib import Path
from .prompts import DISAGREEMENT_ENGINE_PROMPT, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

try:
    from signals.noise_cleaner import apply_all_filters
    NOISE_CLEANER_AVAILABLE = True
except ImportError:
    NOISE_CLEANER_AVAILABLE = False

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

SYNTHESIS_CACHE_FILE = ROOT_DIR / "data" / "syntheses_cache.json"

def _load_cache():
    if SYNTHESIS_CACHE_FILE.exists():
        with open(SYNTHESIS_CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def _save_cache(cache):
    with open(SYNTHESIS_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def synthesize(trend, nykaa_data, myntra_data, meesho_data, internal_data=None,
               meta_ads_data=None, social_data=None):
    trend_id = trend["id"]
    cache = _load_cache()
    if trend_id in cache:
        return cache[trend_id]

    client = _get_client()

    myntra_products = myntra_data.get("products_found", [])
    noise_result = None
    if NOISE_CLEANER_AVAILABLE and myntra_products:
        prices = [p.get("price", 0) for p in myntra_products if p.get("price", 0) > 0]
        avg_price = sum(prices) / max(len(prices), 1) if prices else 0
        noise_result = apply_all_filters(myntra_products, social_buzz_high=False,
                                          avg_price=float(avg_price))

    noise_block = ""
    if noise_result:
        noise_block = f"""
## NOISE-CLEANING PRE-PROCESSING
Verdict: {noise_result['noise_summary']['verdict']}
{chr(10).join(f"- {f}" for f in noise_result['noise_summary'].get('flags', []))}
Price-Buzz Gap: {noise_result['price_buzz_gap'].get('price_buzz_gap_flag') or 'none'}
"""
        myntra_data = {**myntra_data, "products_found": noise_result["products"]}

    user_prompt = f"""## Trend Under Evaluation
{json.dumps({"name": trend["name"], "price_band": trend.get("price_band", ""), "season": trend.get("season", ""), "silhouette": trend.get("silhouette", ""), "fabric": trend.get("fabric", "")}, indent=2)}

## Source 1: Nykaa Fashion — Premium D2C Demand
PRESENCE: {nykaa_data.get("nykaa_presence", "unknown")}. Full-price products: {nykaa_data.get("full_price_products", 0)}. Avg price: ₹{nykaa_data.get("avg_price", 0):.0f}.
{json.dumps(nykaa_data, indent=2)}

## Source 2: Myntra/Ajio — Organized Mass Retail
PRESENCE: {myntra_data.get("marketplace_presence", "unknown")}. Discount risk: {myntra_data.get("discount_distortion_risk", "unknown")}.
{json.dumps(myntra_data, indent=2)}
{noise_block}
## Source 3: Meesho — Price-Sensitive Mass Market
PRESENCE: {meesho_data.get("meesho_presence", "unknown")}. Units: {meesho_data.get("total_units_sold", 0):,}. Resellers: {meesho_data.get("total_resellers", 0)}.
{json.dumps(meesho_data, indent=2)}

## Source 4: Internal POS — Your Own Store Sales
HAS DATA: {"Yes" if (internal_data or {}).get("has_internal_data") else "No prior buy history. Do NOT flag as conflict."}
{json.dumps(internal_data or {"has_internal_data": False}, indent=2)}

## Source 5: Competitor Meta Ads (Instagram/Facebook)
{_format_meta_ads(meta_ads_data)}

## Source 6: YouTube Social Buzz
{_format_social(social_data)}

Analyze the evidence using the Disagreement Engine rules. Detect all conflicts. Output the structured JSON as specified."""

    if not client:
        return {
            "headline": f"Analysis of {trend['name']}: No API key configured. Set DEEPSEEK_API_KEY.",
            "reasoning_trace": [],
            "conflicts": [],
            "convergences": [],
            "upside_summary": "No API key configured.",
            "catch_summary": "Set DEEPSEEK_API_KEY to enable analysis.",
            "bet_lean": "Monitor Only",
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
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=2500,
            timeout=30,
        )
        content = response.choices[0].message.content
        result = json.loads(_clean_json(content))
        result["_mode"] = "disagreement_engine"

        # Validate Chain-of-Thought reasoning trace
        trace = result.get("reasoning_trace")
        if not trace or not isinstance(trace, list) or len(trace) < 4:
            result["_missing_trace"] = True
            result["_mode"] = "disagreement_engine (no CoT)"
        else:
            # Check if proves/cannot_prove are present per source
            has_proves = any("proves" in t for t in trace)
            result["_has_trace"] = len(trace)
            if not has_proves:
                result["_missing_proves"] = True

        cache[trend_id] = result
        _save_cache(cache)
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


# ─── Prompt Formatting Helpers ───

def _format_meta_ads(meta_ads_data):
    """Format Meta Ads competitor data for the LLM prompt."""
    if not meta_ads_data:
        return "No Meta Ads data available for this trend."

    competitors = meta_ads_data.get("competitors_backing_this_trend", [])
    if not competitors:
        return f"No competitors currently running ads for this trend. Ad conviction: {meta_ads_data.get('ad_conviction', 'unknown')}."

    lines = [
        f"Ad conviction: {meta_ads_data.get('ad_conviction', 'unknown')} "
        f"({meta_ads_data.get('competitor_count', 0)} competitors actively advertising)"
    ]
    for c in competitors:
        strength = c.get("signal_strength", "emerging")
        lines.append(
            f"- {c.get('brand', '?')}: {c.get('product', '?')} @ ₹{c.get('price', 0)} — "
            f"{c.get('ad_running_days', 0)} days running ({strength} signal). "
            f"Fabric: {c.get('fabric', 'unknown')}, Silhouette: {c.get('silhouette', 'unknown')}"
        )
    return "\n".join(lines)


def _format_social(social_data):
    """Format YouTube social buzz data for the LLM prompt."""
    if not social_data:
        return "No YouTube social buzz data available for this trend."

    haul_count = social_data.get("hauls_in_last_30d", 0)
    affiliate = social_data.get("affiliate_link_density", 0)
    creators = social_data.get("unique_creators", 0)
    buzz = social_data.get("social_buzz_level", "unknown")

    if haul_count == 0 and creators == 0:
        return f"No YouTube haul videos found for this trend in the last 30 days. Social buzz: {buzz}."

    return (
        f"Social buzz level: {buzz}. "
        f"{haul_count} haul videos found in last 30 days from {creators} unique creators. "
        f"Affiliate link density: {affiliate} links/video. "
        f"{'High affiliate density suggests strong monetization intent from creators — product may be commercially viable.' if affiliate >= 1.0 else 'Low affiliate density — creators may be featuring organically, not commercially.'}"
    )
