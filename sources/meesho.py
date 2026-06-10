import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MEESHO_FILE = DATA_DIR / "meesho_data.json"
TRENDS_FILE = DATA_DIR / "cached_trends.json"

try:
    from sources.browser_scraper import BrowserScraper
    _BROWSER = BrowserScraper()
except ImportError:
    _BROWSER = None


def get_meesho_data(trend_id):
    # Try live browser scrape first
    products_found = _try_live_scrape(trend_id)
    if products_found:
        return _build_from_scraped(products_found)

    # Fall back to static JSON
    return _get_static_meesho_data(trend_id)


def _try_live_scrape(trend_id):
    """Try to scrape Meesho for this trend. Returns list of product dicts or None."""
    if not _BROWSER or not _BROWSER.ready:
        return None

    try:
        trends = _load_trends()
        trend = next((t for t in trends if t["id"] == trend_id), None)
        if not trend:
            return None

        search_terms = trend.get("search_terms", [trend["name"]])
        keyword = search_terms[0] if search_terms else trend["name"]

        scraped = _BROWSER.scrape("meesho", keyword, use_cache=True)
        if scraped and len(scraped) > 0:
            return scraped
    except Exception:
        pass
    return None


def _build_from_scraped(products):
    """Build the same output schema from scraped products."""
    prices = [p["price"] for p in products if p.get("price", 0) > 0]
    ratings = [p["rating"] for p in products if p.get("rating", 0) > 0]
    now = Path(__file__).parent.parent / "data"

    return {
        "source": "meesho",
        "disclaimer": "Live scraped data from Meesho (via Playwright). Prices and availability may change.",
        "platform_note": "Live scraped from Meesho search results. Data is point-in-time.",
        "last_updated": __import__("datetime").datetime.now().isoformat(),
        "products_found": products,
        "meesho_presence": "strong" if len(products) >= 5 else "emerging" if len(products) >= 1 else "weak",
        "demand_signal": f"live scraped — {len(products)} products found",
        "total_units_sold": sum(p.get("reviews", 0) for p in products[:3]),
        "total_resellers": 0,
        "avg_rating": round(sum(ratings) / max(len(ratings), 1), 2) if ratings else 0,
        "reseller_growth_accelerating": False,
        "accelerating_count": 0,
        "regions_covered": ["pan-India"],
        "region_count": 1,
        "price_points": sorted(prices) if prices else [],
        "price_sensitivity_flag": "high" if prices and min(prices) < 300 else "normal",
        "_live_scraped": True,
    }


def _get_static_meesho_data(trend_id):
    """Original static JSON fallback."""
    with open(MEESHO_FILE) as f:
        data = json.load(f)

    trends = _load_trends()
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


def _load_trends():
    with open(TRENDS_FILE) as f:
        return json.load(f)


def _extract_low_price(price_band):
    try:
        parts = price_band.replace("₹", "").split("-")
        return int(parts[0])
    except (ValueError, IndexError):
        return 500
