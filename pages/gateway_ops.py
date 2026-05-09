# ============================================================
# AERO — Gateway Dashboard (Coming Soon)
# ============================================================
import streamlit as st
from aero.ui.header import render_header
from aero.ui.components import render_coming_soon_page

render_header("GATEWAY OPERATIONS", "Cross-dock & hub connectivity management", logo_height=80, badge="GATEWAY")

render_coming_soon_page(
    title="Gateway Operations",
    icon="🔗",
    description="This module will provide cross-dock throughput monitoring, hub connectivity analytics, sort-plan adherence tracking, and inter-facility volume balancing.",
    phase_label="Phase 2 Integration",
    features=[
        ("📦", "Sort-Plan Adherence", "Real-time sort accuracy and misroute tracking across gateway lanes."),
        ("📊", "Throughput Analytics", "Packages-per-hour dashboards with shift-over-shift comparisons."),
        ("🔄", "Volume Balancing", "Inter-facility load redistribution recommendations powered by FAMIS data."),
    ],
)
