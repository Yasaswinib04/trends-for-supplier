import streamlit as st
import sys; sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

st.set_page_config(page_title="Market View", page_icon="📈", layout="wide")

st.title("Market View: H1 Retrospective")
st.caption("Past trend bets against portfolio targets.")

cols = st.columns(3)
with cols[0]:
    st.metric("Portfolio Margin", "42.8%", "-2.2% vs 45% target")
with cols[1]:
    st.metric("Sell-Through Velocity", "Fast", "avg. 14 days")
with cols[2]:
    st.metric("Hit Rate", "68%", "8 of 12 succeeded")

st.markdown("---")
st.markdown("### Historical Bets")

bets = [
    ("Chanderi Silk Straight Kurti", "Success", "48%", "High"),
    ("Linen Blend Kurti", "Underperformed", "31%", "Stagnant"),
    ("Block Print Cotton A-Line", "Learning", "41%", "Medium"),
    ("Organza Embroidered Kurti", "Success", "46%", "High"),
]
for name, status, margin, vel in bets:
    badge_color = "#16a34a" if status == "Success" else "#dc2626" if status == "Underperformed" else "#6b7280"
    st.markdown(f"""
    <div style="border:1px solid #c3c6d8;border-left:4px solid {badge_color};padding:12px;margin-bottom:8px;display:flex;justify-content:space-between;">
        <strong>{name}</strong>
        <span style="color:{badge_color};font-size:12px;">{status}</span>
        <span style="font-size:12px;color:#6b7280;">Margin: {margin} · Vel: {vel}</span>
    </div>""", unsafe_allow_html=True)

st.markdown("---")
st.caption("© 2024 Disagreement Engine · Market View")
