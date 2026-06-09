import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
NYKAA_FILE = DATA_DIR / "nykaa_data.json"
TRENDS_FILE = DATA_DIR / "cached_trends.json"


def get_nykaa_data(trend_id):
    with open(NYKAA_FILE) as f:
        data = json.load(f)
    with open(TRENDS_FILE) as f:
        trends = json.load(f)

    trend = next((t for t in trends if t["id"] == trend_id), None)
    if not trend:
        return {"source": "nykaa", "error": "Trend not found", "products_found": []}

    trend_price_high = _extract_high_price(trend.get("price_band", "₹0-0"))

    products_found = []
    for product in data.get("top_kurti_styles", []):
        if trend_id in product.get("trend_ids", []):
            discount_pct = int(product["discount"].replace("%", ""))
            full_price_signal = discount_pct <= 10
            stock_tight = product.get("stock_status", "").lower().find("limited") >= 0

            products_found.append({
                "name": product["name"],
                "brand": product["brand"],
                "price": product["price"],
                "discount": product["discount"],
                "rating": product["rating"],
                "review_count": product["review_count"],
                "stock_status": product["stock_status"],
                "nykaa_positioning": product["nykaa_positioning"],
                "editorial_placement": product.get("editorial_placement", ""),
                "signal_strength": product.get("signal_strength", "weak"),
                "trickle_down_potential": product["price"] - trend_price_high,
                "full_price_signal": full_price_signal,
                "stock_pressure": stock_tight,
            })

    trend_notes = data.get("trend_notes", {}).get(trend_id, "")

    if not products_found:
        return {
            "source": "nykaa",
            "disclaimer": data["disclaimer"],
            "last_updated": data["last_updated"],
            "products_found": [],
            "nykaa_presence": "absent",
            "demand_signal": "no data",
            "trend_notes": trend_notes,
        }

    top_product = products_found[0]
    avg_price = sum(p["price"] for p in products_found) / len(products_found)
    avg_rating = sum(p["rating"] for p in products_found) / len(products_found)
    full_price_products = [p for p in products_found if p["full_price_signal"]]
    stock_pressure_products = [p for p in products_found if p["stock_pressure"]]
    editorial_featured = [p for p in products_found if p.get("editorial_placement")]

    presence = "strong" if top_product["signal_strength"] == "strong" else "emerging"

    if full_price_products and presence == "strong":
        demand_signal = "strong premium demand — near-zero discount, genuine willingness to pay"
    elif full_price_products:
        demand_signal = "early premium demand — low discount supports genuine interest"
    elif presence == "strong":
        demand_signal = "premium interest present but discount-distorted"
    else:
        demand_signal = "limited premium presence"

    return {
        "source": "nykaa",
        "disclaimer": data["disclaimer"],
        "platform_note": data["platform_note"],
        "last_updated": data["last_updated"],
        "products_found": products_found,
        "nykaa_presence": presence,
        "demand_signal": demand_signal,
        "avg_price": round(avg_price, 0),
        "avg_rating": round(avg_rating, 2),
        "full_price_products": len(full_price_products),
        "stock_pressure_count": len(stock_pressure_products),
        "editorial_featured_count": len(editorial_featured),
        "trickle_down_potential": avg_price - trend_price_high,
        "trend_notes": trend_notes,
        "brands_backing": list(set(p["brand"] for p in products_found)),
    }


def _extract_high_price(price_band):
    try:
        parts = price_band.replace("₹", "").split("-")
        return int(parts[-1])
    except (ValueError, IndexError):
        return 1000
