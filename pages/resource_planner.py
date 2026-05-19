import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd
import math
from aero.data.station_store import get_all_stations, get_station_info

# ==================================================
# CONFIG LOAD
# ==================================================
from aero.config.settings import load_config

config = load_config()
osa = config.get("OSA", {})
lasa = config.get("LASA", {})
dispatcher = config.setdefault("DISPATCHER", {})
trace_agent = config.get("TRACE_AGENT", {})

# ==================================================
# SESSION STATE INIT
# ==================================================
if "calculate_clicked" not in st.session_state:
    st.session_state.calculate_clicked = False

if "osa_excluded_tasks" not in st.session_state:
    st.session_state.osa_excluded_tasks = set()

if "osa_custom_tasks" not in st.session_state:
    st.session_state.osa_custom_tasks = []

# Draft inputs for custom task
if "custom_name" not in st.session_state:
    st.session_state.custom_name = ""

if "custom_tact" not in st.session_state:
    st.session_state.custom_tact = 0.0

if "custom_param" not in st.session_state:
    st.session_state.custom_param = 0.0

# Initialize session state for calculated times so the calculate flow is deterministic
for _k in ("calculated_osa_time", "calculated_lasa_time", "calculated_dispatcher_time", "calculated_trace_time"):
    if _k not in st.session_state:
        st.session_state[_k] = 0

# LASA session state

if "lasa_excluded_tasks" not in st.session_state:
    st.session_state.lasa_excluded_tasks = set()

if "lasa_custom_tasks" not in st.session_state:
    st.session_state.lasa_custom_tasks = []

# ==================================================
# GLOBAL TOTAL TIME HOLDERS (IN MINUTES)
# ==================================================
total_osa_time = 0
total_lasa_time = 0
total_dispatcher_time = 0
total_trace_time = 0


def render():
    """Render the Station Resource Tracker content (called from station_planner.py tab)."""

    # Re-initialize session state every render (module-level inits only run once
    # due to Python's module cache, so we guard here to survive Streamlit reruns)
    _ss_defaults = {
        "calculate_clicked": False,
        "osa_excluded_tasks": set(),
        "osa_custom_tasks": [],
        "custom_name": "",
        "custom_tact": 0.0,
        "custom_param": 0.0,
        "calculated_osa_time": 0,
        "calculated_lasa_time": 0,
        "calculated_dispatcher_time": 0,
        "calculated_trace_time": 0,
        "lasa_excluded_tasks": set(),
        "lasa_custom_tasks": [],
    }
    for _k, _v in _ss_defaults.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # Re-bind globals that the UI code mutates
    global total_osa_time, total_lasa_time, total_dispatcher_time, total_trace_time

    # Uniform card CSS for consistent sizing across summary cards
    st.markdown("""
    <style>
    /* FedEx-themed summary cards with gradient outline */
    .uniform-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px;
        border-radius: 10px;
        min-height: 84px;
        position: relative;
        overflow: hidden;
        /* layered background: inner fill + gradient border */
        background: linear-gradient(90deg, #FFFFFF 0%, #F3E8FF 100%) padding-box,
                    linear-gradient(90deg, #4D148C 0%, #FF6200 100%) border-box;
        border: 2px solid transparent;
    }
    .uniform-card .icon { 
        font-size: 22px; 
        width:44px; height:44px; display:flex; align-items:center; justify-content:center; 
        background: linear-gradient(180deg,#4D148C 0%, #FF6200 100%); 
        color: #FFFFFF; border-radius:8px; box-shadow: 0 6px 18px rgba(77,20,140,0.08);
    }
    .uniform-card .text { font-size:13px; color:#565656; }
    .uniform-card .text strong { color:#333333; font-size:14px; }

    /* Ensure checkboxes and their labels remain visible on all backgrounds */
    input[type="checkbox"] {
        accent-color: #06b6d4 !important;
        filter: none !important;
        opacity: 1 !important;
    }
    .stCheckbox, .stCheckbox label {
        color: #333333 !important;
    }
    /* Reduce spacing for the station LOC-ID input (tighten gap under Station Information) */
    div[data-testid="stTextInput"] {
        margin-top: 0px !important;
        margin-bottom: 6px !important;
    }

    /* Further target first text input on page to bring it closer to the header */
    div[data-testid="stTextInput"]:first-of-type {
        margin-top: 0px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Excel path for station lookup
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EXCEL_DB = os.path.join(_BASE_DIR, "station_planner_master.xlsx")

    # Station selection
    available_stations = get_all_stations(EXCEL_DB)

    # Sort stations
    all_stations = available_stations
    all_stations.sort()

    if "station_name" not in st.session_state:
        st.session_state.station_name = ""

    # Station Information header (re-inserted) and LOC-ID input
    st.markdown("""
    <div style="
        background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
        border-left: 6px solid #DE002E;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 0.5rem 0 0.5rem 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">📍 Station Information</div>
    </div>
    """, unsafe_allow_html=True)

    # Do not show a free-text LOC-ID before a FAMIS upload. Use the FAMIS selector to drive
    # session-state population. If FAMIS data is available, prefer the selected FAMIS station;
    # otherwise fall back to any previously stored session value (but do not render the input).
    famis_data = st.session_state.get('famis_data', None)
    if famis_data is not None and not famis_data.empty:
        # If a station was auto-selected from FAMIS, ensure the canonical session key is populated
        st.session_state['station_name'] = st.session_state.get('resource_famis_station', st.session_state.get('station_name', ''))
    else:
        # No FAMIS upload — keep session value if any but do not render the LOC-ID input box
        st.session_state['station_name'] = st.session_state.get('station_name', '')

    # ==================================================
    # FAMIS STATION SELECTION (Auto-populate from Health Monitor)
    # ==================================================
    famis_data = st.session_state.get('famis_data', None)

    if famis_data is not None and not famis_data.empty:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
            border-left: 4px solid #4D148C;
            border-radius: 8px;
            padding: 1rem 1.25rem;
            margin: 0.5rem 0 1rem 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        ">
            <span style="color: #4D148C; font-weight: 600;">✅ FAMIS Data Loaded</span>
            <span style="color: #565656;"> — Select a station to auto-fill volumes (Gross Total, IB, OB, ROC)</span>
        </div>
        """, unsafe_allow_html=True)

        # Get unique stations and dates
        famis_stations = sorted(famis_data['loc_id'].dropna().unique().tolist())
        famis_dates = sorted(famis_data['date'].unique(), reverse=True)

        famis_col1, famis_col2 = st.columns(2)

        with famis_col1:
            selected_famis_station = st.selectbox(
                "📍 Select FedEx Station",
                options=[""] + famis_stations,
                index=0,
                help="Select a station to auto-populate volumes from FAMIS data",
                key="resource_famis_station"
            )

        with famis_col2:
            selected_famis_date = st.selectbox(
                "📅 Select FAMIS Date",
                options=famis_dates,
                format_func=lambda x: pd.to_datetime(x).strftime('%Y-%m-%d'),
                help="Select the date for volume data",
                key="resource_famis_date"
            )

        # Auto-fill volumes when station is selected
        if selected_famis_station:
            station_data = famis_data[
                (famis_data['loc_id'] == selected_famis_station) & 
                (famis_data['date'] == selected_famis_date)
            ]
            if not station_data.empty:
                row = station_data.iloc[0]
                # Get volume columns from FAMIS
                gross_total = int(row.get('pk_gross_tot', 0)) if pd.notna(row.get('pk_gross_tot')) else 0
                ib_volume = int(row.get('pk_gross_inb', 0)) if pd.notna(row.get('pk_gross_inb')) else 0
                ob_volume = int(row.get('pk_gross_outb', 0)) if pd.notna(row.get('pk_gross_outb')) else 0
                # ROC from FAMIS: ROC = pk_roc * 0.25, ASP = pk_roc - ROC
                roc_from_famis = int(row.get('pk_roc', 0)) if pd.notna(row.get('pk_roc')) else 0
                roc_volume = int(roc_from_famis * 0.25)
                asp_volume = roc_from_famis - roc_volume

                # Store in session state for auto-population across pages
                new_vols = {
                    'loc_id': selected_famis_station,
                    'gross_volume': gross_total,
                    'ib_volume': ib_volume,
                    'ob_volume': ob_volume,
                    'roc_volume': roc_volume,
                    'asp_volume': asp_volume
                }
                # Only rerun if values changed (prevents infinite loop)
                if st.session_state.get('resource_volumes_from_famis') != new_vols:
                    st.session_state['resource_volumes_from_famis'] = new_vols
                    # Update station name
                    st.session_state.station_name = selected_famis_station
                    # Directly set the widget keys so the number_input fields update
                    st.session_state['volume_total'] = gross_total
                    st.session_state['volume_ib'] = ib_volume
                    st.session_state['volume_ob'] = ob_volume
                    st.session_state['volume_roc'] = roc_volume
                    st.session_state['volume_asp'] = asp_volume
                    # Force rerun so number_input widgets pick up new values
                    st.rerun()

                st.success(f"📦 Auto-filled for **{selected_famis_station}**: Gross={gross_total:,} | IB={ib_volume:,} | OB={ob_volume:,} | ASP={asp_volume:,}")
    else:
        st.markdown("""
        <div style="
            background: var(--info-bg);
            border-left: 6px solid var(--fc-purple);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: var(--info-text);
        ">
            <div style="font-weight:700;">💡 Upload FAMIS/Volume data in the <strong>Health Monitor</strong> tab to enable auto-population of volumes</div>
        </div>
        """, unsafe_allow_html=True)

    # ==================================================
    # INPUTS
    # ==================================================

    # Get FAMIS volumes if available
    famis_vols = st.session_state.get('resource_volumes_from_famis', {})
    # Default placeholders: prefer FAMIS values when present, otherwise default to 0
    default_total = int(famis_vols.get('gross_volume', 0))
    default_ib = int(famis_vols.get('ib_volume', 0))
    default_ob = int(famis_vols.get('ob_volume', 0))
    if 'roc_volume' in famis_vols:
        # Use the FAMIS-provided ROC volume even if it's 0 (legitimate value)
        default_roc = int(famis_vols.get('roc_volume', 50))
    else:
        default_roc = 50
    default_asp = int(famis_vols.get('asp_volume', 150)) if famis_vols.get('asp_volume') else 150

    # Volume Details header removed — the expander will act as the card/header

    with st.expander("⚙️ Volume Details", expanded=False):
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        with c1:
            total = st.number_input("Gross Total Volume", min_value=0, value=default_total, step=10, help="Auto-populated from FAMIS", key="volume_total")

        with c2:
            ib = st.number_input("IB Volume", min_value=0, value=default_ib, step=10, help="Auto-populated from FAMIS", key="volume_ib")

        with c3:
            ob = st.number_input("OB Volume", min_value=0, value=default_ob, step=10, help="Auto-populated from FAMIS", key="volume_ob")

        with c4:
            roc = st.number_input("ROC Volume", min_value=0, value=default_roc, step=5, help="Auto-populated from FAMIS", key="volume_roc")

        with c5:
            asp = st.number_input("ASP Volume", min_value=0, value=default_asp, step=10, key="volume_asp")

        with c6:
            on_call_pickup = st.number_input("On-Call Pickup", min_value=0, value=80, step=5, key="on_call_pickup")

        c6, c7, c8 = st.columns(3)

        with c6:
            dex_pct = st.number_input("DEX % of IB", min_value=0.0, max_value=100.0, value=5.0, step=1.0, help="DEX percentage of IB volume", key="dex_pct") / 100

        with c7:
            csbiv_pct = st.number_input("% CSBIV of OB", min_value=0.0, max_value=100.0, value=80.0, step=1.0, help="CSBIV percentage of OB volume", key="csbiv_pct") / 100

        with c8:
            rod_pct = st.number_input("ROD % of IB", min_value=0.0, max_value=100.0, value=30.0, step=1.0, help="ROD percentage of IB volume", key="rod_pct") / 100

        # --- Move Manpower Assumptions inside Volume Details expander as requested ---
        ma1, ma2, ma3 = st.columns(3)

        with ma1:
            shift_hours = st.number_input(
                "Shift Hours(Per day)",
                min_value=1.0,
                max_value=12.0,
                value=9.0,
                step=0.5,
                key="shift_hours_main"
            )

        with ma2:
            absenteeism_pct = st.number_input(
                "Absenteeism(Regular) %",
                min_value=0.0,
                max_value=50.0,
                value=11.0,
                step=1.0
            , key="absenteeism_regular_main") / 100

        with ma3:
            roster_buffer_pct = st.number_input(
                "Roster Buffer(5-days working) %",
                min_value=0.0,
                max_value=30.0,
                value=11.0,
                step=1.0
            ) / 100

    # Persist resource parameters to session state for Health Monitor inheritance
    st.session_state['resource_shift_hours'] = shift_hours
    st.session_state['resource_absenteeism_pct'] = absenteeism_pct * 100  # Store as raw percentage
    st.session_state['resource_roster_buffer_pct'] = roster_buffer_pct * 100  # Store as raw percentage
    st.session_state['resource_on_call_pickup'] = on_call_pickup


    # ==================================================
    # CALCULATE BUTTON
    # ==================================================

    # Set a key and force a rerun after setting the flag so the calculated sections
    # render immediately on the first click instead of requiring multiple clicks.
    if st.button("Calculate Time Requirement", key="calculate_btn"):
        st.session_state.calculate_clicked = True

    # ==================================================
    # Initialize session state for calculated times
    # ==================================================
    if "calculated_osa_time" not in st.session_state:
        st.session_state.calculated_osa_time = 0
    if "calculated_lasa_time" not in st.session_state:
        st.session_state.calculated_lasa_time = 0
    if "calculated_dispatcher_time" not in st.session_state:
        st.session_state.calculated_dispatcher_time = 0
    if "calculated_trace_time" not in st.session_state:
        st.session_state.calculated_trace_time = 0

    # ==================================================
    # CURRENT STATION TYPE 
    # ==================================================
    if total <= 500:
        station_type = "A"
    elif 501 <= total <= 1500:
        station_type = "B"
    elif 1501 <= total <= 3500:
        station_type = "C"
    else:
        station_type = "D"

    # Station type info banner removed per request

    # ==================================================
    # OSA EXPANDER
    # ==================================================
    st.markdown("---")

    # Helper generators for task lists (single source of truth)
    def get_osa_tasks():
        return [
            ("IB / OB Scan", osa.get("IB_OB_SCAN_TACT", 0.12), total, "TACT * Gross Total Volume    "),
            ("Damage Scan & Reporting", osa.get("DAMAGE_SCAN_TACT", 3), ib * osa.get("DAMAGE_SCAN_PCT_IB", 0.005), "TACT*(0.5% * IB Volume)"),
            ("Compliance Report", osa.get("COMPLIANCE_TACT", 5), osa.get("COMPLIANCE_FIXED_COUNT", 2), "TACT * Fixed Count(2)"),
            ("ROD Invoice & BOE", osa.get("ROD_BOE_TACT", 1), ib * rod_pct, "TACT * (ROD%*IB)"),
            ("Queries Handling Emails", osa.get("EMAIL_QUERY_TACT", 1.5), ib * osa.get("EMAIL_QUERY_PCT_IB", 0.15), "TACT * (15% * IB Volume)"),
            ("NEXT App Actioning", osa.get("NEXT_APP_ACTION_TACT", 4), ib * osa.get("NEXT_APP_ACTION_PCT_IB", 0.015), "TACT * (5% * Gross Volume)"),
            ("Courier On-Call Support", osa.get("COURIER_ONCALL_TACT", 4), total * osa.get("COURIER_ONCALL_PCT_TOTAL", 0.05), "TACT * (5% * Total Volume)"),
            ("Incomplete MPS / Holiday", osa.get("INCOMPLETE_MPS_TACT", 0.12), ib * osa.get("INCOMPLETE_MPS_PCT_IB", 0.40), "TACT * (40% * IB Volume)"),
            ("Incomplete Report", osa.get("INCOMPLETE_REPORT_TACT", 20), osa.get("INCOMPLETE_REPORT_COUNT", 1), "TACT * Fixed Count(1)"),
            ("Cage Monitoring", osa.get("CAGE_MONITORING_TACT", 2), ib * osa.get("CAGE_MONITORING_PCT_IB", 0.10), "10% * IB volume"),
            ("DEX Monitoring", osa.get("DEX_MONITORING_TACT", 1.2), ib * dex_pct, f"TACT * DEX % of IB Volume"),
            ("ROC Activities", osa.get("ROC_ACTIVITIES_TACT", 6), roc, f"TACT * ROC Volume"),
            ("DEX Handling", osa.get("DEX_HANDLING_TACT", 4), ib * dex_pct, f"TACT * DEX % of IB Volume"),
            ("Pickup Shipment Handover", osa.get("PICKUP_HANDOVER_TACT", 0.25), ob - asp, f"TACT * (OB - ASP Volume)"),
            ("FAMIS Report", osa.get("FAMIS_TACT", 30), 1, f"TACT * Fixed Count(1)"),
            ("Outbound Scan & Load", osa.get("OB_SCAN_LOAD_TACT", 0.1), ob, f"TACT * OB Volume"),
            ("IPHP Pre-alert", osa.get("IPHP_PREALERT_TACT", 0.2), csbiv_pct * ob, f"TACT * (CSBIV% * OB Volume)"),
            ("IPHP Checking", osa.get("IPHP_CHECKING_TACT", 15), 1, f"TACT * Fixed Count(1)"),
            ("InControl Report OB", osa.get("INCONTROL_OB_TACT", 20), 1, f"TACT * Fixed Count(1)"),
            ("EGNSL Failure", osa.get("EGNSL_TACT", 15), 1, f"TACT * Fixed Count(1)"),
            ("PAR Report", osa.get("PAR_TACT", 10), 1, f"TACT * Fixed Count(1)"),
            ("ASP Handling", osa.get("ASP_HANDLING_TACT", 0.5), asp, f"TACT * ASP Volume"),
            ("REX Application", osa.get("REX_APPLICATION_TACT", 0.2), 0.9 * ob, f"TACT * (0.9 × OB Volume)"),
            ("PPWK Imaging", osa.get("PPWK_IMAGING_TACT", 0.1), 0.8 * ob, f"TACT * (0.8 × OB Volume)"),
            ("Gatekeeper IB & OB", osa.get("GATEKEEPER_TACT", 30), 1, f"TACT * Fixed Count(1)"),
            ("KYC", osa.get("KYC_TACT", 2), ib * osa.get("KYC_PCT_IB", 0.02), f"TACT * ({ib} × {osa.get('KYC_PCT_IB', 0.02)})"),
            ("Station Opening & Closing", osa.get("STATION_OPEN_CLOSE_TACT", 10), 1, f"TACT * Fixed Count(1)"),
        ]

    def get_lasa_tasks():
        return [
            ("Mailing ROD Invoice & BOE Copy", lasa.get("MAILING_ROD_BOE_TACT", 1.0), ib * rod_pct, f"TACT * (ROD% * IB)"),
            ("Banking Activities", lasa.get("BANKING_ACTIVITIES_TACT", 15.0), 1, f"TACT * 1"),
            ("Review of AR / OR File Closure", lasa.get("AR_OR_FILE_REVIEW_TACT", 1.5), ib * 0.10, f"TACT * (IB * 0.10)"),
            ("Checking Emails & Attending Customer Queries", lasa.get("CHECK_EMAILS_CUSTOMER_QUERIES_TACT", 1.0), (0.25 * ib) + (0.02 * ob), f"TACT * ((0.25 × IB) + (0.02 × OB))"),
            ("Closure of GCCS for All Open Cases", lasa.get("GCCS_CLOSURE_TACT", 1.0), (0.25 * ib) + (0.05 * (ob - asp)), f"TACT * ((0.25 × IB) + (0.05 × (OB - ASP)))"),
            ("Review of Invoice Payment", lasa.get("INVOICE_PAYMENT_REVIEW_TACT", 15.0), 1, f"TACT * 1"),
            ("Preparing Vendor Invoice", lasa.get("PREPARING_VENDOR_INVOICE_TACT", 30.0), 1, f"TACT * 1"),
            ("Raising PO for Utilities & Maintenance", lasa.get("PO_UTILITIES_MAINTENANCE_TACT", 10.0), 1, f"TACT * 1"),
            ("Provision File Submission to Manager", lasa.get("PROVISION_FILE_SUBMISSION_TACT", 5.0), 1, f"TACT * 1"),
            ("Preparing Agreement Draft", lasa.get("AGREEMENT_DRAFT_TACT", 5.0), 1, f"TACT * 1"),
            ("EOD Closure, Tallying and Check", lasa.get("EOD_CLOSURE_TACT", 25.0), 1, f"TACT * 1"),
            ("Other Activities", lasa.get("OTHER_ACTIVITIES_TACT", 20.0), 1, f"TACT * 1"),
        ]

    def get_dispatcher_tasks():
        return [
            ("Push Dispatch to Couriers as per Route", dispatcher.get("PUSH_DISPATCH_TACT", 1.5), on_call_pickup, f"TACT * PUP"),
            ("Monitoring of Live DEX", dispatcher.get("LIVE_DEX_MONITORING_TACT", 0.5), dex_pct * ib, f"TACT * (DEX% * IB)"),
            ("Monitoring GDP SIMs", dispatcher.get("GDP_SIMS_MONITORING_TACT", 10), 1, f"TACT * 1"),
            ("EDI Updation of Cash and BCN Pickup", dispatcher.get("EDI_CASH_BCN_PICKUP_TACT", 0.5), 0.20 * ob, f"TACT * (20% * OB)"),
            ("Checking Emails & Responding to Queries", dispatcher.get("EMAIL_QUERY_HANDLING_TACT", 2), 0.03 * total, f"TACT * (3% * Gross Total Volume)"),
            ("Coordinating with Customers", dispatcher.get("CUSTOMER_COORDINATION_TACT", 1), 0.15 * (ob - asp), f"TACT * 15%(OB * ASP)"),
            ("Check Account Status in e-ICS", dispatcher.get("EICS_ACCOUNT_STATUS_CHECK_TACT", 5), 1, f"TACT * Fixed Count"),
            ("Fraudulent Account Misuse", dispatcher.get("FRAUD_ACCOUNT_MISUSE_TACT", 5), 2, f"TACT * Fixed Count"),
            ("Closing Dispatch and EOD Business", dispatcher.get("CLOSE_DISPATCH_EOD_TACT", 0.5), on_call_pickup, f"TACT * PUP"),
        ]

    def get_trace_tasks():
        return [
            ("Calling Customer & Informing Courier for Reattempt", trace_agent.get("CUSTOMER_CALL_REATTEMPT_TACT", 2), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
            ("Work on Cage Ageing Shipment", trace_agent.get("CAGE_AGEING_SHIPMENT_TACT", 3), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
            ("Coordinating with Customers and Sales Team", trace_agent.get("CUSTOMER_SALES_COORDINATION_TACT", 2), 0.01 * ob, f"TACT * (1% * ROC                    )"),
            ("Work on CMOD", trace_agent.get("CMOD_WORK_TACT", 2), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
            ("Assess Open Cases and Work on Closure", trace_agent.get("OPEN_CASES_CLOSURE_TACT", 3), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
            ("Reopen Case if Issue Not Resolved", trace_agent.get("REOPEN_CASES_TACT", 20), 1, f"TACT × Fixed Count"),
            ("CMOD Report Monitoring and Closure", trace_agent.get("CMOD_REPORT_CLOSURE_TACT", 20), 1, f"TACT × Fixed Count"),
        ]

    # Summary cards (render before expanders but reflect checkbox states)
    if st.session_state.get('calculate_clicked'):
        def compute_total(system_tasks, sys_key_prefix, custom_tasks, custom_key_prefix):
            total_time = 0
            for name, tact, param, _ in system_tasks:
                key = f"{sys_key_prefix}{name}"
                included = st.session_state.get(key, True)
                if included:
                    total_time += tact * param
            for task in custom_tasks:
                key = f"{custom_key_prefix}{task['id']}"
                included = st.session_state.get(key, True)
                if included:
                    total_time += task['tact'] * task['param']
            return total_time

        osa_total = compute_total(get_osa_tasks(), "sys_", st.session_state.osa_custom_tasks, "custom_chk_")
        lasa_total = compute_total(get_lasa_tasks(), "lasa_chk_", st.session_state.lasa_custom_tasks, "lasa_custom_chk_")
        dispatcher_total = compute_total(get_dispatcher_tasks(), "dispatcher_chk_", st.session_state.dispatcher_custom_tasks, "dispatcher_custom_chk_")
        trace_total = compute_total(get_trace_tasks(), "trace_chk_", st.session_state.trace_custom_tasks, "trace_custom_chk_")

        # Update session state so expanders and SHARP use same values
        st.session_state.calculated_osa_time = osa_total
        st.session_state.calculated_lasa_time = lasa_total
        st.session_state.calculated_dispatcher_time = dispatcher_total
        st.session_state.calculated_trace_time = trace_total

        # Render summary cards
        osa_hours = osa_total / 60
        lasa_hours = lasa_total / 60
        dispatcher_hours = dispatcher_total / 60
        trace_hours = trace_total / 60

        # Agents required (base) for display on summary cards
        osa_agents_req = osa_hours / shift_hours if shift_hours else 0
        lasa_agents_req = lasa_hours / shift_hours if shift_hours else 0
        dispatcher_agents_req = dispatcher_hours / shift_hours if shift_hours else 0
        trace_agents_req = trace_hours / shift_hours if shift_hours else 0

        # NO DATA condition: if gross total volume is zero, mark summaries as NO DATA
        no_data_flag = (total == 0)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="uniform-card">
                <div class="icon">👩‍💻</div>
                <div class="text">
                    <strong>GENERAL OSA TASK WISE CALCULATION</strong><br>
                    Agents Required = {('—' if no_data_flag else round(osa_agents_req,2))}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="uniform-card">
                <div class="icon">📋</div>
                <div class="text">
                    <strong>LASA TASK WISE CALCULATION</strong><br>
                    Agents Required = {('—' if no_data_flag else round(lasa_agents_req,2))}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="uniform-card">
                <div class="icon">📦</div>
                <div class="text">
                    <strong>DISPATCHER TASK WISE CALCULATION</strong><br>
                    Agents Required = {('—' if no_data_flag else round(dispatcher_agents_req,2))}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="uniform-card">
                <div class="icon">🔎</div>
                <div class="text">
                    <strong>TRACE AGENT TASK WISE CALCULATION</strong><br>
                    Agents Required = {('—' if no_data_flag else round(trace_agents_req,2))}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # continue to expanders below

    if st.session_state.calculate_clicked:

        with st.expander("General OSA – Task-wise Calculation", expanded=False):

            # ------------------------------
            # SYSTEM TASKS (ALL 28)
            # ------------------------------
            system_tasks = [
                ("IB / OB Scan", osa.get("IB_OB_SCAN_TACT", 0.12), total, "TACT * Gross Total Volume    "),
                ("Damage Scan & Reporting", osa.get("DAMAGE_SCAN_TACT", 3), ib * osa.get("DAMAGE_SCAN_PCT_IB", 0.005), "TACT*(0.5% * IB Volume)"),
                ("Compliance Report", osa.get("COMPLIANCE_TACT", 5), osa.get("COMPLIANCE_FIXED_COUNT", 2), "TACT * Fixed Count(2)"),
                ("ROD Invoice & BOE", osa.get("ROD_BOE_TACT", 1), ib * rod_pct, "TACT * (ROD%*IB)"),
                ("Queries Handling Emails", osa.get("EMAIL_QUERY_TACT", 1.5), ib * osa.get("EMAIL_QUERY_PCT_IB", 0.15), "TACT * (15% * IB Volume)"),
                ("NEXT App Actioning", osa.get("NEXT_APP_ACTION_TACT", 4), ib * osa.get("NEXT_APP_ACTION_PCT_IB", 0.015), "TACT * (5% * Gross Volume)"),
                ("Courier On-Call Support", osa.get("COURIER_ONCALL_TACT", 4), total * osa.get("COURIER_ONCALL_PCT_TOTAL", 0.05), "TACT * (5% * Total Volume)"),
                ("Incomplete MPS / Holiday", osa.get("INCOMPLETE_MPS_TACT", 0.12), ib * osa.get("INCOMPLETE_MPS_PCT_IB", 0.40), "TACT * (40% * IB Volume)"),
                ("Incomplete Report", osa.get("INCOMPLETE_REPORT_TACT", 20), osa.get("INCOMPLETE_REPORT_COUNT", 1), "TACT * Fixed Count(1)"),
                ("Cage Monitoring", osa.get("CAGE_MONITORING_TACT", 2), ib * osa.get("CAGE_MONITORING_PCT_IB", 0.10), "10% * IB volume"),
                ("DEX Monitoring", osa.get("DEX_MONITORING_TACT", 1.2), ib * dex_pct, f"TACT * DEX % of IB Volume"),
                ("ROC Activities", osa.get("ROC_ACTIVITIES_TACT", 6), roc, f"TACT * ROC Volume"),
                ("DEX Handling", osa.get("DEX_HANDLING_TACT", 4), ib * dex_pct, f"TACT * DEX % of IB Volume"),
                ("Pickup Shipment Handover", osa.get("PICKUP_HANDOVER_TACT", 0.25), ob - asp, f"TACT * (OB - ASP Volume)"),
                ("FAMIS Report", osa.get("FAMIS_TACT", 30), 1, f"TACT * Fixed Count(1)"),
                ("Outbound Scan & Load", osa.get("OB_SCAN_LOAD_TACT", 0.1), ob, f"TACT * OB Volume"),
                ("IPHP Pre-alert", osa.get("IPHP_PREALERT_TACT", 0.2), csbiv_pct * ob, f"TACT * (CSBIV% * OB Volume)"),
                ("IPHP Checking", osa.get("IPHP_CHECKING_TACT", 15), 1, f"TACT * Fixed Count(1)"),
                ("InControl Report OB", osa.get("INCONTROL_OB_TACT", 20), 1, f"TACT * Fixed Count(1)"),
                ("EGNSL Failure", osa.get("EGNSL_TACT", 15), 1, f"TACT * Fixed Count(1)"),
                ("PAR Report", osa.get("PAR_TACT", 10), 1, f"TACT * Fixed Count(1)"),
                ("ASP Handling", osa.get("ASP_HANDLING_TACT", 0.5), asp, f"TACT * ASP Volume"),

                ("REX Application", osa.get("REX_APPLICATION_TACT", 0.2), 0.9 * ob, f"TACT * (0.9 × OB Volume)"),
                ("PPWK Imaging", osa.get("PPWK_IMAGING_TACT", 0.1), 0.8 * ob, f"TACT * (0.8 × OB Volume)"),
                ("Gatekeeper IB & OB", osa.get("GATEKEEPER_TACT", 30), 1, f"TACT * Fixed Count(1)"),
                ("KYC", osa.get("KYC_TACT", 2), ib * osa.get("KYC_PCT_IB", 0.02), f"TACT * ({ib} × {osa.get('KYC_PCT_IB', 0.02)})"),
                ("Station Opening & Closing", osa.get("STATION_OPEN_CLOSE_TACT", 10), 1, f"TACT * Fixed Count(1)"),
            ]   

            left, right = st.columns([3, 1])
            rows = []

            # ------------------------------
            # CALCULATION
            # ------------------------------
            for name, tact, param, formula in system_tasks:
                # Determine inclusion from the checkbox widget state so changes
                # take effect immediately on rerun. Default to included (True).
                included = st.session_state.get(f"sys_{name}", True)
                if not included:
                    continue
                rows.append([name, tact, round(param, 2), round(tact * param, 2), formula])

            for task in st.session_state.osa_custom_tasks:
                included = st.session_state.get(f"custom_chk_{task['id']}", True)
                if not included:
                    continue
                custom_formula = f"{task['tact']} × {task['param']}"
                rows.append([task["name"], task["tact"], round(task["param"], 2), round(task["tact"] * task["param"], 2), custom_formula])

            df = pd.DataFrame(rows, columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)", "Formula"])

            # ------------------------------
            # LEFT: TABLE
            # ------------------------------
            with left:
                st.subheader("OSA Time Requirement")
                st.table(df)
                total_osa_time = df["Total Time (mins)"].sum()
                osa_hours = total_osa_time / 60
                osa_agents = osa_hours / 9
                # Summary banner removed to declutter UI
                # Store in session state for SHARP summary
                st.session_state.calculated_osa_time = total_osa_time
                st.info(f"**Total OSA Time: {total_osa_time:.0f} minutes / {osa_hours:.2f} hours**")

            # ------------------------------
            # RIGHT: INCLUDE / EXCLUDE
            # ------------------------------
            with right:
                st.subheader("Include / Exclude Tasks")

                for name, _, _, _ in system_tasks:
                    checked = st.checkbox(
                        name,
                        value=name not in st.session_state.osa_excluded_tasks,
                        key=f"sys_{name}"
                    )
                    # Avoid in-place mutation of session_state objects; always reassign
                    if not checked:
                        s = set(st.session_state.osa_excluded_tasks)
                        s.add(name)
                        st.session_state.osa_excluded_tasks = s
                    else:
                        s = set(st.session_state.osa_excluded_tasks)
                        s.discard(name)
                        st.session_state.osa_excluded_tasks = s

                if st.session_state.osa_custom_tasks:
                    st.divider()

                for idx, task in enumerate(st.session_state.osa_custom_tasks):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        checked = st.checkbox(
                            f"[Custom] {task['name']}",
                            value=task["id"] not in st.session_state.osa_excluded_tasks,
                            key=f"custom_chk_{task['id']}"
                        )
                        if not checked:
                            s = set(st.session_state.osa_excluded_tasks)
                            s.add(task["id"])
                            st.session_state.osa_excluded_tasks = s
                        else:
                            s = set(st.session_state.osa_excluded_tasks)
                            s.discard(task["id"])
                            st.session_state.osa_excluded_tasks = s
                    with c2:
                        if st.button("🗑️", key=f"del_{task['id']}"):
                            st.session_state.osa_custom_tasks.pop(idx)
                            s = set(st.session_state.osa_excluded_tasks)
                            s.discard(task["id"])
                            st.session_state.osa_excluded_tasks = s
                            st.rerun()
            # ------------------------------
            # ADD CUSTOM OSA TASK
            # ------------------------------
            st.markdown("---")
            st.subheader("Add Additional OSA Task")

            ma1, ma2, ma3 = st.columns(3)

            with ma1:
                shift_hours_add = st.number_input(
                    "Shift Hours(Per day)",
                    min_value=1.0,
                    max_value=12.0,
                    value=9.0,
                    step=0.5,
                    key="shift_hours_add"
                )

            with ma2:
                absenteeism_pct_add = st.number_input(
                    "Absenteeism(Regular) %",
                    min_value=0.0,
                    max_value=50.0,
                    value=15.0,
                    step=1.0,
                    key="absenteeism_regular_add") / 100

            with ma3:
                roster_buffer_pct_add = st.number_input(
                    "Roster Buffer(5-days working) %",
                    min_value=0.0,
                    max_value=30.0,
                    value=11.0,
                    key="roster_buffer_add") / 100

            # LASA block moved to its own expander to improve layout

        with st.expander("LASA – Task-wise Calculation", expanded=False):

            rows = []
            total_lasa_time = 0

            left, mid, right = st.columns([4, 0.5, 1])

            # ------------------------------
            # CALCULATION
            # ------------------------------
            lasa_tasks = get_lasa_tasks()
            for name, tact, param, formula in lasa_tasks:
                # Use the checkbox widget state to determine inclusion
                included = st.session_state.get(f"lasa_chk_{name}", True)
                if not included:
                    continue

                time_taken = tact * param
                total_lasa_time += time_taken

                rows.append([
                    name,
                    round(tact, 2),
                    round(param, 2),
                    round(time_taken, 2),
                    formula
                ])

            # Add custom tasks
            for task in st.session_state.lasa_custom_tasks:
                included = st.session_state.get(f"lasa_custom_chk_{task['id']}", True)
                if not included:
                    continue

                time_taken = task["tact"] * task["param"]
                total_lasa_time += time_taken
                custom_formula = f"{task['tact']} × {task['param']}"

                rows.append([
                    task["name"],
                    round(task["tact"], 2),
                    round(task["param"], 2),
                    round(time_taken, 2),
                    custom_formula
                ])

            df_lasa = pd.DataFrame(
                rows,
                columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)", "Formula"]
            )

            # ------------------------------
            # LEFT: TABLE
            # ------------------------------
            with left:
                st.subheader("LASA Time Requirement")
                st.table(df_lasa)
                lasa_hours = total_lasa_time / 60
                lasa_agents = lasa_hours / 9
                # Summary banner removed to declutter UI
                # Store in session state for SHARP summary
                st.session_state.calculated_lasa_time = total_lasa_time
                st.info(f"**Total LASA Time: {total_lasa_time:.0f} minutes / {lasa_hours:.2f} hours**")

            # ------------------------------
            # RIGHT: INCLUDE / EXCLUDE (OSA-LIKE UI)
            # ------------------------------
            with right:
                st.subheader("Include / Exclude Tasks")

                # BASE TASKS
                for name, _, _, _ in lasa_tasks:
                    checked = st.checkbox(
                        name,
                        value=st.session_state.get(f"lasa_chk_{name}", True),
                        key=f"lasa_chk_{name}"
                    )
                    # Reassign set to ensure Streamlit detects changes
                    s = set(st.session_state.lasa_excluded_tasks)
                    if not checked:
                        s.add(name)
                    else:
                        s.discard(name)
                    st.session_state.lasa_excluded_tasks = s

                if st.session_state.lasa_custom_tasks:
                    st.divider()

                # CUSTOM TASKS (WITH DELETE)
                for idx, task in enumerate(st.session_state.lasa_custom_tasks):
                    c1, c2 = st.columns([4, 1])

                    with c1:
                        checked = st.checkbox(
                            f"[Custom] {task['name']}",
                            value=st.session_state.get(f"lasa_custom_chk_{task['id']}", True),
                            key=f"lasa_custom_chk_{task['id']}"
                        )
                        s = set(st.session_state.lasa_excluded_tasks)
                        if not checked:
                            s.add(task["id"])
                        else:
                            s.discard(task["id"])
                        st.session_state.lasa_excluded_tasks = s

                    with c2:
                        if st.button("🗑️", key=f"del_lasa_{task['id']}"):
                            st.session_state.lasa_custom_tasks.pop(idx)
                            s = set(st.session_state.lasa_excluded_tasks)
                            s.discard(task["id"])
                            st.session_state.lasa_excluded_tasks = s
                            st.rerun()

            # ------------------------------
            # ADD CUSTOM LASA TASK
            # ------------------------------
            st.divider()
            st.subheader("➕ Add Additional LASA Task")

            if "lasa_new_name" not in st.session_state:
                st.session_state.lasa_new_name = ""
            if "lasa_new_tact" not in st.session_state:
                st.session_state.lasa_new_tact = 0.0
            if "lasa_new_param" not in st.session_state:
                st.session_state.lasa_new_param = 0.0

            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("Task Name", key="lasa_new_name")
            with c2:
                st.number_input("TACT (mins)", min_value=0.0, step=0.5, key="lasa_new_tact")
            with c3:
                st.number_input("Parameter", min_value=0.0, step=1.0, key="lasa_new_param")

            if st.button("Add LASA Task"):
                name = st.session_state.lasa_new_name.strip()
                if name:
                    st.session_state.lasa_custom_tasks.append({
                        "id": f"lasa_custom_{len(st.session_state.lasa_custom_tasks)}",
                        "name": name,
                        "tact": st.session_state.lasa_new_tact,
                        "param": st.session_state.lasa_new_param
                    })
                    st.rerun()

        # Display total time outside expander
        lasa_hours_display = total_lasa_time / 60
        lasa_agents_display = lasa_hours_display / 9
        # Info banner removed to declutter UI

    # ==================================================
    # SESSION STATE INIT 
    # ==================================================
    if "dispatcher_excluded_tasks" not in st.session_state:
        st.session_state.dispatcher_excluded_tasks = set()

    if "dispatcher_custom_tasks" not in st.session_state:
        st.session_state.dispatcher_custom_tasks = []

    # ==================================================
    # DISPATCHER – TASK-WISE CALCULATION (FINAL, LOCKED)
    # ==================================================
    if st.session_state.calculate_clicked:

        with st.expander("Dispatcher – Task-wise Calculation", expanded=False):

            # ---------- BASE DISPATCHER TASKS ----------
            dispatcher_tasks = [
                ("Push Dispatch to Couriers as per Route", dispatcher.get("PUSH_DISPATCH_TACT", 1.5), on_call_pickup, f"TACT * PUP"),
                ("Monitoring of Live DEX", dispatcher.get("LIVE_DEX_MONITORING_TACT", 0.5), dex_pct * ib, f"TACT * (DEX% * IB)"),
                ("Monitoring GDP SIMs", dispatcher.get("GDP_SIMS_MONITORING_TACT", 10), 1, f"TACT * 1"),
                ("EDI Updation of Cash and BCN Pickup", dispatcher.get("EDI_CASH_BCN_PICKUP_TACT", 0.5), 0.20 * ob, f"TACT * (20% * OB)"),
                ("Checking Emails & Responding to Queries", dispatcher.get("EMAIL_QUERY_HANDLING_TACT", 2), 0.03 * total, f"TACT * (3% * Gross Total Volume)"),
                ("Coordinating with Customers", dispatcher.get("CUSTOMER_COORDINATION_TACT", 1), 0.15 * (ob - asp), f"TACT * 15%(OB * ASP)"),
                ("Check Account Status in e-ICS", dispatcher.get("EICS_ACCOUNT_STATUS_CHECK_TACT", 5), 1, f"TACT * Fixed Count"),
                ("Fraudulent Account Misuse", dispatcher.get("FRAUD_ACCOUNT_MISUSE_TACT", 5), 2, f"TACT * Fixed Count"),
                ("Closing Dispatch and EOD Business", dispatcher.get("CLOSE_DISPATCH_EOD_TACT", 0.5), on_call_pickup, f"TACT * PUP"),
            ]

            rows = []
            total_dispatcher_time = 0

            left, right = st.columns([3, 1])

            # ------------------------------
            # CALCULATION
            # ------------------------------
            for name, tact, param, formula in dispatcher_tasks:
                included = st.session_state.get(f"dispatcher_chk_{name}", True)
                if not included:
                    continue

                time_taken = tact * param
                total_dispatcher_time += time_taken

                rows.append([
                    name,
                    round(tact, 2),
                    round(param, 2),
                    round(time_taken, 2),
                    formula
                ])

            # Add custom tasks
            for task in st.session_state.dispatcher_custom_tasks:
                included = st.session_state.get(f"dispatcher_custom_chk_{task['id']}", True)
                if not included:
                    continue

                time_taken = task["tact"] * task["param"]
                total_dispatcher_time += time_taken
                custom_formula = f"{task['tact']} × {task['param']}"

                rows.append([
                    task["name"],
                    round(task["tact"], 2),
                    round(task["param"], 2),
                    round(time_taken, 2),
                    custom_formula
                ])

            df_dispatcher = pd.DataFrame(
                rows,
                columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)", "Formula"]
            )

            # ------------------------------
            # LEFT: TABLE + TOTAL
            # ------------------------------
            with left:
                st.subheader("Dispatcher Time Requirement")
                st.table(df_dispatcher)
                # Store in session state for SHARP summary
                st.session_state.calculated_dispatcher_time = total_dispatcher_time
                dispatcher_hours = total_dispatcher_time / 60
                st.info(f"**Total Dispatcher Time: {total_dispatcher_time:.0f} minutes / {dispatcher_hours:.2f} hours**")

            # ------------------------------
            # RIGHT: INCLUDE / EXCLUDE + CUSTOM TASKS
            # ------------------------------
            with right:
                st.subheader("Include / Exclude Tasks")

                # BASE TASKS (NO DELETE)
                for name, _, _, _ in dispatcher_tasks:
                    checked = st.checkbox(
                        name,
                        value=st.session_state.get(f"dispatcher_chk_{name}", True),
                        key=f"dispatcher_chk_{name}"
                    )
                    s = set(st.session_state.dispatcher_excluded_tasks)
                    if not checked:
                        s.add(name)
                    else:
                        s.discard(name)
                    st.session_state.dispatcher_excluded_tasks = s

                if st.session_state.dispatcher_custom_tasks:
                    st.divider()

                # CUSTOM TASKS (CHECKBOX + DELETE)
                for idx, task in enumerate(st.session_state.dispatcher_custom_tasks):
                    c1, c2 = st.columns([4, 1])

                    with c1:
                        checked = st.checkbox(
                            f"[Custom] {task['name']}",
                            value=st.session_state.get(f"dispatcher_custom_chk_{task['id']}", True),
                            key=f"dispatcher_custom_chk_{task['id']}"
                        )
                        s = set(st.session_state.dispatcher_excluded_tasks)
                        if not checked:
                            s.add(task["id"])
                        else:
                            s.discard(task["id"])
                        st.session_state.dispatcher_excluded_tasks = s

                    with c2:
                        if st.button("🗑️", key=f"del_dispatcher_{task['id']}"):
                            st.session_state.dispatcher_custom_tasks.pop(idx)
                            s = set(st.session_state.dispatcher_excluded_tasks)
                            s.discard(task["id"])
                            st.session_state.dispatcher_excluded_tasks = s
                            st.rerun()

            # ------------------------------
            # ADD CUSTOM DISPATCHER TASK (BOTTOM)
            # ------------------------------
            st.divider()
            st.subheader("➕ Add Additional Dispatcher Task")

            if "dispatcher_new_name" not in st.session_state:
                st.session_state.dispatcher_new_name = ""
            if "dispatcher_new_tact" not in st.session_state:
                st.session_state.dispatcher_new_tact = 0.0
            if "dispatcher_new_param" not in st.session_state:
                st.session_state.dispatcher_new_param = 0.0

            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("Task Name", key="dispatcher_new_name")
            with c2:
                st.number_input(
                    "TACT (mins)",
                    min_value=0.0,
                    step=0.5,
                    key="dispatcher_new_tact"
                )
            with c3:
                st.number_input(
                    "Parameter",
                    min_value=0.0,
                    step=1.0,
                    key="dispatcher_new_param"
                )

            if st.button("Add Dispatcher Task"):
                name = st.session_state.dispatcher_new_name.strip()
                if name:
                    st.session_state.dispatcher_custom_tasks.append({
                        "id": f"dispatcher_custom_{len(st.session_state.dispatcher_custom_tasks)}",
                        "name": name,
                        "tact": st.session_state.dispatcher_new_tact,
                        "param": st.session_state.dispatcher_new_param
                    })
                    st.rerun()

        # Display total time outside expander
        dispatcher_hours_display = total_dispatcher_time / 60
        dispatcher_agents_display = dispatcher_hours_display / 9
        # Dispatcher summary banner removed to declutter UI

    # ==================================================
    # SESSION STATE INIT 
    # ==================================================
    if "trace_excluded_tasks" not in st.session_state:
        st.session_state.trace_excluded_tasks = set()

    if "trace_custom_tasks" not in st.session_state:
        st.session_state.trace_custom_tasks = []

    # ==================================================
    # TRACE AGENT – TASK-WISE CALCULATION 
    # ==================================================
    if st.session_state.calculate_clicked:

        with st.expander("Trace Agent – Task-wise Calculation", expanded=False):

            # ---------- BASE TRACE AGENT TASKS ----------
            trace_tasks = [
                ("Calling Customer & Informing Courier for Reattempt", trace_agent.get("CUSTOMER_CALL_REATTEMPT_TACT", 2), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
                ("Work on Cage Ageing Shipment", trace_agent.get("CAGE_AGEING_SHIPMENT_TACT", 3), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
                ("Coordinating with Customers and Sales Team", trace_agent.get("CUSTOMER_SALES_COORDINATION_TACT", 2), 0.01 * ob, f"TACT * (1% * ROC                    )"),
                ("Work on CMOD", trace_agent.get("CMOD_WORK_TACT", 2), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
                ("Assess Open Cases and Work on Closure", trace_agent.get("OPEN_CASES_CLOSURE_TACT", 3), 0.02 * total, f"TACT * (2% * Gross Total Volume)"),
                ("Reopen Case if Issue Not Resolved", trace_agent.get("REOPEN_CASES_TACT", 20), 1, f"TACT × Fixed Count"),
                ("CMOD Report Monitoring and Closure", trace_agent.get("CMOD_REPORT_CLOSURE_TACT", 20), 1, f"TACT × Fixed Count"),
            ]

            rows = []
            total_trace_time = 0

            left, right = st.columns([3, 1])

            # ------------------------------
            # CALCULATION
            # ------------------------------
            for name, tact, param, formula in trace_tasks:
                included = st.session_state.get(f"trace_chk_{name}", True)
                if not included:
                    continue

                time_taken = tact * param
                total_trace_time += time_taken

                rows.append([
                    name,
                    round(tact, 2),
                    round(param, 2),
                    round(time_taken, 2),
                    formula
                ])

            # Add custom tasks
            for task in st.session_state.trace_custom_tasks:
                included = st.session_state.get(f"trace_custom_chk_{task['id']}", True)
                if not included:
                    continue

                time_taken = task["tact"] * task["param"]
                total_trace_time += time_taken
                custom_formula = f"{task['tact']} × {task['param']}"

                rows.append([
                    task["name"],
                    round(task["tact"], 2),
                    round(task["param"], 2),
                    round(time_taken, 2),
                    custom_formula
                ])

            df_trace = pd.DataFrame(
                rows,
                columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)", "Formula"]
            )

            # ------------------------------
            # LEFT: TABLE + TOTAL
            # ------------------------------
            with left:
                st.subheader("Trace Agent Time Requirement")
                st.table(df_trace)
                # Summary banner removed to declutter UI
                # Store in session state for SHARP summary
                st.session_state.calculated_trace_time = total_trace_time
                trace_hours = total_trace_time / 60
                st.info(f"**Total Trace Agent Time: {total_trace_time:.0f} minutes / {trace_hours:.2f} hours**")

            # ------------------------------
            # RIGHT: INCLUDE / EXCLUDE + CUSTOM TASKS
            # ------------------------------
            with right:
                st.subheader("Include / Exclude Tasks")

                # BASE TASKS
                for name, _, _, _ in trace_tasks:
                    checked = st.checkbox(
                        name,
                        value=st.session_state.get(f"trace_chk_{name}", True),
                        key=f"trace_chk_{name}"
                    )
                    s = set(st.session_state.trace_excluded_tasks)
                    if not checked:
                        s.add(name)
                    else:
                        s.discard(name)
                    st.session_state.trace_excluded_tasks = s

                if st.session_state.trace_custom_tasks:
                    st.divider()

                # CUSTOM TASKS (CHECKBOX + DELETE)
                for idx, task in enumerate(st.session_state.trace_custom_tasks):
                    c1, c2 = st.columns([4, 1])

                    with c1:
                        checked = st.checkbox(
                            f"[Custom] {task['name']}",
                            value=st.session_state.get(f"trace_custom_chk_{task['id']}", True),
                            key=f"trace_custom_chk_{task['id']}"
                        )
                        s = set(st.session_state.trace_excluded_tasks)
                        if not checked:
                            s.add(task["id"])
                        else:
                            s.discard(task["id"])
                        st.session_state.trace_excluded_tasks = s

                    with c2:
                        if st.button("🗑️", key=f"del_trace_{task['id']}"):
                            st.session_state.trace_custom_tasks.pop(idx)
                            s = set(st.session_state.trace_excluded_tasks)
                            s.discard(task["id"])
                            st.session_state.trace_excluded_tasks = s
                            st.rerun()

            # ------------------------------
            # ADD ADDITIONAL TRACE AGENT TASK
            # ------------------------------
            st.divider()
            st.subheader("➕ Add Additional Trace Agent Task")

            if "trace_new_name" not in st.session_state:
                st.session_state.trace_new_name = ""
            if "trace_new_tact" not in st.session_state:
                st.session_state.trace_new_tact = 0.0
            if "trace_new_param" not in st.session_state:
                st.session_state.trace_new_param = 0.0

            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("Task Name", key="trace_new_name")
            with c2:
                st.number_input(
                    "TACT (mins)",
                    min_value=0.0,
                    step=0.5,
                    key="trace_new_tact"
                )
            with c3:
                st.number_input(
                    "Parameter",
                    min_value=0.0,
                    step=1.0,
                    key="trace_new_param"
                )

            if st.button("Add Trace Agent Task"):
                name = st.session_state.trace_new_name.strip()
                if name:
                    st.session_state.trace_custom_tasks.append({
                        "id": f"trace_custom_{len(st.session_state.trace_custom_tasks)}",
                        "name": name,
                        "tact": st.session_state.trace_new_tact,
                        "param": st.session_state.trace_new_param
                    })
                    st.rerun()

        # Display total time outside expander
        trace_hours_display = total_trace_time / 60
        trace_agents_display = trace_hours_display / 9
        # Info banner removed to declutter UI

    # ==================================================
    # SHARP TIME CALCULATIONS & SUMMARY (Uses actual expander-calculated times)
    # ==================================================
    if st.session_state.calculate_clicked:
        import math

        # Section header
        st.markdown("""
        <div style="
            background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
            border-left: 6px solid #DE002E;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 0.5rem 0 0.5rem 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        ">
            <div style="font-weight:700;color:#333333;font-size:16px;">📊 OSA Requirements & Summary</div>
        </div>
        """, unsafe_allow_html=True)

        # Get actual calculated times from session state
        total_osa_time = st.session_state.calculated_osa_time
        total_lasa_time = st.session_state.calculated_lasa_time
        total_dispatcher_time = st.session_state.calculated_dispatcher_time
        total_trace_time = st.session_state.calculated_trace_time

        # ---- Convert minutes → hours ----
        osa_hrs = total_osa_time / 60
        lasa_hrs = total_lasa_time / 60
        dispatcher_hrs = total_dispatcher_time / 60
        trace_hrs = total_trace_time / 60

        # ---- Agent WITHOUT SHARP (Base HC) ----
        osa_base = osa_hrs / shift_hours
        lasa_base = lasa_hrs / shift_hours
        dispatcher_base = dispatcher_hrs / shift_hours
        trace_base = trace_hrs / shift_hours

        # ---- SHARP time ----
        osa_sharp = math.ceil(osa_base) * 0.25
        lasa_sharp = math.ceil(lasa_base) * 0.25
        dispatcher_sharp = math.ceil(dispatcher_base) * 0.25
        trace_sharp = math.ceil(trace_base) * 0.25

        # ---- Total time INCLUDING SHARP ----
        osa_total_with_sharp = osa_hrs + osa_sharp
        lasa_total_with_sharp = lasa_hrs + lasa_sharp
        dispatcher_total_with_sharp = dispatcher_hrs + dispatcher_sharp
        trace_total_with_sharp = trace_hrs + trace_sharp

        # ---- Agent total (WITHOUT absenteeism) ----
        osa_agent_total = osa_total_with_sharp / shift_hours
        lasa_agent_total = lasa_total_with_sharp / shift_hours
        dispatcher_agent_total = dispatcher_total_with_sharp / shift_hours
        trace_agent_total = trace_total_with_sharp / shift_hours

        # ---- Facility Model Adjustments ----
        from aero.core.resource_calculator import get_model_adjustments
        model_adj = get_model_adjustments(total)
        osa_agent_total *= model_adj['osa']
        lasa_agent_total *= model_adj['lasa']
        dispatcher_agent_total *= model_adj['dispatcher']

        # Display model adjustment info if applicable
        if model_adj['model'] in ('C', 'D'):
            _osa_label = f"+{int((model_adj['osa'] - 1) * 100)}%" if model_adj['osa'] > 1 else "No change"
            _lasa_label = f"-{int((1 - model_adj['lasa']) * 100)}%" if model_adj['lasa'] < 1 else "No change"
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg,#FFFFFF 0%, #FFF6E8 100%);
                border-left: 6px solid #FF6200;
                border-radius: 8px;
                padding: 10px 16px;
                margin-bottom: 12px;
            ">
                <div style="font-weight:700;color:#333333;font-size:14px;">📊 Facility Model {model_adj['model']} Adjustments Applied</div>
                <div style="color:#565656;font-size:12px;margin-top:4px;">
                    OSA: {_osa_label} &nbsp;|&nbsp; LASA: {_lasa_label} &nbsp;|&nbsp; Dispatcher: {_lasa_label}
                </div>
            </div>
            """, unsafe_allow_html=True)

        sharp_df = pd.DataFrame({
            "Role": ["OSA", "LASA", "Dispatcher", "Trace Agent"],
            "Total Time (Minutes)": [
                round(total_osa_time, 2),
                round(total_lasa_time, 2),
                round(total_dispatcher_time, 2),
                round(total_trace_time, 2)
            ],
            "Time Taken (Hours)": [
                round(osa_hrs, 2),
                round(lasa_hrs, 2),
                round(dispatcher_hrs, 2),
                round(trace_hrs, 2)
            ],
            "Agent Without SHARP (Hrs)": [
                round(osa_base, 2),
                round(lasa_base, 2),
                round(dispatcher_base, 2),
                round(trace_base, 2)
            ],
            "SHARP Time (Hrs)": [
                round(osa_sharp, 2),
                round(lasa_sharp, 2),
                round(dispatcher_sharp, 2),
                round(trace_sharp, 2)
            ],
            "Total Time incl SHARP (Hrs)": [
                round(osa_total_with_sharp, 2),
                round(lasa_total_with_sharp, 2),
                round(dispatcher_total_with_sharp, 2),
                round(trace_total_with_sharp, 2)
            ],
            "Agent Total (Without Absenteeism)": [
                round(osa_agent_total, 2),
                round(lasa_agent_total, 2),
                round(dispatcher_agent_total, 2),
                round(trace_agent_total, 2)
            ]
        })

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.dataframe(sharp_df, hide_index=True, width="stretch")

        # Final Agent Requirement
        # Use model-adjusted agent totals (osa/lasa/dispatcher already multiplied above)
        total_time_all_agents_with_sharp = (
            osa_total_with_sharp
            + lasa_total_with_sharp
            + dispatcher_total_with_sharp
            + trace_total_with_sharp
        )

        agent_required_base = (
            osa_agent_total
            + lasa_agent_total
            + dispatcher_agent_total
            + trace_agent_total
        )
        agent_required_with_abs = agent_required_base * (1 + absenteeism_pct)

        # Final Agent Requirement header removed to declutter UI

        # Output cards row 1 - Time and calculation metrics (include Team Lead & Manager)
        card_col1, card_col2, card_col3, card_col4, card_col5, card_col6 = st.columns(6)

        # Base agent required is the sum of agent totals (without absenteeism)
        base_agents_required = agent_required_base
        # Compute values based off the global base
        # Use the user-provided Absenteeism(Regular) input (absenteeism_pct) to compute additional agents
        absenteeism_additional = base_agents_required * absenteeism_pct
        roster_additional = base_agents_required * roster_buffer_pct

        # Final agents total is the sum of Base + Absenteeism (post-calc 16%) + Roster Buffer additional
        final_agents_total = base_agents_required + absenteeism_additional + roster_additional

        with card_col1:
            st.markdown(f"""
            <div class="hm-card">
                <div class="hm-title">Total Time (incl SHARP)</div>
                <div class="hm-value">{round(total_time_all_agents_with_sharp, 2)}<span style="font-size:12px; font-weight:500; color:#565656;"> hrs</span></div>
            </div>
            """, unsafe_allow_html=True)

        with card_col2:
            st.markdown(f"""
            <div class="hm-card">
                <div class="hm-title">Base Agents Required</div>
                <div class="hm-value">{base_agents_required:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        with card_col3:
            st.markdown(f"""
            <div class="hm-card">
                <div class="hm-title">ABSENTEEISM (Regular)</div>
                <div class="hm-value">{round(absenteeism_additional, 2)}</div>
            </div>
            """, unsafe_allow_html=True)

        with card_col4:
            st.markdown(f"""
            <div class="hm-card">
                <div class="hm-title">ROSTER BUFFER (5-days) Additional</div>
                <div class="hm-value">{round(roster_additional,2)}</div>
            </div>
            """, unsafe_allow_html=True)
        # Team Lead card (match structure of other cards)
        with card_col5:
            st.markdown(f"""
            <div class="hm-card">
                <div class="hm-title">Team Lead</div>
                <div class="hm-value" style="color:#4D148C;">1</div>
            </div>
            """, unsafe_allow_html=True)
        # Manager card (match structure of other cards)
        with card_col6:
            st.markdown(f"""
            <div class="hm-card">
                <div class="hm-title">Manager</div>
                <div class="hm-value" style="color:#4D148C;">1</div>
            </div>
            """, unsafe_allow_html=True)

        # Main highlight card - Final Agents Required
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #4D148C 0%, #671CAA 100%);
            border-radius: 16px;
            padding: 1.5rem 2rem;
            margin: 1rem 0;
            box-shadow: 0 6px 20px rgba(77,20,140,0.3);
            text-align: center;
        ">
            <div style="color: rgba(255,255,255,0.9); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
                Final OSA's Required
            </div>
                <div style="color: #FF6200; font-size: 48px; font-weight: 800; font-family: 'DM Sans', sans-serif;">
                    {math.ceil(final_agents_total)}
                </div>
        </div>
        """, unsafe_allow_html=True)

