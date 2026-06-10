import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MARKETPLACE_FILE = DATA_DIR / "marketplace_data.json"
TRENDS_FILE = DATA_DIR / "cached_trends.json"


def get_marketplace_data(trend_id):
    with open(MARKETPLACE_FILE) as f:
        data = json.load(f)
    with open(TRENDS_FILE) as f:
        trends = json.load(f)

    trend = next((t for t in trends if t["id"] == trend_id), None)
    if not trend:
        return {"source": "marketplace", "error": "Trend not found", "products_found": []}

    tname = trend["name"].lower()
    tterms = [t.lower() for t in trend.get("search_terms", [])]
    tfabric = trend.get("fabric", "").lower()
    tsilhouette = trend.get("silhouette", "").lower()

    products_found = []
    for platform, pdata in data.get("platforms", {}).items():
        for product in pdata.get("top_kurti_styles", []):
            pname_lower = product["name"].lower()
            pfabric = product.get("fabric", "").lower() if isinstance(product, dict) else ""
            score = 0

            pwords = set(pname_lower.split())

            if trend_id in product.get("trend_ids", []):
                score = 10

            if score < 10:
                for term in tterms:
                    twords = set(term.lower().split())
                    if twords.issubset(pwords):
                        score += 3

            if tfabric and tfabric in pname_lower:
                score += 2
            if tsilhouette and tsilhouette in pname_lower:
                score += 2

            for feature in trend.get("key_features", []):
                fwords = set(feature.lower().split())
                if fwords.issubset(pwords):
                    score += 1

            if score >= 3:
                discount = int(product["discount"].replace("%", ""))
                discount_risk = "high" if discount >= 30 else "medium" if discount >= 15 else "low"
                if product.get("stock_status") == "Low stock":
                    discount_risk = "high"

                products_found.append({
                    "platform": platform,
                    "name": product["name"],
                    "brand": product["brand"],
                    "price": product["price"],
                    "discount": product["discount"],
                    "discount_percentage": product.get("discount_percentage", int(product["discount"].replace("%", ""))),
                    "is_sponsored": product.get("is_sponsored", False),
                    "rank": product["rank"],
                    "reviews": product["reviews"],
                    "avg_rating": product["avg_rating"],
                    "review_velocity": product["review_velocity_30d"],
                    "stock_status": product["stock_status"],
                    "discount_risk": discount_risk,
                })

    if not products_found:
        return {
            "source": "marketplace",
            "disclaimer": data["disclaimer"],
            "last_updated": data["last_updated"],
            "products_found": [],
            "marketplace_presence": "absent",
            "demand_signal": "no data",
        }

    avg_rank = sum(p["rank"] for p in products_found) / len(products_found)
    avg_rating = sum(p["avg_rating"] for p in products_found) / len(products_found)
    total_velocity = sum(p["review_velocity"] for p in products_found)
    high_discount = any(p["discount_risk"] == "high" for p in products_found)

    presence = "strong" if avg_rank <= 20 else "moderate" if avg_rank <= 40 else "weak"
    signal = "strong organic demand" if not high_discount and total_velocity > 50 else "mixed — discount may inflate" if high_discount and total_velocity > 50 else "early/weak signal"

    return {
        "source": "marketplace",
        "disclaimer": data["disclaimer"],
        "last_updated": data["last_updated"],
        "products_found": products_found,
        "marketplace_presence": presence,
        "demand_signal": signal,
        "avg_rank": round(avg_rank, 1),
        "avg_rating": round(avg_rating, 2),
        "review_velocity_30d": total_velocity,
        "discount_distortion_risk": "high" if high_discount else "low",
    }
