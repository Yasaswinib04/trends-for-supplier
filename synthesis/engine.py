import json
import os
import re
from openai import OpenAI
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

from .prompts import get_system_prompt, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

DATA_DIR = Path(__file__).parent.parent / "data"


def _clean_json_response(raw: str) -> str:
    stripped = raw.strip()
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        return match.group(0)
    return stripped


def _get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def synthesize(trend, trends_data, meta_data, marketplace_data, review_data,
               meesho_data=None, nykaa_data=None, lang="en"):
    client = _get_client()

    user_prompt = f"""## Trend Under Evaluation
{json.dumps(trend, indent=2)}

## Source 1: Google Trends (search intent)
{json.dumps(trends_data, indent=2)}

## Source 2: Meta Ad Library (competitor conviction)
{json.dumps(meta_data, indent=2)}

## Source 3: Myntra/Ajio Marketplace (organized retail demand)
{json.dumps(marketplace_data, indent=2)}

## Source 4: Meesho (price-sensitive, tier-2/3/4, remote geography demand)
{json.dumps(meesho_data or {}, indent=2)}

## Source 5: Nykaa Fashion (premium trickle-down validation)
{json.dumps(nykaa_data or {}, indent=2)}

## Source 6: Customer Reviews (fit, quality, sentiment)
{json.dumps(review_data, indent=2)}

Analyze the evidence from these six sources. Pay special attention to:
- Meesho vs Nykaa: do the same trends appear at both price extremes? This validates a complete demand pyramid.
- Regional concentration: Meesho data may show which states/regions are driving demand.
- Trickle-down: Nykaa demand at premium prices supports value-fashion versions.
- Remote geography signal: Meesho covers customers who never shop on Myntra/Ajio.
Output the structured JSON as specified."""

    if client:
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": get_system_prompt(lang)},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=2500,
            )
            content = response.choices[0].message.content
            result = json.loads(_clean_json_response(content))
        except Exception as e:
            result = _rule_based_fallback(
                trend, trends_data, meta_data, marketplace_data,
                review_data, meesho_data, nykaa_data
            )
            result["_deepseek_error"] = str(e)
    else:
        result = _rule_based_fallback(
            trend, trends_data, meta_data, marketplace_data,
            review_data, meesho_data, nykaa_data
        )
        result["_note"] = "No DEEPSEEK_API_KEY set. Using rule-based fallback synthesis."

    return result


def _rule_based_fallback(trend, trends_data, meta_data, marketplace_data,
                          review_data, meesho_data=None, nykaa_data=None):
    evidence_for = []
    evidence_against = []
    disagreements = []

    tname = trend.get("name", "")
    meesho_data = meesho_data or {}
    nykaa_data = nykaa_data or {}

    # Google Trends signals
    momentum = trends_data.get("momentum_score", 0)
    interest = trends_data.get("interest_data", {})
    if momentum > 0.15:
        evidence_for.append({
            "source": "Google Trends",
            "signal": f"Search momentum is rising ({momentum:.0%} change). Early buyer intent signal.",
            "strength": "strong" if momentum > 0.25 else "moderate"
        })
    elif momentum < -0.05:
        evidence_against.append({
            "source": "Google Trends",
            "signal": f"Search momentum is declining ({momentum:.0%} change). Fading interest.",
            "strength": "moderate"
        })
    else:
        evidence_for.append({
            "source": "Google Trends",
            "signal": "Search interest is stable — not declining, which supports a trial.",
            "strength": "weak"
        })

    if not interest:
        evidence_against.append({
            "source": "Google Trends",
            "signal": "No search volume data for these specific terms. Demand may be too niche for search-based discovery.",
            "strength": "moderate"
        })

    # Competitor signals
    competitors = meta_data.get("competitors_backing_this_trend", [])
    conviction = meta_data.get("ad_conviction", "low")
    if conviction == "high":
        evidence_for.append({
            "source": "Competitor Ads (Meta)",
            "signal": f"{len(competitors)} competitors actively advertising similar styles, several with long-running campaigns (28+ days) suggesting conviction.",
            "strength": "strong"
        })
    elif conviction == "medium":
        evidence_for.append({
            "source": "Competitor Ads (Meta)",
            "signal": f"{len(competitors)} competitor(s) backing this trend. Follow campaign duration — if ads persist, conviction is real.",
            "strength": "moderate"
        })
    else:
        evidence_against.append({
            "source": "Competitor Ads (Meta)",
            "signal": "No competitor backing this trend with paid ads. Either they missed it (opportunity) or tested and dropped (risk).",
            "strength": "moderate"
        })

    # Marketplace signals (Myntra/Ajio)
    mkt_presence = marketplace_data.get("marketplace_presence", "absent")
    discount_risk = marketplace_data.get("discount_distortion_risk", "high")

    if mkt_presence == "strong" and discount_risk == "low":
        evidence_for.append({
            "source": "Myntra/Ajio",
            "signal": "Strong marketplace presence with minimal discounting — organic demand signal is credible.",
            "strength": "strong"
        })
    elif mkt_presence == "strong" and discount_risk == "high":
        evidence_for.append({
            "source": "Myntra/Ajio",
            "signal": "Strong marketplace presence, but heavy discounting may inflate ranks. Demand may be price-driven.",
            "strength": "weak"
        })
        evidence_against.append({
            "source": "Myntra/Ajio",
            "signal": "High discounting on top-ranked products suggests demand at full price is unproven. Margins at risk.",
            "strength": "moderate"
        })
        disagreements.append({
            "topic": "Demand quality (Myntra/Ajio)",
            "source_a": "Myntra/Ajio (ranks)",
            "source_b": "Myntra/Ajio (discounts)",
            "detail": "High ranks suggest demand, but deep discounting means buyers may respond to price, not style. If prices rise, demand could evaporate."
        })
    elif mkt_presence == "moderate":
        evidence_for.append({
            "source": "Myntra/Ajio",
            "signal": "Moderate marketplace presence — trend is visible but not yet dominant. Room to enter before saturation.",
            "strength": "moderate"
        })
    elif mkt_presence == "absent":
        evidence_against.append({
            "source": "Myntra/Ajio",
            "signal": "No significant marketplace presence. Trend may be too early or not resonating with online shoppers.",
            "strength": "strong"
        })

    # ---- Meesho signals (price-sensitive, remote geography) ----
    meesho_presence = meesho_data.get("meesho_presence", "absent")
    meesho_units = meesho_data.get("total_units_sold", 0)
    meesho_resellers = meesho_data.get("total_resellers", 0)
    meesho_accelerating = meesho_data.get("reseller_growth_accelerating", False)
    meesho_regions = meesho_data.get("regions_covered", [])

    if meesho_presence == "strong":
        evidence_for.append({
            "source": "Meesho (Price-sensitive)",
            "signal": f"Strong volume signal: {meesho_units:,}+ units sold, {meesho_resellers} resellers across {len(meesho_regions)} states. Price-sensitive demand is proven at ₹{meesho_data['products_found'][0]['price'] if meesho_data.get('products_found') else '?'} price point.",
            "strength": "strong"
        })
        if meesho_accelerating:
            evidence_for.append({
                "source": "Meesho (Reseller growth)",
                "signal": f"Reseller count growing fast (+{meesho_data.get('accelerating_count', 0)} products accelerating). Resellers add products BEFORE demand peaks — this is a leading indicator.",
                "strength": "strong" if meesho_data.get("accelerating_count", 0) >= 2 else "moderate"
            })
    elif meesho_presence == "emerging":
        evidence_for.append({
            "source": "Meesho (Price-sensitive)",
            "signal": f"Emerging signal: {meesho_units:,}+ units, {meesho_resellers} resellers in {len(meesho_regions)} regions. Early price-sensitive demand, worth monitoring for acceleration.",
            "strength": "moderate" if meesho_units >= 1000 else "weak"
        })
    elif meesho_presence == "weak":
        evidence_for.append({
            "source": "Meesho (Price-sensitive)",
            "signal": f"Weak presence on Meesho. Limited volume ({meesho_units} units). May not resonate with price-sensitive tier-2/3 customers or trend hasn't reached mass-market yet.",
            "strength": "weak"
        })
    else:
        evidence_against.append({
            "source": "Meesho (Price-sensitive)",
            "signal": "No Meesho presence. This trend has not reached the price-sensitive mass market. Either too premium, too niche, or too early for tier-2/3/4 customers.",
            "strength": "moderate"
        })

    # ---- Nykaa Fashion signals (premium trickle-down) ----
    nykaa_presence = nykaa_data.get("nykaa_presence", "absent")
    nykaa_full_price = nykaa_data.get("full_price_products", 0)
    nykaa_trickle = nykaa_data.get("trickle_down_potential", 0)
    nykaa_editorial = nykaa_data.get("editorial_featured_count", 0)

    if nykaa_presence == "strong" and nykaa_full_price >= 2:
        evidence_for.append({
            "source": "Nykaa Fashion (Premium)",
            "signal": f"Strong premium demand: {nykaa_full_price} products selling at near-zero discount at ₹{nykaa_data.get('avg_price', 0):.0f} avg. Validates trickle-down — if premium customers pay full price, value-fashion has proven demand pyramid.",
            "strength": "strong"
        })
    elif nykaa_presence == "strong":
        evidence_for.append({
            "source": "Nykaa Fashion (Premium)",
            "signal": f"Premium segment backing this trend. {nykaa_data.get('avg_price', 0):.0f} avg price. Discount levels suggest some but not full conviction at premium tier.",
            "strength": "moderate"
        })
    elif nykaa_presence == "emerging":
        evidence_for.append({
            "source": "Nykaa Fashion (Premium)",
            "signal": f"Early premium interest. {nykaa_full_price} products at near-zero discount. Small but clean signal from D2C/premium brands.",
            "strength": "moderate" if nykaa_full_price >= 1 else "weak"
        })
    else:
        evidence_against.append({
            "source": "Nykaa Fashion (Premium)",
            "signal": "No premium presence. Either too basic for Nykaa's positioning (not necessarily bad) or trend lacks upward demand validation.",
            "strength": "weak"
        })

    if nykaa_editorial >= 1:
        evidence_for.append({
            "source": "Nykaa Editorial",
            "signal": f"Featured in Nykaa editorial ({nykaa_editorial} placement(s)). Suggests Nykaa's merchandising team sees this as a trend worth pushing — editorial conviction.",
            "strength": "moderate"
        })

    # ---- Cross-source disagreements (Meesho vs Nykaa) ----
    if meesho_presence == "strong" and nykaa_presence == "absent":
        disagreements.append({
            "topic": "Mass vs. Premium split",
            "source_a": "Meesho (mass, strong)",
            "source_b": "Nykaa (premium, absent)",
            "detail": "Strong mass-market demand on Meesho but zero premium presence on Nykaa. This could mean the trend is purely value-driven — good for sales volume but may cap aspirational appeal. Validates buy but may limit pricing power."
        })

    if nykaa_presence == "strong" and meesho_presence == "absent":
        disagreements.append({
            "topic": "Premium aspiration vs. Mass reach",
            "source_a": "Nykaa (premium, strong)",
            "source_b": "Meesho (mass, absent)",
            "detail": "Strong premium demand on Nykaa but zero mass-market presence on Meesho. The trend may be too aspirational for value-fashion customers, or Meesho hasn't caught up yet. Danger: premium trends don't always translate to ₹399-799."
        })

    if meesho_presence == "strong" and nykaa_presence == "strong":
        evidence_for.append({
            "source": "Cross-source (Meesho + Nykaa)",
            "signal": "Complete demand pyramid validated: strong sales at both ₹200-400 (Meesho) and ₹1,000-2,000 (Nykaa). This is the strongest possible signal — demand exists across the entire price spectrum.",
            "strength": "strong"
        })

    # ---- Review signals ----
    if review_data.get("available"):
        sentiment_q = review_data.get("sentiment_quality", "mixed")
        if sentiment_q == "strong":
            evidence_for.append({
                "source": "Customer Reviews",
                "signal": f"Review sentiment is strongly positive ({review_data['sentiment']['positive']:.0%}). Buyers perceive good value.",
                "strength": "strong"
            })
        elif sentiment_q == "solid":
            evidence_for.append({
                "source": "Customer Reviews",
                "signal": f"Review sentiment is solid ({review_data['sentiment']['positive']:.0%}). Generally positive with manageable complaints.",
                "strength": "moderate"
            })
        warnings = review_data.get("watch_out_for", [])
        for w in warnings:
            evidence_against.append({"source": "Customer Reviews", "signal": w, "strength": "moderate"})
    else:
        evidence_against.append({
            "source": "Customer Reviews",
            "signal": "No review data available. Fabric quality, fit, and wash durability are unknown.",
            "strength": "weak"
        })

    # ---- Cross-source conflict detection ----
    if momentum > 0.15 and conviction == "low":
        disagreements.append({
            "topic": "Search vs. Competitor Action",
            "source_a": "Google Trends",
            "source_b": "Meta Ads",
            "detail": "Consumer search interest is rising, but no competitor is advertising. First-mover opportunity, or competitors know something you don't."
        })

    if momentum < -0.05 and conviction == "high":
        disagreements.append({
            "topic": "Search vs. Competitor Action",
            "source_a": "Google Trends",
            "source_b": "Meta Ads",
            "detail": "Search interest declining but competitors still advertising heavily. They may be clearing inventory or targeting different segment."
        })

    # Missing evidence
    missing = [
        "Store-floor feedback from the last 2 seasons on similar fabric/silhouette bets",
        "Supplier lead times — can we re-order in-season if test sells out?",
        "Regional breakdown — Meesho data shows where demand lives, but store-level validation needed",
        "Instagram creator velocity — how many creators feature this style organically?"
    ]

    # Confidence
    strong_for = sum(1 for e in evidence_for if e["strength"] == "strong")
    strong_against = sum(1 for e in evidence_against if e["strength"] == "strong")
    total_for = len(evidence_for)
    total_against = len(evidence_against)

    if strong_for >= 4 and strong_against <= 1:
        confidence = "moderate"
    elif strong_for >= 3:
        confidence = "moderate"
    elif total_against > total_for + 1:
        confidence = "low"
    elif total_for >= 1:
        confidence = "low"
    else:
        confidence = "low"

    watch = [
        "Check if competitor ads continue past 30-day mark (real conviction)",
        "Monitor Meesho reseller growth — accelerating reseller count is a leading indicator",
        "Track Nykaa discount levels — if premium segment starts discounting, demand may be softening",
        "Survey 5 top stores — are customers asking for this style/print/fabric?",
        "Check fabric supplier availability — can you commit small quantities and re-order?"
    ]

    summary = (
        f"Analysis of '{tname}': {total_for} signals for, {total_against} against "
        f"across 6 sources. "
        f"{'Multiple sources show converging positive signals.' if total_for >= 4 else 'Limited but non-zero evidence.'} "
        f"Confidence: {confidence}. "
    )
    if confidence == "moderate":
        summary += "Evidence supports a meaningful buy, with caution on the risk factors noted."
    elif total_for >= 2:
        summary += "Consider a trial buy while monitoring for the signals below."
    else:
        summary += "Wait for stronger signal convergence before committing inventory."

    return {
        "summary": summary,
        "for": evidence_for,
        "against": evidence_against,
        "disagreements": disagreements,
        "missing_evidence": missing,
        "confidence_assessment": confidence,
        "watch_next": watch,
    }


def compute_bet_size(trend, synthesis, source_weights=None):
    evidence_for = synthesis.get("for", [])
    evidence_against = synthesis.get("against", [])
    disagreements = synthesis.get("disagreements", [])

    if source_weights is None:
        source_weights = {}

    strong_for = sum(1 for e in evidence_for if e["strength"] == "strong")
    moderate_for = sum(1 for e in evidence_for if e["strength"] == "moderate")
    strong_against = sum(1 for e in evidence_against if e["strength"] == "strong")
    moderate_against = sum(1 for e in evidence_against if e["strength"] == "moderate")

    convergence_score = (strong_for * 2.5 + moderate_for * 1.5
                        - strong_against * 2.5 - moderate_against * 0.75)
    convergence_score = max(0, min(10, convergence_score))

    if source_weights:
        total_weight = sum(source_weights.values())
        if total_weight > 0:
            weighted_score = 0
            for evidence in evidence_for:
                src = evidence["source"]
                w = source_weights.get(src, 1.0)
                if evidence["strength"] == "strong":
                    weighted_score += 2.5 * w
                elif evidence["strength"] == "moderate":
                    weighted_score += 1.5 * w
            for evidence in evidence_against:
                src = evidence["source"]
                w = source_weights.get(src, 1.0)
                if evidence["strength"] == "strong":
                    weighted_score -= 2.5 * w
                elif evidence["strength"] == "moderate":
                    weighted_score -= 0.75 * w
            convergence_score = max(0, min(10, weighted_score))

    disagreement_penalty = len(disagreements) * 1.5

    total = convergence_score - disagreement_penalty
    total = max(0, min(10, total))

    if total >= 7.5:
        sizing = "DEEP BUY"
        sizing_zone = "commit"
        rationale = (
            f"Exceptional convergence across 6 sources ({strong_for} strong, {moderate_for} moderate). "
            "Independent signals agree. Recommend committing 60-70% of planned open-to-buy."
        )
        suggested_action = "Commit 60-70% of planned open-to-buy. Allocate to top 50 stores initially, expand based on week-1 sell-through."
        risk_level = "Low — but monitor discount patterns and return rates."
    elif total >= 5:
        sizing = "MODERATE BUY"
        sizing_zone = "commit"
        rationale = (
            f"Good convergence ({strong_for} strong sources, {moderate_for} moderate) "
            "with manageable disagreement. Evidence supports meaningful inventory with hedging."
        )
        suggested_action = "Commit 30-50% of planned open-to-buy. Use re-orderable fabric. Test in top 20 stores for 2 weeks before expanding."
        risk_level = "Moderate — hedge with re-orderable fabric and monitor sell-through weekly."
    elif total >= 3:
        sizing = "TRIAL"
        sizing_zone = "test"
        rationale = (
            f"Mixed or early signals ({strong_for + moderate_for} positive sources). "
            "Not enough conviction for deep commitment, but enough to test."
        )
        suggested_action = "Buy 300-500 units. Place in top 15-20 stores. Measure sell-through in 2 weeks. Have re-order fabric on standby."
        risk_level = "High — this is a test, not a commitment. Be willing to walk away."
    elif total >= 2:
        sizing = "NEAR TRIAL"
        sizing_zone = "monitor"
        rationale = (
            f"Weak but real signals ({strong_for + moderate_for} positive sources). "
            "One strong source or a shift in disagreement could push this into TRIAL territory. "
            "Don't buy yet — but watch closely."
        )
        suggested_action = "No buy this cycle. Re-check in 2 weeks. If any source upgrades (new competitor ad, reseller acceleration, search spike), re-run analysis immediately."
        risk_level = "Wait — close to actionable. One more signal could flip this."
    else:
        sizing = "WAIT"
        sizing_zone = "monitor"
        rationale = (
            f"Insufficient converging evidence ({strong_for + moderate_for} positive sources). "
            "Signals are too weak, conflicting, or absent. Buying now would be gambling."
        )
        suggested_action = "No buy this cycle. Track search trends, competitor ad duration, Meesho reseller growth, and store inquiries for 2-4 weeks. Significant new evidence needed to reconsider."
        risk_level = "Avoid — cost of waiting is low. Cost of being wrong is high."

    threshold_next = None
    if sizing == "WAIT":
        threshold_next = f"Need {2.0 - total:.1f} more points to reach NEAR TRIAL"
    elif sizing == "NEAR TRIAL":
        threshold_next = f"Need {3.0 - total:.1f} more points to reach TRIAL"
    elif sizing == "TRIAL":
        threshold_next = f"Need {5.0 - total:.1f} more points to reach MODERATE BUY"
    elif sizing == "MODERATE BUY":
        threshold_next = f"Need {7.5 - total:.1f} more points to reach DEEP BUY"

    price_band = trend.get("price_band", "₹499-799")
    season = trend.get("season", "Unknown")

    return {
        "sizing": sizing,
        "sizing_zone": sizing_zone,
        "score": round(total, 1),
        "max_score": 10,
        "rationale": rationale,
        "suggested_action": suggested_action,
        "risk_level": risk_level,
        "threshold_next": threshold_next,
        "price_band": price_band,
        "season": season,
        "source_weights_used": bool(source_weights),
        "components": {
            "convergence_score": round(convergence_score, 1),
            "disagreement_penalty": round(disagreement_penalty, 1),
            "strong_for_count": strong_for,
            "moderate_for_count": moderate_for,
            "strong_against_count": strong_against,
            "moderate_against_count": moderate_against,
            "disagreement_count": len(disagreements),
        }
    }
