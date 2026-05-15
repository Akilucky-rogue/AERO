# ============================================================
# AERO — Services Operations (Coming Soon)
# ============================================================
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.auth.service import get_current_user
from aero.ui.components import render_coming_soon_page, render_info_banner, _PURPLE, _ORANGE, _GREEN

_user = get_current_user()

render_header(
    "SERVICES OPERATIONS",
    "FedEx Planning & Engineering",
    logo_height=80,
    badge="SERVICES",
)

render_coming_soon_page(
    title="Services Operations",
    icon="🛎️",
    description=(
        "A new use case is being built for the Services module. "
        "This space will feature operational analytics and workflows "
        "specifically designed for the Services team. Stay tuned for updates."
    ),
    phase_label="New Use Case — In Development",
    features=[
        ("📊", "Operational Analytics", "Real-time service performance metrics and KPIs tailored for the Services division."),
        ("🔮", "Predictive Insights", "Data-driven insights to help the Services team anticipate and act on operational trends."),
        ("📋", "Workflow Tools", "Purpose-built tools and dashboards designed around Services-specific workflows."),
    ],
)

render_footer("SERVICES")
