# ============================================================
# AERO — Hub Planning  [frontend/field/hub_coming_soon.py]
# Future scope — coming in a later release.
# ============================================================
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
from aero.ui.header import render_header, render_footer
from aero.ui.components import render_coming_soon_page

render_header(
    "HUB PLANNING",
    "Cross-Dock & Hub Facility Planning — Future Scope",
    logo_height=80,
    badge="HUB",
)

render_coming_soon_page(
    title="Hub Planning Suite",
    icon="🏭",
    description=(
        "The Hub Planning module is currently under development and will extend AERO's "
        "station-level planning capabilities to cross-dock and hub-level operations. "
        "This will include dedicated health monitoring, area, resource, and courier "
        "planning tools specifically designed for hub facilities."
    ),
    phase_label="Future Scope — Phase 3",
    features=[
        (
            "📊",
            "Hub Health Monitor",
            "Real-time health monitoring for hub facilities with FAMIS-driven volume "
            "analysis across inbound, outbound, and transit packages.",
        ),
        (
            "📐",
            "Hub Area Planning",
            "Capacity and floor-space planning for large-format cross-dock facilities "
            "with multi-sort-plan and multi-shift support.",
        ),
        (
            "👥",
            "Hub Resource Planning",
            "Workforce requirements modelling for hub operations including OSA, LASA, "
            "Dispatcher, Trace Agent, and sort-team roles.",
        ),
        (
            "🚚",
            "Hub Courier Planning",
            "Fleet and delivery-route optimisation analytics for hub-attached courier "
            "networks with ODA / ROC / ASP breakdown.",
        ),
    ],
)

render_footer("HUB")
