# ============================================================
# AERO — Station Planning Suite  [frontend/field/planning_suite.py]
# Area, Resource and Courier planning tools for Field Engineers.
# Three focussed tabs — no health monitor clutter here.
# Health analytics live in Station Analytics (frontend/field/analytics.py).
# ============================================================
import os
import sys

# Ensure project root on path
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
from aero.ui.header import render_header, render_footer

render_header(
    "STATION PLANNING SUITE",
    "Area · Resource · Courier Planning Tools for Field Engineers",
    logo_height=80,
    badge="PLANNING",
)

# ── Tabbed interface ──────────────────────────────────────────────────────────
tab_area, tab_resource, tab_courier = st.tabs([
    "📐  AREA PLANNING",
    "👥  RESOURCE PLANNING",
    "🚚  COURIER PLANNING",
])

with tab_area:
    from pages.area_planner import render as _render_area
    _render_area()

with tab_resource:
    from pages.resource_planner import render as _render_resource
    _render_resource()

with tab_courier:
    from pages.courier_planner import render as _render_courier
    _render_courier()

render_footer("PLANNING")
