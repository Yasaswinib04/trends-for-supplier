import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MEESHO_FILE = DATA_DIR / "meesho_data.json"
TRENDS_FILE = DATA_DIR / "cached_trends.json"


def get_meesho_data(trend_id):
    with open(MEESHO_FILE) as f:
        data = json.load(f)
    with open(TRENDS_FILE) as f:
        trends = json.load(f)

    trend = next((t for t in trends if t["id"] == trend_id), None)
    if not trend:
        return {"source": "meesho", "error": "Trend not found", "products_found": []}

    trend_price_low = _extract_low_price(trend.get("price_band", "₹0-0"))

    products_found = []
    for product in data.get("top_kurti_styles", []):
        if trend_id in product.get("trend_ids", []):
            reseller_growth = product.get("reseller_growth_mom", "0%")
            growth_pct = int(reseller_growth.replace("%", "").replace("+", ""))
            is_accelerating = growth_pct >= 25

            products_found.append({
                "name": product["name"],
                "price": product["price"],
                "units_sold": product["units_sold"],
                "rating": product["rating"],
                "review_count": product["review_count"],
                "reseller_count": product["reseller_count"],
                "regions": product["regions"],
                "reseller_growth_mom": reseller_growth,
                "signal_strength": product.get("signal_strength", "weak"),
                "price_gap_vs_trend": product["price"] - trend_price_low,
                "is_accelerating": is_accelerating,
            })

    if not products_found:
        return {
            "source": "meesho",
            "disclaimer": data["disclaimer"],
            "last_updated": data["last_updated"],
            "products_found": [],
            "meesho_presence": "absent",
            "demand_signal": "no data",
            "remote_geo_signal": None,
        }

    top_product = products_found[0]
    total_units = sum(
        int(p["units_sold"].replace(",", "").replace("+", ""))
        for p in products_found
    )
    total_resellers = sum(p["reseller_count"] for p in products_found)
    avg_rating = sum(p["rating"] for p in products_found) / len(products_found)
    accelerating_products = [p for p in products_found if p["is_accelerating"]]

    presence = "strong" if top_product["signal_strength"] == "strong" else "emerging" if top_product["signal_strength"] == "emerging" else "weak"

    all_regions = set()
    for p in products_found:
        all_regions.update(p["regions"])

    demand_signal = "strong volume signal" if total_units >= 5000 and total_resellers >= 100 else "emerging volume signal" if total_units >= 1000 else "weak volume signal"

    return {
        "source": "meesho",
        "disclaimer": data["disclaimer"],
        "platform_note": data["platform_note"],
        "last_updated": data["last_updated"],
        "products_found": products_found,
        "meesho_presence": presence,
        "demand_signal": demand_signal,
        "total_units_sold": total_units,
        "total_resellers": total_resellers,
        "avg_rating": round(avg_rating, 2),
        "reseller_growth_accelerating": len(accelerating_products) > 0,
        "accelerating_count": len(accelerating_products),
        "regions_covered": sorted(all_regions),
        "region_count": len(all_regions),
        "price_points": sorted([p["price"] for p in products_found]),
        "price_sensitivity_flag": "high" if total_units >= 5000 and low_rating_risk(products_found) else "normal",
    }


def low_rating_risk(products):
    return any(p["rating"] < 3.5 and int(p["review_count"]) > 500 for p in products)


def _extract_low_price(price_band):
    try:
        parts = price_band.replace("₹", "").split("-")
        return int(parts[0])
    except (ValueError, IndexError):
        return 500
