import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from pytrends.request import TrendReq

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "google_trends_cache.json"

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def fetch_google_trends(search_terms, geo="IN", timeframe="today 12-m", use_cache=True):
    cache = load_cache()
    cache_key = "|".join(sorted(search_terms))

    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        return {
            "source": "google_trends",
            "live": False,
            "cached_at": cached["cached_at"],
            "interest_data": cached["interest_data"],
            "related_queries": cached.get("related_queries", []),
            "regional_interest": cached.get("regional_interest", []),
            "trend_direction": cached.get("trend_direction", "unknown"),
            "momentum_score": cached.get("momentum_score", 0),
        }

    try:
        pytrends = TrendReq(hl="en-IN", tz=330)
        pytrends.build_payload(search_terms, cat=0, timeframe=timeframe, geo=geo)

        interest_df = pytrends.interest_over_time()
        interest_data = {}
        if not interest_df.empty:
            for term in search_terms:
                if term in interest_df.columns:
                    values = interest_df[term].dropna()
                    if not values.empty:
                        interest_data[term] = {
                            "current": int(values.iloc[-1]),
                            "peak": int(values.max()),
                            "avg_3m": round(float(values.tail(12).mean()), 1),
                            "direction": "rising" if values.iloc[-1] > values.tail(6).mean() else "falling" if values.iloc[-1] < values.tail(6).mean() else "stable",
                            "weekly_values": [int(v) for v in values.tail(8).tolist()]
                        }

        direction_scores = {"rising": 1, "stable": 0, "falling": -1}
        directions = [d["direction"] for d in interest_data.values()] if interest_data else []
        trend_direction = "rising" if sum(direction_scores.get(d, 0) for d in directions) > 0 else "falling" if sum(direction_scores.get(d, 0) for d in directions) < 0 else "mixed"

        momentum = 0
        if interest_data:
            changes = []
            for d in interest_data.values():
                wv = d.get("weekly_values", [])
                if len(wv) >= 4:
                    changes.append((wv[-1] - wv[0]) / max(wv[0], 1))
            if changes:
                momentum = sum(changes) / len(changes)
                momentum = max(0, min(1, (momentum + 0.2) / 0.8))

        result = {
            "source": "google_trends",
            "live": True,
            "cached_at": datetime.now().isoformat(),
            "interest_data": interest_data,
            "related_queries": [],
            "regional_interest": [],
            "trend_direction": trend_direction,
            "momentum_score": round(momentum, 2),
        }

        cache[cache_key] = {
            "cached_at": datetime.now().isoformat(),
            "interest_data": interest_data,
            "related_queries": [],
            "regional_interest": [],
            "trend_direction": trend_direction,
            "momentum_score": result["momentum_score"],
        }
        save_cache(cache)

        return result

    except Exception as e:
        if cache_key in cache:
            cached = cache[cache_key]
            return {
                "source": "google_trends",
                "live": False,
                "cached_at": cached["cached_at"],
                "interest_data": cached["interest_data"],
                "error": str(e),
                "trend_direction": cached.get("trend_direction", "unknown"),
                "momentum_score": cached.get("momentum_score", 0),
                "fallback_used": True,
            }
        return {
            "source": "google_trends",
            "live": False,
            "error": str(e),
            "interest_data": {},
            "trend_direction": "unknown",
            "momentum_score": 0,
            "fallback_used": True,
        }
