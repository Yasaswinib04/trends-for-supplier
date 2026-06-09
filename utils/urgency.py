"""
Urgency scoring engine for the Triage Inbox.

Computes a composite urgency score for each trend by running all 6 sources
and weighting their signals. Higher urgency = trend needs attention sooner.

Weights:
  - Google Trends momentum change:  0.25
  - Meta Ad spend / ad duration:    0.20
  - Meesho reseller acceleration:   0.20
  - Marketplace rank velocity:      0.15
  - Nykaa full-price products:      0.10
  - Data staleness penalty:         0.10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.google_trends import fetch_google_trends
from sources.meta_ads import get_meta_ad_signals
from sources.marketplace import get_marketplace_data
from sources.meesho import get_meesho_data
from sources.nykaa import get_nykaa_data
from sources.reviews import get_review_signals
from utils.normalize import normalize_source, check_staleness


def compute_urgency(trend):
    """
    Compute urgency score (0-100) for a single trend.
    Returns dict with score, status, micro_context, and source data.
    """
    trend_id = trend["id"]

    # Fetch all 6 sources
    trends_data = fetch_google_trends(trend.get("search_terms", []), use_cache=True)
    meta_data = get_meta_ad_signals(trend_id)
    marketplace_data = get_marketplace_data(trend_id)
    meesho_data = get_meesho_data(trend_id)
    nykaa_data = get_nykaa_data(trend_id)
    review_data = get_review_signals(trend_id)

    all_sources = {
        "google_trends": trends_data,
        "meta_ads": meta_data,
        "marketplace": marketplace_data,
        "meesho": meesho_data,
        "nykaa": nykaa_data,
        "reviews": review_data,
    }

    # Normalize each source
    normalized = {}
    for key, data in all_sources.items():
        normalized[key] = normalize_source(data)

    # --- Compute weighted urgency score ---
    score = 0.0

    # Google Trends momentum (0.25 weight)
    gt_momentum = trends_data.get("momentum_score", 0)
    gt_signal = min(1.0, max(0.0, gt_momentum * 2.0))  # Scale: 0.5 momentum → 1.0 urgency
    score += gt_signal * 25

    # Meta Ad signals (0.20 weight)
    competitors = meta_data.get("competitors_backing_this_trend", [])
    max_ad_days = max((c.get("ad_running_days", 0) for c in competitors), default=0)
    competitor_count = len(competitors)
    meta_signal = min(1.0, (competitor_count * 0.3) + (max_ad_days / 45))
    score += meta_signal * 20

    # Meesho reseller acceleration (0.20 weight)
    meesho_accel = meesho_data.get("reseller_growth_accelerating", False)
    meesho_units = meesho_data.get("total_units_sold", 0)
    meesho_signal = 0.0
    if meesho_accel:
        meesho_signal = 0.8
    if meesho_units >= 5000:
        meesho_signal = min(1.0, meesho_signal + 0.3)
    elif meesho_units >= 1000:
        meesho_signal = min(1.0, meesho_signal + 0.15)
    score += meesho_signal * 20

    # Marketplace velocity (0.15 weight)
    mkt_velocity = marketplace_data.get("review_velocity_30d", 0)
    mkt_presence = marketplace_data.get("marketplace_presence", "absent")
    mkt_signal = min(1.0, mkt_velocity / 150)
    if mkt_presence == "strong":
        mkt_signal = min(1.0, mkt_signal + 0.2)
    score += mkt_signal * 15

    # Nykaa full-price (0.10 weight)
    nk_full = nykaa_data.get("full_price_products", 0)
    nk_editorial = nykaa_data.get("editorial_featured_count", 0)
    nk_signal = min(1.0, (nk_full * 0.3) + (nk_editorial * 0.2))
    score += nk_signal * 10

    # Staleness penalty (0.10 weight — reduces score if data is stale)
    stale_count = sum(
        1 for n in normalized.values()
        if check_staleness(n.get("last_updated", ""))
    )
    freshness_signal = max(0.0, 1.0 - (stale_count * 0.2))
    score += freshness_signal * 10

    score = min(100, max(0, round(score, 1)))

    # Classify status
    status = classify_status(score)

    # Generate micro-context
    micro_context = generate_micro_context(trend, all_sources, normalized)

    return {
        "urgency_score": score,
        "status": status,
        "micro_context": micro_context,
        "source_data": all_sources,
        "normalized": normalized,
        "stale_count": stale_count,
    }


def classify_status(urgency_score):
    """Map urgency score to status badge."""
    if urgency_score >= 65:
        return "CRITICAL DECISION"
    elif urgency_score >= 35:
        return "EMERGING"
    else:
        return "MONITOR"


STATUS_EMOJI = {
    "CRITICAL DECISION": "🔴",
    "EMERGING": "🟡",
    "MONITOR": "🟢",
}


def generate_micro_context(trend, sources, normalized):
    """Generate a one-sentence dynamic summary of the top risk/opportunity."""
    parts = []

    # Margin risk assessment
    mkt = sources.get("marketplace", {})
    discount_risk = mkt.get("discount_distortion_risk", "low")
    if discount_risk == "high":
        parts.append("Margin Risk: High")
    else:
        parts.append("Margin Risk: Low")

    # Top issue/opportunity
    gt_momentum = sources.get("google_trends", {}).get("momentum_score", 0)
    meesho_accel = sources.get("meesho", {}).get("reseller_growth_accelerating", False)
    nykaa_presence = sources.get("nykaa", {}).get("nykaa_presence", "absent")
    meta_conviction = sources.get("meta_ads", {}).get("ad_conviction", "low")

    issues = []
    if gt_momentum > 0.3:
        issues.append(f"Search spike +{gt_momentum:.0%}")
    if meesho_accel:
        issues.append("Reseller growth accelerating")
    if nykaa_presence == "absent":
        issues.append("No premium validation")
    if meta_conviction == "high":
        issues.append("Competitors spending heavily")
    if discount_risk == "high":
        issues.append("Discount distortion on marketplace")

    # Check staleness
    stale_sources = [
        k for k, v in normalized.items()
        if check_staleness(v.get("last_updated", ""))
    ]
    if len(stale_sources) >= 3:
        issues.append(f"{len(stale_sources)} sources stale (>72h)")

    if issues:
        parts.append(f"Issue: {issues[0]}")
    else:
        parts.append("No urgent flags")

    return " | ".join(parts)


def compute_all_urgencies(trends):
    """Compute urgency for all trends and return sorted list."""
    results = []
    for trend in trends:
        urgency = compute_urgency(trend)
        results.append({
            "trend": trend,
            **urgency,
        })
    results.sort(key=lambda x: x["urgency_score"], reverse=True)
    return results
