"""
Google Trends — 12-Month Historical Cache
------------------------------------------
Fetches 12-month rolling search interest from Google Trends (pytrends)
for India (geo="IN"). Stores weekly values + computes monthly aggregates,
seasonality detection, year trajectory, and momentum scoring.

Includes seed_historical_cache() to pre-populate 12-month data for all
kurti search terms — so the Decision Board always has historical context.

Usage:
    from sources.google_trends import fetch_google_trends, seed_historical_cache
    data = fetch_google_trends(["chanderi kurti"], timeframe="today 12-m")
    seed_historical_cache()  # fetches all 15 kurti terms in batches
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "google_trends_cache.json"

# All kurti search terms we track — batched in groups of 5 (pytrends limit)
KURTI_TERMS = [
    "chanderi kurti", "organza kurti", "block print kurti", "ajrakh kurti", "bandhani kurti",
    "ikat kurti", "linen kurti", "palazzo kurti set", "cotton kurti", "anarkali kurti",
    "straight kurti", "chikankari kurti", "mirror work kurti", "kota doria kurti", "kalamkari kurti",
]

KURTI_TERM_BATCHES = [KURTI_TERMS[i:i+5] for i in range(0, len(KURTI_TERMS), 5)]


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def fetch_google_trends(search_terms, geo="IN", timeframe="today 12-m",
                        use_cache=True):
    """Fetch Google Trends interest for search terms. Returns enriched data
    with 12-month trajectory, monthly aggregates, and seasonality flag."""
    cache = load_cache()
    cache_key = "|".join(sorted(search_terms))

    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        return {
            "source": "google_trends",
            "live": False,
            "cached_at": cached.get("cached_at", ""),
            "interest_data": cached.get("interest_data", {}),
            "trend_direction": cached.get("trend_direction", "unknown"),
            "momentum_score": cached.get("momentum_score", 0),
            "year_trajectory": cached.get("year_trajectory", "unknown"),
            "avg_12m": cached.get("avg_12m", {}),
        }

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-IN", tz=330)
        pytrends.build_payload(search_terms, cat=0, timeframe=timeframe, geo=geo)

        interest_df = pytrends.interest_over_time()
        interest_data = {}

        if not interest_df.empty:
            for term in search_terms:
                if term in interest_df.columns:
                    values = interest_df[term].dropna()
                    if not values.empty:
                        all_vals = [int(v) for v in values.tolist()]
                        weeks = len(all_vals)

                        # Monthly aggregates (group ~4 weeks per month)
                        monthly = _to_monthly(all_vals)

                        # 12-month trajectory
                        trajectory = _compute_trajectory(monthly)

                        # Current vs year baseline
                        current = all_vals[-1] if all_vals else 0
                        recent_4w = all_vals[-4:] if len(all_vals) >= 4 else all_vals
                        older_4w = all_vals[-8:-4] if len(all_vals) >= 8 else all_vals[:4] if len(all_vals) >= 4 else [1]
                        recent_mean = sum(recent_4w) / max(len(recent_4w), 1)
                        older_mean = sum(older_4w) / max(len(older_4w), 1)
                        growth_8w = round(((recent_mean - older_mean) / max(older_mean, 1)) * 100, 1)

                        year_max = max(all_vals) if all_vals else 1
                        year_avg = sum(all_vals) / max(len(all_vals), 1)

                        interest_data[term] = {
                            "current": current,
                            "peak": int(year_max),
                            "avg_12m": round(year_avg, 1),
                            "current_vs_peak_pct": round(current / max(year_max, 1) * 100, 0),
                            "current_vs_avg_pct": round(current / max(year_avg, 1) * 100, 0),
                            "direction": "rising" if growth_8w >= 10 else "falling" if growth_8w <= -10 else "stable",
                            "growth_8w_pct": growth_8w,
                            "monthly_values": monthly,
                            "weekly_values": all_vals[-12:] if weeks >= 12 else all_vals,
                            "year_trajectory": trajectory["label"],
                            "seasonality_detected": trajectory["seasonal"],
                            "peak_month": trajectory["peak_month"],
                            "trough_month": trajectory["trough_month"],
                            "volatility": trajectory["volatility"],
                            "weeks_of_data": weeks,
                        }

        # Aggregate direction across all terms
        direction_scores = {"rising": 1, "stable": 0, "falling": -1}
        directions = [d["direction"] for d in interest_data.values()] if interest_data else []
        trend_direction = (
            "rising" if sum(direction_scores.get(d, 0) for d in directions) > 0
            else "falling" if sum(direction_scores.get(d, 0) for d in directions) < 0
            else "mixed"
        )

        # Overall momentum
        momentums = [d.get("growth_8w_pct", 0) for d in interest_data.values()]
        momentum = round(sum(momentums) / max(len(momentums), 1), 1) if momentums else 0

        avg_12m = {
            term: d["avg_12m"] for term, d in interest_data.items()
        }

        result = {
            "source": "google_trends",
            "live": True,
            "cached_at": datetime.now().isoformat(),
            "timeframe": timeframe,
            "interest_data": interest_data,
            "trend_direction": trend_direction,
            "momentum_score": momentum,
            "year_trajectory": trend_direction,
            "avg_12m": avg_12m,
        }

        # Save enriched cache
        cache[cache_key] = {
            "cached_at": datetime.now().isoformat(),
            "timeframe": timeframe,
            "interest_data": interest_data,
            "trend_direction": trend_direction,
            "momentum_score": momentum,
            "year_trajectory": trend_direction,
            "avg_12m": avg_12m,
        }
        save_cache(cache)
        return result

    except Exception as e:
        if cache_key in cache:
            cached = cache[cache_key]
            return {
                "source": "google_trends",
                "live": False,
                "cached_at": cached.get("cached_at", ""),
                "interest_data": cached.get("interest_data", {}),
                "trend_direction": cached.get("trend_direction", "unknown"),
                "momentum_score": cached.get("momentum_score", 0),
                "year_trajectory": cached.get("year_trajectory", "unknown"),
                "avg_12m": cached.get("avg_12m", {}),
                "fallback_used": True,
                "error": str(e)[:80],
            }
        return {
            "source": "google_trends",
            "live": False,
            "interest_data": {},
            "trend_direction": "unknown",
            "momentum_score": 0,
            "year_trajectory": "unknown",
            "avg_12m": {},
            "fallback_used": True,
            "error": str(e)[:80],
        }


def seed_historical_cache(force_refresh=False):
    """
    Pre-fetch 12-month Google Trends data for all 15 kurti terms.
    Called at app startup. Runs in batches of 5 to avoid pytrends rate limits.
    Skips terms already in cache unless force_refresh=True.
    """
    cache = load_cache()
    fetched = 0
    skipped = 0

    for batch_idx, batch in enumerate(KURTI_TERM_BATCHES):
        cache_key = "|".join(sorted(batch))
        if not force_refresh and cache_key in cache:
            cached = cache[cache_key]
            age = datetime.now() - datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
            if age.days < 7:
                skipped += len(batch)
                continue

        try:
            fetch_google_trends(batch, geo="IN", timeframe="today 12-m",
                               use_cache=False)
            fetched += len(batch)
        except Exception as e:
            print(f"  ⚠️ Trends batch {batch_idx+1}: {str(e)[:60]}")
            skipped += len(batch)

        # Rate-limit pause between batches
        if batch_idx < len(KURTI_TERM_BATCHES) - 1:
            import time
            time.sleep(2)

    print(f"  📊 Trends cache: {fetched} terms fetched, {skipped} skipped (already cached)")
    return fetched


def get_historical_trends():
    """
    Return all cached historical trend data, keyed by individual term.
    Useful for the Decision Board to show year-long patterns.
    """
    cache = load_cache()
    results = {}

    for cache_key, data in cache.items():
        interest = data.get("interest_data", {})
        for term, tdata in interest.items():
            results[term] = {
                "current": tdata.get("current", 0),
                "peak": tdata.get("peak", 0),
                "avg_12m": tdata.get("avg_12m", 0),
                "direction": tdata.get("direction", "stable"),
                "growth_8w_pct": tdata.get("growth_8w_pct", 0),
                "monthly_values": tdata.get("monthly_values", []),
                "year_trajectory": tdata.get("year_trajectory", "unknown"),
                "seasonality": tdata.get("seasonality_detected", False),
                "peak_month": tdata.get("peak_month", 0),
                "current_vs_peak_pct": tdata.get("current_vs_peak_pct", 0),
                "current_vs_avg_pct": tdata.get("current_vs_avg_pct", 0),
                "volatility": tdata.get("volatility", "low"),
                "cached_at": data.get("cached_at", ""),
            }

    return results


# ─── Internal Helpers ───

def _to_monthly(weekly_values: list) -> list:
    """Group weekly values into ~12 monthly buckets (4 weeks each)."""
    monthly = []
    bucket_size = max(1, len(weekly_values) // 12) if len(weekly_values) >= 12 else 1
    for i in range(0, len(weekly_values), bucket_size):
        chunk = weekly_values[i:i + bucket_size]
        monthly.append(round(sum(chunk) / len(chunk), 1))
    return monthly[-12:]  # keep last 12 months


def _compute_trajectory(monthly: list) -> dict:
    """Analyze 12-month pattern for trajectory, seasonality, and volatility."""
    if len(monthly) < 3:
        return {"label": "unknown", "seasonal": False, "peak_month": 0,
                "trough_month": 0, "volatility": "low"}

    first_half = monthly[:len(monthly)//2]
    second_half = monthly[len(monthly)//2:]

    first_avg = sum(first_half) / max(len(first_half), 1)
    second_avg = sum(second_half) / max(len(second_half), 1)

    if first_avg < 1 and second_avg < 1:
        trajectory = "flat"
    elif second_avg > first_avg * 1.15:
        trajectory = "rising"
    elif second_avg < first_avg * 0.85:
        trajectory = "declining"
    else:
        trajectory = "stable"

    # Detect seasonality: does the pattern repeat?
    seasonal = False
    if len(monthly) >= 8:
        peaks = []
        for i in range(2, len(monthly) - 2):
            if monthly[i] > monthly[i-1] and monthly[i] > monthly[i+1]:
                peaks.append(i)
        if len(peaks) >= 2 and max(peaks) - min(peaks) >= 3:
            seasonal = True

    peak_idx = monthly.index(max(monthly)) if monthly else 0
    trough_idx = monthly.index(min(monthly)) if monthly else 0

    # Volatility: std dev / mean
    mean = sum(monthly) / max(len(monthly), 1)
    variance = sum((m - mean) ** 2 for m in monthly) / max(len(monthly), 1)
    std_dev = variance ** 0.5
    cv = std_dev / max(mean, 1)
    if cv > 0.5:
        volatility = "high"
    elif cv > 0.25:
        volatility = "medium"
    else:
        volatility = "low"

    return {
        "label": trajectory,
        "seasonal": seasonal,
        "peak_month": peak_idx + 1,
        "trough_month": trough_idx + 1,
        "volatility": volatility,
    }
