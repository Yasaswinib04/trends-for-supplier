import json
import os
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sources.marketplace import get_marketplace_data
from sources.meesho import get_meesho_data
from sources.nykaa import get_nykaa_data
from sources.reviews import get_review_signals
from sources.internal_pos import get_internal_pos_data
from synthesis.engine import synthesize, log_override, get_override_stats, init_telemetry
try:
    from signals.noise_cleaner import apply_all_filters as _clean_marketplace
    SIGNALS_AVAILABLE = True
except ImportError:
    _clean_marketplace = None
    SIGNALS_AVAILABLE = False

LIVE_SOURCES_AVAILABLE = False
_get_live_marketplace = None
_get_google_shopping = None
_fetch_google_trends_fn = None
try:
    from sources.live_marketplace import search_all_platforms as _get_live_marketplace
    from sources.google_shopping import get_price_context_for_trend as _get_google_shopping
    from sources.google_trends import fetch_google_trends as _fetch_google_trends_fn
    LIVE_SOURCES_AVAILABLE = True
except ImportError:
    pass

app = Flask(__name__)
DATA_DIR = Path(__file__).parent / "data"

init_telemetry()

with open(DATA_DIR / "cached_trends.json") as f:
    TRENDS = json.load(f)

DECISION_MAP = {
    "chanderi-straight": ("action", "HIGH CONFLICT", "red"),
    "organza-embroidered": ("action", "HIGH CONFLICT", "red"),
    "ajrakh-cotton": ("rising", "RISING", "orange"),
    "ikat-anarkali": ("rising", "RISING", "orange"),
    "bandhani-straight": ("rising", "RISING", "orange"),
    "fusion-palazzo": ("tracking", "TRACKING", "gray"),
    "blockprint-cotton": ("tracking", "TRACKING", "gray"),
    "linen-chinese-collar": ("tracking", "TRACKING", "gray"),
}

PAST_BETS_FILE = DATA_DIR / "past_bets.json"
with open(PAST_BETS_FILE) as f:
    PAST_BETS = json.load(f)

_synth_cache = {}

def _enrich_marketplace_data(trend):
    base = get_marketplace_data(trend["id"])
    if not LIVE_SOURCES_AVAILABLE or not _get_live_marketplace:
        return base
    try:
        terms = trend.get("search_terms", [trend["name"]])
        query = terms[0] if terms else trend["name"]
        live = _get_live_marketplace(query, platforms=["myntra", "ajio"], use_cache=False)
        if live and live.get("total_products", 0) > 0:
            all_products = []
            for platform, pdata in live.get("platform_results", {}).items():
                for p in pdata.get("products", []):
                    all_products.append({
                        "platform": platform, "name": p["name"],
                        "brand": p.get("brand", ""), "price": p["price"],
                        "discount": p.get("discount", "0%"),
                        "discount_percentage": p.get("discount_percentage", 0),
                        "is_sponsored": p.get("is_sponsored", False),
                        "rank": p.get("rank", 99), "reviews": p.get("reviews", 0),
                        "avg_rating": p.get("rating", 0),
                        "review_velocity": p.get("review_velocity", 0),
                        "stock_status": p.get("stock_status", "In stock"),
                        "discount_risk": _discount_risk(p),
                    })
            if all_products:
                base["live_data"] = True
                base["products_found"] = all_products
                return base
    except Exception:
        pass
    return base

def _discount_risk(product):
    disc = product.get("discount_percentage", 0)
    if disc >= 60: return "high"
    if disc >= 30: return "medium"
    return "low"

def _precache_all():
    print("\U0001f504 Pre-caching syntheses for all 8 trends...")
    for i, t in enumerate(TRENDS):
        if t["id"] in _synth_cache: continue
        try:
            ny = get_nykaa_data(t["id"]); my = _enrich_marketplace_data(t)
            ms = get_meesho_data(t["id"]); pos = get_internal_pos_data(t["id"])
            synth = synthesize(t, ny, my, ms, pos)
            _synth_cache[t["id"]] = synth
            print(f"  \u2705 {i+1}/8 {t['name'][:40]}")
        except Exception as e:
            print(f"  \u26a0\ufe0f {i+1}/8 {t['name'][:40]}: {str(e)[:60]}")
    print("\u2705 Pre-cache complete.")

_precache_thread = threading.Thread(target=_precache_all, daemon=True)
_precache_thread.start()


# ─── Decision Board ───

@app.route("/")
def decision_board():
    trends_with_status = []
    for t in TRENDS:
        priority, label, color = DECISION_MAP.get(t["id"], ("tracking", "TRACKING", "gray"))
        is_high_conflict = priority == "action"
        is_festive = "Festive" in t.get("season", "") or "Wedding" in t.get("season", "")
        is_commit_fabric = "Chanderi" in t["name"] or "Organza" in t["name"] or "Linen" in t["name"]
        is_reorderable = "Cotton" in t["name"] or "Rayon" in t.get("fabric", "")
        risk_score = 0
        if is_high_conflict: risk_score += 3
        if is_festive: risk_score += 2
        if is_commit_fabric: risk_score += 2
        if is_reorderable: risk_score -= 1
        trends_with_status.append({**t, "priority": priority, "label": label,
            "color": color, "risk_score": risk_score})
    trends_with_status.sort(key=lambda x: -x["risk_score"])
    action_items = [t for t in trends_with_status if t["priority"] == "action"]
    watching = [t for t in trends_with_status if t["priority"] != "action"]

    live_pulse = _get_live_pulse()

    return render_template("decision_board.html",
        action_items=action_items, watching=watching,
        live_pulse=live_pulse, trends=TRENDS,
        live_sources_available=LIVE_SOURCES_AVAILABLE)


def _get_live_pulse():
    """Aggregate live signals from Google Trends + marketplace APIs for the board."""
    pulse = {"search_signals": [], "marketplace_signals": [], "price_signals": [],
             "scanned": False, "error": None}
    kurti_terms = [
        "chanderi kurti", "organza kurti", "block print kurti", "ajrakh kurti",
        "bandhani kurti", "ikat kurti", "linen kurti", "palazzo kurti set",
        "cotton kurti", "anarkali kurti", "straight kurti", "chikankari kurti",
        "mirror work kurti", "kota doria kurti", "kalamkari kurti"
    ]

    # Google Trends — try live, fallback to cache
    if _fetch_google_trends_fn:
        try:
            gt = _fetch_google_trends_fn(kurti_terms, geo="IN", timeframe="today 3-m",
                                           use_cache=False)
            interest = gt.get("interest_data", {})
            for term, td in interest.items():
                direction = td.get("direction", "stable")
                if direction in ("rising", "surging"):
                    pulse["search_signals"].append({
                        "term": term, "direction": direction,
                        "momentum": mimax(99, int((td.get("current", 0) /
                            max(td.get("peak", 1), 1)) * 100)),
                        "live": gt.get("live", False),
                    })
            pulse["search_signals"].sort(key=lambda s: -s["momentum"])
            pulse["scanned"] = True
        except Exception as e:
            pulse["error"] = f"Trends: {str(e)[:60]}"
    else:
        try:
            from sources.google_trends import load_cache
            cache = load_cache()
            for ck, cd in cache.items():
                interest = cd.get("interest_data", {})
                for term, td in interest.items():
                    if td.get("direction") in ("rising", "surging") and "kurti" in term.lower():
                        pulse["search_signals"].append({
                            "term": term, "direction": td["direction"],
                            "momentum": mimax(99, int((td.get("current", 0) /
                                max(td.get("peak", 1), 1)) * 100)),
                            "live": False,
                        })
            pulse["search_signals"].sort(key=lambda s: -s["momentum"])
            pulse["scanned"] = True
        except Exception:
            pass

    # Live marketplace — top products across platforms
    if LIVE_SOURCES_AVAILABLE and _get_live_marketplace:
        try:
            for qt in kurti_terms[:5]:
                cross = _get_live_marketplace(qt, platforms=["myntra", "ajio"], use_cache=True)
                for plat, pdata in cross.get("platform_results", {}).items():
                    for p in pdata.get("products", [])[:3]:
                        if p.get("price", 0) > 0:
                            pulse["marketplace_signals"].append({
                                "term": qt, "platform": plat,
                                "name": (p.get("name") or "")[:50],
                                "price": p.get("price", 0),
                                "discount": p.get("discount_percentage", 0),
                                "rating": p.get("rating", 0),
                                "reviews": p.get("reviews", 0),
                                "stock": p.get("stock_status", ""),
                            })
            pulse["scanned"] = True
        except Exception as e:
            pulse["error"] = (pulse.get("error") or "") + f" Marketplace: {str(e)[:60]}"

    # Google Shopping — price context for top rising terms
    if LIVE_SOURCES_AVAILABLE and _get_google_shopping and pulse["search_signals"]:
        try:
            top_term = pulse["search_signals"][0]["term"] if pulse["search_signals"] else "kurti"
            gs = _get_google_shopping(top_term)
            if gs.get("available"):
                pulse["price_signals"] = [{
                    "query": top_term,
                    "listings": gs.get("listing_count", 0),
                    "low_price": gs.get("observed_range", {}).get("low", 0),
                    "high_price": gs.get("observed_range", {}).get("high", 0),
                    "median_price": gs.get("observed_range", {}).get("median", 0),
                    "stores": gs.get("store_diversity", 0),
                }]
        except Exception:
            pass

    # Deduplicate + cap
    seen = set()
    uniq = []
    for s in pulse["search_signals"]:
        if s["term"] not in seen:
            uniq.append(s); seen.add(s["term"])
    pulse["search_signals"] = uniq[:10]
    pulse["marketplace_signals"] = pulse["marketplace_signals"][:15]
    return pulse


def mimax(limit, val):
    return min(limit, max(0, val))


# ─── API: Live Scan ───

@app.route("/api/live-scan")
def api_live_scan():
    """API endpoint: trigger a live market scan and return results as JSON."""
    pulse = _get_live_pulse()
    return jsonify(pulse)


# ─── API: Product Deep Dive ───

@app.route("/api/product-deep-dive")
def api_product_deep_dive():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing ?q= query parameter"}), 400

    result = {"query": query, "live": False, "products": [], "price_context": None,
              "trends": None, "noise_summary": None}

    if LIVE_SOURCES_AVAILABLE and _get_live_marketplace:
        try:
            cross = _get_live_marketplace(query, platforms=["myntra", "ajio", "amazon", "flipkart"],
                                           use_cache=False)
            result["live"] = True
            all_prods = []
            for plat, pdata in cross.get("platform_results", {}).items():
                for p in pdata.get("products", [])[:5]:
                    all_prods.append({
                        "platform": plat, "name": p.get("name", ""),
                        "brand": p.get("brand", ""), "price": p.get("price", 0),
                        "original_price": p.get("original_price", 0),
                        "discount": p.get("discount_percentage", 0),
                        "rating": p.get("rating", 0), "reviews": p.get("reviews", 0),
                        "stock": p.get("stock_status", ""),
                        "sponsored": p.get("is_sponsored", False),
                    })
            result["products"] = all_prods

            if SIGNALS_AVAILABLE and _clean_marketplace and all_prods:
                noisy = _clean_marketplace(all_prods)
                result["noise_summary"] = noisy.get("noise_summary", {})
        except Exception as e:
            result["error"] = str(e)[:100]

    if LIVE_SOURCES_AVAILABLE and _get_google_shopping:
        try:
            gs = _get_google_shopping(query, "")
            if gs.get("available"):
                result["price_context"] = {
                    "listings": gs.get("listing_count", 0),
                    "price_low": gs.get("observed_range", {}).get("low", 0),
                    "price_high": gs.get("observed_range", {}).get("high", 0),
                    "price_median": gs.get("observed_range", {}).get("median", 0),
                    "stores": gs.get("store_diversity", 0),
                    "band_match": gs.get("price_band_match"),
                }
        except Exception:
            pass

    if _fetch_google_trends_fn:
        try:
            gt = _fetch_google_trends_fn([query], geo="IN", timeframe="today 3-m",
                                           use_cache=False)
            result["trends"] = {
                "direction": gt.get("trend_direction", "unknown"),
                "momentum": gt.get("momentum_score", 0),
                "live": gt.get("live", False),
            }
        except Exception:
            pass

    return jsonify(result)


# ─── Briefing Routes ───

@app.route("/briefing/<trend_id>")
def briefing(trend_id):
    trend = next((t for t in TRENDS if t["id"] == trend_id), None)
    if not trend:
        return "Trend not found", 404
    nykaa = get_nykaa_data(trend_id)
    myntra = _enrich_marketplace_data(trend)
    meesho = get_meesho_data(trend_id)
    reviews = get_review_signals(trend_id)
    internal = get_internal_pos_data(trend_id)
    prio, label, color = DECISION_MAP.get(trend_id, ("tracking", "TRACKING", "gray"))
    past = [b for b in PAST_BETS if b.get("current_trend_id") == trend_id]
    return render_template("briefing_loading.html",
        trend=trend, nykaa=nykaa, myntra=myntra, meesho=meesho,
        reviews=reviews, internal=internal, prio=prio, label=label, color=color,
        past_bets=past)

@app.route("/api/briefing/<trend_id>")
def api_briefing(trend_id):
    trend = next((t for t in TRENDS if t["id"] == trend_id), None)
    if not trend:
        return jsonify({"error": "Trend not found"}), 404
    if trend_id in _synth_cache:
        return jsonify(_synth_cache[trend_id])
    nykaa = get_nykaa_data(trend_id)
    myntra = _enrich_marketplace_data(trend)
    meesho = get_meesho_data(trend_id)
    internal = get_internal_pos_data(trend_id)
    synth = synthesize(trend, nykaa, myntra, meesho, internal)
    _synth_cache[trend_id] = synth
    return jsonify(synth)


# ─── Market View ───

@app.route("/market-view")
def market_view():
    live_pulse = _get_live_pulse()
    return render_template("market_view.html",
        live_pulse=live_pulse,
        live_sources_available=LIVE_SOURCES_AVAILABLE,
        past_bets=PAST_BETS)


# ─── Telemetry ───

@app.route("/api/override", methods=["POST"])
def api_override():
    data = request.get_json()
    log_override(data.get("trend_id", ""), data.get("trend_name", ""),
        data.get("system_bet", ""), data.get("reason", ""), data.get("notes", ""))
    return jsonify({"status": "ok"})

@app.route("/api/commit", methods=["POST"])
def api_commit():
    data = request.get_json()
    log_override(data.get("trend_id", ""), data.get("trend_name", ""),
        data.get("system_bet", ""), "Bet committed", data.get("notes", ""))
    return jsonify({"status": "ok"})

@app.route("/api/telemetry")
def api_telemetry():
    stats = get_override_stats()
    return jsonify([{"reason": r, "count": c} for r, c in stats])


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
