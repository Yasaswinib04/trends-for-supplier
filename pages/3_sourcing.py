import streamlit as st
import sys; sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

st.set_page_config(page_title="Sourcing", page_icon="📦", layout="wide")

st.markdown("✅ **TREND BET APPROVED**")
st.title("Sourcing Handoff")
st.caption("Automated vendor matching and PO generation.")

ref_col, _ = st.columns([2, 4])
with ref_col:
    st.code("REF: TB-2024-089A", language=None)

# Sourcing Brief
brief_cols = st.columns(3)
with brief_cols[0]:
    st.metric("Allocation", "Core Commitment")
with brief_cols[1]:
    st.metric("Approved OTB", "₹450,000")
with brief_cols[2]:
    st.metric("Target Landed Cost", "₹18.50 /unit")

st.markdown("---")

# Vendor Match
st.markdown("### 🤝 Vendor Match")
col_v, col_m = st.columns([2, 1])
with col_v:
    st.success("**Vardhman Textiles Ltd.** — India · Linen/Blends")
    st.caption("Est. Lead Time: 45 Days · Capacity Score: 92/100")
with col_m:
    st.button("View Alternates (2)", use_container_width=True)

# Timeline
st.markdown("---")
st.markdown("### ⏱️ Procurement Timeline")
steps = ["📄 PO Issuance (Today)", "🏭 Fabric Booking (+5d)", "✂️ Cut & Sew (+20d)", "🚢 In Transit (+35d)", "🏗️ Warehouse (+45d)"]
timeline_cols = st.columns(len(steps))
for i, step in enumerate(steps):
    with timeline_cols[i]:
        active = i == 0
        st.markdown(f"""
        <div style="text-align:center;padding:8px;">
            <div style="width:32px;height:32px;border-radius:50%;background:{'#004ccd' if active else '#ecedfa'};color:{'white' if active else '#424656'};display:inline-flex;align-items:center;justify-content:center;font-size:14px;margin-bottom:4px;">{'✓' if active else '○'}</div>
            <div style="font-size:10px;color:#5e5e5e;">{step}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")
c1, c2 = st.columns(2)
with c1: st.button("Modify Specs", use_container_width=True)
with c2:
    if st.button("🚀 Release PO", use_container_width=True, type="primary"):
        st.success("PO Released! #PO-2024-089A")

st.caption("© 2024 Disagreement Engine · Sourcing")
