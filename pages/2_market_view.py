import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from styles.design import SIDEBAR_NAV_CSS, STATUS_BADGE_CSS, DESIGN_TOKENS

st.set_page_config(
    page_title="Market View — H1 Retrospective",
    page_icon="📈",
    layout="wide",
)
st.markdown(SIDEBAR_NAV_CSS + STATUS_BADGE_CSS, unsafe_allow_html=True)

# ---- HEADER ----
st.title("Market View: H1 Retrospective")
st.caption("Analyzing performance of past trend bets against portfolio targets.")

# ---- SUMMARY METRICS ----
metric_cols = st.columns(3)

with metric_cols[0]:
    st.markdown(f"""
    <div style="border:1px solid #c3c6d8;border-radius:4px;padding:16px;height:100%;">
        <div style="display:flex;justify-content:space-between;align-items:start;">
            <span class="metric-label" style="font-size:11px;color:#5e5e5e;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Portfolio Realized Margin</span>
            <span style="color:{DESIGN_TOKENS['colors']['tertiary']};">📉</span>
        </div>
        <div style="font-size:24px;font-weight:700;margin:8px 0;">42.8%</div>
        <div style="font-size:14px;color:{DESIGN_TOKENS['colors']['tertiary']};">-2.2% vs Target</div>
        <div style="font-size:11px;color:#5e5e5e;margin-top:4px;">Target: 45.0%</div>
    </div>
    """, unsafe_allow_html=True)

with metric_cols[1]:
    st.markdown(f"""
    <div style="border:1px solid #c3c6d8;border-radius:4px;padding:16px;height:100%;">
        <div style="display:flex;justify-content:space-between;align-items:start;">
            <span class="metric-label" style="font-size:11px;color:#5e5e5e;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Sell-Through Velocity</span>
            <span style="color:{DESIGN_TOKENS['colors']['primary']};">⚡</span>
        </div>
        <div style="font-size:24px;font-weight:700;margin:8px 0;color:{DESIGN_TOKENS['colors']['primary']};">Fast</div>
        <div style="font-size:14px;color:#424656;">avg. 14 days</div>
        <div style="font-size:11px;color:#5e5e5e;margin-top:4px;">Target: &lt; 21 days</div>
    </div>
    """, unsafe_allow_html=True)

with metric_cols[2]:
    st.markdown(f"""
    <div style="border:1px solid #c3c6d8;border-radius:4px;padding:16px;height:100%;">
        <div style="display:flex;justify-content:space-between;align-items:start;">
            <span class="metric-label" style="font-size:11px;color:#5e5e5e;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Trend Bet Hit Rate</span>
            <span>📡</span>
        </div>
        <div style="font-size:24px;font-weight:700;margin:8px 0;">68%</div>
        <div style="font-size:14px;color:#424656;">8 of 12 succeeded</div>
        <div style="background:#e5e7eb;height:4px;border-radius:2px;margin-top:8px;">
            <div style="background:{DESIGN_TOKENS['colors']['primary']};height:4px;width:68%;border-radius:2px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ---- HISTORICAL BETS ----
hist_col1, hist_col2 = st.columns([7, 5])

with hist_col1:
    st.markdown("### Historical Bets")

    historical_bets = [
        {"name": "Chanderi Silk Straight Kurti", "status": "Success", "margin": "48%", "velocity": "High", "border": DESIGN_TOKENS['colors']['primary']},
        {"name": "Linen Blend Kurti", "status": "Underperformed", "margin": "31%", "velocity": "Stagnant", "border": DESIGN_TOKENS['colors']['tertiary']},
        {"name": "Block Print Cotton A-Line", "status": "Learning", "margin": "41%", "velocity": "Medium", "border": DESIGN_TOKENS['colors']['outline']},
        {"name": "Organza Embroidered Kurti", "status": "Success", "margin": "46%", "velocity": "High", "border": DESIGN_TOKENS['colors']['primary']},
        {"name": "Fusion Kurti with Palazzo", "status": "Learning", "margin": "38%", "velocity": "Medium", "border": DESIGN_TOKENS['colors']['outline']},
        {"name": "Ajrakh Print Cotton Kurti", "status": "Success", "margin": "44%", "velocity": "Fast", "border": DESIGN_TOKENS['colors']['primary']},
    ]

    for bet_item in historical_bets:
        status_label = bet_item["status"]
        if status_label == "Success":
            status_html = f'<span class="status-badge-success">{status_label}</span>'
        elif status_label == "Underperformed":
            status_html = f'<span class="status-badge-critical">{status_label}</span>'
        else:
            status_html = f'<span class="status-badge-monitor">{status_label}</span>'

        selected_bg = "#f2f3ff" if "Linen" in bet_item["name"] else "#ffffff"
        selected_border = f"border:2px solid {DESIGN_TOKENS['colors']['primary']};" if "Linen" in bet_item["name"] else ""

        st.markdown(f"""
        <div style="border:1px solid #c3c6d8;border-radius:4px;border-left:4px solid {bet_item['border']};padding:12px;margin-bottom:8px;cursor:pointer;{selected_border}background:{selected_bg};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong style="font-size:14px;color:#191b24;">{bet_item['name']}</strong>
                {status_html}
            </div>
            <div style="display:flex;gap:16px;font-size:12px;color:#424656;margin-top:4px;font-family:'IBM Plex Mono',monospace;">
                <span>Margin: {bet_item['margin']}</span>
                <span>Velocity: {bet_item['velocity']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

with hist_col2:
    st.markdown("### Retrospective: Linen Blend")
    st.caption("[View Source]")

    st.markdown(f"""
    <div style="border:1px solid #c3c6d8;border-radius:4px;padding:16px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div>
                <div style="font-weight:600;font-size:12px;color:{DESIGN_TOKENS['colors']['primary']};margin-bottom:6px;">🧠 What we thought</div>
                <p style="font-size:13px;color:#424656;margin:0;">Predicted high demand in urban centers (Tier-1) due to return-to-office mandates. Expected fast velocity.</p>
            </div>
            <div>
                <div style="font-weight:600;font-size:12px;color:{DESIGN_TOKENS['colors']['tertiary']};margin-bottom:6px;">🔧 What happened</div>
                <p style="font-size:13px;color:#424656;margin:0;">Urban adoption stalled due to price sensitivity. Actual demand localized in Tier-2 coastal cities, insufficient to offset volume drop.</p>
            </div>
        </div>
        <div style="margin-top:16px;border-top:1px solid #c3c6d8;padding-top:12px;">
            <div style="font-size:11px;font-weight:600;color:#191b24;margin-bottom:8px;">Velocity Chart (First 30 Days)</div>
            <div style="display:flex;align-items:end;gap:2px;height:80px;">
                {''.join(f'<div style="flex:1;background:{"#c3c6d8" if i < 4 else "#ffb59d" if i < 6 else "#9e3100"};border-radius:2px 2px 0 0;height:{[80,75,60,40,35,25,20,15][i]}%;"></div>' for i in range(8))}
            </div>
            <div style="display:flex;justify-content:space-between;font-size:10px;color:#6b7280;margin-top:4px;">
                <span>Launch</span><span>Day 15</span><span>Day 30</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Regional Velocity Heatmap")
    heat_cols = st.columns(3)
    heatmap_data = [
        ("North", "High", DESIGN_TOKENS['colors']['primary'], DESIGN_TOKENS['colors']['on_primary']),
        ("West", "Medium", DESIGN_TOKENS['colors']['primary_container'], DESIGN_TOKENS['colors']['on_primary']),
        ("South", "Low", DESIGN_TOKENS['colors']['error_container'], DESIGN_TOKENS['colors']['on_error_container']),
    ]
    for i, (region, level, bg, text_color) in enumerate(heatmap_data):
        with heat_cols[i]:
            st.markdown(f"""
            <div style="text-align:center;font-size:10px;color:#5e5e5e;margin-bottom:4px;">{region}</div>
            <div style="background:{bg};color:{text_color};border-radius:4px;padding:20px;text-align:center;font-weight:700;font-size:16px;">{level}</div>
            """, unsafe_allow_html=True)

st.markdown("---")
st.caption("© 2024 Merchandising IQ Decision Engine")
