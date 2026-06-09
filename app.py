import streamlit as st
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from styles.design import SIDEBAR_NAV_CSS, STATUS_BADGE_CSS, DESIGN_TOKENS

st.set_page_config(
    page_title="Merchandising IQ — Triage",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(SIDEBAR_NAV_CSS + STATUS_BADGE_CSS, unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent / "data"
with open(DATA_DIR / "cached_trends.json") as f:
    ALL_TRENDS = json.load(f)

# Sidebar navigation
with st.sidebar:
    st.markdown("### Merchandising IQ")
    st.caption("Category Buyer · High Velocity Retail")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📥 Triage Inbox", "📈 Market View", "📦 Sourcing", "📋 Archive"],
        label_visibility="collapsed",
        index=0,
    )
    st.markdown("---")
    if st.button("🪡 New Analysis", use_container_width=True):
        st.rerun()

# Map trends to triage categories based on bet sizing
def classify_trend(trend):
    tid = trend["id"]
    price = trend.get("price_band", "")
    season = trend.get("season", "")

    # Priority scoring
    is_high_margin = "₹699" in price or "₹799" in price or "₹899" in price or "₹999" in price
    is_festive = "Festive" in season or "Wedding" in season
    is_urgent = is_festive

    # Critical: Chanderi, Organza (high margin, active competitor ads)
    if tid in ("chanderi-straight", "organza-embroidered"):
        return {"priority": "critical", "group": "Action Required Today", "label": "CRITICAL DECISION",
                "metric": "Margin Risk: High" if is_high_margin else "Stockout Risk: Medium",
                "context": "Premium validated on Nykaa. Active competitor campaigns."}

    # Emerging with strong signals
    if tid in ("ajrakh-cotton", "ikat-anarkali", "bandhani-straight"):
        return {"priority": "emerging", "group": "On the Radar", "label": "EMERGING",
                "metric": f"Signal Strength: Growing" if is_urgent else "Momentum: Rising",
                "context": "Multi-platform validation. Regional strength detected."}

    # Monitor (fusion, linen, block-print)
    return {"priority": "monitor", "group": "On the Radar", "label": "MONITOR",
            "metric": "Discount Distortion: High" if tid == "fusion-palazzo" else "Category: Steady",
            "context": "Watch for price stabilization and reseller growth."}

# Classify all trends
trend_cards = []
for t in ALL_TRENDS:
    c = classify_trend(t)
    c["trend"] = t
    trend_cards.append(c)

critical = [c for c in trend_cards if c["priority"] == "critical"]
emerging = [c for c in trend_cards if c["priority"] == "emerging"]
monitor = [c for c in trend_cards if c["priority"] == "monitor"]

# ---- PAGE CONTENT ----
st.title("Triage Inbox")
st.caption("Review pending trend judgments and margin risks.")

sort_col, _ = st.columns([2, 4])
with sort_col:
    sort_by = st.selectbox("Sort by:", ["Action Urgency", "Margin Risk", "Velocity"], label_visibility="collapsed")

st.markdown("---")

# Action Required Today
st.markdown(f"#### ⚠️ Action Required Today")
st.caption(f"{len(critical)} trends need immediate attention")

for card in critical:
    t = card["trend"]
    with st.container():
        st.markdown(f"""
        <div style="border:1px solid #c3c6d8;border-radius:4px;border-left:4px solid {DESIGN_TOKENS['colors']['error']};padding:16px;margin-bottom:8px;background:#ffffff;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div style="flex:1;min-width:200px;">
                    <span class="status-badge-critical">{card['label']}</span>
                    <strong style="font-size:18px;color:#191b24;margin-left:8px;">{t['name']}</strong>
                    <div style="margin-top:6px;font-size:13px;color:#424656;">
                        <span style="color:#ba1a1a;font-weight:500;">{card['metric']}</span>
                        <span style="margin:0 8px;color:#c3c6d8;">|</span>
                        <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;">{card['context']}</span>
                    </div>
                </div>
                <div>
        """, unsafe_allow_html=True)
        if st.button("📋 Briefing", key=f"brief_{t['id']}", type="primary"):
            st.session_state.selected_trend = t
            st.switch_page("pages/1_briefing.py")
        st.markdown("</div></div></div>", unsafe_allow_html=True)

st.markdown("---")

# On the Radar
st.markdown(f"#### 🔭 On the Radar")
st.caption(f"{len(emerging) + len(monitor)} trends being tracked")

for card in emerging + monitor:
    t = card["trend"]
    badge_class = "status-badge-emerging" if card["priority"] == "emerging" else "status-badge-monitor"
    border_color = DESIGN_TOKENS['colors']['tertiary_container'] if card["priority"] == "emerging" else DESIGN_TOKENS['colors']['outline_variant']

    with st.container():
        st.markdown(f"""
        <div style="border:1px solid #c3c6d8;border-radius:4px;border-left:4px solid {border_color};padding:16px;margin-bottom:8px;background:#ffffff;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div style="flex:1;min-width:200px;">
                    <span class="{badge_class}">{card['label']}</span>
                    <strong style="font-size:18px;color:#191b24;margin-left:8px;">{t['name']}</strong>
                    <div style="margin-top:6px;font-size:13px;color:#424656;">
                        <span>{card['metric']}</span>
                        <span style="margin:0 8px;color:#c3c6d8;">|</span>
                        <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;">{card['context']}</span>
                    </div>
                </div>
                <div>
        """, unsafe_allow_html=True)
        if st.button("📋 Briefing", key=f"brief_{t['id']}", type="secondary"):
            st.session_state.selected_trend = t
            st.switch_page("pages/1_briefing.py")
        st.markdown("</div></div></div>", unsafe_allow_html=True)
