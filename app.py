import streamlit as st
import json
import sys
from pathlib import Path

# Load .env file before anything else
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))

from sources.google_trends import fetch_google_trends
from sources.meta_ads import get_meta_ad_signals
from sources.marketplace import get_marketplace_data
from sources.reviews import get_review_signals
from sources.meesho import get_meesho_data
from sources.nykaa import get_nykaa_data
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
    st.info("📡 Scanned 6 sources · 8 trends surfaced · Last updated just now")

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
        with st.status("Pulling signals from 6 sources...", expanded=True) as status:
            st.write("📈 Google Trends...")
            trends_data = fetch_google_trends(trend.get("search_terms", []), use_cache=True)

            st.write("📢 Competitor ads (Meta Ad Library)...")
            meta_data = get_meta_ad_signals(trend["id"])

            st.write("🛒 Marketplace rankings (Myntra/Ajio)...")
            marketplace_data = get_marketplace_data(trend["id"])

            st.write("📦 Meesho (price-sensitive, tier-2/3/4)...")
            meesho_data = get_meesho_data(trend["id"])

            st.write("✨ Nykaa Fashion (premium trickle-down)...")
            nykaa_data = get_nykaa_data(trend["id"])

            st.write("💬 Customer review signals...")
            review_data = get_review_signals(trend["id"])

            status.update(label="Synthesizing evidence with AI...", state="running")
            synthesis = synthesize(trend, trends_data, meta_data, marketplace_data,
                                   review_data, meesho_data, nykaa_data)
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

    # Source quality at a glance
    gt_momentum = trends_data.get("momentum_score", 0)
    gt_live = trends_data.get("live", False)
    meta_competitors = len(meta_data.get("competitors_backing_this_trend", []))
    meta_max_days = max((c.get("ad_running_days", 0) for c in meta_data.get("competitors_backing_this_trend", [])), default=0)
    ms_units = meesho_data.get("total_units_sold", 0)
    ms_resellers = meesho_data.get("total_resellers", 0)
    ms_growth = any(p.get("is_accelerating") for p in meesho_data.get("products_found", []))
    nk_full_price = nykaa_data.get("full_price_products", 0)
    nk_editorial = nykaa_data.get("editorial_featured_count", 0)
    rv_count = review_data.get("total_analyzed", 0)
    rv_sentiment = review_data.get("sentiment", {}).get("positive", 0)

    source_quality_cols = st.columns(6)
    quality_items = [
        ("📈 Trends", f"Momentum: {gt_momentum:.0%}", "green" if gt_momentum > 0.15 else "orange" if gt_momentum > 0 else "grey"),
        ("📢 Ads", f"{meta_competitors} competitors, max {meta_max_days}d", "green" if meta_max_days >= 21 else "orange"),
        ("🛒 Mktplc", f"{marketplace_data.get('marketplace_presence', '?')} presence", "green" if marketplace_data.get('marketplace_presence') == 'strong' else "orange"),
        ("📦 Meesho", f"{ms_units:,}u, {ms_resellers} sellers{' ↗' if ms_growth else ''}", "green" if ms_units > 5000 else "orange" if ms_units > 1000 else "grey"),
        ("✨ Nykaa", f"{nk_full_price} full-price, {nk_editorial} editorial", "green" if nk_full_price >= 2 else "orange" if nk_full_price >= 1 else "grey"),
        ("💬 Reviews", f"{rv_count} reviews, {rv_sentiment:.0%} positive", "green" if rv_sentiment > 0.7 else "orange" if rv_sentiment > 0.5 else "grey"),
    ]
    for i, (label, value, color) in enumerate(quality_items):
        with source_quality_cols[i]:
            border = "1px solid #d1d5db" if color == "grey" else "1px solid #16a34a" if color == "green" else "1px solid #d97706"
            st.markdown(
                f"<div style='font-size:0.65rem;padding:6px;border-radius:4px;border:{border};text-align:center;'>"
                f"<div style='font-weight:600;margin-bottom:2px;'>{label}</div>"
                f"<div style='color:#374151;'>{value}</div></div>",
                unsafe_allow_html=True
            )
    st.caption("Quality indicators per source. Green = strong signal. Orange = moderate. Grey = weak/absent.")

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

    # Trust weight sliders (collapsible)
    source_weights = {}
    with st.expander("⚖️ Adjust source trust (how much do you believe each source?)", expanded=False):
        st.caption("Default: all sources weighted equally. Increase weight for sources you trust more, decrease for ones you think may mislead. The score updates automatically.")
        tw_col1, tw_col2 = st.columns(2)
        default_sources = [
            "Google Trends", "Competitor Ads (Meta)", "Myntra/Ajio",
            "Meesho (Price-sensitive)", "Nykaa Fashion (Premium)", "Customer Reviews"
        ]
        for i, src in enumerate(default_sources):
            with tw_col1 if i < 3 else tw_col2:
                source_weights[src] = st.slider(
                    src, 0.0, 2.0, 1.0, 0.1,
                    key=f"weight_{i}",
                    help="1.0 = default. >1 = trust more. <1 = trust less. 0 = ignore this source."
                )

    use_custom = any(abs(w - 1.0) > 0.05 for w in source_weights.values())
    if use_custom:
        bet = compute_bet_size(trend, synthesis, source_weights)
    else:
        bet = compute_bet_size(trend, synthesis)

    sizing = bet["sizing"]
    score = bet["score"]

    bet_col1, bet_col2 = st.columns([1, 2])

    with bet_col1:
        if sizing == "DEEP BUY":
            st.success(f"## {sizing}")
        elif sizing == "MODERATE BUY":
            st.info(f"## {sizing}")
        elif sizing == "TRIAL":
            st.warning(f"## {sizing}")
        elif sizing == "NEAR TRIAL":
            st.warning(f"## {sizing}")
        else:
            st.error(f"## {sizing}")

        st.metric("Confidence Score", f"{score}/{bet['max_score']}")

        # Visual gauge
        gauge_html = f"""
        <div style="background:#e5e7eb;border-radius:4px;height:8px;margin:8px 0;position:relative;">
          <div style="background:{'#16a34a' if score >= 7.5 else '#2563eb' if score >= 5 else '#ca8a04' if score >= 3 else '#d97706' if score >= 2 else '#dc2626'};border-radius:4px;height:8px;width:{score * 10}%;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#6b7280;margin-top:2px;">
          <span>0 WAIT</span><span>2 NEAR</span><span>3 TRIAL</span><span>5 MOD</span><span>7.5 DEEP</span><span>10</span>
        </div>
        """
        st.markdown(gauge_html, unsafe_allow_html=True)

        if bet.get("threshold_next"):
            st.caption(f"📏 {bet['threshold_next']}")
        st.caption(f"Price band: {bet['price_band']}")
        st.caption(f"Season: {bet['season']}")
        st.caption(f"Risk level: {bet['risk_level']}")
        if bet.get("source_weights_used"):
            st.caption("⚖️ Custom source weights applied")

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
        st.write(f"- Convergence score: {comps['convergence_score']} (from {comps['strong_for_count']} strong + {comps['moderate_for_count']} moderate sources for, {comps['strong_against_count']} strong + {comps['moderate_against_count']} moderate sources against)")
        st.write(f"- Disagreement penalty: -{comps['disagreement_penalty']} (from {comps['disagreement_count']} source conflicts)")
        st.write(f"- **Thresholds are set by judgment, not backtested data.** They will improve as sell-through outcomes feed back in.")
        if bet.get("source_weights_used"):
            st.write(f"- Custom source weights applied (see trust sliders above)")

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

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        with st.expander("📈 Google Trends", expanded=False):
            live_badge = "🟢 Live" if trends_data.get("live") else f"🔴 Cached ({trends_data.get('cached_at', 'unknown')})"
            st.caption(live_badge)
            if trends_data.get("error"):
                st.warning(f"Error: {trends_data['error']}")
            interest = trends_data.get("interest_data", {})
            if interest:
                for term, data in interest.items():
                    st.write(f"**{term}**")
                    st.write(f"  Current: {data.get('current')}  |  Direction: {data.get('direction')}  |  3m avg: {data.get('avg_3m')}")
            else:
                st.caption("No search interest data available.")
        with st.expander("🛒 Myntra/Ajio", expanded=False):
            st.caption(f"Last updated: {marketplace_data.get('last_updated', 'unknown')}")
            if marketplace_data.get("products_found"):
                st.dataframe(
                    [{"Product": p["name"], "Platform": p["platform"], "Brand": p["brand"],
                      "Price": f"₹{p['price']}", "Rank": p["rank"], "Rating": p["avg_rating"],
                      "Reviews/30d": p["review_velocity"], "Discount": p["discount"]}
                     for p in marketplace_data["products_found"]
                    ],
                    hide_index=True, use_container_width=True
                )
            else:
                st.caption("No matching products found.")
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
        with st.expander("📦 Meesho (Price-sensitive)", expanded=False):
            st.caption(meesho_data.get("disclaimer", ""))
            st.caption(meesho_data.get("platform_note", ""))
            if meesho_data.get("products_found"):
                st.dataframe(
                    [{"Product": p["name"], "Price": f"₹{p['price']}",
                      "Units Sold": p["units_sold"], "Rating": p["rating"],
                      "Resellers": p["reseller_count"], "Growth": p["reseller_growth_mom"],
                      "Regions": ", ".join(p["regions"][:3])}
                     for p in meesho_data["products_found"]
                    ],
                    hide_index=True, use_container_width=True
                )
                st.metric("Total Resellers", meesho_data.get("total_resellers", 0))
                st.metric("Total Units", f"{meesho_data.get('total_units_sold', 0):,}")
                st.caption(f"Regions covered: {', '.join(meesho_data.get('regions_covered', []))}")
            else:
                st.caption("No matching products on Meesho.")
    with col_c:
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
        with st.expander("✨ Nykaa Fashion (Premium)", expanded=False):
            st.caption(nykaa_data.get("disclaimer", ""))
            st.caption(nykaa_data.get("platform_note", ""))
            if nykaa_data.get("products_found"):
                st.dataframe(
                    [{"Product": p["name"], "Brand": p["brand"],
                      "Price": f"₹{p['price']}", "Discount": p["discount"],
                      "Rating": p["rating"], "Stock": p["stock_status"],
                      "Positioning": p["nykaa_positioning"]}
                     for p in nykaa_data["products_found"]
                    ],
                    hide_index=True, use_container_width=True
                )
                st.caption(f"Avg price: ₹{nykaa_data.get('avg_price', 0):.0f} | Trickle-down gap: ₹{nykaa_data.get('trickle_down_potential', 0):.0f}")
                if nykaa_data.get("full_price_products", 0) > 0:
                    st.success(f"{nykaa_data['full_price_products']} products at near-zero discount (genuine demand)")
                if nykaa_data.get("editorial_featured_count", 0) > 0:
                    st.info(f"Featured in {nykaa_data['editorial_featured_count']} Nykaa editorial placement(s)")
            else:
                st.caption("No matching products on Nykaa Fashion.")
            trend_notes = nykaa_data.get("trend_notes", "")
            if trend_notes:
                st.caption(f"📝 {trend_notes}")

    # -------- Empty State (no trend selected) --------
else:
    st.markdown("---")
    st.info("👆 Select a trend above to run a full evidence analysis with bet sizing recommendation.")

# -------- Footer --------
st.markdown("---")
st.caption("""**How to read this:** This tool organizes evidence — it does not make the decision for you.
Each source can mislead. Competitor ads may target a different customer. Marketplace ranks may reflect discounting, not demand.
Search trends may be inspiration, not purchase intent. Use this to reason through uncertainty, not replace it.""")
