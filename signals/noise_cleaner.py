"""
Noise-Cleaning Pre-Processing Layer
------------------------------------
Applied BEFORE data reaches the LLM agent. These heuristics filter out marketplace
distortions that would otherwise fool the trend engine.

All functions are non-destructive — they annotate the input data with noise tags
rather than mutating the original values.

Discount Context Philosophy:
  Not all discounts are equal. A ₹499 kurti at 40% off selling 5,000 units/week
  with a 4.2 rating IS genuine demand — the discount is a volume amplifier, not a
  demand substitute. Meanwhile a ₹899 kurti at 70% off selling 200 units with a 3.1
  rating is dead stock in a clearance bin.

  This module classifies every discounted product into one of 6 contexts
  based on velocity, rating, stock pressure, and discount depth — then adjusts
  the signal weight proportionally, NOT with a single binary cutoff.
"""


def classify_discount_context(product: dict) -> dict:
    """
    Classify what the discount actually MEANS for this product based on
    the full context: velocity, rating, stock, and discount depth.

    Returns a context dict with:
      - context: label (Genuine Volume Driver, Subsidized Liquidation, etc.)
      - velocity_multiplier: how much to trust the review velocity (1.0 = full trust)
      - demand_integrity: the demand quality tag
      - rationale: 1-sentence explanation for the LLM
    """
    discount = _parse_discount(product)
    velocity = product.get("review_velocity", 0) or product.get("review_velocity_30d", 0)
    rating = product.get("avg_rating", product.get("rating", 0))
    stock = (product.get("stock_status", "") or "").lower()
    reviews = product.get("reviews", product.get("review_count", 0))
    is_low_stock = "low" in stock or "limited" in stock
    is_out_of_stock = "out" in stock

    # Velocity buckets (relative to typical kurti category on Myntra/Ajio)
    # Low: < 15/month, Medium: 15-50/month, High: > 50/month
    is_high_velocity = velocity >= 50
    is_medium_velocity = velocity >= 15
    is_low_velocity = velocity < 15

    is_good_rating = rating >= 4.0
    is_mediocre_rating = rating < 3.5
    has_significant_reviews = reviews >= 200

    # ---- CONTEXT CLASSIFICATION ----
    # Order matters — first match wins

    # 1. Dead Stock Clearance: deep discount + not selling + available stock
    if discount >= 60 and is_low_velocity and not is_low_stock:
        return {
            "context": "Dead Stock Clearance",
            "velocity_multiplier": 0.10,
            "demand_integrity": "Dead Stock Clearance",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off, {velocity} reviews/mo, "
                f"{'plentiful stock' if not is_low_stock else 'stock'}. "
                "Not selling even at deep discount. Zero demand signal."
            ),
        }

    # 2. Subsidized Liquidation: deep discount + mediocre product (not completely dead)
    if discount >= 60 and (is_mediocre_rating or not has_significant_reviews):
        return {
            "context": "Subsidized Liquidation",
            "velocity_multiplier": 0.25,
            "demand_integrity": "Subsidized Liquidation",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off, rating {rating}. "
                "Discount IS the demand — not a style signal."
            ),
        }

    # 3. End-of-Life Fast Mover: deep discount BUT high velocity + good rating = final clearance of a hit
    if discount >= 60 and is_high_velocity and is_good_rating:
        return {
            "context": "End-of-Life Fast Mover",
            "velocity_multiplier": 0.50,
            "demand_integrity": "End-of-Life Fast Mover",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off, "
                f"BUT {velocity} reviews/mo + {rating}★ + "
                f"{'low stock' if is_low_stock else 'selling out'}. "
                "Proven demand at full price first — clearing the hit. "
                "Signal: the STYLE proved itself, discount is seasonal exit."
            ),
        }

    # 4. Suspect Discount: moderate-high discount + mediocre rating + not flying
    if discount >= 40 and is_mediocre_rating and not is_high_velocity:
        return {
            "context": "Suspect Discount",
            "velocity_multiplier": 0.50,
            "demand_integrity": "Suspect Discount",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off, rating {rating}, "
                f"{velocity} reviews/mo. "
                "Discount may be the primary purchase driver — not style preference."
            ),
        }

    # 5. Genuine Volume Driver: moderate discount + high velocity + good rating
    if discount >= 30 and is_high_velocity and is_good_rating:
        return {
            "context": "Genuine Volume Driver",
            "velocity_multiplier": 1.0,
            "demand_integrity": "Genuine Volume Driver",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off, "
                f"{velocity} reviews/mo + {rating}★. "
                "Discount is accelerating a genuinely hot product — "
                "not substituting for demand. High confidence signal."
            ),
        }

    # 6. Strategic Value Pricing: low-moderate discount + good product
    if discount < 30 and is_good_rating:
        return {
            "context": "Strategic Value Pricing",
            "velocity_multiplier": 1.0,
            "demand_integrity": "Strategic Value Pricing",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off. "
                "Low discount + good rating. Price positioning is strategic, "
                "not distress-driven. Clean demand signal."
            ),
        }

    # Default / catch-all: moderate discount, moderate everything
    if discount < 60:
        return {
            "context": "Moderate Discount — Unclear Driver",
            "velocity_multiplier": 0.75,
            "demand_integrity": "Needs Closer Watch",
            "rationale": (
                f"₹{product.get('price', '?')} at {discount:.0f}% off. "
                "Mixed signals — monitor for discount dependency."
            ),
        }

    # Fallback: should rarely hit this, but treat as suspect
    return {
        "context": "Unclassified Discount",
        "velocity_multiplier": 0.50,
        "demand_integrity": "Unclassified Discount",
        "rationale": f"No clear pattern. Treat with caution.",
    }


def clean_discount_distortion(products: list) -> list:
    """
    Classify every product's discount context using multi-signal heuristics
    (velocity, rating, stock pressure, discount depth) rather than a single
    60% binary cutoff.

    Returns enriched products list with:
      - discount_context: the classified label
      - demand_integrity: the integrity tag
      - review_velocity_multiplier: 0.10 to 1.0
      - review_velocity_adjusted: velocity × multiplier
      - discount_rationale: 1-sentence explanation
    """
    cleaned = []
    for p in products:
        flags = p.get("noise_flags", [])

        context = classify_discount_context(p)

        orig_velocity = p.get("review_velocity", 0) or p.get("review_velocity_30d", 0)
        multiplier = context["velocity_multiplier"]
        p["review_velocity_adjusted"] = int(orig_velocity * multiplier)
        p["review_velocity_multiplier"] = multiplier
        p["discount_context"] = context["context"]
        p["discount_rationale"] = context["rationale"]
        p["demand_integrity"] = context["demand_integrity"]

        # Only add a noise flag if the signal is genuinely distorted
        if multiplier < 1.0:
            flag = context["context"]
            if flag not in flags:
                flags.append(flag)
        p["noise_flags"] = flags

        cleaned.append(p)
    return cleaned


def clean_sponsored_placement(products: list) -> list:
    """
    If an item's is_sponsored flag is True, tag its demand integrity as
    'Paid Visibility' and reduce its weight in algorithmic trend calculations by 50%.

    If the product already has a discount-related integrity tag, append
    ' + Paid Visibility' to create a compound label so the buyer sees
    both dimensions of noise (e.g. 'Suspect Discount + Paid Visibility').

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
            if integrity in ("clean", "Strategic Value Pricing", "Genuine Volume Driver",
                             "Moderate Discount — Unclear Driver", "Needs Closer Watch"):
                integrity = f"{integrity} + Paid Visibility" if integrity != "clean" else "Paid Visibility"
            elif "Paid Visibility" not in integrity:
                integrity = f"{integrity} + Paid Visibility"
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
    total = len(products)

    # Count each discount context type
    context_counts = {}
    for p in products:
        ctx = p.get("discount_context", "unknown")
        context_counts[ctx] = context_counts.get(ctx, 0) + 1

    dead_stock = context_counts.get("Dead Stock Clearance", 0)
    subsidized = context_counts.get("Subsidized Liquidation", 0)
    end_of_life = context_counts.get("End-of-Life Fast Mover", 0)
    suspect = context_counts.get("Suspect Discount", 0)
    genuine_volume = context_counts.get("Genuine Volume Driver", 0)
    strategic = context_counts.get("Strategic Value Pricing", 0)
    unclear = context_counts.get("Moderate Discount — Unclear Driver", 0)

    sponsored = sum(1 for p in products
                    if "Paid Visibility" in p.get("noise_flags", []))

    signals_distorted = dead_stock + subsidized + suspect
    signals_genuine = genuine_volume + strategic + end_of_life

    flags_present = []

    if genuine_volume > 0:
        flags_present.append(
            f"{genuine_volume}/{total} products: Genuine Volume Driver — discount is "
            f"accelerating a real trend, not substituting for demand. FULL signal weight."
        )
    if strategic > 0:
        flags_present.append(
            f"{strategic}/{total} products: Strategic Value Pricing — low-discount "
            f"clean demand signal. FULL signal weight."
        )
    if end_of_life > 0:
        flags_present.append(
            f"{end_of_life}/{total} products: End-of-Life Fast Mover — clearing a proven "
            f"hit at deep discount. Signal: the STYLE was validated at full price. "
            f"50% signal weight (discount discounted, style retained)."
        )
    if subsidized > 0:
        pct = int(subsidized / max(total, 1) * 100)
        flags_present.append(
            f"{subsidized}/{total} products ({pct}%): Subsidized Liquidation — "
            f"discount IS the demand. Review velocity down-weighted 75%."
        )
    if dead_stock > 0:
        pct = int(dead_stock / max(total, 1) * 100)
        flags_present.append(
            f"{dead_stock}/{total} products ({pct}%): Dead Stock Clearance — "
            f"not selling even at deep discount. Near-zero demand signal. "
            f"Velocity down-weighted 90%."
        )
    if suspect > 0:
        pct = int(suspect / max(total, 1) * 100)
        flags_present.append(
            f"{suspect}/{total} products ({pct}%): Suspect Discount — "
            f"discount may be the primary purchase driver. Velocity down-weighted 50%."
        )
    if unclear > 0:
        flags_present.append(
            f"{unclear}/{total} products: Moderate discount, unclear driver. "
            f"Treat with caution. Velocity down-weighted 25%."
        )
    if sponsored > 0:
        flags_present.append(
            f"{sponsored}/{total} products flagged as Paid Visibility. "
            f"Rank weight reduced 50%."
        )

    if price_buzz.get("price_buzz_gap_flag"):
        flags_present.append(
            f"Price-Buzz Gap: {price_buzz['price_buzz_gap_flag']} — "
            f"{price_buzz['price_buzz_rationale']}"
        )

    # Verdict: based on what proportion of signal weight is distorted vs genuine
    if signals_distorted >= total / 2:
        verdict = "HEAVILY DISTORTED"
    elif signals_distorted > 0:
        verdict = "MODERATE NOISE"
    elif genuine_volume >= total / 2:
        verdict = "GENUINE DEMAND — DISCOUNT IS VOLUME DRIVER"
    elif strategic >= total / 2:
        verdict = "CLEAN — STRATEGIC PRICING"
    else:
        verdict = "CLEAN"

    return {
        "total_products": total,
        "dead_stock_clearance_count": dead_stock,
        "subsidized_liquidation_count": subsidized,
        "end_of_life_fast_mover_count": end_of_life,
        "suspect_discount_count": suspect,
        "genuine_volume_driver_count": genuine_volume,
        "strategic_value_pricing_count": strategic,
        "unclear_driver_count": unclear,
        "paid_visibility_count": sponsored,
        "signals_distorted": signals_distorted,
        "signals_genuine": signals_genuine,
        "clean_count": signals_genuine,
        "flags": flags_present,
        "verdict": verdict,
    }
