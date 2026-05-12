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
# FACILITY (default)
# ════════════════════════════════════════════════════════════
render_header(
    "AERO — Automated Evaluation Of Resource Occupancy",
    "FedEx Planning & Engineering | Area, Resource & Courier Planning",
    logo_height=80,
)

render_info_banner(
    "How to Use AERO",
    "Follow the steps below to get started with facility planning and health monitoring.",
)

render_step_guide([
    {"title": "Prepare Data Files",
     "description": "Download the Excel templates below and populate them with your FAMIS "
                    "volume data and Facility Master data. Ensure <code>loc_id</code> and "
                    "<code>date</code> columns are filled correctly."},
    {"title": "Upload to Health Monitor",
     "description": "Navigate to <b>Health Monitoring → Health Monitor</b>. Upload both the "
                    "FAMIS file and the Facility Master file using the file uploaders at the top."},
    {"title": "Select File Type & Date",
     "description": "Choose the FAMIS file type (Daily / Weekly / Monthly) for volume "
                    "normalisation, then select the date to analyse from the dropdown."},
    {"title": "Review Health Tabs",
     "description": "Switch between <b>Area Monitor</b>, <b>Station Agent Monitor</b>, "
                    "<b>Courier Monitor</b>, and <b>Analytics</b> tabs to review health status."},
    {"title": "Publish Reports",
     "description": "Use <b>Publish to Excel</b> to download reports, or <b>Publish to Database</b> "
                    "to store results in the central database."},
    {"title": "Individual Trackers",
     "description": "Use the <b>Area Tracker</b>, <b>Resource Tracker</b>, and <b>Courier Tracker</b> "
                    "for detailed single-station calculations. They auto-populate from uploaded FAMIS data."},
])

st.markdown(
    '<div style="font-weight:700;color:#333;font-size:12px;text-transform:uppercase;'
    'letter-spacing:0.6px;margin:1.5rem 0 12px;">Modules</div>',
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)
render_module_card(c1, "🏢", "Area Tracker",
    "Calculate facility area requirements: sorting, equipment, caging & supplies "
    "based on volume and model type.", accent=_PURPLE)
render_module_card(c2, "👥", "Resource Tracker",
    "Calculate General OSA, LASA, Dispatcher & Trace Agent requirements "
    "for a station.", accent=_PURPLE)
render_module_card(c3, "🚚", "Courier Tracker",
    "Compute courier headcount requirements based on stops, productivity "
    "and absenteeism.", accent=_PURPLE)

st.markdown("<br>", unsafe_allow_html=True)

c4, c5 = st.columns(2)
render_module_card(c4, "📊", "Health Monitor",
    "Upload FAMIS + Master data to analyse Area, Resource & Courier health across "
    "all stations. Publish results to Excel or the central database.",
    accent=_PURPLE, gradient=True)
render_module_card(c5, "⚙️", "Admin Controls",
    "Configure global parameters, thresholds and model settings that drive all "
    "calculations across the application.",
    accent=_ORANGE, gradient=True)

# ── Excel templates ──────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
render_info_banner(
    "Download Excel Templates",
    "Use these templates to prepare your data for upload into the Health Monitor.",
    accent=_ORANGE,
)

dl1, dl2 = st.columns(2)

with dl1:
    st.markdown("**FAMIS / Volume Data Template**")
    st.caption("date · loc_id · pk_gross_tot · pk_gross_inb · pk_gross_outb · pk_oda · pk_opa · pk_roc · fte_tot · st_cr_or · st_h_or · pk_st_or · pk_fte · pk_cr_or")
    famis_tpl = pd.DataFrame([
        ['2025-01-01', 'ABCD', 1000, 600, 400, 50, 30, 200, 10, 2.0, 8.0, 1.5, 100, 2.5]
    ], columns=['date','loc_id','pk_gross_tot','pk_gross_inb','pk_gross_outb',
                'pk_oda','pk_opa','pk_roc','fte_tot','st_cr_or','st_h_or','pk_st_or','pk_fte','pk_cr_or'])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        famis_tpl.to_excel(w, index=False, sheet_name='FAMIS')
    st.download_button("⬇️  Download FAMIS Template", buf.getvalue(),
                       "FAMIS_Template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

with dl2:
    st.markdown("**Facility Master Data Template**")
    st.caption("date · loc_id · total_facility_area · ops_area · current_total_osa · current_total_couriers")
    master_tpl = pd.DataFrame([
        ['2025-01-01', 'ABCD', 50000, 35000, 25.0, 12]
    ], columns=['date','loc_id','total_facility_area','ops_area',
                'current_total_osa','current_total_couriers'])
    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine='openpyxl') as w:
        master_tpl.to_excel(w, index=False, sheet_name='Master')
    st.download_button("⬇️  Download Master Template", buf2.getvalue(),
                       "Master_Template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

render_footer("HOME")
