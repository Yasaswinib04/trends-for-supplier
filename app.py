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

TRIAGE_MAP = {
    "chanderi-straight": ("critical", "CRITICAL", "red"),
    "organza-embroidered": ("critical", "CRITICAL", "red"),
    "ajrakh-cotton": ("emerging", "EMERGING", "orange"),
    "ikat-anarkali": ("emerging", "EMERGING", "orange"),
    "bandhani-straight": ("emerging", "EMERGING", "orange"),
    "fusion-palazzo": ("monitor", "MONITOR", "gray"),
    "blockprint-cotton": ("monitor", "MONITOR", "gray"),
    "linen-chinese-collar": ("monitor", "MONITOR", "gray"),
}

@app.route("/")
def triage():
    trends_with_status = []
    for t in TRENDS:
        priority, label, color = TRIAGE_MAP.get(t["id"], ("monitor", "MONITOR", "gray"))
        trends_with_status.append({**t, "priority": priority, "label": label, "color": color})

    critical = [t for t in trends_with_status if t["priority"] == "critical"]
    others = [t for t in trends_with_status if t["priority"] != "critical"]
    return render_template("triage.html", critical=critical, others=others, trends=TRENDS)

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

    prio, label, color = TRIAGE_MAP.get(trend_id, ("monitor", "MONITOR", "gray"))

    return render_template("briefing.html",
        trend=trend, nykaa=nykaa, myntra=myntra, meesho=meesho,
        reviews=reviews, synth=synth, prio=prio, label=label, color=color)

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
