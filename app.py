import json
import os
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
from synthesis.engine import synthesize, log_override, get_override_stats, init_telemetry

app = Flask(__name__)
DATA_DIR = Path(__file__).parent / "data"

init_telemetry()

with open(DATA_DIR / "cached_trends.json") as f:
    TRENDS = json.load(f)

DECISION_MAP = {
    "chanderi-straight": ("action", "ACTION NOW", "red"),
    "organza-embroidered": ("action", "ACTION NOW", "red"),
    "ajrakh-cotton": ("rising", "RISING", "orange"),
    "ikat-anarkali": ("rising", "RISING", "orange"),
    "bandhani-straight": ("rising", "RISING", "orange"),
    "fusion-palazzo": ("tracking", "TRACKING", "gray"),
    "blockprint-cotton": ("tracking", "TRACKING", "gray"),
    "linen-chinese-collar": ("tracking", "TRACKING", "gray"),
}

@app.route("/")
def decision_board():
    trends_with_status = []
    for t in TRENDS:
        priority, label, color = DECISION_MAP.get(t["id"], ("tracking", "TRACKING", "gray"))
        trends_with_status.append({**t, "priority": priority, "label": label, "color": color})

    action_items = [t for t in trends_with_status if t["priority"] == "action"]
    watching = [t for t in trends_with_status if t["priority"] != "action"]

    # Try to surface live search trends as supplement
    scanned = _scan_live_trends()

    return render_template("decision_board.html",
        action_items=action_items, watching=watching,
        scanned_trends=scanned, trends=TRENDS)

@app.route("/briefing/<trend_id>")
def briefing(trend_id):
    trend = next((t for t in TRENDS if t["id"] == trend_id), None)
    if not trend:
        return "Trend not found", 404

    nykaa  = get_nykaa_data(trend_id)
    myntra = get_marketplace_data(trend_id)
    meesho = get_meesho_data(trend_id)
    reviews = get_review_signals(trend_id)
    synth = synthesize(trend, nykaa, myntra, meesho)

    prio, label, color = DECISION_MAP.get(trend_id, ("tracking", "TRACKING", "gray"))

    return render_template("briefing.html",
        trend=trend, nykaa=nykaa, myntra=myntra, meesho=meesho,
        reviews=reviews, synth=synth, prio=prio, label=label, color=color)


def _scan_live_trends():
    try:
        from sources.google_trends import load_cache
        cache = load_cache()
        scanned = []

        for cache_key, data in cache.items():
            interest = data.get("interest_data", {})
            for term, term_data in interest.items():
                direction = term_data.get("direction", "stable")
                if direction == "rising" and "kurti" in term.lower():
                    current = term_data.get("current", 0)
                    peak = term_data.get("peak", 1)
                    momentum = min(99, int(current / max(peak, 1) * 100))
                    scanned.append({
                        "term": term, "direction": direction,
                        "momentum": momentum, "current": current
                    })

        scanned.sort(key=lambda s: -s["momentum"])
        seen = set()
        unique = []
        for s in scanned:
            if s["term"] not in seen:
                unique.append(s)
                seen.add(s["term"])
        return unique[:8]
    except Exception:
        return []

@app.route("/market-view")
def market_view():
    return render_template("market_view.html")

@app.route("/sourcing")
def sourcing():
    return render_template("sourcing.html")

@app.route("/api/override", methods=["POST"])
def api_override():
    data = request.get_json()
    log_override(
        data.get("trend_id", ""), data.get("trend_name", ""),
        data.get("system_bet", ""), data.get("reason", ""),
        data.get("notes", "")
    )
    return jsonify({"status": "ok"})

@app.route("/api/telemetry")
def api_telemetry():
    stats = get_override_stats()
    return jsonify([{"reason": r, "count": c} for r, c in stats])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
