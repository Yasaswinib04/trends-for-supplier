"""
Live Google Shopping — Real-Time Price Comparison
--------------------------------------------------
Uses SearchAPI.io's Google Shopping engine to pull live product listings,
pricing, ratings, and seller data from Google Shopping search results.

Falls back gracefully to cached data when API key is missing or credits exhausted.

Env var: GOOGLE_SHOPPING_API_KEY
Provider: SearchAPI.io (https://www.searchapi.io)

Usage:
    from sources.google_shopping import search_google_shopping
    results = search_google_shopping("chanderi silk kurti")
"""

import json
import os
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "google_shopping_cache.json"

SEARCHAPI_BASE = "https://www.searchapi.io/api/v1/search"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def search_google_shopping(query: str, use_cache: bool = True) -> dict:
    """
    Search Google Shopping for a product query. Returns live price
    comparison data across retailers found on Google Shopping.

    Returns:
        dict with:
          - live: bool
          - products: list of {title, price, rating, store, link, position}
          - price_range: {low, high, median}
          - store_count: number of unique sellers
          - fetched_at: ISO timestamp
    """
    api_key = os.getenv("GOOGLE_SHOPPING_API_KEY", "")
    cache_key = query.strip().lower()

    cache = _load_cache()
    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        return {**cached, "live": False, "source": "google_shopping"}

    if not api_key:
        return _empty_response(cache_key, "No GOOGLE_SHOPPING_API_KEY configured")

    try:
        params = urllib.parse.urlencode({
            "engine": "google_shopping",
            "q": query,
            "gl": "in",
            "hl": "en",
            "api_key": api_key,
        })
        url = f"{SEARCHAPI_BASE}?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": "KurtiTrendEngine/1.0"})
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read())

        if data.get("error"):
            return _fallback_response(cache_key, cache,
                                       f"API error: {data['error']}")

        shopping_results = data.get("shopping_results", [])
        if not shopping_results:
            return _fallback_response(cache_key, cache,
                                       "No shopping results returned")

        products = []
        prices = []
        stores = set()

        for item in shopping_results[:20]:
            price_val = _parse_price(item.get("price", "0"))
            rating_val = item.get("rating")

            product = {
                "title": item.get("title", ""),
                "price": price_val,
                "price_display": item.get("price", ""),
                "rating": float(rating_val) if rating_val else None,
                "reviews": item.get("reviews", 0),
                "store": item.get("source", ""),
                "link": item.get("link", ""),
                "position": item.get("position", 0),
                "thumbnail": item.get("thumbnail", ""),
            }
            products.append(product)
            if price_val > 0:
                prices.append(price_val)
            if product["store"]:
                stores.add(product["store"])

        prices_sorted = sorted(prices) if prices else [0]

        result = {
            "source": "google_shopping",
            "live": True,
            "query": query,
            "fetched_at": datetime.now().isoformat(),
            "products": products,
            "total_results": len(products),
            "price_range": {
                "low": prices_sorted[0] if prices_sorted else 0,
                "high": prices_sorted[-1] if prices_sorted else 0,
                "median": prices_sorted[len(prices_sorted) // 2] if prices_sorted else 0,
                "avg": round(sum(prices_sorted) / max(len(prices_sorted), 1), 0),
            },
            "store_count": len(stores),
            "stores": sorted(stores),
            "discount_prevalence": _discount_prevalence(products),
        }

        cache[cache_key] = {
            "fetched_at": result["fetched_at"],
            "query": query,
            "products": result["products"],
            "price_range": result["price_range"],
            "store_count": result["store_count"],
            "stores": result["stores"],
            "discount_prevalence": result["discount_prevalence"],
        }
        _save_cache(cache)

        return result

    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _fallback_response(cache_key, cache, "Rate limited (429)")
        if e.code == 401:
            return _empty_response(cache_key, "Invalid API key (401)")
        return _fallback_response(cache_key, cache, f"HTTP {e.code}")
    except Exception as e:
        return _fallback_response(cache_key, cache, str(e)[:100])


def get_price_context_for_trend(trend_name: str, expected_band: str = "",
                                 cache_ok: bool = True) -> dict:
    """
    Convenience: search Google Shopping for a trend name, then compare
    the actual price distribution to the expected price band.

    Returns enriched data with:
      - price_band_match: whether live prices fall in expected range
      - premium_gap: how far above expected range
      - market_fragmentation: how many sellers / price variance
    """
    result = search_google_shopping(trend_name, use_cache=cache_ok)
    if not result.get("products"):
        return {"source": "google_shopping", "available": False,
                "reason": result.get("error", "No data")}

    price_range = result["price_range"]
    store_count = result["store_count"]

    expected_low, expected_high = _parse_price_band(expected_band)

    in_band = (expected_low <= price_range["median"] <= expected_high) if expected_high else None

    return {
        "source": "google_shopping",
        "available": True,
        "live": result.get("live", False),
        "query": trend_name,
        "listing_count": result["total_results"],
        "observed_range": price_range,
        "expected_band": {"low": expected_low, "high": expected_high},
        "price_band_match": in_band,
        "premium_gap": max(0, price_range["median"] - expected_high) if expected_high else 0,
        "store_diversity": store_count,
        "discount_prevalence": result.get("discount_prevalence", "unknown"),
        "sellers": result.get("stores", []),
    }


def _parse_price(price_str: str) -> float:
    """Parse ₹1,499 or '1,499' or '1499.00' to float."""
    try:
        cleaned = price_str.replace("₹", "").replace(",", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return 0


def _parse_price_band(band: str) -> tuple:
    """Parse '₹399-599' to (399, 599)."""
    try:
        parts = band.replace("₹", "").split("-")
        return (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return (0, 0)


def _discount_prevalence(products: list) -> str:
    """How many products show discount badges in their listing."""
    discounted = 0
    for p in products:
        title = (p.get("title") or "").lower()
        if any(w in title for w in ["sale", "discount", "off", "clearance",
                                     "deal", "%", "save"]):
            discounted += 1
    if not products:
        return "unknown"
    pct = discounted / len(products)
    if pct > 0.5:
        return "heavy discounting"
    elif pct > 0.25:
        return "moderate discounting"
    return "mostly full-price"


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
        "source": "google_shopping",
        "live": False,
        "query": cache_key,
        "products": [],
        "price_range": {"low": 0, "high": 0, "median": 0},
        "store_count": 0,
        "error": reason,
    }


def _fallback_response(cache_key: str, cache: dict, reason: str) -> dict:
    if cache_key in cache:
        cached = cache[cache_key]
        return {**cached, "live": False, "source": "google_shopping",
                "fallback": True, "fallback_reason": reason}
    return _empty_response(cache_key, reason)
