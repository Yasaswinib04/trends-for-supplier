import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
REVIEWS_FILE = DATA_DIR / "reviews.json"


def get_review_signals(trend_id):
    with open(REVIEWS_FILE) as f:
        data = json.load(f)

    trend_reviews = data.get("trends", {}).get(trend_id)

    if not trend_reviews:
        return {
            "source": "reviews",
            "available": False,
            "message": f"No review data for trend '{trend_id}'. Consider collecting store feedback.",
            "sentiment": {},
            "praise": [],
            "complaints": [],
        }

    sentiment = trend_reviews["sentiment_ratio"]
    sentiment_quality = "strong" if sentiment["positive"] >= 0.75 else "solid" if sentiment["positive"] >= 0.60 else "mixed"

    return {
        "source": "reviews",
        "disclaimer": data["disclaimer"],
        "last_updated": data["last_updated"],
        "available": True,
        "total_analyzed": trend_reviews["total_reviews_analyzed"],
        "sentiment": sentiment,
        "sentiment_quality": sentiment_quality,
        "praise": trend_reviews["common_praise"],
        "complaints": trend_reviews["common_complaints"],
        "watch_out_for": _extract_warnings(trend_reviews),
    }


def _extract_warnings(review_data):
    warnings = []
    wash_issues = any("wash" in c.lower() or "bleed" in c.lower() or "fade" in c.lower() for c in review_data["common_complaints"])
    fit_issues = any("size" in c.lower() or "slim" in c.lower() or "small" in c.lower() or "long" in c.lower() for c in review_data["common_complaints"])
    quality_issues = any("quality" in c.lower() or "material" in c.lower() or "fabric" in c.lower() for c in review_data["common_complaints"])

    if wash_issues:
        warnings.append("Wash durability risk — color bleed or fade reported after washes")
    if fit_issues:
        warnings.append("Sizing inconsistency — may drive returns and negative store feedback")
    if quality_issues:
        warnings.append("Perceived quality gap — fabric or finishing below customer expectation")

    return warnings
