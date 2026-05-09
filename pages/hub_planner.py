# ============================================================
# AERO — Hub Planner (Tabbed Container)
# Mirrors the Station Planner tab structure with Hub-specific
# health monitoring, area, resource, and courier planning.
# ============================================================
import streamlit as st
from aero.ui.header import render_header, render_footer

render_header(
    "HUB PLANNER",
    "Health Monitoring, Area, Resource & Courier Planning for Hubs",
    logo_height=80,
    badge="HUB",
)

# ── Tabbed interface (mirrors Station Planner) ───────────────
tab_health, tab_area, tab_resource, tab_courier = st.tabs([
    "📊  HEALTH MONITOR",
    "📐  AREA TRACKER",
    "👥  RESOURCE TRACKER",
    "🚚  COURIER TRACKER",
])

with tab_health:
    from pages.hub_health_monitor import render as _render_health
    _render_health()

with tab_area:
    from pages.hub_area_planner import render as _render_area
    _render_area()

with tab_resource:
    from pages.hub_resource_planner import render as _render_resource
    _render_resource()

with tab_courier:
    from pages.hub_courier_planner import render as _render_courier
    _render_courier()

render_footer("HUB")
