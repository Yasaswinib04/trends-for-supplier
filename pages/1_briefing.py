import streamlit as st
import streamlit.components.v1 as components
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.google_trends import fetch_google_trends
from sources.meta_ads import get_meta_ad_signals
from sources.marketplace import get_marketplace_data
from sources.reviews import get_review_signals
from sources.meesho import get_meesho_data
from sources.nykaa import get_nykaa_data
from synthesis.engine import synthesize, compute_bet_size
from styles.design import SIDEBAR_NAV_CSS, STATUS_BADGE_CSS, EVIDENCE_DRAWER_JS, DESIGN_TOKENS

st.set_page_config(
    page_title="The Briefing",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(SIDEBAR_NAV_CSS + STATUS_BADGE_CSS + EVIDENCE_DRAWER_JS, unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent.parent / "data"

if "selected_trend" not in st.session_state:
    st.error("No trend selected. Return to Triage.")
    if st.button("← Back to Triage"):
        st.switch_page("app.py")
    st.stop()

trend = st.session_state.selected_trend

# Back + header
col_back, col_title = st.columns([1, 10])
with col_back:
    if st.button("← Back", key="btn_back"):
        del st.session_state.selected_trend
        st.switch_page("app.py")

# Load analysis data
@st.cache_data(show_spinner=False)
def load_sources(_trend_id, _search_terms):
    gt = fetch_google_trends(_search_terms, use_cache=True)
    ma = get_meta_ad_signals(_trend_id)
    mp = get_marketplace_data(_trend_id)
    ms = get_meesho_data(_trend_id)
    nk = get_nykaa_data(_trend_id)
    rv = get_review_signals(_trend_id)
    return gt, ma, mp, ms, nk, rv

gt, ma, mp, ms, nk, rv = load_sources(trend["id"], trend.get("search_terms", []))

# Run synthesis
with st.spinner(""):
    synthesis = synthesize(trend, gt, ma, mp, rv, ms, nk)
    bet = compute_bet_size(trend, synthesis)

# ---- HEADER ----
st.markdown(f"# {trend['name']}")
st.caption("The Briefing · Detail View")

# Status badges row
badge_cols = st.columns(3)
with badge_cols[0]:
    risk = bet.get("risk_level", "")
    risk_color = "#16a34a" if "Low" in risk else "#d97706" if "Moderate" in risk else "#dc2626"
    margin_risk = "High" if bet["score"] < 3 else "Medium" if bet["score"] < 6 else "Low"
    st.markdown(f"""
    <div style="padding:6px 12px;border-radius:4px;font-size:12px;font-weight:600;display:inline-block;
    background:#ffdad6;color:#93000a;border:1px solid #ba1a1a;">
    ⚠ Margin Risk: {margin_risk}</div>""", unsafe_allow_html=True)

with badge_cols[1]:
    velocity = "Fast" if bet["score"] >= 5 else "Medium"
    st.markdown(f"""
    <div style="padding:6px 12px;border-radius:4px;font-size:12px;font-weight:600;display:inline-block;
    background:#94f990;color:#002204;border:1px solid #006e1c;">
    📈 Inventory Velocity: {velocity}</div>""", unsafe_allow_html=True)

with badge_cols[2]:
    otb = int(bet["score"] * 25000) if bet["score"] > 0 else 5000
    st.markdown(f"""
    <div style="padding:6px 12px;border-radius:4px;font-size:12px;font-weight:600;display:inline-block;
    background:#ecedfa;color:#424656;border:1px solid #c3c6d8;">
    💰 OTB Impact: ₹{otb:,}</div>""", unsafe_allow_html=True)

st.markdown("---")

# ---- CONVICTION SCORE ----
conviction_pct = max(10, min(98, int(bet["score"] * 10)))
st.markdown(f"""
<div style="background:#f2f3ff;border:1px solid #c3c6d8;padding:16px;border-radius:4px;display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
    <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:40px;height:40px;border-radius:50%;background:#0f62fe;color:white;display:flex;align-items:center;justify-content:center;">📊</div>
        <div>
            <strong style="font-size:14px;color:#191b24;">Bet Conviction</strong>
            <p style="font-size:12px;color:#424656;margin:0;">Based on 6 independent sources across 3 platforms.</p>
        </div>
    </div>
    <div style="text-align:right;">
        <span style="font-size:48px;font-weight:700;color:#004ccd;line-height:1;">{conviction_pct}%</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---- CONTEXTUAL BRIEF (Upside vs Catch) ----
st.markdown("### The Contextual Brief")
st.caption("Last updated just now")

col_upside, col_catch = st.columns(2)

with col_upside:
    st.markdown("""
    <div style="margin-bottom:12px;color:#006e1c;font-size:13px;font-weight:600;">
    📈 THE UPSIDE (WHY WE BUY)
    </div>
    """, unsafe_allow_html=True)
    for evidence in synthesis.get("for", []):
        strength_icon = "●" if evidence["strength"] == "strong" else "◐" if evidence["strength"] == "moderate" else "○"
        strength_color = "#16a34a" if evidence["strength"] == "strong" else "#ca8a04" if evidence["strength"] == "moderate" else "#6b7280"
        with st.container():
            st.markdown(f"""
            <div style="border:1px solid #c3c6d8;border-radius:4px;padding:12px;margin-bottom:8px;">
                <div style="color:{strength_color};font-size:12px;font-weight:600;margin-bottom:4px;">{strength_icon} {evidence['source']}</div>
                <p style="font-size:14px;color:#191b24;margin:0;">{evidence['signal']}</p>
            </div>
            """, unsafe_allow_html=True)

with col_catch:
    st.markdown("""
    <div style="margin-bottom:12px;color:#855300;font-size:13px;font-weight:600;">
    ⚡ THE CATCH (WHERE THE RISK SITS)
    </div>
    """, unsafe_allow_html=True)
    for evidence in synthesis.get("against", []):
        concern_color = "#dc2626" if evidence["strength"] == "strong" else "#d97706" if evidence["strength"] == "moderate" else "#6b7280"
        with st.container():
            st.markdown(f"""
            <div style="border:1px solid #c3c6d8;border-radius:4px;padding:12px;margin-bottom:8px;background:#faf8ff;">
                <div style="color:{concern_color};font-size:12px;font-weight:600;margin-bottom:4px;">⚠ {evidence['source']}</div>
                <p style="font-size:14px;color:#191b24;margin:0;">{evidence['signal']}</p>
            </div>
            """, unsafe_allow_html=True)

# Disagreements
disagreements = synthesis.get("disagreements", [])
if disagreements:
    st.markdown("---")
    st.markdown("### ⚡ Source Disagreements")
    for d in disagreements:
        with st.container():
            st.warning(f"**{d['topic']}**")
            st.caption(f"{d['source_a']} vs. {d['source_b']} — {d['detail']}")

# ---- VISUAL PROOF ----
st.markdown("---")
st.markdown("### 📸 Visual Proof")
vis_cols = st.columns(4)
platforms = [
    ("Myntra", "Myntra bestseller listing"),
    ("Nykaa", "Nykaa editorial feature"),
    ("Meesho", "Meesho reseller listing"),
    ("Meta Ads", "Competitor Meta ad creative"),
]
for i, (platform, desc) in enumerate(platforms):
    with vis_cols[i]:
        st.markdown(f"""
        <div style="border:1px solid #c3c6d8;border-radius:4px;overflow:hidden;text-align:center;">
            <div style="height:120px;background:#ecedfa;display:flex;align-items:center;justify-content:center;font-size:32px;">
                {'🛍️' if platform == 'Myntra' else '✨' if platform == 'Nykaa' else '📦' if platform == 'Meesho' else '📢'}
            </div>
            <div style="padding:6px;font-size:11px;color:#424656;background:#f2f3ff;">{platform}</div>
        </div>
        """, unsafe_allow_html=True)

# ---- CUSTOMER SENTIMENT ----
st.markdown("---")
sent_col1, sent_col2 = st.columns(2)

with sent_col1:
    st.markdown("### 👍 Top Praise")
    for p in rv.get("praise", [])[:3]:
        st.markdown(f"""
        <div style="background:#f2f3ff;padding:8px 12px;border-radius:4px;margin-bottom:4px;font-size:13px;color:#191b24;">
        💬 {p}
        </div>
        """, unsafe_allow_html=True)

with sent_col2:
    st.markdown("### 👎 Top Complaints")
    for c in rv.get("complaints", [])[:3]:
        st.markdown(f"""
        <div style="background:#f2f3ff;padding:8px 12px;border-radius:4px;margin-bottom:4px;font-size:13px;color:#191b24;">
        💬 {c}
        </div>
        """, unsafe_allow_html=True)

# ---- SOURCE DETAILS ----
st.markdown("---")
st.markdown("### 📋 Source Evidence")
src_col1, src_col2, src_col3 = st.columns(3)

with src_col1:
    with st.expander("📈 Google Trends", expanded=False):
        interest = gt.get("interest_data", {})
        if interest:
            for term, d in interest.items():
                st.write(f"**{term}** — {d.get('direction', '?')}, current: {d.get('current')}")
        else:
            st.caption("No search data")
    with st.expander("📢 Competitor Ads (Meta)", expanded=False):
        for c in ma.get("competitors_backing_this_trend", []):
            st.write(f"- **{c['brand']}**: {c['product']} ({c['ad_running_days']}d)")

with src_col2:
    with st.expander("🛒 Myntra/Ajio", expanded=False):
        for p in mp.get("products_found", []):
            st.write(f"- {p['name']} — Rank #{p['rank']}, {p['discount']} off")
    with st.expander("📦 Meesho", expanded=False):
        for p in ms.get("products_found", []):
            st.write(f"- {p['name']} — {p['units_sold']} sold, {p['reseller_count']} sellers")

with src_col3:
    with st.expander("✨ Nykaa Fashion", expanded=False):
        for p in nk.get("products_found", []):
            st.write(f"- {p['brand']}: {p['name']} — ₹{p['price']}, {p['discount']} off")
    with st.expander("💬 Reviews", expanded=False):
        if rv.get("available"):
            s = rv.get("sentiment", {})
            st.write(f"Positive: {s.get('positive',0):.0%} | Total: {rv.get('total_analyzed')} reviews")

# ---- STICKY FOOTER (BET SIZING) ----
st.markdown("---")
st.markdown("### 💰 The Final Call")

footer_col1, footer_col2 = st.columns([3, 1])
with footer_col1:
    sizing = bet["sizing"]
    sizing_color = "#16a34a" if sizing == "DEEP BUY" else "#2563eb" if sizing == "MODERATE BUY" else "#ca8a04" if sizing in ("TRIAL", "NEAR TRIAL") else "#dc2626"
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:12px;font-weight:600;color:#424656;">System Suggestion:</span>
        <span style="font-size:18px;font-weight:700;color:{sizing_color};">{sizing}</span>
        <span style="font-size:13px;color:#424656;">— {bet['suggested_action'][:80]}...</span>
    </div>
    """, unsafe_allow_html=True)

    # Score gauge
    score = bet["score"]
    bar_color = "#16a34a" if score >= 7.5 else "#2563eb" if score >= 5 else "#ca8a04" if score >= 3 else "#d97706" if score >= 2 else "#dc2626"
    st.markdown(f"""
    <div style="background:#e5e7eb;border-radius:4px;height:6px;margin:8px 0;">
        <div style="background:{bar_color};border-radius:4px;height:6px;width:{score*10}%;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#6b7280;">
        <span>0</span><span>2 WAIT</span><span>3 NEAR</span><span>5 MOD</span><span>7.5 DEEP</span><span>10</span>
    </div>
    """, unsafe_allow_html=True)

with footer_col2:
    if st.button("✏️ Override Call", use_container_width=True, type="secondary"):
        st.session_state.show_override = True
    if st.button("✅ Commit to Bet", use_container_width=True, type="primary"):
        st.success("Bet committed! Redirecting to Sourcing...")
        st.balloons()

# Override modal
if st.session_state.get("show_override"):
    with st.form("override_form"):
        st.markdown("### Override Rationale")
        reason = st.selectbox("Reason:", ["Lead time constraints", "Silhouette not aligned", "Margin limits", "Other"])
        detail = st.text_area("Detailed rationale required", placeholder="Enter justification...")
        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("Cancel"):
                st.session_state.show_override = False
                st.rerun()
        with c2:
            if st.form_submit_button("Confirm Override", type="primary"):
                st.warning(f"Override recorded: {reason}")
                st.session_state.show_override = False
                st.rerun()

# What to watch + missing evidence
st.markdown("---")
watch_col1, watch_col2 = st.columns(2)
with watch_col1:
    st.markdown("### 🔭 What to Watch")
    for w in synthesis.get("watch_next", []):
        st.markdown(f"- {w}")
with watch_col2:
    st.markdown("### ❓ Missing Evidence")
    for m in synthesis.get("missing_evidence", []):
        st.markdown(f"- {m}")
