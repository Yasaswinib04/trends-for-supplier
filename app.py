import streamlit as st
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sources.google_trends import fetch_google_trends
from sources.meta_ads import get_meta_ad_signals
from sources.marketplace import get_marketplace_data
from sources.reviews import get_review_signals
from synthesis.engine import synthesize, compute_bet_size

st.set_page_config(
    page_title="Kurti Trend Judgment Engine",
    page_icon="🪡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent / "data"

with open(DATA_DIR / "cached_trends.json") as f:
    ALL_TRENDS = json.load(f)

st.title("🪡 Kurti Trend Judgment Engine")
st.caption("For category buyers: find early evidence, judge it honestly, decide what inventory to bet on.")

st.markdown("---")

# -------- PHASE 1: Trend Discovery --------
st.header("Surfaced Trends")
st.caption("Trends surfaced from competitor activity, search momentum, and marketplace movement. Select one to investigate.")

# Animated scan indicator
scan_placeholder = st.empty()
with scan_placeholder.container():
    st.info("📡 Scanned 4 sources · 8 trends surfaced · Last updated just now")

cols = st.columns(4)
selected_idx = None

for i, trend in enumerate(ALL_TRENDS):
    with cols[i % 4]:
        with st.container(border=True):
            title_html = f"<div style='font-size:0.95rem;font-weight:600;line-height:1.3;min-height:3rem;margin-bottom:0.5rem;'>{trend['name']}</div>"
            st.markdown(title_html, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.caption(f"💰 {trend['price_band']}")
            with c2:
                st.caption(f"🌤️ {trend['season']}")

            st.caption(f"📊 {trend['signal_summary']}")

            if st.button("Analyze →", key=f"select_{i}", use_container_width=True):
                selected_idx = i

# -------- Handle Trend Selection --------
if selected_idx is not None:
    st.session_state.selected_trend = ALL_TRENDS[selected_idx]
    st.rerun()

if "selected_trend" in st.session_state and st.session_state.selected_trend:
    trend = st.session_state.selected_trend

    st.markdown("---")
    st.header(f"Deep Dive: {trend['name']}")

    back_col, _ = st.columns([1, 5])
    with back_col:
        if st.button("← Back to trends"):
            del st.session_state.selected_trend
            st.rerun()

    # -------- PHASE 2: Run Analysis --------
    with st.spinner("🔍 Researching across sources..."):
        with st.status("Pulling signals from 4 sources...", expanded=True) as status:
            st.write("📈 Google Trends...")
            trends_data = fetch_google_trends(trend.get("search_terms", []), use_cache=True)

            st.write("📢 Competitor ads (Meta Ad Library)...")
            meta_data = get_meta_ad_signals(trend["id"])

            st.write("🛒 Marketplace rankings (Myntra/Ajio)...")
            marketplace_data = get_marketplace_data(trend["id"])

            st.write("💬 Customer review signals...")
            review_data = get_review_signals(trend["id"])

            status.update(label="Synthesizing evidence with AI...", state="running")
            synthesis = synthesize(trend, trends_data, meta_data, marketplace_data, review_data)
            bet = compute_bet_size(trend, synthesis)
            status.update(label="Analysis complete", state="complete")

    # -------- Results Display --------
    st.markdown("---")

    # Summary
    st.subheader("Summary")
    st.markdown(f"> {synthesis.get('summary', 'No summary available.')}")
    if synthesis.get("_note"):
        st.caption(f"⚠️ {synthesis['_note']}")
    if synthesis.get("_deepseek_error"):
        st.caption(f"⚠️ AI synthesis unavailable: {synthesis['_deepseek_error']}")

    st.markdown("---")

    # Evidence For / Against
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("✅ Evidence For")
        for_count = len(synthesis.get("for", []))
        st.caption(f"{for_count} signals supporting this bet")
        for item in synthesis.get("for", []):
            strength_color = "#16a34a" if item["strength"] == "strong" else "#ca8a04" if item["strength"] == "moderate" else "#6b7280"
            with st.container(border=True):
                st.markdown(f"<span style='color:{strength_color};font-size:0.8rem;font-weight:600;'>[{item['strength'].upper()}]</span> **{item['source']}**", unsafe_allow_html=True)
                st.write(item["signal"])

    with col2:
        st.subheader("❌ Evidence Against")
        against_count = len(synthesis.get("against", []))
        st.caption(f"{against_count} signals warning against this bet")
        for item in synthesis.get("against", []):
            strength_color = "#dc2626" if item["strength"] == "strong" else "#d97706" if item["strength"] == "moderate" else "#6b7280"
            with st.container(border=True):
                st.markdown(f"<span style='color:{strength_color};font-size:0.8rem;font-weight:600;'>[CONCERN]</span> **{item['source']}**", unsafe_allow_html=True)
                st.write(item["signal"])

    # Disagreements
    disagreements = synthesis.get("disagreements", [])
    if disagreements:
        st.markdown("---")
        st.subheader("⚡ Sources Disagree On")
        for d in disagreements:
            with st.container(border=True):
                st.warning(f"**{d['topic']}**")
                st.caption(f"{d['source_a']} vs. {d['source_b']}")
                st.write(d["detail"])

    # Bet Sizing Recommendation
    st.markdown("---")
    st.subheader("💰 Bet Sizing Recommendation")

    bet_col1, bet_col2 = st.columns([1, 2])

    with bet_col1:
        sizing = bet["sizing"]
        if sizing == "DEEP BUY":
            st.success(f"## {sizing}")
        elif sizing == "MODERATE BUY":
            st.info(f"## {sizing}")
        elif sizing == "TRIAL":
            st.warning(f"## {sizing}")
        else:
            st.error(f"## {sizing}")

        st.metric("Confidence Score", f"{bet['score']}/{bet['max_score']}")
        st.caption(f"Price band: {bet['price_band']}")
        st.caption(f"Season: {bet['season']}")
        st.caption(f"Risk level: {bet['risk_level']}")

    with bet_col2:
        with st.container(border=True):
            st.markdown("**Why this call**")
            st.write(bet["rationale"])
        with st.container(border=True):
            st.markdown("**What to do**")
            st.write(bet["suggested_action"])

    # Scoring breakdown (collapsible)
    with st.expander("📐 See scoring breakdown", expanded=False):
        comps = bet["components"]
        st.write(f"- Convergence score: {comps['convergence_score']} (from {comps['strong_for_count']} strong + {comps['moderate_for_count']} moderate sources for, {comps['strong_against_count']} strong sources against)")
        st.write(f"- Disagreement penalty: -{comps['disagreement_penalty']} (from {comps['disagreement_count']} source conflicts)")

    # What to watch
    st.markdown("---")
    st.subheader("🔭 What to Watch Next")
    for item in synthesis.get("watch_next", []):
        st.markdown(f"- {item}")

    # Missing evidence
    missing = synthesis.get("missing_evidence", [])
    if missing:
        st.markdown("---")
        st.subheader("❓ Missing Evidence")
        st.caption("What would change the call if we knew it:")
        for item in missing:
            st.markdown(f"- {item}")

    # Source Details (collapsible)
    st.markdown("---")
    st.subheader("📋 Source Details")
    st.caption("Inspect raw signals. Every recommendation links back to these.")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("📈 Google Trends", expanded=False):
            live_badge = "🟢 Live" if trends_data.get("live") else f"🔴 Cached ({trends_data.get('cached_at', 'unknown')})"
            st.caption(live_badge)
            if trends_data.get("error"):
                st.warning(f"Error: {trends_data['error']}")
            st.json({k: v for k, v in trends_data.items() if k not in ("interest_data",)})
            interest = trends_data.get("interest_data", {})
            if interest:
                for term, data in interest.items():
                    st.write(f"**{term}**")
                    st.write(f"  Current: {data.get('current')}  |  Direction: {data.get('direction')}  |  3m avg: {data.get('avg_3m')}")
            else:
                st.caption("No search interest data available.")
        with st.expander("🛒 Marketplace Data", expanded=False):
            st.caption(f"Last updated: {marketplace_data.get('last_updated', 'unknown')}")
            if marketplace_data.get("products_found"):
                st.table([
                    {"Product": p["name"], "Platform": p["platform"], "Brand": p["brand"],
                     "Price": f"₹{p['price']}", "Rank": p["rank"], "Rating": p["avg_rating"],
                     "Reviews/30d": p["review_velocity"], "Discount": p["discount"]}
                    for p in marketplace_data["products_found"]
                ])
            else:
                st.caption("No matching products found on marketplace.")
    with col_b:
        with st.expander("📢 Competitor Ads (Meta)", expanded=False):
            st.caption(meta_data.get("disclaimer", ""))
            st.caption(f"Competitor conviction: **{meta_data.get('ad_conviction', 'unknown')}**")
            competitors = meta_data.get("competitors_backing_this_trend", [])
            if competitors:
                for c in competitors:
                    st.write(f"- **{c['brand']}** — {c['product']} (₹{c['price']}, ad running {c['ad_running_days']}d, signal: {c['signal_strength']})")
            else:
                st.caption("No competitors actively advertising this trend.")
        with st.expander("💬 Review Signals", expanded=False):
            if review_data.get("available"):
                st.caption(f"Reviews analyzed: {review_data.get('total_analyzed')}")
                s = review_data.get("sentiment", {})
                st.write(f"Positive: {s.get('positive', 0):.0%}  |  Neutral: {s.get('neutral', 0):.0%}  |  Negative: {s.get('negative', 0):.0%}")
                st.write("**Top praise:**")
                for p in review_data.get("praise", []):
                    st.write(f"  👍 {p}")
                st.write("**Top complaints:**")
                for c in review_data.get("complaints", []):
                    st.write(f"  👎 {c}")
            else:
                st.caption("No review data available for this trend.")

# -------- Empty State (no trend selected) --------
else:
    st.markdown("---")
    st.info("👆 Select a trend above to run a full evidence analysis with bet sizing recommendation.")

# -------- Footer --------
st.markdown("---")
st.caption("""**How to read this:** This tool organizes evidence — it does not make the decision for you.
Each source can mislead. Competitor ads may target a different customer. Marketplace ranks may reflect discounting, not demand.
Search trends may be inspiration, not purchase intent. Use this to reason through uncertainty, not replace it.""")
