# ============================================================
# AERO — Gateway Operations  [frontend/gateway/operations.py]
# Future scope — Gateway dataset and logic not yet defined.
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
    "GATEWAY OPERATIONS",
    "Cross-dock & Hub Connectivity Management — Future Scope",
    logo_height=80,
    badge="GATEWAY",
)

render_coming_soon_page(
    title="Gateway Operations",
    icon="✈️",
    description=(
        "The Gateway Operations module will provide cross-dock sort analysis, "
        "volume balancing, and network throughput monitoring across all FedEx "
        "gateway stations. This module requires a dedicated Gateway dataset and "
        "operational logic definitions before it can be built."
    ),
    phase_label="Future Scope — Pending Dataset",
    features=[
        (
            "📊",
            "Sort Throughput Analytics",
            "Cross-dock sort performance monitoring with station-level throughput "
            "per FTE, ODA / ROC / OPA rate tracking, and sort efficiency scoring.",
        ),
        (
            "🔗",
            "Station Network View",
            "Regional gateway station grid with inbound/outbound volume breakdown, "
            "sort efficiency scoring, and network health indicators.",
        ),
        (
            "📈",
            "Volume & Trend Analysis",
            "30-day volume trends, week-over-week comparisons, and ODA/ROC/OPA "
            "rate trend lines across the gateway network.",
        ),
        (
            "⚖️",
            "Volume Balancing",
            "Inbound/outbound imbalance detection with per-station recommendations "
            "for redistribution and capacity optimisation.",
        ),
    ],
)

render_footer("GATEWAY")
