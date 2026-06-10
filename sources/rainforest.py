"""
Rainforest API — Live Amazon India Product Data
-------------------------------------------------
Uses Rainforest API (rainforestapi.com) to pull live Amazon.in product
listings, prices, ratings, discounts, and stock status.

Falls back gracefully when the API key is missing.

Env var: RAPIDAPI_KEY (same key used for Rainforest)

Usage:
    from sources.rainforest import search_amazon
    results = search_amazon("chanderi silk kurti")
"""

import json
import os
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "rainforest_cache.json"

try:
    from dotenv import load_dotenv
    load_dotenv(DATA_DIR.parent / ".env")
except ImportError:
    pass

RAINFOREST_BASE = "https://api.rainforestapi.com/request"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def search_amazon(query, use_cache=True, domain="amazon.in", max_results=20):
    """
    Search Amazon.in for products matching the query.

    Returns:
        dict with products list, avg_price, avg_rating, discount summary.
    """
    api_key = os.getenv("RAPIDAPI_KEY", "")
    cache_key = f"{domain}|{query.strip().lower()}"

    cache = _load_cache()
    if use_cache and cache_key in cache:
        cached = cache[cache_key]
        cached["live"] = False
        cached["source"] = "rainforest"
        return cached

    if not api_key:
        return _empty_response(cache_key, "No RAPIDAPI_KEY configured")

    try:
        params = urllib.parse.urlencode({
            "api_key": api_key,
            "type": "search",
            "amazon_domain": domain,
            "search_term": query,
            "max_page": 1,
        })
        url = f"{RAINFOREST_BASE}?{params}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read())

        request_info = data.get("request_info", {})
        if not request_info.get("success", True):
            return _fallback_response(cache_key, cache,
                                       request_info.get("message", "API error"))

        results = data.get("search_results", [])
        if not results:
            return _fallback_response(cache_key, cache, "No results")

        products = []
        prices = []

        for item in results[:max_results]:
            price_info = item.get("price", {})
            price_val = float(price_info.get("value", 0) or 0)
            orig_price_info = item.get("original_price", item.get("rrp", {}))
            orig_val = float(orig_price_info.get("value", 0) or 0) if isinstance(orig_price_info, dict) else 0

            discount_pct = 0
            if orig_val > price_val > 0:
                discount_pct = round((1 - price_val / orig_val) * 100, 0)

            rating_val = item.get("rating", 0)
            reviews_val = item.get("reviews_total", item.get("ratings_total", 0))

            is_sponsored = bool(item.get("is_sponsored", False)) or bool(item.get("sponsored", False))
            is_prime = bool(item.get("is_prime", False))

            avail = item.get("availability")
            stock_status = "In stock"
            if avail and isinstance(avail, dict):
                raw = (avail.get("raw") or "").lower()
                if "out of stock" in raw or "currently unavailable" in raw:
                    stock_status = "Out of stock"
                elif "only" in raw and "left" in raw:
                    stock_status = "Low stock"

            product = {
                "name": item.get("title", ""),
                "platform": "amazon",
                "price": price_val if price_val else 0,
                "original_price": orig_val if orig_val else price_val,
                "discount": f"{int(discount_pct)}%" if discount_pct > 0 else "0%",
                "discount_percentage": int(discount_pct),
                "rating": float(rating_val) if rating_val else 0,
                "reviews": int(reviews_val) if reviews_val else 0,
                "review_velocity": int(item.get("reviews_monthly", 0) or 0),
                "rank": item.get("position", item.get("rank", len(prices) + 1)),
                "stock_status": stock_status,
                "is_sponsored": is_sponsored,
                "is_prime": is_prime,
                "image_url": item.get("image", ""),
                "product_url": item.get("link", ""),
                "brand": item.get("brand", ""),
            }
            products.append(product)
            if price_val > 0:
                prices.append(price_val)

        prices_sorted = sorted(prices) if prices else [0]

        result = {
            "source": "rainforest",
            "live": True,
            "query": query,
            "domain": domain,
            "fetched_at": datetime.now().isoformat(),
            "products": products,
            "total_found": len(products),
            "avg_price": round(sum(prices) / max(len(prices), 1), 0),
            "avg_rating": round(sum(p["rating"] for p in products if p["rating"] > 0) / max(len([p for p in products if p["rating"] > 0]), 1), 2),
            "avg_discount_pct": round(sum(p["discount_percentage"] for p in products) / max(len(products), 1), 0),
            "price_range": {"low": prices_sorted[0], "high": prices_sorted[-1], "median": prices_sorted[len(prices_sorted)//2]} if prices_sorted else {"low": 0, "high": 0, "median": 0},
            "has_sponsored": any(p["is_sponsored"] for p in products),
            "sponsored_count": sum(1 for p in products if p["is_sponsored"]),
            "prime_count": sum(1 for p in products if p.get("is_prime")),
        }

        cache[cache_key] = {
            "fetched_at": result["fetched_at"],
            "query": query,
            "domain": domain,
            "products": result["products"],
            "total_found": result["total_found"],
            "avg_price": result["avg_price"],
            "avg_rating": result["avg_rating"],
            "avg_discount_pct": result["avg_discount_pct"],
            "price_range": result["price_range"],
            "has_sponsored": result["has_sponsored"],
            "sponsored_count": result["sponsored_count"],
        }
        _save_cache(cache)

        return result

    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _fallback_response(cache_key, cache, "Rate limited (429)")
        return _fallback_response(cache_key, cache, f"HTTP {e.code}")
    except Exception as e:
        return _fallback_response(cache_key, cache, str(e)[:100])


def _load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _empty_response(cache_key, reason):
    return {
        "source": "rainforest",
        "live": False,
        "query": cache_key.split("|")[-1] if "|" in cache_key else cache_key,
        "products": [],
        "total_found": 0,
        "avg_price": 0, "avg_rating": 0, "avg_discount_pct": 0,
        "price_range": {"low": 0, "high": 0, "median": 0},
        "has_sponsored": False, "sponsored_count": 0, "prime_count": 0,
        "error": reason,
    }


def _fallback_response(cache_key, cache, reason):
    if cache_key in cache:
        cached = cache[cache_key]
        cached["live"] = False
        cached["source"] = "rainforest"
        cached["fallback"] = True
        cached["fallback_reason"] = reason
        return cached
    return _empty_response(cache_key, reason)
