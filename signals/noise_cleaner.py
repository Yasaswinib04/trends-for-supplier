"""
Noise-Cleaning Pre-Processing Layer
------------------------------------
Applied BEFORE data reaches the LLM agent. These heuristics filter out marketplace
distortions that would otherwise fool the trend engine.

All functions are non-destructive — they annotate the input data with noise tags
rather than mutating the original values.
"""


def clean_discount_distortion(products: list) -> list:
    """
    If a product's discount_percentage >= 60%, down-weight its review velocity
    multiplier to 25% and tag demand integrity as 'Subsidized Liquidation'.

    Returns enriched products list with noise flags added.
    """
    cleaned = []
    for p in products:
        discount = _parse_discount(p)
        flags = p.get("noise_flags", [])
        integrity = p.get("demand_integrity", "clean")

        if discount >= 60:
            orig_velocity = p.get("review_velocity", 0) or p.get("review_velocity_30d", 0)
            p["review_velocity_adjusted"] = int(orig_velocity * 0.25)
            p["review_velocity_multiplier"] = 0.25
            if "Subsidized Liquidation" not in flags:
                flags.append("Subsidized Liquidation")
            integrity = "Subsidized Liquidation"
        else:
            p["review_velocity_adjusted"] = p.get("review_velocity", 0) or p.get("review_velocity_30d", 0)
            p["review_velocity_multiplier"] = 1.0

        p["noise_flags"] = flags
        p["demand_integrity"] = integrity
        cleaned.append(p)
    return cleaned


def clean_sponsored_placement(products: list) -> list:
    """
    If an item's is_sponsored flag is True, tag its demand integrity as
    'Paid Visibility' and reduce its weight in algorithmic trend calculations by 50%.

    Returns enriched products list with noise flags added.
    """
    cleaned = []
    for p in products:
        flags = p.get("noise_flags", [])
        integrity = p.get("demand_integrity", "clean")

        if p.get("is_sponsored", False):
            p["rank_weight_multiplier"] = 0.5
            if "Paid Visibility" not in flags:
                flags.append("Paid Visibility")
            if integrity == "clean":
                integrity = "Paid Visibility"
            elif integrity == "Subsidized Liquidation":
                integrity = "Subsidized Liquidation + Paid Visibility"
        else:
            p["rank_weight_multiplier"] = 1.0

        p["noise_flags"] = flags
        p["demand_integrity"] = integrity
        cleaned.append(p)
    return cleaned


def clean_price_buzz_gap(social_buzz_high: bool, avg_price: float) -> dict:
    """
    Price-to-Buzz Gap Filter:
    - If social buzz (YouTube/Instagram) is high but avg price > 1800:
      flag as 'Aesthetic Trap' (visually viral but commercial risk for value-fashion).
    - If pricing sits between 399-899 with high buzz:
      flag as 'Mass Market Conversion'.
    Returns a dict with flag and rationale.
    """
    result = {
        "price_buzz_gap_flag": None,
        "price_buzz_rationale": "",
    }

    if not social_buzz_high:
        return result

    if avg_price > 1800:
        result["price_buzz_gap_flag"] = "Aesthetic Trap"
        result["price_buzz_rationale"] = (
            "Visually viral but commercial risk for value-fashion. "
            f"Average price ₹{avg_price:.0f} exceeds value customer willingness."
        )
    elif 399 <= avg_price <= 899:
        result["price_buzz_gap_flag"] = "Mass Market Conversion"
        result["price_buzz_rationale"] = (
            f"High social buzz + value price ₹{avg_price:.0f} suggests strong "
            "conversion potential for tier 2/3 buyer."
        )
    elif avg_price > 899:
        result["price_buzz_gap_flag"] = "Price Friction"
        result["price_buzz_rationale"] = (
            f"Price ₹{avg_price:.0f} is above typical mass impulse range. "
            "Buzz may not convert at scale."
        )
    else:
        result["price_buzz_gap_flag"] = "Impulse Zone"
        result["price_buzz_rationale"] = (
            f"Sub-₹399 pricing may drive volume but signals low margin."
        )

    return result


def apply_all_filters(products: list, social_buzz_high: bool = False,
                      avg_price: float = 0) -> dict:
    """
    One-call pipeline: run all three noise filters and return enriched payload.
    """
    products = clean_discount_distortion(products)
    products = clean_sponsored_placement(products)
    price_buzz_result = clean_price_buzz_gap(social_buzz_high, avg_price)

    noise_summary = _summarize_noise(products, price_buzz_result)

    return {
        "products": products,
        "noise_summary": noise_summary,
        "price_buzz_gap": price_buzz_result,
    }


def _parse_discount(product: dict) -> float:
    """Parse discount from various formats: '15%', 15, '15', 15.0."""
    discount = product.get("discount_percentage", product.get("discount", 0))
    if isinstance(discount, str):
        return float(discount.replace("%", ""))
    return float(discount)


def _summarize_noise(products: list, price_buzz: dict) -> dict:
    """Create a human-readable noise summary for the LLM prompt."""
    subsidized = sum(1 for p in products
                     if "Subsidized Liquidation" in p.get("noise_flags", []))
    sponsored = sum(1 for p in products
                    if "Paid Visibility" in p.get("noise_flags", []))
    total = len(products)

    flags_present = []
    if subsidized > 0:
        pct = int(subsidized / max(total, 1) * 100)
        flags_present.append(
            f"{subsidized}/{total} products ({pct}%) flagged as Subsidized Liquidation "
            f"(discount >= 60%). Review velocity down-weighted 75%."
        )
    if sponsored > 0:
        pct = int(sponsored / max(total, 1) * 100)
        flags_present.append(
            f"{sponsored}/{total} products ({pct}%) flagged as Paid Visibility. "
            f"Rank weight reduced 50%."
        )

    if price_buzz.get("price_buzz_gap_flag"):
        flags_present.append(
            f"Price-Buzz Gap: {price_buzz['price_buzz_gap_flag']} — "
            f"{price_buzz['price_buzz_rationale']}"
        )

    return {
        "total_products": total,
        "subsidized_liquidation_count": subsidized,
        "paid_visibility_count": sponsored,
        "clean_count": total - subsidized - sponsored,
        "flags": flags_present,
        "verdict": "HEAVILY DISTORTED" if subsidized + sponsored >= total / 2
                   else "MODERATE NOISE" if subsidized + sponsored > 0
                   else "CLEAN",
    }
