# ============================================================
# AERO — Home Page (Role-Aware)
# ============================================================
import streamlit as st
import pandas as pd
import io

from aero.ui.header import render_header, render_footer
from aero.auth.service import get_current_user
from aero.ui.components import (
    render_module_card,
    render_step_guide,
    render_kpi_row,
    render_info_banner,
    _PURPLE, _ORANGE, _GREEN, _RED,
)

_user = get_current_user()
_role = _user.get("role", "") if _user else ""


# ════════════════════════════════════════════════════════════
# LEADERSHIP
# ════════════════════════════════════════════════════════════
if _role == "Leadership":
    render_header(
        "EXECUTIVE DASHBOARD",
        "Leadership Analytics | FedEx Planning & Engineering",
        logo_height=80,
        badge="LEADERSHIP",
    )

    render_info_banner(
        "About the Executive Dashboard",
        "The Executive Dashboard provides a consolidated, read-only view of operational health "
        "and performance analytics across all FedEx divisions. Select a division tab in the "
        "<b>Executive Dashboard</b> page to view its dedicated report.",
    )

    st.markdown(
        '<div style="font-weight:700;color:#333;font-size:12px;text-transform:uppercase;'
        'letter-spacing:0.6px;margin-bottom:10px;">Division Overview</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    render_module_card(c1, "🏢", "Station / Hub",
        "Health status reports published by Facility teams covering Area, Resource, and Courier "
        "monitoring with Healthy / Review / Critical classifications and volume trend charts.",
        accent=_PURPLE)
    render_module_card(c2, "✈️", "Gateway",
        "Inter-hub linehaul and air gateway performance metrics. Covers on-time departure, "
        "linehaul utilisation, cross-dock efficiency, and route-level benchmarks. (Phase 2)",
        accent="#1A5276")
    render_module_card(c3, "🛎️", "Services",
        "SLA compliance, delay prediction, customer contact volume, and first-attempt delivery "
        "rates across all service types and station divisions. (Phase 2 for dashboard view)",
        accent="#7B241C")

    st.markdown("<br>", unsafe_allow_html=True)

    render_step_guide([
        {"title": "Open Executive Dashboard",
         "description": "Select <b>Executive Dashboard</b> from the left navigation panel."},
        {"title": "Select Division Tab",
         "description": "Choose from <b>STATION / HUB</b>, <b>GATEWAY</b>, or <b>SERVICES</b>. "
                        "Each tab is independently scoped."},
        {"title": "Review the Report",
         "description": "Station / Hub data auto-populates from published Facility health reports. "
                        "Gateway and Services tabs activate in Phase 2."},
    ])

    render_footer("LEADERSHIP")
    st.stop()


# ════════════════════════════════════════════════════════════
# SERVICES
# ════════════════════════════════════════════════════════════
if _role == "Services":
    render_header(
        "SERVICES OPERATIONS",
        "Delay Prediction Engine | FedEx Planning & Engineering",
        logo_height=80,
        badge="SERVICES",
    )

    render_info_banner(
        "Welcome to the Services Module",
        "The Services module uses a <b>Bayesian delay prediction engine</b> trained on NSL "
        "historical shipment data. Upload your NSL file to build the model, then score daily "
        "AWB files to identify which packages are at risk of missing their SLA commit window.",
        accent=_PURPLE,
    )

    c1, c2, c3, c4 = st.columns(4)
    render_module_card(c1, "📥", "Training Data",
        "Upload your IN SPAC NSL file (.txt / .csv / .xlsx) to parse and review historical "
        "shipment performance before training.",
        accent=_PURPLE)
    render_module_card(c2, "🧠", "Model",
        "View the trained network profile: fail rates by lane, hub, market, service type, "
        "POF causes, and transit time distributions.",
        accent="#1A5276")
    render_module_card(c3, "🔮", "Daily Prediction",
        "Upload today's AWB file to score every shipment. Results are colour-coded: "
        "Critical / High Risk / At Risk / Passing with per-AWB drilldown.",
        accent=_GREEN)
    render_module_card(c4, "📋", "History",
        "Browse and download all past prediction sessions stored as timestamped Excel sheets.",
        accent=_ORANGE)

    st.markdown("<br>", unsafe_allow_html=True)

    render_step_guide([
        {"title": "Prepare NSL File",
         "description": "Export the <b>IN SPAC NSL</b> report as a tab-separated .txt file "
                        "(or .csv / .xlsx). Required columns: "
                        "<code>orig_loc_cd</code>, <code>dest_loc_cd</code>, <code>NSL_OT_VOL</code>."},
        {"title": "Train the Model",
         "description": "Go to <b>Services Operations → Training Data</b>, upload the NSL file, "
                        "preview the parse stats, then click <b>Train Model</b>. "
                        "The model persists across sessions — train once, predict daily."},
        {"title": "Upload Daily AWB File",
         "description": "Go to <b>Daily Prediction</b>, upload today's AWB extract "
                        "(needs at least <code>orig_loc_cd</code> and <code>dest_loc_cd</code>), "
                        "then click <b>Run Prediction</b>."},
        {"title": "Review & Act",
         "description": "Filter by risk level or market. Drilldown into individual AWBs for "
                        "root-cause signals and recommended actions. Download results as CSV "
                        "or save the session to History."},
    ])

    render_footer("SERVICES")
    st.stop()


# ════════════════════════════════════════════════════════════
# GATEWAY
# ════════════════════════════════════════════════════════════
if _role == "Gateway":
    render_header(
        "GATEWAY OPERATIONS",
        "Cross-dock & Hub Connectivity | FedEx Planning & Engineering",
        logo_height=80,
        badge="GATEWAY",
    )

    render_info_banner(
        "Gateway Module — Phase 2",
        "The Gateway module will provide inter-hub linehaul analytics, sort-plan adherence "
        "tracking, cross-dock throughput monitoring, and volume balancing recommendations. "
        "Full integration is planned for Phase 2.",
        accent=_ORANGE,
    )

    c1, c2, c3 = st.columns(3)
    render_module_card(c1, "📦", "Sort-Plan Adherence",
        "Real-time sort accuracy and misroute tracking across gateway lanes. "
        "Shift-over-shift comparison view.", accent=_PURPLE)
    render_module_card(c2, "📊", "Throughput Analytics",
        "Packages-per-hour dashboards with volume trend charts and exception flagging "
        "by sort lane and gateway station.", accent="#1A5276")
    render_module_card(c3, "🔄", "Volume Balancing",
        "Inter-facility load redistribution recommendations powered by FAMIS data. "
        "Identify over/under-utilised gateways at a glance.", accent=_GREEN)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#FFFBEB;border-left:4px solid #FFB800;border-radius:8px;
        padding:14px 18px;font-size:13px;color:#7C4F00;">
        <b>Coming in Phase 2</b> — Gateway Operations is currently in development.
        Navigate to <b>Gateway Operations</b> in the sidebar to see the module preview.
    </div>""", unsafe_allow_html=True)

    render_footer("GATEWAY")
    st.stop()


# ════════════════════════════════════════════════════════════
# OPERATIONS (all-access role)
# ════════════════════════════════════════════════════════════
if _role == "Operations":
    render_header(
        "AERO — Operations Overview",
        "All Modules | FedEx Planning & Engineering",
        logo_height=80,
        badge="OPERATIONS",
    )

    render_info_banner(
        "Operations Role — Full Access",
        "As an Operations user you have access to all AERO modules: Facility planning, "
        "Hub planning, Gateway operations, Services delay prediction, and Leadership analytics. "
        "Use the left sidebar to navigate between modules.",
        accent=_PURPLE,
    )

    st.markdown(
        '<div style="font-weight:700;color:#333;font-size:12px;text-transform:uppercase;'
        'letter-spacing:0.6px;margin-bottom:12px;">Available Modules</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    render_module_card(c1, "🏢", "Station Planner",
        "Area, resource, and courier planning for individual station facilities. "
        "Upload FAMIS data and calculate health status.", accent=_PURPLE)
    render_module_card(c2, "🏭", "Hub Planner",
        "Health monitoring and capacity planning for hub-level operations. "
        "Mirrors Station Planner with hub-specific models.", accent=_PURPLE)
    render_module_card(c3, "✈️", "Gateway Operations",
        "Cross-dock throughput monitoring, sort-plan adherence, and volume balancing. "
        "(Phase 2)", accent="#1A5276")

    st.markdown("<br>", unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3)
    render_module_card(c4, "🔮", "Services Operations",
        "Bayesian delay prediction engine — train on NSL history, score daily AWB files, "
        "identify at-risk shipments before they fail.", accent=_GREEN, gradient=True)
    render_module_card(c5, "📊", "Analytics Overview",
        "Cross-divisional executive analytics: Station/Hub health, Gateway metrics, "
        "and Services SLA performance in one view.", accent=_ORANGE, gradient=True)
    render_module_card(c6, "⚙️", "Admin Controls",
        "Configure global thresholds, model parameters, and user settings that drive "
        "all calculations across the application.", accent=_PURPLE)

    render_footer("OPERATIONS")
    st.stop()


# ════════════════════════════════════════════════════════════
# FACILITY / FIELD ENGINEER (default)
# ════════════════════════════════════════════════════════════
render_header(
    "FIELD OPERATIONS OVERVIEW",
    "FedEx Planning & Engineering | Field Engineer Dashboard",
    logo_height=80,
    badge="FIELD",
)

# ── Quick-status banner from session ───────────────────────
_famis  = st.session_state.get("famis_data")
_master = st.session_state.get("master_data")
_famis_ok  = _famis  is not None and not _famis.empty
_master_ok = _master is not None and not _master.empty

if _famis_ok and _master_ok:
    _n   = len(_famis)
    _st  = _famis["loc_id"].nunique() if "loc_id" in _famis.columns else 0
    _dt  = pd.to_datetime(_famis["date"]).max().strftime("%d %b %Y") if "date" in _famis.columns else "—"
    render_info_banner(
        "Data Ready",
        f"<b>{_n:,}</b> FAMIS records across <b>{_st}</b> stations loaded "
        f"(latest: <b>{_dt}</b>). Master data loaded. Use the navigation on the left to begin planning or view analytics.",
        accent=_GREEN,
    )
elif _famis_ok:
    render_info_banner(
        "FAMIS Data Loaded — Master Data Missing",
        "FAMIS volume data is loaded but no Facility Master file has been uploaded. "
        "Go to <b>Data Upload Centre</b> to upload the master file for full health calculations.",
        accent=_ORANGE,
    )
else:
    render_info_banner(
        "Getting Started",
        "No data has been uploaded yet. Start by going to <b>Data Upload Centre</b> "
        "to upload your FAMIS volume file and Facility Master file.",
        accent=_PURPLE,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Workflow guide ──────────────────────────────────────────
st.markdown(
    '<div style="font-weight:700;color:#4D148C;font-size:13px;text-transform:uppercase;' +
    'letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">' +
    'Field Engineer Workflow</div>',
    unsafe_allow_html=True,
)

render_step_guide([
    {"title": "1 · Upload Data",
     "description": "Navigate to <b>Data Upload Centre</b>. Upload your FAMIS REPORT Excel file "
                    "(weekly/daily/monthly) and your Facility Master file. "
                    "Data is automatically saved to the database — no manual publish required."},
    {"title": "2 · Plan — Area, Resource & Courier",
     "description": "Go to <b>Station Planning</b> to use the three planning tools: "
                    "<b>Area Planning</b> calculates space requirements, "
                    "<b>Resource Planning</b> calculates OSA/LASA/Dispatcher headcount, and "
                    "<b>Courier Planning</b> calculates courier headcount. "
                    "All tools auto-populate from uploaded FAMIS data."},
    {"title": "3 · Monitor Health & Analytics",
     "description": "Go to <b>Station Analytics</b> for the full health view: "
                    "region-level KPI cards, per-station AREA/RESOURCE/COURIER status, "
                    "and drill-down into individual stations with historical trend charts."},
    {"title": "4 · Hub Operations",
     "description": "Use <b>Hub Planning</b> for equivalent planning and monitoring "
                    "at the hub level. Data is scoped separately from station data."},
])

st.markdown("<br>", unsafe_allow_html=True)

# ── Module cards ────────────────────────────────────────────
st.markdown(
    '<div style="font-weight:700;color:#4D148C;font-size:13px;text-transform:uppercase;' +
    'letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">' +
    'Available Modules</div>',
    unsafe_allow_html=True,
)

mc1, mc2 = st.columns(2)
render_module_card(mc1, "📤", "Data Upload Centre",
    "Upload FAMIS volume files and Facility Master data. "
    "Automatically persists to PostgreSQL and backs up locally. "
    "View upload history and download data templates.",
    accent=_PURPLE, gradient=True)
render_module_card(mc2, "📊", "Station Analytics",
    "Region-level health overview for all stations. "
    "Click any station to drill down into historical Area, Resource and Courier trends. "
    "Filterable by date, region and status.",
    accent=_GREEN, gradient=True)

st.markdown("<br>", unsafe_allow_html=True)

mc3, mc4, mc5 = st.columns(3)
render_module_card(mc3, "📐", "Area Planning",
    "Calculate facility area requirements based on FAMIS volume: "
    "sorting area, caging, equipment and aisle space.",
    accent=_PURPLE)
render_module_card(mc4, "👥", "Resource Planning",
    "Calculate OSA, LASA, Dispatcher and Trace Agent headcount "
    "requirements using configurable TACT values.",
    accent=_PURPLE)
render_module_card(mc5, "🚚", "Courier Planning",
    "Compute courier headcount from volume, productivity, "
    "absenteeism and training percentages.",
    accent=_PURPLE)

render_footer("FIELD")
