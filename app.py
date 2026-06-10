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
_get_historical_trends = None
_seed_historical_cache = None
_fetch_timeframe_trends = None
_get_festive_comparison = None
_search_amazon = None
KURTI_TERMS = [
    "chanderi kurti", "organza kurti", "block print kurti", "ajrakh kurti",
    "bandhani kurti", "ikat kurti", "linen kurti", "palazzo kurti set",
    "cotton kurti", "anarkali kurti", "straight kurti", "chikankari kurti",
    "mirror work kurti", "kota doria kurti", "kalamkari kurti"
]
try:
    from sources.rainforest import search_amazon as _search_amazon
    from sources.google_shopping import get_price_context_for_trend as _get_google_shopping
    from sources.google_trends import fetch_google_trends as _fetch_google_trends_fn
    from sources.google_trends import get_historical_trends as _get_historical_trends
    from sources.google_trends import seed_historical_cache as _seed_historical_cache
    from sources.google_trends import fetch_timeframe_trends as _fetch_timeframe_trends
    from sources.google_trends import get_festive_comparison as _get_festive_comparison
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

# Seed 12-month Google Trends cache in background
def _seed_trends_cache():
    if _seed_historical_cache:
        try:
            print("📊 Seeding 12-month Google Trends cache...")
            fetched = _seed_historical_cache()
            print(f"📊 Historical trends seeded: {fetched} terms")
        except Exception as e:
            print(f"⚠️ Trends seed error: {e}")

_trends_thread = threading.Thread(target=_seed_trends_cache, daemon=True)
_trends_thread.start()

# Pre-cache Amazon data for live pulse
def _seed_amazon_cache():
    if _search_amazon:
        try:
            print("📦 Pre-caching Amazon.in data...")
            _search_amazon("kurti ethnic women", use_cache=False)
            _search_amazon("chanderi kurti", use_cache=False)
            print("📦 Amazon cache seeded")
        except Exception as e:
            print(f"⚠️ Amazon cache seed: {str(e)[:60]}")

_amazon_thread = threading.Thread(target=_seed_amazon_cache, daemon=True)
_amazon_thread.start()


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
    """Aggregate live signals + 12-month historical trends for the board."""
    pulse = {"search_signals": [], "marketplace_signals": [], "price_signals": [],
             "historical_trends": [], "scanned": False, "error": None}
    kurti_terms = [
        "chanderi kurti", "organza kurti", "block print kurti", "ajrakh kurti",
        "bandhani kurti", "ikat kurti", "linen kurti", "palazzo kurti set",
        "cotton kurti", "anarkali kurti", "straight kurti", "chikankari kurti",
        "mirror work kurti", "kota doria kurti", "kalamkari kurti"
    ]

    # ── Historical Trends (12-month data from cache) ──
    if _get_historical_trends:
        try:
            hist = _get_historical_trends()
            for term, td in hist.items():
                if "kurti" in term.lower():
                    monthly = td.get("monthly_values", [])
                    mx = max(monthly) if monthly else 1
                    pulse["historical_trends"].append({
                        "term": term,
                        "direction": td["direction"],
                        "trajectory": td.get("year_trajectory", "unknown"),
                        "current": td["current"],
                        "peak": td["peak"],
                        "current_vs_peak": td.get("current_vs_peak_pct", 0),
                        "growth_8w": td.get("growth_8w_pct", 0),
                        "monthly": monthly,
                        "max_monthly": mx,
                        "seasonality": td.get("seasonality", False),
                        "peak_month": td.get("peak_month", 0),
                        "volatility": td.get("volatility", "low"),
                        "cached_at": td.get("cached_at", "")[:10],
                    })
            pulse["historical_trends"].sort(key=lambda h: -abs(h["growth_8w"]))
            pulse["scanned"] = True
        except Exception as e:
            pulse["error"] = f"Historical: {str(e)[:60]}"
    else:
        # Fallback to old-style cache
        try:
            from sources.google_trends import load_cache
            cache = load_cache()
            for ck, cd in cache.items():
                interest = cd.get("interest_data", {})
                for term, td in interest.items():
                    if "kurti" in term.lower():
                        monthly = td.get("monthly_values", [])
                        mx = max(monthly) if monthly else 1
                        pulse["historical_trends"].append({
                            "term": term,
                            "direction": td.get("direction", "stable"),
                            "trajectory": cd.get("year_trajectory",
                                       td.get("year_trajectory", "unknown")),
                            "current": td.get("current", 0),
                            "peak": td.get("peak", 1),
                            "current_vs_peak": int((td.get("current", 0) /
                                max(td.get("peak", 1), 1)) * 100),
                            "growth_8w": td.get("growth_8w_pct", 0),
                            "monthly": monthly,
                            "max_monthly": mx,
                            "seasonality": td.get("seasonality_detected", False),
                            "peak_month": td.get("peak_month", 0),
                            "volatility": "low",
                            "cached_at": cd.get("cached_at", "")[:10],
                        })
            pulse["historical_trends"].sort(key=lambda h: -abs(h["growth_8w"]))
            pulse["scanned"] = True
        except Exception:
            pass

    # ── Live Google Trends (current momentum) ──
    if _fetch_google_trends_fn:
        try:
            gt = _fetch_google_trends_fn(kurti_terms, geo="IN", timeframe="today 12-m",
                                           use_cache=False)
            interest = gt.get("interest_data", {})
            for term, td in interest.items():
                direction = td.get("direction", "stable")
                if direction in ("rising", "stable"):
                    pulse["search_signals"].append({
                        "term": term, "direction": direction,
                        "momentum": mimax(99, int((td.get("current", 0) /
                            max(td.get("peak", 1), 1)) * 100)),
                        "growth_8w": td.get("growth_8w_pct", 0),
                        "trajectory": td.get("year_trajectory", "unknown"),
                        "live": gt.get("live", False),
                    })
            pulse["search_signals"].sort(key=lambda s: -s["momentum"])
            pulse["scanned"] = True
        except Exception:
            pass

    # ── Fallback: generate search signals from historical trends ──
    if not pulse["search_signals"] and pulse["historical_trends"]:
        for h in pulse["historical_trends"]:
            if h.get("direction") in ("rising", "surging", "stable"):
                pulse["search_signals"].append({
                    "term": h["term"],
                    "direction": h["direction"],
                    "momentum": h.get("current_vs_peak", 50),
                    "growth_8w": h.get("growth_8w", 0),
                    "trajectory": h.get("trajectory", "unknown"),
                    "live": False,
                })
        pulse["search_signals"].sort(key=lambda s: -(s.get("growth_8w", 0)))
        if not pulse["scanned"]:
            pulse["scanned"] = True

    # ── Amazon Marketplace (Rainforest API) ──
    if LIVE_SOURCES_AVAILABLE and _search_amazon:
        try:
            az = _search_amazon("kurti ethnic women", use_cache=True)
            for p in az.get("products", [])[:10]:
                if p.get("price", 0) > 0:
                    pulse["marketplace_signals"].append({
                        "term": "kurti", "platform": "amazon",
                        "name": (p.get("name") or "")[:50],
                        "price": p.get("price", 0),
                        "discount": p.get("discount_percentage", 0),
                        "rating": p.get("rating", 0),
                        "reviews": p.get("reviews", 0),
                        "stock": p.get("stock_status", ""),
                        "sponsored": p.get("is_sponsored", False),
                    })
            pulse["scanned"] = True
        except Exception as e:
            pulse["error"] = (pulse.get("error") or "") + f" Amazon: {str(e)[:60]}"

    # ── Google Shopping ──
    if LIVE_SOURCES_AVAILABLE and _get_google_shopping:
        top_term = None
        if pulse["search_signals"]:
            top_term = pulse["search_signals"][0]["term"]
        elif pulse["historical_trends"]:
            top_term = pulse["historical_trends"][0]["term"]
        if top_term:
            try:
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

    pulse["search_signals"] = pulse["search_signals"][:10]
    pulse["marketplace_signals"] = pulse["marketplace_signals"][:15]
    pulse["historical_trends"] = pulse["historical_trends"][:15]
    return pulse


def mimax(limit, val):
    return min(limit, max(0, val))


# ─── API: Live Scan ───

@app.route("/api/live-scan")
def api_live_scan():
    """API endpoint: trigger a live market scan and return results as JSON."""
    pulse = _get_live_pulse()
    return jsonify(pulse)


# ─── API: Historical Trends (Time-Windowed) ───

@app.route("/api/historical-trends")
def api_historical_trends():
    """Returns Google Trends data for a specific time window or festive season."""
    window = request.args.get("window", "1Y").strip()
    festive = request.args.get("festive", "").strip()

    if festive and _get_festive_comparison:
        comp = _get_festive_comparison(KURTI_TERMS[:3], festive)
        return jsonify(comp)

    if _fetch_timeframe_trends:
        try:
            data = _fetch_timeframe_trends(KURTI_TERMS[:5], window=window)
            if data.get("interest_data"):
                terms_data = {}
                for term, td in data.get("interest_data", {}).items():
                    vals = td.get("weekly_values", [])
                    monthly = td.get("monthly_values", [])
                    terms_data[term] = {
                        "direction": td.get("direction", "stable"),
                        "trajectory": td.get("year_trajectory", "unknown"),
                        "current": td.get("current", 0),
                        "peak": td.get("peak", 0),
                        "avg": td.get("avg_12m", 0),
                        "growth_8w": td.get("growth_8w_pct", 0),
                        "weekly_values": vals[-8:] if vals else [],
                        "monthly_values": monthly[-6:] if monthly else [],
                        "live": data.get("live", False),
                    }
                return jsonify({
                    "window": window,
                    "window_label": data.get("window_label", window),
                    "trends": terms_data,
                    "overall_direction": data.get("trend_direction", "unknown"),
                    "live": data.get("live", False),
                })
        except Exception as e:
            pass  # fall through to fallback

    # Fallback: use get_historical_trends (possibly from static JSON)
    if _get_historical_trends:
        hist = _get_historical_trends()
        is_fallback = any(td.get("_fallback") for td in hist.values())
        terms_data = {}

        # Determine how many monthly bars to show based on window
        window_months = {"1M": 1, "3M": 3, "6M": 6, "YTD": 6, "1Y": 12}.get(window, 12)

        for term, td in hist.items():
            if "kurti" in term.lower():
                monthly = td.get("monthly_values", [])
                vals = td.get("weekly_values", [])

                # Slice to window size for fallback data
                monthly_sliced = monthly[-window_months:] if monthly and is_fallback else monthly
                weekly_sliced = vals[-min(window_months*2, len(vals)):] if vals and is_fallback else vals[-8:]

                terms_data[term] = {
                    "direction": td.get("direction", "stable"),
                    "trajectory": td.get("year_trajectory", "unknown"),
                    "current": td.get("current", 0),
                    "peak": td.get("peak", 0),
                    "avg": td.get("avg_12m", 0),
                    "growth_8w": td.get("growth_8w_pct", 0),
                    "weekly_values": weekly_sliced if weekly_sliced else [],
                    "monthly_values": monthly_sliced,
                    "live": False,
                }
        return jsonify({
            "window": window,
            "window_label": window,
            "trends": terms_data,
            "overall_direction": "mixed",
            "live": False,
            "fallback": is_fallback,
        })

    return jsonify({"error": "No trends source available", "window": window}), 503


# ─── API: Product Deep Dive ───

@app.route("/api/product-deep-dive")
def api_product_deep_dive():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing ?q= query parameter"}), 400

    result = {"query": query, "live": False, "products": [], "price_context": {},
              "trends": None, "noise_summary": None}

    if LIVE_SOURCES_AVAILABLE and _search_amazon:
        try:
            az = _search_amazon(query, use_cache=False)
            result["live"] = True
            all_prods = []
            for p in az.get("products", [])[:15]:
                all_prods.append({
                    "platform": "amazon",
                    "name": p.get("name", ""),
                    "brand": p.get("brand", ""),
                    "price": p.get("price", 0),
                    "original_price": p.get("original_price", 0),
                    "discount": p.get("discount_percentage", 0),
                    "rating": p.get("rating", 0),
                    "reviews": p.get("reviews", 0),
                    "stock": p.get("stock_status", ""),
                    "sponsored": p.get("is_sponsored", False),
                })
            result["products"] = all_prods
            result["avg_price"] = az.get("avg_price", 0)
            result["avg_rating"] = az.get("avg_rating", 0)
            result["price_range"] = az.get("price_range", {})
            result["sponsored_count"] = az.get("sponsored_count", 0)

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
            gt = _fetch_google_trends_fn([query], geo="IN", timeframe="today 12-m",
                                           use_cache=False)
            result["trends"] = {
                "direction": gt.get("trend_direction", "unknown"),
                "momentum": gt.get("momentum_score", 0),
                "live": gt.get("live", False),
                "year_trajectory": gt.get("year_trajectory", "unknown"),
                "monthly_values": [],
                "seasonality": False,
            }
            interest = gt.get("interest_data", {})
            if query in interest:
                td = interest[query]
                result["trends"].update({
                    "current": td.get("current", 0),
                    "peak": td.get("peak", 0),
                    "avg_12m": td.get("avg_12m", 0),
                    "growth_8w_pct": td.get("growth_8w_pct", 0),
                    "monthly_values": td.get("monthly_values", []),
                    "seasonality": td.get("seasonality_detected", False),
                })
            elif _get_historical_trends:
                # Fallback: search all cached historical entries for this term
                hist = _get_historical_trends()
                for tname, td in hist.items():
                    if query.lower() in tname.lower() or tname.lower() in query.lower():
                        result["trends"].update({
                            "current": td.get("current", 0),
                            "peak": td.get("peak", 0),
                            "avg_12m": td.get("avg_12m", 0),
                            "growth_8w_pct": td.get("growth_8w_pct", 0),
                            "monthly_values": td.get("monthly_values", []),
                            "seasonality": td.get("seasonality", False),
                            "year_trajectory": td.get("year_trajectory", "unknown"),
                            "matched_term": tname,
                        })
                        break
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
