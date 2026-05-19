# ============================================================
# AERO — Station Planning Suite
# Area, Resource and Courier planning tools for Field Engineers.
# Health analytics are available in Station Analytics.
# ============================================================
import streamlit as st
from aero.ui.header import render_header, render_footer


render_header(
    "STATION PLANNING SUITE",
    "Area · Resource · Courier Planning Tools",
    logo_height=80,
    badge="PLANNING",
)

# ── Tabbed interface ─────────────────────────────────────────
tab_area, tab_resource, tab_courier = st.tabs([
    "📐  AREA PLANNING",
    "👥  RESOURCE PLANNING",
    "🚚  COURIER PLANNING",
])

with tab_area:
    from pages.area_planner import render as render_area
    render_area()

with tab_resource:
    from pages.resource_planner import render as render_resource
    render_resource()

with tab_courier:
    from pages.courier_planner import render as render_courier
    render_courier()

render_footer("PLANNING")
