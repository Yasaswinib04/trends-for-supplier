import streamlit as st
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="Disagreement Engine — Triage",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"
with open(DATA_DIR / "cached_trends.json") as f:
    ALL_TRENDS = json.load(f)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚡ Disagreement Engine")
    st.caption("Category Buyer · Value Fashion")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📥 Triage Inbox", "📈 Market View", "📦 Sourcing"],
        label_visibility="collapsed",
    )
    if page == "📈 Market View":
        st.switch_page("pages/2_market_view.py")
    if page == "📦 Sourcing":
        st.switch_page("pages/3_sourcing.py")
    st.markdown("---")
    st.caption("V2 · Conflict-First Analysis")

# --- Triage Inbox ---
st.title("⚡ Triage Inbox")
st.caption("Conflict-first trend analysis. The system detects disagreements — you decide.")

triage_map = {
    "chanderi-straight":      {"priority": "critical", "label": "CONFLICT: HIGH",  "badge": "status-badge-critical", "border": "#ba1a1a", "metric": "Nykaa premium vs Meesho absence"},
    "organza-embroidered":    {"priority": "critical", "label": "CONFLICT: HIGH",  "badge": "status-badge-critical", "border": "#ba1a1a", "metric": "Narrow occasion window + lead time risk"},
    "ajrakh-cotton":          {"priority": "emerging", "label": "CONFLICT: MEDIUM","badge": "status-badge-emerging", "border": "#c84000", "metric": "Strong reviews, weak marketplace scale"},
    "ikat-anarkali":          {"priority": "emerging", "label": "CONFLICT: MEDIUM","badge": "status-badge-emerging", "border": "#c84000", "metric": "Full price pyramid, discount distortion"},
    "bandhani-straight":      {"priority": "emerging", "label": "CONFLICT: MEDIUM","badge": "status-badge-emerging", "border": "#c84000", "metric": "Regional strength vs national absence"},
    "fusion-palazzo":         {"priority": "monitor",  "label": "MONITOR",          "badge": "status-badge-monitor",  "border": "#c3c6d8", "metric": "Volume strong, discount dependency high"},
    "blockprint-cotton":      {"priority": "monitor",  "label": "MONITOR",          "badge": "status-badge-monitor",  "border": "#c3c6d8", "metric": "Meesho commodity, no premium signal"},
    "linen-chinese-collar":   {"priority": "monitor",  "label": "MONITOR",          "badge": "status-badge-monitor",  "border": "#c3c6d8", "metric": "Slow search, narrow addressable market"},
}

css = """
<style>
.status-badge-critical { background:#ffdad6;color:#93000a;padding:2px 8px;border-radius:2px;font-size:11px;font-weight:600;border:1px solid #ba1a1a;display:inline-block; }
.status-badge-emerging { background:#ffdbd0;color:#390c00;padding:2px 8px;border-radius:2px;font-size:11px;font-weight:600;border:1px solid #9e3100;display:inline-block; }
.status-badge-monitor { background:#ecedfa;color:#424656;padding:2px 8px;border-radius:2px;font-size:11px;font-weight:600;border:1px solid #c3c6d8;display:inline-block; }
</style>
"""
st.markdown(css, unsafe_allow_html=True)

st.markdown("---")

# Critical
st.markdown("#### ⚠️ Action Required Today")
critical_trends = [t for t in ALL_TRENDS if triage_map[t["id"]]["priority"] == "critical"]
for t in critical_trends:
    m = triage_map[t["id"]]
    with st.container():
        st.markdown(f"""
        <div style="border:1px solid #c3c6d8;border-left:4px solid {m['border']};border-radius:4px;padding:16px;margin-bottom:8px;background:#fff;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div>
                    <span class="{m['badge']}">{m['label']}</span>
                    <strong style="font-size:18px;color:#191b24;margin-left:8px;">{t['name']}</strong>
                    <div style="margin-top:4px;font-size:13px;color:#424656;">{m['metric']}</div>
                </div>
                <div>""", unsafe_allow_html=True)
        if st.button("⚡ Analyze Conflict", key=f"c_{t['id']}", type="primary"):
            st.session_state.selected_trend = t
            st.switch_page("pages/1_briefing.py")
        st.markdown("</div></div></div>", unsafe_allow_html=True)

st.markdown("---")

# Radar
st.markdown("#### 🔭 On the Radar")
radar_trends = [t for t in ALL_TRENDS if triage_map[t["id"]]["priority"] != "critical"]
for t in radar_trends:
    m = triage_map[t["id"]]
    with st.container():
        st.markdown(f"""
        <div style="border:1px solid #c3c6d8;border-left:4px solid {m['border']};border-radius:4px;padding:16px;margin-bottom:8px;background:#fff;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div>
                    <span class="{m['badge']}">{m['label']}</span>
                    <strong style="font-size:18px;color:#191b24;margin-left:8px;">{t['name']}</strong>
                    <div style="margin-top:4px;font-size:13px;color:#424656;">{m['metric']}</div>
                </div>
                <div>""", unsafe_allow_html=True)
        if st.button("⚡ Analyze Conflict", key=f"r_{t['id']}", type="secondary"):
            st.session_state.selected_trend = t
            st.switch_page("pages/1_briefing.py")
        st.markdown("</div></div></div>", unsafe_allow_html=True)
