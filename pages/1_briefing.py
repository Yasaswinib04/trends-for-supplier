import streamlit as st
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.marketplace import get_marketplace_data
from sources.meesho import get_meesho_data
from sources.nykaa import get_nykaa_data
from synthesis.engine import synthesize, log_override, get_override_stats

st.set_page_config(
    page_title="Disagreement Engine — Briefing",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "selected_trend" not in st.session_state:
    st.error("No trend selected. Return to Triage.")
    if st.button("← Back to Triage"):
        st.switch_page("app.py")
    st.stop()

trend = st.session_state.selected_trend

# --- Load Sources ---
nykaa_data  = get_nykaa_data(trend["id"])
myntra_data = get_marketplace_data(trend["id"])
meesho_data = get_meesho_data(trend["id"])

# --- Synthesis ---
with st.spinner("Running Disagreement Engine..."):
    synth = synthesize(trend, nykaa_data, myntra_data, meesho_data)

# --- Header ---
col_b, col_t = st.columns([1, 10])
with col_b:
    if st.button("← Back", key="back"):
        del st.session_state.selected_trend
        st.switch_page("app.py")

st.markdown(f"# {trend['name']}")
st.caption(f"Disagreement Engine · {synth.get('_mode', 'unknown')} mode")

# Conflict summary row
conflicts = synth.get("conflicts", [])
high_count = sum(1 for c in conflicts if c.get("severity") == "HIGH")
med_count = sum(1 for c in conflicts if c.get("severity") == "MEDIUM")
if high_count:
    st.error(f"⚡ {high_count} HIGH severity conflict(s) detected — sources flatly contradict")
elif med_count:
    st.warning(f"⚡ {med_count} MEDIUM severity conflict(s) detected — sources show tension")

st.markdown("---")

# --- Headline ---
st.markdown(f"## {synth.get('headline', 'Analysis')}")

# --- Bet Lean ---
bet = synth.get("bet_lean", "SKIP")
bet_colors = {"Deeper Buy": "#16a34a", "Small Trial": "#ca8a04", "Monitor Only": "#6b7280", "SKIP": "#dc2626"}
bc = bet_colors.get(bet, "#6b7280")
st.markdown(f"""
<div style="background:#f2f3ff;border:1px solid #c3c6d8;padding:20px;border-radius:4px;margin:16px 0;">
    <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
            <div style="font-size:12px;font-weight:600;color:#5e5e5e;text-transform:uppercase;">System Verdict</div>
            <div style="font-size:32px;font-weight:700;color:{bc};margin-top:4px;">{bet}</div>
        </div>
        <div style="max-width:60%;font-size:14px;color:#424656;">{synth.get('bet_rationale', '')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Upside / Catch ---
st.markdown("### The Contextual Brief")
col_up, col_catch = st.columns(2)

with col_up:
    st.markdown("#### 📈 The Upside (Why We Buy)")
    st.write(synth.get("upside_summary", "No upside data."))

with col_catch:
    st.markdown("#### ⚡ The Catch (Where The Risk Sits)")
    st.write(synth.get("catch_summary", "No catch data."))

st.markdown("---")

# --- CONFLICTS (THE SHARP EDGE) ---
if conflicts:
    st.markdown("## ⚡ Conflicts Detected")
    st.caption("The system found these disagreements between sources. Each conflict raises a specific buyer question.")

    for i, c in enumerate(conflicts):
        severity_color = "#ba1a1a" if c["severity"] == "HIGH" else "#d97706" if c["severity"] == "MEDIUM" else "#6b7280"
        with st.expander(f"{c.get('flag', 'CONFLICT')}: {c.get('title', 'Unknown')}", expanded=(c["severity"] == "HIGH")):
            # Source comparison
            src_cols = st.columns(3)
            with src_cols[0]:
                st.markdown("**Nykaa (Premium)**")
                st.caption(c.get("nykaa_says", "No signal"))
            with src_cols[1]:
                st.markdown("**Myntra/Ajio (Mass)**")
                st.caption(c.get("myntra_says", "No signal"))
            with src_cols[2]:
                st.markdown("**Meesho (Value)**")
                st.caption(c.get("meesho_says", "No signal"))

            st.markdown(f"**Buyer Question:** {c.get('buyer_question', '')}")

            # Evidence drawer — raw data traceability
            raw_keys = c.get("raw_evidence_keys", [])
            if raw_keys:
                if st.button(f"🔍 View Raw Signals ({len(raw_keys)} data points)", key=f"raw_{i}"):
                    with st.container():
                        st.markdown("### Raw Source Data")
                        raw_data = {"nykaa": nykaa_data, "myntra": myntra_data, "meesho": meesho_data}
                        for key in raw_keys:
                            parts = key.split(".", 1)
                            source = parts[0]
                            path = parts[1] if len(parts) > 1 else None
                            src_data = raw_data.get(source, {})
                            if path:
                                value = _resolve_path(src_data, path)
                            else:
                                value = src_data
                            if isinstance(value, str) and value.startswith("{"):
                                try:
                                    value = json.loads(value)
                                except json.JSONDecodeError:
                                    pass
                            st.caption(f"`{key}`")
                            st.json(value if isinstance(value, (dict, list)) else str(value)[:500])

    st.markdown("---")

# --- Convergences ---
convergences = synth.get("convergences", [])
if convergences:
    st.markdown("## ✅ Source Convergence")
    for c in convergences:
        with st.container():
            st.success(f"**{c.get('title', '')}**")
            st.write(c.get("detail", ""))

    st.markdown("---")

# --- Watch + Missing ---
w1, w2 = st.columns(2)
with w1:
    st.markdown("### 🔭 Watch Triggers")
    for w in synth.get("watch_triggers", []):
        st.markdown(f"- {w}")
with w2:
    st.markdown("### ❓ Missing Evidence")
    for m in synth.get("missing_evidence", []):
        st.markdown(f"- {m}")

st.markdown("---")

# --- Structured Override (Telemetry) ---
st.markdown("### 📝 Override System Call")

with st.form("override_form", clear_on_submit=True):
    st.caption(f"System recommends: **{bet}**")
    reason = st.selectbox(
        "Override reason (required):",
        ["", "Lead time exceeds buying window", "Margin threshold breached",
         "Target audience mismatch", "Silhouette/fabric not aligned with core", "Other"]
    )
    notes = st.text_input("Additional notes (optional):", placeholder="e.g., Supplier confirmed 90-day lead time")

    c1, c2 = st.columns(2)
    with c1:
        submitted = st.form_submit_button("✏️ Confirm Override", type="primary")
    with c2:
        cancelled = st.form_submit_button("Cancel")

    if submitted and reason:
        log_override(trend["id"], trend["name"], bet, reason, notes=notes)
        st.success(f"Override logged. Reason: {reason}")
        st.rerun()
    elif submitted and not reason:
        st.error("Please select an override reason.")

# Telemetry stats (developer toggle)
if st.checkbox("📊 Show telemetry stats (dev)", value=False):
    stats = get_override_stats()
    if stats:
        st.caption("Override patterns logged in telemetry.db:")
        for reason, count in stats:
            st.write(f"- **{reason}**: {count} override(s)")
    else:
        st.caption("No overrides logged yet.")
    if st.button("Clear telemetry", type="secondary"):
        from synthesis.engine import clear_telemetry
        clear_telemetry()
        st.rerun()


def _resolve_path(data, path):
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)] if int(part) < len(current) else None
        else:
            return None
    return current
