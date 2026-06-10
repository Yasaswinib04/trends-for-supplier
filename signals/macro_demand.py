"""
Macro Demand Signal — Rolling 7-Day Google Trends
--------------------------------------------------
Pulls real-time search interest data from Google Trends for India (geo="IN")
on a rolling 7-day window. Calculates a growth vector comparing the last 3 days
to the previous 4 days. Falls back to cached dictionary on rate-limiting.

Usage:
    from signals.macro_demand import get_macro_demand
    signals = get_macro_demand(["chanderi kurti", "organza kurti"])
"""

import json
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
CACHE_FILE = ROOT_DIR / "data" / "macro_demand_cache.json"

try:
    from pytrends.request import TrendReq
    PYTENDS_AVAILABLE = True
except ImportError:
    PYTENDS_AVAILABLE = False


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_macro_demand(search_terms: list, geo: str = "IN",
                     use_cache: bool = True) -> dict:
    """
    Fetch rolling 7-day search interest for given terms in India.

    Returns:
        dict with per-term direction, growth_vector, current_interest, and top_rising.
    """
    cache = load_cache()
    cache_key = "|".join(sorted(search_terms))

    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        return {
            "source": "macro_demand",
            "live": False,
            "cached_at": cached["cached_at"],
            "window": "7-day rolling",
            "geo": geo,
            "terms": cached["terms"],
            "overall_direction": cached.get("overall_direction", "unknown"),
            "strongest_term": cached.get("strongest_term", ""),
            "fallback": False,
        }

    if not PYTENDS_AVAILABLE:
        return _fallback_response(search_terms, cache_key, cache,
                                  "pytrends not installed")

    try:
        pytrends = TrendReq(hl="en-IN", tz=330)
        pytrends.build_payload(search_terms, cat=0, timeframe="now 7-d",
                               geo=geo)

        interest_df = pytrends.interest_over_time()
        terms_data = {}

        if not interest_df.empty:
            for term in search_terms:
                if term in interest_df.columns:
                    values = interest_df[term].dropna()
                    if not values.empty and len(values) >= 4:
                        values_list = [int(v) for v in values.tolist()]

                        last_3 = values_list[-3:]
                        prev_4 = values_list[-7:-3] if len(values_list) >= 7 else values_list[:-3]

                        last_3_mean = sum(last_3) / max(len(last_3), 1)
                        prev_4_mean = sum(prev_4) / max(len(prev_4), 1)

                        if prev_4_mean > 0:
                            growth_pct = round(
                                ((last_3_mean - prev_4_mean) / prev_4_mean) * 100, 1
                            )
                        else:
                            growth_pct = 100.0 if last_3_mean > 0 else 0.0

                        if growth_pct >= 20:
                            direction = "surging"
                        elif growth_pct >= 5:
                            direction = "rising"
                        elif growth_pct >= -5:
                            direction = "stable"
                        elif growth_pct >= -20:
                            direction = "declining"
                        else:
                            direction = "collapsing"

                        terms_data[term] = {
                            "current_interest": values_list[-1],
                            "last_3d_mean": round(last_3_mean, 1),
                            "prev_4d_mean": round(prev_4_mean, 1),
                            "growth_pct": growth_pct,
                            "direction": direction,
                            "daily_values": values_list,
                        }
                    else:
                        terms_data[term] = {
                            "current_interest": 0,
                            "direction": "insufficient data",
                            "growth_pct": 0,
                        }

        directions = [d["direction"] for d in terms_data.values() if d.get("direction")]
        direction_scores = {"surging": 2, "rising": 1, "stable": 0,
                            "declining": -1, "collapsing": -2}
        avg_direction = (
            sum(direction_scores.get(d, 0) for d in directions) / max(len(directions), 1)
        )

        if avg_direction >= 1.5:
            overall = "strongly rising"
        elif avg_direction >= 0.5:
            overall = "rising"
        elif avg_direction >= -0.5:
            overall = "stable"
        else:
            overall = "declining"

        strongest = max(terms_data.items(),
                        key=lambda x: x[1].get("growth_pct", -999)) if terms_data else ("", {})

        result = {
            "source": "macro_demand",
            "live": True,
            "cached_at": datetime.now().isoformat(),
            "window": "7-day rolling",
            "geo": geo,
            "terms": terms_data,
            "overall_direction": overall,
            "strongest_term": strongest[0],
            "fallback": False,
        }

        cache[cache_key] = {
            "cached_at": datetime.now().isoformat(),
            "terms": terms_data,
            "overall_direction": overall,
            "strongest_term": strongest[0],
        }
        save_cache(cache)

        return result

    except Exception as e:
        return _fallback_response(search_terms, cache_key, cache, str(e))


def _fallback_response(search_terms, cache_key, cache, error_msg):
    if cache_key in cache:
        cached = cache[cache_key]
        return {
            "source": "macro_demand",
            "live": False,
            "cached_at": cached["cached_at"],
            "window": "7-day rolling",
            "geo": "IN",
            "terms": cached["terms"],
            "overall_direction": cached.get("overall_direction", "unknown"),
            "strongest_term": cached.get("strongest_term", ""),
            "fallback": True,
            "fallback_reason": error_msg[:100] if error_msg else "rate limited",
        }

    return {
        "source": "macro_demand",
        "live": False,
        "window": "7-day rolling",
        "geo": "IN",
        "terms": {term: {"direction": "no data", "growth_pct": 0}
                  for term in search_terms},
        "overall_direction": "unknown",
        "strongest_term": "",
        "fallback": True,
        "fallback_reason": error_msg[:100] if error_msg else "rate limited",
    }
