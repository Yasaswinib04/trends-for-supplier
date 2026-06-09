"""
Standardized ingestion payload normalizer.

No matter where data comes from (Google Trends, Meesho, Nykaa), it gets
normalized into the strict JSON schema required by the synthesis engine:
  - source_name: str
  - signal_strength: float (0-1)
  - distortion_flag: bool
  - last_updated: str (ISO timestamp)
"""

from datetime import datetime, timedelta


STALENESS_THRESHOLD_HOURS = 72


def normalize_source(source_data):
    """Convert any source module output into the standardized payload."""
    source_name = source_data.get("source", "unknown")

    normalizers = {
        "google_trends": _normalize_google_trends,
        "meta_ad_library": _normalize_meta_ads,
        "marketplace": _normalize_marketplace,
        "meesho": _normalize_meesho,
        "nykaa": _normalize_nykaa,
        "reviews": _normalize_reviews,
    }

    normalizer = normalizers.get(source_name, _normalize_generic)
    result = normalizer(source_data)
    result["source_name"] = source_name
    return result


def _normalize_google_trends(data):
    momentum = data.get("momentum_score", 0)
    signal = min(1.0, max(0.0, momentum))
    has_error = bool(data.get("error"))
    return {
        "signal_strength": round(signal, 2),
        "distortion_flag": has_error or data.get("fallback_used", False),
        "last_updated": data.get("cached_at", ""),
    }


def _normalize_meta_ads(data):
    conviction = data.get("ad_conviction", "low")
    strength_map = {"high": 0.85, "medium": 0.55, "low": 0.15}
    signal = strength_map.get(conviction, 0.15)
    return {
        "signal_strength": signal,
        "distortion_flag": False,
        "last_updated": data.get("last_updated", ""),
    }


def _normalize_marketplace(data):
    presence = data.get("marketplace_presence", "absent")
    discount_risk = data.get("discount_distortion_risk", "high")
    presence_map = {"strong": 0.8, "moderate": 0.5, "weak": 0.25, "absent": 0.0}
    signal = presence_map.get(presence, 0.0)
    # Penalize if discount distortion
    if discount_risk == "high":
        signal *= 0.6
    return {
        "signal_strength": round(signal, 2),
        "distortion_flag": discount_risk == "high",
        "last_updated": data.get("last_updated", ""),
    }


def _normalize_meesho(data):
    presence = data.get("meesho_presence", "absent")
    presence_map = {"strong": 0.85, "emerging": 0.55, "weak": 0.25, "absent": 0.0}
    signal = presence_map.get(presence, 0.0)
    # Boost for acceleration
    if data.get("reseller_growth_accelerating"):
        signal = min(1.0, signal + 0.1)
    return {
        "signal_strength": round(signal, 2),
        "distortion_flag": data.get("price_sensitivity_flag") == "high",
        "last_updated": data.get("last_updated", ""),
    }


def _normalize_nykaa(data):
    presence = data.get("nykaa_presence", "absent")
    full_price = data.get("full_price_products", 0)
    presence_map = {"strong": 0.8, "emerging": 0.45, "absent": 0.0}
    signal = presence_map.get(presence, 0.0)
    # Boost for full-price validation
    if full_price >= 2:
        signal = min(1.0, signal + 0.15)
    return {
        "signal_strength": round(signal, 2),
        "distortion_flag": False,
        "last_updated": data.get("last_updated", ""),
    }


def _normalize_reviews(data):
    if not data.get("available"):
        return {
            "signal_strength": 0.0,
            "distortion_flag": False,
            "last_updated": data.get("last_updated", ""),
        }
    positive = data.get("sentiment", {}).get("positive", 0)
    total = data.get("total_analyzed", 0)
    signal = positive * min(1.0, total / 30)  # Scale by sample size
    return {
        "signal_strength": round(min(1.0, signal), 2),
        "distortion_flag": total < 15,
        "last_updated": data.get("last_updated", ""),
    }


def _normalize_generic(data):
    return {
        "signal_strength": 0.0,
        "distortion_flag": True,
        "last_updated": data.get("last_updated", ""),
    }


def check_staleness(last_updated, threshold_hours=STALENESS_THRESHOLD_HOURS):
    """Return True if the data is older than threshold_hours."""
    if not last_updated:
        return True
    try:
        if "T" in str(last_updated):
            dt = datetime.fromisoformat(str(last_updated).replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(str(last_updated), "%Y-%m-%d")
        cutoff = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return (cutoff - dt) > timedelta(hours=threshold_hours)
    except (ValueError, TypeError):
        return True
