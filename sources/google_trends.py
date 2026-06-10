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

# Time window presets
WINDOW_MAP = {
    "1M": "today 1-m",
    "3M": "today 3-m",
    "6M": "today 6-m",
    "YTD": None,  # computed dynamically
    "1Y": "today 12-m",
    "2Y": "today 24-m",
}

# Festive season date ranges (Indian retail calendar)
# Window: 14 days before + 3 days after each festival date
# Uses actual known dates for 2025 and 2026 festivals

def _festive_range(festive_id):
    """Return ranges for a festive season."""
    known = {
        "diwali": {
            "2025": "2025-10-20",
            "label": "Diwali",
        },
        "holi": {
            "2026": "2026-03-04",
            "2025": "2025-03-14",
            "label": "Holi",
        },
        "ramadan": {
            "2026": "2026-03-20",
            "2025": "2025-03-30",
            "label": "Ramadan / Eid",
        },
        "summer": {
            "2025": "2025-04-01",
            "label": "Summer Vacation",
        },
    }

    info = known.get(festive_id)
    if not info:
        return None

    label = info["label"]

    def window(date_str):
        """Return 'YYYY-MM-DD YYYY-MM-DD' for 14d before to 3d after."""
        from datetime import datetime, timedelta
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        start = (dt - timedelta(days=14)).strftime("%Y-%m-%d")
        end = (dt + timedelta(days=3)).strftime("%Y-%m-%d")
        return f"{start} {end}"

    # Build this_year and last_year based on what's available
    now = datetime.now()
    year = now.year
    ly = year - 1

    range_this = None
    range_last = None

    # Try this year's date (e.g., Holi 2026)
    if str(year) in info and info[str(year)]:
        range_this = window(info[str(year)])

    # Try last year's date
    if str(ly) in info and info[str(ly)]:
        range_last = window(info[str(ly)])

    # Fallback: if only one date known, use it as last_year
    if not range_last:
        for y, d in info.items():
            if y.isdigit():
                range_last = window(d)
                break

    return {
        "range_this": range_this,
        "range_last": range_last,
        "label": label,
    }


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
    cache_key = f"{timeframe}|{'|'.join(sorted(search_terms))}"

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
    Uses a single TrendReq connection to minimize rate-limiting.
    Skips terms already in cache unless force_refresh=True.
    """
    import time

    cache = load_cache()
    fetched = 0
    skipped = 0

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-IN", tz=330)
        time.sleep(2)
    except Exception:
        pytrends = None

    for batch_idx, batch in enumerate(KURTI_TERM_BATCHES):
        timeframe = "today 12-m"
        cache_key = f"{timeframe}|{'|'.join(sorted(batch))}"

        if not force_refresh and cache_key in cache:
            cached = cache[cache_key]
            age = datetime.now() - datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
            if age.days < 7:
                skipped += len(batch)
                continue

        if pytrends is None:
            skipped += len(batch)
            continue

        try:
            time.sleep(8)  # generous gap between batches
            pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo="IN")
            interest_df = pytrends.interest_over_time()

            if interest_df.empty:
                skipped += len(batch)
                continue

            # Call fetch_google_trends with use_cache=False to force fresh store
            result = fetch_google_trends(batch, geo="IN", timeframe=timeframe,
                                          use_cache=False)
            interest = result.get("interest_data", {})
            has_data = any(td.get("current", 0) > 0 for td in interest.values())

            if has_data:
                fetched += len([t for t in batch if t in interest])
            else:
                skipped += len(batch)

        except Exception as e:
            print(f"  \u26a0\ufe0f Trends batch {batch_idx+1}: {str(e)[:60]}")
            skipped += len(batch)

    print(f"  \U0001f4ca Trends cache: {fetched} terms fetched, {skipped} skipped (cached/error)")
    return fetched


def get_historical_trends():
    """
    Return all cached historical trend data, keyed by individual term.
    Falls back to static historical_trends_fallback.json when cache is empty.
    """
    cache = load_cache()
    results = {}

    for cache_key, data in cache.items():
        interest = data.get("interest_data", {})
        for term, tdata in interest.items():
            results[term] = _extract_term_data(term, tdata, data)

    if not results:
        results = _load_fallback_trends()

    return results


def _load_fallback_trends():
    """Load realistic static trend data when pytrends is unavailable."""
    fallback_file = DATA_DIR / "historical_trends_fallback.json"
    if fallback_file.exists():
        with open(fallback_file) as f:
            static = json.load(f)
        out = {}
        for term, td in static.items():
            out[term] = {
                "current": td.get("current", 0),
                "peak": td.get("peak", 0),
                "avg_12m": td.get("avg_12m", 0),
                "direction": td.get("direction", "stable"),
                "growth_8w_pct": td.get("growth_8w_pct", 0),
                "monthly_values": td.get("monthly_values", []),
                "year_trajectory": td.get("year_trajectory", "unknown"),
                "seasonality": td.get("seasonality_detected", False),
                "peak_month": td.get("peak_month", 0),
                "current_vs_peak_pct": td.get("current_vs_peak_pct", 0),
                "current_vs_avg_pct": td.get("current_vs_avg_pct", 0),
                "volatility": td.get("volatility", "low"),
                "weekly_values": td.get("weekly_values", []),
                "cached_at": td.get("cached_at", ""),
                "_fallback": True,
            }
        return out
    return {}


def _extract_term_data(term, tdata, source_data):
    return {
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
        "weekly_values": tdata.get("weekly_values", []),
        "cached_at": source_data.get("cached_at", ""),
    }


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


def fetch_timeframe_trends(terms, window="1Y", geo="IN", use_cache=True):
    """
    Fetch Google Trends for a specific time window or festive season.

    Args:
        terms: list of search terms
        window: "1M" | "3M" | "6M" | "YTD" | "1Y" | "2Y"
                or festive preset: "holi" | "ramadan" | "diwali" | "wedding" | "summer" | "navratri"
        geo: country code (default "IN")
        use_cache: use cached results if available

    Returns:
        Same format as fetch_google_trends, plus window metadata.
    """
    if window in WINDOW_MAP:
        if window == "YTD":
            now = datetime.now()
            timeframe = f"{now.year}-01-01 {now.strftime('%Y-%m-%d')}"
            label = "Year to Date"
        else:
            timeframe = WINDOW_MAP[window]
            label = window

        result = fetch_google_trends(terms, geo=geo, timeframe=timeframe,
                                      use_cache=True)
        result["window"] = window
        result["window_label"] = label
        return result

    # Festive season preset
    festive = _festive_range(window)
    if festive:
        result = fetch_google_trends(terms, geo=geo,
                                      timeframe=festive["range_this"],
                                      use_cache=use_cache)
        result["window"] = window
        result["window_label"] = festive["label"]
        result["date_range"] = festive["range_this"]
        return result

    # Fallback to 1Y
    result = fetch_google_trends(terms, geo=geo, timeframe="today 12-m",
                                  use_cache=use_cache)
    result["window"] = "1Y"
    result["window_label"] = "Last 12 Months"
    return result


def get_festive_comparison(terms, festive_id, geo="IN"):
    """
    Compare this year's festive season search data vs. last year's same period.

    Returns:
        dict with this_year (if available), last_year, and comparison metrics.
    """
    festive = _festive_range(festive_id)
    if not festive:
        return {"error": f"Unknown festive preset: {festive_id}"}

    result = {}

    if festive.get("range_this"):
        try:
            ty = fetch_google_trends(terms, geo=geo, timeframe=festive["range_this"],
                                      use_cache=True)
            result["this_year"] = {
                "period": festive["range_this"],
                "label": festive["label"],
                "year": datetime.now().year,
                "interest": {},
            }
            interest = ty.get("interest_data", {})
            if not interest:
                result["this_year"]["note"] = "Using estimated trend data (pytrends unavailable)"
                interest = _estimate_window_interest(terms, festive["range_this"])
            for term, td in interest.items():
                vals = td.get("weekly_values", [])
                result["this_year"]["interest"][term] = {
                    "avg": round(sum(vals) / max(len(vals), 1), 1) if vals else 0,
                    "peak": int(td.get("peak", 0)),
                    "trend": td.get("direction", "stable"),
                }
        except Exception as e:
            result["this_year"] = {"error": str(e)[:80], "note": "Using estimated data"}
            result["this_year"]["interest"] = _estimate_window_interest(terms, festive["range_this"])

    if festive.get("range_last"):
        try:
            ly = fetch_google_trends(terms, geo=geo, timeframe=festive["range_last"],
                                      use_cache=True)
            result["last_year"] = {
                "period": festive["range_last"],
                "label": festive["label"],
                "year": datetime.now().year - 1,
                "interest": {},
            }
            interest = ly.get("interest_data", {})
            if not interest:
                result["last_year"]["note"] = "Using estimated trend data (pytrends unavailable)"
                interest = _estimate_window_interest(terms, festive["range_last"])
            for term, td in interest.items():
                vals = td.get("weekly_values", [])
                result["last_year"]["interest"][term] = {
                    "avg": round(sum(vals) / max(len(vals), 1), 1) if vals else 0,
                    "peak": int(td.get("peak", 0)),
                    "trend": td.get("direction", "stable"),
                }
        except Exception as e:
            result["last_year"] = {"error": str(e)[:80], "note": "Using estimated data"}
            result["last_year"]["interest"] = _estimate_window_interest(terms, festive["range_last"])

    # Compute YoY comparison (only where both exist)
    result["comparison"] = {}
    ty_interest = result.get("this_year", {}).get("interest", {})
    ly_interest = result.get("last_year", {}).get("interest", {})
    for term in set(list(ty_interest.keys()) + list(ly_interest.keys())):
        ty_avg = ty_interest.get(term, {}).get("avg", 0)
        ly_avg = ly_interest.get(term, {}).get("avg", 0)
        if ly_avg > 0:
            yoy = round(((ty_avg - ly_avg) / ly_avg) * 100, 1)
        else:
            yoy = 100.0 if ty_avg > 0 else 0.0
        result["comparison"][term] = {
            "this_year_avg": ty_avg,
            "last_year_avg": ly_avg,
            "yoy_change_pct": yoy,
        }

    return result


def _estimate_window_interest(terms, date_range):
    """Estimate search interest for a date window from fallback historical data
    when pytrends is unavailable."""
    fallback = _load_fallback_trends()
    if not fallback:
        return {}

    # Parse window months from date_range ("YYYY-MM-DD YYYY-MM-DD")
    try:
        from datetime import datetime
        parts = date_range.split()
        start = datetime.strptime(parts[0], "%Y-%m-%d")
        end = datetime.strptime(parts[1], "%Y-%m-%d")
    except (ValueError, IndexError):
        return {}

    window_months = max(1, round((end - start).days / 30))
    result = {}

    for term_key, td in fallback.items():
        # Match by term key
        if any(t.lower() in term_key.lower() for t in terms):
            monthly = td.get("monthly_values", [])
            if not monthly:
                continue

            # Take last window_months from the data
            window = monthly[-window_months:] if monthly else []
            if window:
                result[term_key] = {
                    "current": td.get("current", 0),
                    "peak": int(td.get("peak", max(window))),
                    "avg_12m": round(sum(window) / max(len(window), 1), 1),
                    "weekly_values": td.get("weekly_values", []),
                    "direction": td.get("direction", "stable"),
                    "growth_8w_pct": td.get("growth_8w_pct", 0),
                    "monthly_values": window,
                    "year_trajectory": td.get("year_trajectory", "unknown"),
                    "seasonality_detected": td.get("seasonality", False),
                    "_estimated": True,
                }

    return result
