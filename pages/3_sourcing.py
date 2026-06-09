import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from styles.design import SIDEBAR_NAV_CSS, STATUS_BADGE_CSS, DESIGN_TOKENS

st.set_page_config(
    page_title="Sourcing Automation",
    page_icon="📦",
    layout="wide",
)
st.markdown(SIDEBAR_NAV_CSS + STATUS_BADGE_CSS, unsafe_allow_html=True)

# ---- HEADER ----
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <span style="color:{DESIGN_TOKENS['colors']['success']};font-size:14px;">✅</span>
    <span class="status-badge-success" style="font-size:11px;">TREND BET APPROVED</span>
</div>
""", unsafe_allow_html=True)
st.title("Sourcing Handoff: Summer Linen Capsule")
st.caption("Automated vendor matching and PO generation for approved allocation.")

ref_col, _ = st.columns([2, 4])
with ref_col:
    st.markdown(f"""
    <div style="display:inline-block;background:#ecedfa;padding:4px 12px;border-radius:4px;font-family:'IBM Plex Mono',monospace;font-size:13px;color:#191b24;border:1px solid #c3c6d8;">
        REF: TB-2024-089A
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ---- BENTO GRID ----
grid_col1, grid_col2 = st.columns([8, 4])

with grid_col1:
    st.markdown("### 📄 Sourcing Brief")
    brief_col = st.columns(3)
    fields = [
        ("Allocation Type", "Core Commitment"),
        ("Approved OTB", "₹450,000"),
        ("Target Landed Cost", "₹18.50 /unit"),
    ]
    for i, (label, value) in enumerate(fields):
        with brief_col[i]:
            st.markdown(f"""
            <div style="border:1px solid #c3c6d8;border-radius:4px;padding:12px;text-align:center;">
                <div style="font-size:10px;color:#5e5e5e;text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px;">{label}</div>
                <div style="font-size:18px;font-weight:700;color:#191b24;font-family:'IBM Plex Mono',monospace;">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("#### Material Requirements")
    mat_cols = st.columns(3)
    materials = ["100% European Flax Linen", "160 GSM weight", "Garment Washed finish"]
    for i, mat in enumerate(materials):
        with mat_cols[i]:
            st.markdown(f"""
            <div style="border:1px solid #c3c6d8;border-radius:4px;padding:8px 12px;text-align:center;font-size:13px;color:#191b24;">
                {mat}
            </div>
            """, unsafe_allow_html=True)

with grid_col2:
    st.markdown("### 🤝 Vendor Match")
    st.markdown(f"""
    <div style="display:inline-block;background:#006e1c;color:white;padding:2px 8px;border-radius:2px;font-size:10px;font-weight:700;margin-bottom:8px;">
        SYSTEM SUGGESTION
    </div>
    <div style="border:2px solid {DESIGN_TOKENS['colors']['primary']};border-radius:4px;padding:16px;">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:12px;">
            <div>
                <div style="font-size:16px;font-weight:600;color:#191b24;">Vardhman Textiles Ltd.</div>
                <div style="font-size:11px;color:#424656;display:flex;align-items:center;gap:4px;margin-top:4px;">
                    📍 India · Specialization: Linen/Blends
                </div>
            </div>
            <span style="color:{DESIGN_TOKENS['colors']['primary']};font-size:20px;">✅</span>
        </div>
        <div style="border-top:1px solid #c3c6d8;padding-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div>
                <div style="font-size:10px;color:#5e5e5e;text-transform:uppercase;">Est. Lead Time</div>
                <div style="font-weight:600;font-size:14px;color:#191b24;">45 Days <span style="color:#006e1c;font-size:10px;">▼ 5d avg</span></div>
            </div>
            <div>
                <div style="font-size:10px;color:#5e5e5e;text-transform:uppercase;">Capacity Score</div>
                <div style="font-weight:600;font-size:14px;color:#191b24;">92/100</div>
                <div style="background:#e5e7eb;height:4px;border-radius:2px;margin-top:4px;">
                    <div style="background:#006e1c;height:4px;width:92%;border-radius:2px;"></div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("View Alternate Vendors (2)", use_container_width=True):
        st.info("Alternate: FabricFolio Exports (Lead: 35d, Score: 78/100) | LuxTex India (Lead: 55d, Score: 85/100)")

# ---- PROCUREMENT TIMELINE ----
st.markdown("---")
st.markdown("### ⏱️ Procurement Timeline")

timeline_steps = [
    ("📄", "PO Issuance", "Today", True),
    ("🏭", "Fabric Booking", "+5 Days", False),
    ("✂️", "Cut & Sew", "+20 Days", False),
    ("🚢", "In Transit", "+35 Days", False),
    ("🏗️", "Warehouse Receipt", "+45 Days (Est)", False),
]

timeline_cols = st.columns(len(timeline_steps))
for i, (icon, label, date, active) in enumerate(timeline_steps):
    with timeline_cols[i]:
        color = DESIGN_TOKENS['colors']['primary'] if active else "#c3c6d8"
        bg = DESIGN_TOKENS['colors']['primary'] if active else "#ecedfa"
        text_color = DESIGN_TOKENS['colors']['on_primary'] if active else "#424656"
        st.markdown(f"""
        <div style="text-align:center;">
            <div style="width:32px;height:32px;border-radius:50%;background:{bg};color:{text_color};display:inline-flex;align-items:center;justify-content:center;font-size:16px;border:3px solid #faf8ff;margin-bottom:6px;">
                {icon}
            </div>
            <div style="font-size:11px;font-weight:600;color:{'#191b24' if active else '#6b7280'};text-align:center;">{label}</div>
            <div style="font-size:10px;color:#5e5e5e;margin-top:2px;">{date}</div>
        </div>
        """, unsafe_allow_html=True)

# Connecting line
st.markdown("""
<div style="position:relative;height:2px;background:#c3c6d8;margin:-20px 8% 0 8%;"></div>
""", unsafe_allow_html=True)

# ---- STICKY FOOTER ----
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns([3, 1, 1])
with footer_col1:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:4px;height:32px;background:#006e1c;border-radius:2px;"></div>
        <div>
            <div style="font-size:12px;font-weight:600;color:#191b24;text-transform:uppercase;">Automated PO Ready</div>
            <div style="font-size:11px;color:#424656;">Vardhman Textiles Ltd. · 24,300 Units</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with footer_col2:
    st.button("Modify Specs", use_container_width=True, key="modify", type="secondary")
with footer_col3:
    if st.button("🚀 Release PO", use_container_width=True, type="primary"):
        st.success("PO Released! Confirmation: #PO-2024-089A")
        st.balloons()

st.caption("© 2024 Merchandising IQ Decision Engine")
