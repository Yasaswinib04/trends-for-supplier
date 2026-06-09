DESIGN_TOKENS = {
    "colors": {
        "primary": "#004ccd",
        "primary_container": "#0f62fe",
        "on_primary": "#ffffff",
        "background": "#faf8ff",
        "surface": "#faf8ff",
        "surface_container": "#ecedfa",
        "surface_container_low": "#f2f3ff",
        "surface_container_lowest": "#ffffff",
        "on_surface": "#191b24",
        "on_surface_variant": "#424656",
        "outline": "#737687",
        "outline_variant": "#c3c6d8",
        "error": "#ba1a1a",
        "error_container": "#ffdad6",
        "on_error_container": "#93000a",
        "tertiary": "#9e3100",
        "tertiary_container": "#c84000",
        "tertiary_fixed": "#ffdbd0",
        "on_tertiary_fixed": "#390c00",
        "success": "#006e1c",
        "success_container": "#94f990",
        "stagnant": "#855300",
        "stagnant_container": "#ffddb3",
    },
    "spacing": {
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px",
    },
    "border_radius": "0.125rem",
}

SIDEBAR_NAV_CSS = """
<style>
[data-testid="stSidebar"] {
    background-color: #faf8ff;
    border-right: 1px solid #c3c6d8;
}
[data-testid="stSidebar"] .stRadio > div {
    gap: 4px;
}
[data-testid="stSidebar"] .st-ae {
    gap: 0;
}
div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column"] > div[data-testid="stVerticalBlock"] {
    gap: 0.25rem;
}
</style>
"""

STATUS_BADGE_CSS = """
<style>
.status-badge-critical {
    background: #ffdad6;
    color: #93000a;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    display: inline-block;
    border: 1px solid #ba1a1a;
}
.status-badge-emerging {
    background: #ffdbd0;
    color: #390c00;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    display: inline-block;
    border: 1px solid #9e3100;
}
.status-badge-monitor {
    background: #ecedfa;
    color: #424656;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    display: inline-block;
    border: 1px solid #c3c6d8;
}
.status-badge-success {
    background: #94f990;
    color: #002204;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    display: inline-block;
    border: 1px solid #006e1c;
}
.metric-label {
    font-size: 11px;
    color: #5e5e5e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}
.metric-value-lg {
    font-size: 24px;
    font-weight: 700;
    color: #191b24;
}
.metric-value-xl {
    font-size: 32px;
    font-weight: 600;
    color: #191b24;
}
.triage-item {
    border-left: 4px solid transparent;
    transition: border-color 0.2s;
}
.triage-item:hover {
    border-color: #0f62fe;
}
.triage-critical { border-left-color: #ba1a1a; }
.triage-emerging { border-left-color: #c84000; }
.triage-monitor { border-left-color: #c3c6d8; }

.evidence-drawer-container {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 100;
    justify-content: flex-end;
}
.drawer-backdrop {
    position: absolute;
    inset: 0;
    background: rgba(25, 27, 36, 0.4);
    backdrop-filter: blur(8px);
}
.drawer-panel {
    position: relative;
    background: #faf8ff;
    width: 100%;
    max-width: 500px;
    height: 100%;
    border-left: 1px solid #c3c6d8;
    overflow-y: auto;
    padding: 24px;
}

.conviction-score {
    font-size: 48px;
    font-weight: 700;
    color: #004ccd;
    line-height: 1;
}
</style>
"""

EVIDENCE_DRAWER_JS = """
<script>
function openDrawer(id) {
    var container = document.getElementById('drawer-' + id);
    if (container) { container.style.display = 'flex'; }
}
function closeDrawer(id) {
    var container = document.getElementById('drawer-' + id);
    if (container) { container.style.display = 'none'; }
}
</script>
"""
