"""
Live Marketplace — Real-Time Ecommerce Product Data (RapidAPI)
----------------------------------------------------------------
Queries RapidAPI's realtime ecommerce endpoint for live product listings
across Amazon, Flipkart, Myntra, and Ajio. Returns actual prices, ranks,
ratings, and stock status — replacing cached JSON with live data.

Env var: RAPIDAPI_KEY
API Host: realtime-flipkart-amazon-myntra-ajio-croma-product-details.p.rapidapi.com

Gracefully falls back to cached marketplace_data.json when key is missing
or rate-limited.

Usage:
    from sources.live_marketplace import search_live_marketplace
    results = search_live_marketplace("chanderi kurti", platform="myntra")
"""

import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "live_marketplace_cache.json"

RAPIDAPI_HOST = "realtime-flipkart-amazon-myntra-ajio-croma-product-details.p.rapidapi.com"
RAPIDAPI_BASE = "https://realtime-flipkart-amazon-myntra-ajio-croma-product-details.p.rapidapi.com"

SUPPORTED_PLATFORMS = ["amazon", "flipkart", "myntra", "ajio", "croma"]


def search_live_marketplace(query: str, platform: str = "myntra",
                            use_cache: bool = True) -> dict:
    """
    Search a specific ecommerce platform for live product data.

    Args:
        query: search term (e.g. "chanderi silk kurti")
        platform: one of amazon, flipkart, myntra, ajio, croma
        use_cache: if True, use cached result if available

    Returns:
        dict with live product listings, prices, ratings, ranks.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "")
    cache_key = f"{platform}|{query.strip().lower()}"

    cache = _load_cache()
    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        return {**cached, "live": False, "source": "live_marketplace"}

    if not api_key:
        return _empty_response(cache_key, "No RAPIDAPI_KEY configured")

    try:
        params = urllib.parse.urlencode({
            "q": query,
            "platform": platform,
            "country": "IN",
        })
        url = f"{RAPIDAPI_BASE}/search?{params}"

        headers = {
            "x-api-host": RAPIDAPI_HOST,
            "x-api-key": api_key,
            "Accept": "application/json",
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        if not data or data.get("error"):
            return _fallback_response(cache_key, cache,
                                       data.get("error", "Empty response"))

        products = _normalize_products(data, platform)

        result = {
            "source": "live_marketplace",
            "live": True,
            "query": query,
            "platform": platform,
            "fetched_at": datetime.now().isoformat(),
            "products": products,
            "total_found": len(products),
            "avg_price": _avg_price(products),
            "avg_rating": _avg_rating(products),
            "avg_discount_pct": _avg_discount(products),
            "has_sponsored": any(p.get("is_sponsored") for p in products),
            "stock_available": sum(1 for p in products
                                   if p.get("in_stock", True)),
        }

        cache[cache_key] = {
            "fetched_at": result["fetched_at"],
            "query": query,
            "platform": platform,
            "products": result["products"],
            "total_found": result["total_found"],
            "avg_price": result["avg_price"],
            "avg_rating": result["avg_rating"],
            "avg_discount_pct": result["avg_discount_pct"],
            "has_sponsored": result["has_sponsored"],
            "stock_available": result["stock_available"],
        }
        _save_cache(cache)

        return result

    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _fallback_response(cache_key, cache, "Rate limited (429)")
        if e.code == 401:
            return _empty_response(cache_key, "Invalid RAPIDAPI_KEY (401)")
        return _fallback_response(cache_key, cache, f"HTTP {e.code}")
    except Exception as e:
        return _fallback_response(cache_key, cache, str(e)[:100])


def search_all_platforms(query: str, platforms: list = None,
                         use_cache: bool = True) -> dict:
    """
    Search all supported platforms for a query. Returns a
    cross-platform comparison view.

    Args:
        query: search term
        platforms: list of platform names (default: myntra, ajio, amazon, flipkart)
        use_cache: use cached results if available

    Returns:
        dict with per-platform results + cross-platform summary.
    """
    platforms = platforms or ["myntra", "ajio", "amazon", "flipkart"]

    platform_results = {}
    all_prices = []
    all_products = []

    for platform in platforms:
        result = search_live_marketplace(query, platform, use_cache=use_cache)
        platform_results[platform] = result
        for p in result.get("products", []):
            p["_platform"] = platform
            all_products.append(p)
            if p.get("price", 0) > 0:
                all_prices.append(p["price"])

    prices_sorted = sorted(all_prices) if all_prices else [0]

    return {
        "source": "live_marketplace",
        "query": query,
        "fetched_at": datetime.now().isoformat(),
        "platforms_searched": len(platforms),
        "total_products": len(all_products),
        "platform_results": platform_results,
        "cross_platform_summary": {
            "price_range": {
                "low": prices_sorted[0] if prices_sorted else 0,
                "high": prices_sorted[-1] if prices_sorted else 0,
                "median": prices_sorted[len(prices_sorted) // 2] if prices_sorted else 0,
            },
            "platforms_with_data": [p for p in platforms
                                    if platform_results.get(p, {}).get("total_found", 0) > 0],
            "platforms_silent": [p for p in platforms
                                 if platform_results.get(p, {}).get("total_found", 0) == 0],
            "total_listings": len(all_products),
        },
    }


def _normalize_products(raw_data: dict, platform: str) -> list:
    """
    Normalize RapidAPI response into a standard product schema.
    The API response format can vary by platform — this handles
    common shapes.

    Common response shapes:
      {"products": [...]}
      {"results": [...]}
      {"data": [...]}
      [...] (bare array)
    """
    items = []

    if isinstance(raw_data, list):
        items = raw_data
    elif isinstance(raw_data, dict):
        for key in ("products", "results", "data", "items"):
            if key in raw_data and isinstance(raw_data[key], list):
                items = raw_data[key]
                break
        if not items:
            items = [raw_data]

    normalized = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        discount_pct = 0
        orig_price = item.get("original_price", item.get("mrp", item.get("price", 0)))
        sale_price = item.get("sale_price", item.get("price", item.get("discounted_price", 0)))
        if isinstance(orig_price, str):
            orig_price = float(orig_price.replace("₹", "").replace(",", "").strip() or 0)
        if isinstance(sale_price, str):
            sale_price = float(sale_price.replace("₹", "").replace(",", "").strip() or 0)
        if orig_price > sale_price > 0:
            discount_pct = round(((orig_price - sale_price) / orig_price) * 100, 0)

        normalized.append({
            "name": item.get("title", item.get("name", f"Product {i+1}")),
            "brand": item.get("brand", item.get("seller", "")),
            "platform": platform,
            "price": float(sale_price) if sale_price else 0,
            "original_price": float(orig_price) if orig_price else 0,
            "discount": f"{int(discount_pct)}%" if discount_pct > 0 else "0%",
            "discount_percentage": int(discount_pct),
            "rank": item.get("rank", item.get("position", i + 1)),
            "rating": float(item.get("rating", item.get("avg_rating", 0)) or 0),
            "reviews": int(item.get("reviews", item.get("review_count", 0)) or 0),
            "review_velocity": int(item.get("review_velocity_30d", item.get("velocity", 0)) or 0),
            "in_stock": item.get("in_stock", item.get("available", True)),
            "stock_status": "Low stock" if item.get("stock_left", 99) < 10 else "In stock",
            "is_sponsored": item.get("is_sponsored", item.get("sponsored", False)),
            "image_url": item.get("image", item.get("thumbnail", "")),
            "product_url": item.get("url", item.get("link", "")),
        })

    return normalized


def _avg_price(products: list) -> float:
    prices = [p["price"] for p in products if p.get("price", 0) > 0]
    return round(sum(prices) / max(len(prices), 1), 0) if prices else 0


def _avg_rating(products: list) -> float:
    ratings = [p["rating"] for p in products if p.get("rating", 0) > 0]
    return round(sum(ratings) / max(len(ratings), 1), 2) if ratings else 0


def _avg_discount(products: list) -> float:
    discounts = [p.get("discount_percentage", 0) for p in products]
    return round(sum(discounts) / max(len(discounts), 1), 0) if discounts else 0


def _load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _empty_response(cache_key: str, reason: str) -> dict:
    return {
        "source": "live_marketplace",
        "live": False,
        "query": cache_key.split("|")[-1] if "|" in cache_key else cache_key,
        "products": [],
        "total_found": 0,
        "error": reason,
    }


def _fallback_response(cache_key: str, cache: dict, reason: str) -> dict:
    if cache_key in cache:
        cached = cache[cache_key]
        return {**cached, "live": False, "source": "live_marketplace",
                "fallback": True, "fallback_reason": reason}
    return _empty_response(cache_key, reason)
