# ============================================================
# AERO — Station Planner (Tabbed Container)
# Combines Health Monitor, Area Tracker, Resource Tracker,
# and Courier Tracker into a single tabbed interface.
# ============================================================
import streamlit as st
from aero.ui.header import render_header, render_footer


render_header(
    "STATION PLANNER",
    "Health Monitoring, Area, Resource & Courier Planning",
    logo_height=80,
    badge="STATION",
)

# ── Tabbed interface ─────────────────────────────────────────
tab_health, tab_area, tab_resource, tab_courier = st.tabs([
    "📊  HEALTH MONITOR",
    "📐  AREA TRACKER",
    "👥  RESOURCE TRACKER",
    "🚚  COURIER TRACKER",
])

with tab_health:
    from pages.health_monitor import render as render_health
    render_health()

with tab_area:
    from pages.area_planner import render as render_area
    render_area()

with tab_resource:
    from pages.resource_planner import render as render_resource
    render_resource()

with tab_courier:
    from pages.courier_planner import render as render_courier
    render_courier()

render_footer("STATION")
