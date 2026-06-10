"""
Marketplace Parser — Noise-Cleaned Data Wrapper
-------------------------------------------------
Wraps sources/marketplace.get_marketplace_data() and pipes all products
through the noise-cleaning filters before returning.

Usage:
    from signals.marketplace_parser import get_clean_marketplace_data
    clean_data = get_clean_marketplace_data("chanderi-straight")
"""

from pathlib import Path
from sources.marketplace import get_marketplace_data
from signals.noise_cleaner import apply_all_filters

DATA_DIR = Path(__file__).parent.parent / "data"


def get_clean_marketplace_data(trend_id: str,
                                social_buzz_high: bool = False,
                                avg_price: float = 0) -> dict:
    """
    Fetch marketplace data through the noise-cleaning pipeline.

    Returns enriched dict with:
      - noise_summary: aggregate noise verdict
      - price_buzz_gap: Aesthetic Trap / Mass Market Conversion flags
      - noise_flags per product
      - All original fields preserved
    """
    raw = get_marketplace_data(trend_id)
    products = raw.get("products_found", [])

    if not products:
        return {**raw, "noise_summary": {"verdict": "NO DATA",
                                          "flags": []},
                "price_buzz_gap": {"price_buzz_gap_flag": None,
                                   "price_buzz_rationale": ""},
                "_cleaned": True, "_cleaned_by": "marketplace_parser"}

    cleaned = apply_all_filters(products, social_buzz_high, avg_price)

    recalc = _recalc_metrics(cleaned["products"], raw)

    return {
        **raw,
        "products_found": cleaned["products"],
        "noise_summary": cleaned["noise_summary"],
        "price_buzz_gap": cleaned["price_buzz_gap"],
        "avg_rank": recalc.get("avg_rank", raw.get("avg_rank", 0)),
        "review_velocity_30d": recalc.get("adjusted_velocity",
                                          raw.get("review_velocity_30d", 0)),
        "discount_distortion_risk": recalc.get("discount_risk",
                                               raw.get("discount_distortion_risk",
                                                      "unknown")),
        "_cleaned": True,
        "_cleaned_by": "marketplace_parser",
    }


def _recalc_metrics(cleaned_products: list, raw: dict) -> dict:
    """Recompute summary metrics using noise-adjusted values."""
    if not cleaned_products:
        return {}

    total_rank = 0
    total_velocity = 0
    valid_count = 0

    for p in cleaned_products:
        rank = p.get("rank", 99)
        weight = p.get("rank_weight_multiplier", 1.0)
        total_rank += rank * (1.0 / max(weight, 0.01))
        total_velocity += p.get("review_velocity_adjusted",
                                p.get("review_velocity_30d", 0))
        valid_count += 1

    avg_rank = round(total_rank / max(valid_count, 1), 1)
    adj_velocity = total_velocity

    high_discount = any(
        "Subsidized Liquidation" in p.get("noise_flags", [])
        for p in cleaned_products
    )

    return {
        "avg_rank": avg_rank,
        "adjusted_velocity": adj_velocity,
        "discount_risk": "high" if high_discount else "low",
    }
