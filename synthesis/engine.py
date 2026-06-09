import json
import os
from openai import OpenAI
from pathlib import Path
from .prompts import SYNTHESIS_SYSTEM_PROMPT, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

DATA_DIR = Path(__file__).parent.parent / "data"


def _get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def synthesize(trend, trends_data, meta_data, marketplace_data, review_data):
    client = _get_client()

    user_prompt = f"""## Trend Under Evaluation
{json.dumps(trend, indent=2)}

## Source 1: Google Trends
{json.dumps(trends_data, indent=2)}

## Source 2: Meta Ad Library (Competitor Ads)
{json.dumps(meta_data, indent=2)}

## Source 3: Marketplace Rankings (Myntra/Ajio)
{json.dumps(marketplace_data, indent=2)}

## Source 4: Customer Reviews
{json.dumps(review_data, indent=2)}

Analyze the evidence from these four sources. Output the structured JSON as specified."""

    if client:
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            result = json.loads(content)
        except Exception as e:
            result = _rule_based_fallback(trend, trends_data, meta_data, marketplace_data, review_data)
            result["_deepseek_error"] = str(e)
    else:
        result = _rule_based_fallback(trend, trends_data, meta_data, marketplace_data, review_data)
        result["_note"] = "No DEEPSEEK_API_KEY set. Using rule-based fallback synthesis."

    return result


def _rule_based_fallback(trend, trends_data, meta_data, marketplace_data, review_data):
    evidence_for = []
    evidence_against = []
    disagreements = []

    tname = trend.get("name", "")

    # Google Trends signals
    momentum = trends_data.get("momentum_score", 0)
    interest = trends_data.get("interest_data", {})
    if momentum > 0.15:
        evidence_for.append({"source": "Google Trends", "signal": f"Search momentum is rising ({momentum:.0%} change). Early buyer intent signal.", "strength": "strong" if momentum > 0.25 else "moderate"})
    elif momentum < -0.05:
        evidence_against.append({"source": "Google Trends", "signal": f"Search momentum is declining ({momentum:.0%} change). Fading interest.", "strength": "moderate"})
    else:
        evidence_for.append({"source": "Google Trends", "signal": "Search interest is stable — not declining, which supports a trial.", "strength": "weak"})

    if not interest:
        evidence_against.append({"source": "Google Trends", "signal": "No search volume data available for these specific terms. Demand may be too niche for search-based discovery.", "strength": "moderate"})

    # Competitor signals
    competitors = meta_data.get("competitors_backing_this_trend", [])
    conviction = meta_data.get("ad_conviction", "low")
    if conviction == "high":
        evidence_for.append({"source": "Competitor Ads (Meta)", "signal": f"{len(competitors)} competitors are actively advertising similar styles, several with long-running campaigns (28+ days) suggesting conviction.", "strength": "strong"})
    elif conviction == "medium":
        evidence_for.append({"source": "Competitor Ads (Meta)", "signal": f"{len(competitors)} competitor(s) backing this trend. Follow their campaign duration — if ads persist, conviction is real.", "strength": "moderate"})
    else:
        evidence_against.append({"source": "Competitor Ads (Meta)", "signal": "No competitor is actively backing this trend with paid ads. Either they missed it (opportunity) or they tested and dropped it (risk).", "strength": "moderate"})

    # Marketplace signals
    mkt_presence = marketplace_data.get("marketplace_presence", "absent")
    discount_risk = marketplace_data.get("discount_distortion_risk", "high")
    products = marketplace_data.get("products_found", [])

    if mkt_presence == "strong" and discount_risk == "low":
        evidence_for.append({"source": "Marketplace", "signal": "Strong marketplace presence with minimal discounting — organic demand signal is credible.", "strength": "strong"})
    elif mkt_presence == "strong" and discount_risk == "high":
        evidence_for.append({"source": "Marketplace", "signal": "Strong marketplace presence, but heavy discounting may be inflating ranks. Demand may be price-driven, not style-driven.", "strength": "weak"})
        evidence_against.append({"source": "Marketplace", "signal": "High discounting on top-ranked products suggests demand at full price is unproven. Margins at risk.", "strength": "moderate"})
        disagreements.append({"topic": "Demand quality", "source_a": "Marketplace (ranks)", "source_b": "Marketplace (discounts)", "detail": "High ranks suggest demand, but deep discounting means buyers may be responding to price, not style. If competitor raises prices, demand could evaporate."})
    elif mkt_presence == "moderate":
        evidence_for.append({"source": "Marketplace", "signal": "Moderate marketplace presence — trend is visible but not yet dominant. Room to enter before saturation.", "strength": "moderate"})
    elif mkt_presence == "absent":
        evidence_against.append({"source": "Marketplace", "signal": "No significant marketplace presence found. This trend may be too early or not resonating with online shoppers.", "strength": "strong"})

    # Review signals
    if review_data.get("available"):
        sentiment_q = review_data.get("sentiment_quality", "mixed")
        if sentiment_q == "strong":
            evidence_for.append({"source": "Customer Reviews", "signal": f"Review sentiment is strongly positive ({review_data['sentiment']['positive']:.0%}). Buyers perceive good value.", "strength": "strong"})
        elif sentiment_q == "solid":
            evidence_for.append({"source": "Customer Reviews", "signal": f"Review sentiment is solid ({review_data['sentiment']['positive']:.0%}). Generally positive with manageable complaints.", "strength": "moderate"})
        warnings = review_data.get("watch_out_for", [])
        for w in warnings:
            evidence_against.append({"source": "Customer Reviews", "signal": w, "strength": "moderate"})
    else:
        evidence_against.append({"source": "Customer Reviews", "signal": "No review data available. Fabric quality, fit, and wash durability are unknown.", "strength": "weak"})

    # Conflicts between Google Trends and Competitor
    if momentum > 0.15 and conviction == "low":
        disagreements.append({"topic": "Search vs. Competitor Action", "source_a": "Google Trends", "source_b": "Meta Ads", "detail": "Consumer search interest is rising, but no competitor is advertising yet. This could be a first-mover opportunity, or competitors may know something you don't (e.g., supply constraints, quality issues)."})

    if momentum < -0.05 and conviction == "high":
        disagreements.append({"topic": "Search vs. Competitor Action", "source_a": "Google Trends", "source_b": "Meta Ads", "detail": "Search interest is declining but competitors continue to advertise heavily. They may be clearing inventory or targeting a different customer segment."})

    # Missing evidence
    missing = [
        "Store-floor feedback from the last 2 seasons on similar fabric/silhouette bets",
        "Supplier lead times — can we re-order in-season if test sells out?",
        "Regional breakdown — is this a pan-India trend or specific to 2-3 states?",
        "Instagram creator velocity — how many creators are featuring this style organically?"
    ]

    # Confidence
    strong_for = sum(1 for e in evidence_for if e["strength"] == "strong")
    strong_against = sum(1 for e in evidence_against if e["strength"] == "strong")
    total_for = len(evidence_for)
    total_against = len(evidence_against)

    if strong_for >= 3 and strong_against <= 1:
        confidence = "moderate"
    elif strong_for >= 2:
        confidence = "moderate"
    elif total_against > total_for + 1:
        confidence = "low"
    elif total_for >= 1:
        confidence = "low"
    else:
        confidence = "low"

    # Watch next
    watch = [
        "Check if competitor ads for this style continue past 30-day mark (indicates real conviction)",
        "Monitor review velocity — if it accelerates without discount increase, demand is real",
        "Survey 5 top stores — are customers asking for this style/print/fabric?",
        "Check fabric supplier availability — can you commit small quantities and re-order?"
    ]

    return {
        "summary": f"Analysis of '{tname}': {total_for} signals for, {total_against} against. {'Multiple sources show converging positive signals, but ' if total_for >= 3 else 'Limited evidence available — '} confidence is {confidence}. {'Consider a trial buy while monitoring for the signals below.' if confidence in ('low', 'moderate') else 'Evidence supports a meaningful buy, with caution on the risk factors noted.'}",
        "for": evidence_for,
        "against": evidence_against,
        "disagreements": disagreements,
        "missing_evidence": missing,
        "confidence_assessment": confidence,
        "watch_next": watch,
    }


def compute_bet_size(trend, synthesis):
    evidence_for = synthesis.get("for", [])
    evidence_against = synthesis.get("against", [])
    disagreements = synthesis.get("disagreements", [])
    confidence = synthesis.get("confidence_assessment", "low")

    strong_for = sum(1 for e in evidence_for if e["strength"] == "strong")
    moderate_for = sum(1 for e in evidence_for if e["strength"] == "moderate")
    strong_against = sum(1 for e in evidence_against if e["strength"] == "strong")

    convergence_score = strong_for * 2.5 + moderate_for * 1.5 - strong_against * 2.0
    convergence_score = max(0, min(10, convergence_score))

    disagreement_penalty = len(disagreements) * 1.5

    total = convergence_score - disagreement_penalty
    total = max(0, min(10, total))

    if total >= 7:
        sizing = "DEEP BUY"
        rationale = f"Multiple strong converging signals ({strong_for} strong affirmative sources). High conviction across independent sources. Recommend committing 60-70% of planned open-to-buy for this style."
        suggested_action = "Commit 60-70% of planned open-to-buy. Allocate to top 50 stores initially, expand based on week-1 sell-through."
        risk_level = "Low — but monitor discount patterns and return rates."
    elif total >= 4.5:
        sizing = "MODERATE BUY"
        rationale = f"Good convergence ({strong_for} strong sources, {moderate_for} moderate) with manageable disagreement. Evidence supports meaningful inventory with hedging."
        suggested_action = "Commit 30-50% of planned open-to-buy. Use re-orderable fabric. Test in top 20 stores for 2 weeks before expanding allocation."
        risk_level = "Moderate — hedge with re-orderable fabric and monitor sell-through weekly."
    elif total >= 2.5:
        sizing = "TRIAL"
        rationale = f"Mixed or early signals ({strong_for + moderate_for} positive sources). Not enough conviction for a deep commitment, but enough to test."
        suggested_action = "Buy 300-500 units. Place in top 15-20 stores. Measure sell-through in 2 weeks. Have re-order fabric on standby."
        risk_level = "High — this is a test, not a commitment. Be willing to walk away."
    else:
        sizing = "MONITOR"
        rationale = f"Insufficient converging evidence ({strong_for + moderate_for} positive sources). Signals are weak, conflicting, or absent. Buying now would be gambling, not betting."
        suggested_action = "No buy this cycle. Track search trends, competitor ad duration, and store inquiries for 2-4 weeks. Re-evaluate before next buying window."
        risk_level = "Avoid — cost of waiting is low. Cost of being wrong is high."

    price_band = trend.get("price_band", "₹499-799")
    season = trend.get("season", "Unknown")

    return {
        "sizing": sizing,
        "score": round(total, 1),
        "max_score": 10,
        "rationale": rationale,
        "suggested_action": suggested_action,
        "risk_level": risk_level,
        "price_band": price_band,
        "season": season,
        "components": {
            "convergence_score": round(convergence_score, 1),
            "disagreement_penalty": round(disagreement_penalty, 1),
            "strong_for_count": strong_for,
            "moderate_for_count": moderate_for,
            "strong_against_count": strong_against,
            "disagreement_count": len(disagreements),
        }
    }
