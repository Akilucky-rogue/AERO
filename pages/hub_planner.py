# ============================================================
# AERO — Hub Planner (Tabbed Container — Placeholder)
# Mirrors the Station Planner tab structure so that Hub-specific
# calculators can be plugged in later without structural changes.
# ============================================================
import streamlit as st
from aero.ui.header import render_header, render_footer
from aero.ui.components import render_coming_soon_page


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

_PHASE = "Phase 2 Integration"

with tab_health:
    render_coming_soon_page(
        title="Hub Health Monitor",
        icon="📊",
        description="Hub-wide health monitoring with aggregated KPIs, throughput analytics, and cross-dock performance dashboards.",
        phase_label=_PHASE,
        features=[
            ("📈", "Throughput Analytics", "Monitor hub processing rates and bottleneck identification"),
            ("🔄", "Cross-Dock Performance", "Track sort-plan adherence and volume balancing"),
            ("⚡", "Real-Time Alerts", "Automated health alerts for hub operations"),
        ],
    )

with tab_area:
    render_coming_soon_page(
        title="Hub Area Tracker",
        icon="📐",
        description="Hub-specific area calculations including dock doors, sort lanes, conveyor systems, and staging zones.",
        phase_label=_PHASE,
        features=[
            ("🚪", "Dock Door Planning", "Calculate optimal dock door allocation"),
            ("🔀", "Sort Lane Layout", "Plan sort lanes based on volume and destinations"),
            ("📦", "Staging Zones", "Determine staging area requirements for hub operations"),
        ],
    )

with tab_resource:
    render_coming_soon_page(
        title="Hub Resource Tracker",
        icon="👥",
        description="Hub staffing models for package handlers, sorters, dock workers, and supervisory roles.",
        phase_label=_PHASE,
        features=[
            ("👷", "Handler Planning", "Calculate package handler requirements by shift"),
            ("🔧", "Equipment Allocation", "Plan conveyor operators and equipment needs"),
            ("📋", "Shift Scheduling", "Optimize staffing across hub shifts"),
        ],
    )

with tab_courier:
    render_coming_soon_page(
        title="Hub Courier Tracker",
        icon="🚚",
        description="Hub-level courier and linehaul planning with route optimization and fleet management.",
        phase_label=_PHASE,
        features=[
            ("🗺️", "Linehaul Planning", "Optimize linehaul routes and schedules"),
            ("🚛", "Fleet Management", "Track and plan fleet utilization"),
            ("📊", "Volume Balancing", "Balance volumes across routes and hubs"),
        ],
    )

render_footer("HUB")
