import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
COMPETITOR_FILE = DATA_DIR / "competitor_snapshot.json"


def get_meta_ad_signals(trend_id):
    with open(COMPETITOR_FILE) as f:
        data = json.load(f)

    trends = _load_trends()
    trend = next((t for t in trends if t["id"] == trend_id), None)

    brand_matches = []
    for brand_name, brand_data in data["brands"].items():
        for product in brand_data.get("recent_launches", []):
            product_name_lower = product["product"].lower()
            if trend:
                matches = 0
                if trend_id in product.get("trend_ids", []):
                    matches = 3
                else:
                    for feat in trend.get("key_features", []):
                        fwords = set(feat.lower().split())
                        pwords = set(product_name_lower.split())
                        if fwords.issubset(pwords):
                            matches += 1
                    if trend["silhouette"].lower() in product_name_lower:
                        matches += 1
                    if trend["fabric"].lower() in product["fabric"].lower():
                        matches += 1
                    if trend.get("name", "").lower().split()[0] in product_name_lower:
                        matches += 2

                if matches >= 2:
                    brand_matches.append({
                        "brand": brand_name,
                        "product": product["product"],
                        "price": product["price"],
                        "fabric": product["fabric"],
                        "silhouette": product["silhouette"],
                        "ad_running_days": product["ad_running_days"],
                        "signal_strength": "strong" if product["ad_running_days"] >= 21 else "emerging"
                    })

    return {
        "source": "meta_ad_library",
        "disclaimer": data["disclaimer"],
        "last_updated": data["last_updated"],
        "competitors_backing_this_trend": brand_matches,
        "competitor_count": len(brand_matches),
        "ad_conviction": "high" if len([b for b in brand_matches if b["signal_strength"] == "strong"]) >= 2 else "medium" if brand_matches else "low"
    }


def _load_trends():
    with open(DATA_DIR / "cached_trends.json") as f:
        return json.load(f)
