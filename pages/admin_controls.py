import streamlit as st
import pandas as pd
import json
import os

# ==================================================
# CONFIG (centralized — reads/writes app/config/ so services always see edits)
# ==================================================
from aero.config.settings import (
    load_config,
    save_config,
    load_area_config,
    save_area_config,
)

cfg = load_config()

# ✅ ADD THESE LINES
osa = cfg.setdefault("OSA", {})
lasa = cfg.setdefault("LASA", {})
dispatcher = cfg.setdefault("DISPATCHER", {})
trace_agent = cfg.setdefault("TRACE_AGENT", {})

# ==================================================
# SESSION STATE
# ==================================================
from aero.ui.header import render_header

# Apply styles (page config handled by HOME.py via st.navigation)

# Shared compact header (logo + title)
render_header("ADMIN CONFIGURATION", "Manage system parameters and constants", logo_height=80)

# ==================================================
# ADMIN PAGE
# ==================================================

# Page header is provided by shared top header

# ==================================================
# HELPER (OSA – FIXED)
# ==================================================
def num(label, key, default, step=0.1, minv=None, maxv=None):
    cfg["OSA"][key] = st.number_input(
        label,
        value=float(cfg["OSA"].get(key, default)),
        step=float(step),
        min_value=minv,
        max_value=maxv,
        key=f"osa_{key}" 
    )
# ==================================================
# AREA CONFIG HEADER
# ==================================================

st.markdown("""
<div class="table-header-box">📐 Area Configuration</div>
""", unsafe_allow_html=True)

# ==================================================
# AREA – ADMIN CONTROLS 
# ==================================================
# Load Area config
area_cfg = load_area_config()
area_constants = area_cfg.setdefault("AREA_CONSTANTS", {})

with st.expander("AREA – Facility Planner Constants", expanded=False):

    st.subheader("Area Planner Backend Assumptions")

    area_constants["PALLET_AREA"] = st.number_input(
        "Pallet Area (sq.ft per pallet)",
        value=float(area_constants.get("PALLET_AREA", 16)),
        step=1.0,
        key="admin_area_pallet_area"
    )

    area_constants["AISLE_PERCENT"] = st.number_input(
        "Aisle Percentage",
        value=float(area_constants.get("AISLE_PERCENT", 0.15)),
        step=0.01,
        min_value=0.0,
        max_value=0.5,
        key="admin_area_aisle_percent"
    )

    area_constants["CAGE_PALLET_AREA"] = st.number_input(
        "Cage Pallet Area (sq.ft)",
        value=float(area_constants.get("CAGE_PALLET_AREA", 25)),
        step=1.0,
        key="admin_area_cage_pallet_area"
    )

    area_constants["STACKING_PER_PALLET"] = st.number_input(
        "Vertical Stacking Factor (pallets)",
        value=int(area_constants.get("STACKING_PER_PALLET", 20)),
        step=1,
        key="admin_area_stacking_per_pallet"
    )

# ==================================================
# AGENT CONFIG HEADER
# ==================================================

st.markdown("""
<div class="table-header-box">👥 Agent Configuration</div>
""", unsafe_allow_html=True)

# ==================================================
# OSA EXPANDER (28 TASKS)
# ==================================================
with st.expander("OSA – Operational Support Assistant", expanded=False):

    st.subheader("Core Scanning")
    num("1. IB / OB Scan TACT", "IB_OB_SCAN_TACT", 0.12, 0.01)
    num("3. Compliance Report TACT", "COMPLIANCE_TACT", 5, 1)
    osa["COMPLIANCE_FIXED_COUNT"] = st.number_input(
        "3. Compliance Fixed Count",
        value=int(osa.get("COMPLIANCE_FIXED_COUNT", 2)),
        step=1,
        key="COMPLIANCE_FIXED_COUNT"
    )

    st.divider()

    st.subheader("Exception & Reporting")
    num("2. Damage Scan TACT", "DAMAGE_SCAN_TACT", 3, 0.5)
    num("2. Damage % of IB", "DAMAGE_SCAN_PCT_IB", 0.005, 0.001, 0.0, 1.0)

    num("4. ROD & BOE TACT", "ROD_BOE_TACT", 1, 0.5)
    num("4. ROD % of IB", "ROD_BOE_PCT_IB", 0.30, 0.05, 0.0, 1.0)

    num("5. Queries Handling TACT", "EMAIL_QUERY_TACT", 1.5, 0.5)
    num("5. Queries % of IB", "EMAIL_QUERY_PCT_IB", 0.15, 0.05, 0.0, 1.0)

    num("6. NEXT App Actioning TACT", "NEXT_APP_ACTION_TACT", 4, 1)
    num("6. NEXT App % of IB", "NEXT_APP_ACTION_PCT_IB", 0.015, 0.005, 0.0, 1.0)

    num("7. Courier On-Call TACT", "COURIER_ONCALL_TACT", 4, 1)
    num("7. Courier % of Total", "COURIER_ONCALL_PCT_TOTAL", 0.05, 0.01, 0.0, 1.0)

    num("8. Incomplete MPS TACT", "INCOMPLETE_MPS_TACT", 0.12, 0.01)
    num("8. Incomplete % of IB", "INCOMPLETE_MPS_PCT_IB", 0.40, 0.05, 0.0, 1.0)

    num("9. Incomplete Report TACT", "INCOMPLETE_REPORT_TACT", 20, 1)
    osa["INCOMPLETE_REPORT_COUNT"] = st.number_input(
        "9. Incomplete Report Count",
        value=int(osa.get("INCOMPLETE_REPORT_COUNT", 1)),
        step=1,
        key="INCOMPLETE_REPORT_COUNT"
    )

    st.divider()

    st.subheader("Monitoring")
    num("10. Cage Monitoring TACT", "CAGE_MONITORING_TACT", 2, 0.5)
    num("10. Cage % of IB", "CAGE_MONITORING_PCT_IB", 0.10, 0.05, 0.0, 1.0)

    num("11. DEX Monitoring TACT", "DEX_MONITORING_TACT", 1.2, 0.1)
    num("13. DEX Handling TACT", "DEX_HANDLING_TACT", 4, 1)

    num("12. ROC Activities TACT", "ROC_ACTIVITIES_TACT", 6, 1)
    num("23. ROC TACT", "ROC_TACT", 5, 1)

    st.divider()

    st.subheader("Outbound Ops")
    num("14. Pickup Shipment Handover TACT", "PICKUP_HANDOVER_TACT", 0.25, 0.05)
    num("16. OB Scan & Load TACT", "OB_SCAN_LOAD_TACT", 0.1, 0.01)
    num("17. IPHP Pre-alert TACT", "IPHP_PREALERT_TACT", 0.2, 0.05)
    num("18. IPHP Checking TACT", "IPHP_CHECKING_TACT", 15, 1)
    num("24. REX Application TACT", "REX_APPLICATION_TACT", 0.2, 0.05)
    num("25. PPWK Imaging TACT", "PPWK_IMAGING_TACT", 0.1, 0.01)
    num("22. ASP Handling TACT", "ASP_HANDLING_TACT", 0.5, 0.1)

    st.divider()

    st.subheader("Fixed / Admin Tasks")
    num("15. FAMIS Report TACT", "FAMIS_TACT", 30, 1)
    num("19. InControl OB Report TACT", "INCONTROL_OB_TACT", 20, 1)
    num("20. EGNSL Failure TACT", "EGNSL_TACT", 15, 1)
    num("21. PAR Report TACT", "PAR_TACT", 10, 1)
    num("26. Gatekeeper IB & OB TACT", "GATEKEEPER_TACT", 30, 1)
    num("27. KYC TACT", "KYC_TACT", 2, 0.5)
    num("27. KYC % of IB", "KYC_PCT_IB", 0.02, 0.01, 0.0, 1.0)
    num("28. Station Open/Close TACT", "STATION_OPEN_CLOSE_TACT", 10, 1)

# ==================================================
# LASA ADMIN CONTROLS
# ==================================================
with st.expander("LASA – Admin Controls", expanded=False):

    if "LASA" not in cfg:
        cfg["LASA"] = {}

    st.subheader("LASA Task Assumptions")

    cfg["LASA"]["MAILING_ROD_BOE_TACT"] = st.number_input(
        "Mailing ROD Invoice & BOE Copy – TACT (mins)",
        value=float(cfg["LASA"].get("MAILING_ROD_BOE_TACT", 1)),
        step=0.1,
        key="lasa_mailing_rod_boe_tact"
    )
    cfg["LASA"]["BANKING_ACTIVITIES_TACT"] = st.number_input(
    "Banking Activities – TACT (mins)",
    value=float(cfg["LASA"].get("BANKING_ACTIVITIES_TACT", 15)),
    step=1.0,
    key="lasa_banking_activities_tact"
)
    cfg["LASA"]["AR_OR_FILE_REVIEW_TACT"] = st.number_input(
    "Review of AR / OR File Closure – TACT (mins)",
    value=float(cfg["LASA"].get("AR_OR_FILE_REVIEW_TACT", 1.5)),
    step=0.1,
    key="lasa_ar_or_file_review_tact"
)
    cfg["LASA"]["CHECK_EMAILS_CUSTOMER_QUERIES_TACT"] = st.number_input(
    "Checking Emails & Customer Queries – TACT (mins)",
    value=float(cfg["LASA"].get("CHECK_EMAILS_CUSTOMER_QUERIES_TACT", 1.0)),
    step=0.5,
    key="lasa_check_emails_queries_tact"
)
    cfg["LASA"]["GCCS_CLOSURE_TACT"] = st.number_input(
    "Closure of GCCS for Open Cases – TACT (mins)",
    value=float(cfg["LASA"].get("GCCS_CLOSURE_TACT", 1.0)),
    step=0.5,
    key="lasa_gccs_closure_tact"
)
    cfg["LASA"]["INVOICE_PAYMENT_REVIEW_TACT"] = st.number_input(
    "Review of Invoice Payment – TACT (mins)",
    value=float(cfg["LASA"].get("INVOICE_PAYMENT_REVIEW_TACT", 15.0)),
    step=1.0,
    key="lasa_invoice_payment_review_tact"
)
    cfg["LASA"]["PREPARING_VENDOR_INVOICE_TACT"] = st.number_input(
    "Preparing Vendor Invoice – TACT (mins)",
    value=float(cfg["LASA"].get("PREPARING_VENDOR_INVOICE_TACT", 30.0)),
    step=5.0,
    key="lasa_preparing_vendor_invoice_tact"
)
    cfg["LASA"]["PO_UTILITIES_MAINTENANCE_TACT"] = st.number_input(
    "Raising PO for Utilities & Maintenance – TACT (mins)",
    value=float(cfg["LASA"].get("PO_UTILITIES_MAINTENANCE_TACT", 10.0)),
    step=1.0,
    key="lasa_po_utilities_maintenance_tact"
)
    cfg["LASA"]["PROVISION_FILE_SUBMISSION_TACT"] = st.number_input(
    "Provision File Submission to Manager – TACT (mins)",
    value=float(cfg["LASA"].get("PROVISION_FILE_SUBMISSION_TACT", 5.0)),
    step=1.0,
    key="lasa_provision_file_submission_tact"
)
    cfg["LASA"]["AGREEMENT_DRAFT_TACT"] = st.number_input(
    "Preparing Agreement Draft – TACT (mins)",
    value=float(cfg["LASA"].get("AGREEMENT_DRAFT_TACT", 5.0)),
    step=1.0,
    key="lasa_agreement_draft_tact"
)
    cfg["LASA"]["EOD_CLOSURE_TACT"] = st.number_input(
    "EOD Closure, Tallying and Check – TACT (mins)",
    value=float(cfg["LASA"].get("EOD_CLOSURE_TACT", 25.0)),
    step=1.0,
    key="lasa_eod_closure_tact"
)
    cfg["LASA"]["OTHER_ACTIVITIES_TACT"] = st.number_input(
    "Other Activities – TACT (mins)",
    value=float(cfg["LASA"].get("OTHER_ACTIVITIES_TACT", 20.0)),
    step=1.0,
    key="lasa_other_activities_tact"
)

# ==================================================
# DISPATCHER – ADMIN CONTROLS (FIXED & GROUPED)
# ==================================================
with st.expander("DISPATCHER – Admin Controls", expanded=False):

    st.subheader("Dispatcher Task Assumptions")

    dispatcher["PUSH_DISPATCH_TACT"] = st.number_input(
        "Push Dispatch to Couriers as per Route – TACT (mins)",
        value=float(dispatcher.get("PUSH_DISPATCH_TACT", 1.5)),
        step=0.1,
        key="dispatcher_push_dispatch_tact"
    )

    dispatcher["LIVE_DEX_MONITORING_TACT"] = st.number_input(
        "Monitoring of Live DEX – TACT (mins)",
        value=float(dispatcher.get("LIVE_DEX_MONITORING_TACT", 0.5)),
        step=0.1,
        key="dispatcher_live_dex_tact"
    )

    dispatcher["GDP_SIMS_MONITORING_TACT"] = st.number_input(
        "Monitoring GDP SIMs – TACT (mins)",
        value=float(dispatcher.get("GDP_SIMS_MONITORING_TACT", 10)),
        step=1.0,
        key="dispatcher_gdp_sims_tact"
    )

    dispatcher["EDI_CASH_BCN_PICKUP_TACT"] = st.number_input(
        "EDI Updation of Cash and BCN Pickup – TACT (mins)",
        value=float(dispatcher.get("EDI_CASH_BCN_PICKUP_TACT", 0.5)),
        step=0.1,
        key="dispatcher_edi_cash_bcn_tact"
    )

    dispatcher["EMAIL_QUERY_HANDLING_TACT"] = st.number_input(
        "Checking Emails & Responding to Queries – TACT (mins)",
        value=float(dispatcher.get("EMAIL_QUERY_HANDLING_TACT", 2)),
        step=0.5,
        key="dispatcher_email_query_tact"
    )

    dispatcher["CUSTOMER_COORDINATION_TACT"] = st.number_input(
        "Coordinating with Customers – TACT (mins)",
        value=float(dispatcher.get("CUSTOMER_COORDINATION_TACT", 1)),
        step=0.5,
        key="dispatcher_customer_coord_tact"
    )

    dispatcher["EICS_ACCOUNT_STATUS_CHECK_TACT"] = st.number_input(
        "Check Account Status in e-ICS – TACT (mins)",
        value=float(dispatcher.get("EICS_ACCOUNT_STATUS_CHECK_TACT", 5)),
        step=1.0,
        key="dispatcher_eics_status_tact"
    )

    dispatcher["FRAUD_ACCOUNT_MISUSE_TACT"] = st.number_input(
        "Fraudulent Account Misuse – TACT (mins)",
        value=float(dispatcher.get("FRAUD_ACCOUNT_MISUSE_TACT", 5)),
        step=1.0,
        key="dispatcher_fraud_misuse_tact"
    )

    dispatcher["CLOSE_DISPATCH_EOD_TACT"] = st.number_input(
        "Closing Dispatch & EOD Business – TACT (mins)",
        value=float(dispatcher.get("CLOSE_DISPATCH_EOD_TACT", 0.5)),
        step=0.1,
        key="dispatcher_close_dispatch_eod_tact"
    )

# ==================================================
# TRACE AGENT – ADMIN CONTROLS (UPDATED)
# ==================================================
trace_agent = cfg.setdefault("TRACE_AGENT", {})

with st.expander("TRACE AGENT – Admin Controls", expanded=False):

    st.subheader("Trace Agent Task Assumptions")

    trace_agent["CUSTOMER_CALL_REATTEMPT_TACT"] = st.number_input(
        "Calling Customer & Informing Courier for Reattempt – TACT (mins)",
        value=float(trace_agent.get("CUSTOMER_CALL_REATTEMPT_TACT", 2)),
        step=0.5,
        key="trace_agent_call_reattempt_tact"
    )

    trace_agent["CAGE_AGEING_TACT"] = st.number_input(
        "Work on Cage Ageing Shipment – TACT (mins)",
        value=float(trace_agent.get("CAGE_AGEING_TACT", 3)),
        step=0.5,
        key="trace_agent_cage_ageing_tact"
    )

    trace_agent["CUSTOMER_COORD_SALES_TACT"] = st.number_input(
        "Coordinating with Customers & Sales Team – TACT (mins)",
        value=float(trace_agent.get("CUSTOMER_COORD_SALES_TACT", 2)),
        step=0.5,
        key="trace_agent_customer_sales_coord_tact"
    )

    trace_agent["CMOD_WORK_TACT"] = st.number_input(
        "Work on CMOD – TACT (mins)",
        value=float(trace_agent.get("CMOD_WORK_TACT", 2)),
        step=0.5,
        key="trace_agent_cmod_work_tact"
    )

    trace_agent["ASSESS_OPEN_CASES_TACT"] = st.number_input(
        "Assess Open Cases & Work on Closure – TACT (mins)",
        value=float(trace_agent.get("ASSESS_OPEN_CASES_TACT", 3)),
        step=0.5,
        key="trace_agent_assess_open_cases_tact"
    )

    trace_agent["REOPEN_CASE_TACT"] = st.number_input(
        "Reopen Case if Issue Not Resolved – TACT (mins)",
        value=float(trace_agent.get("REOPEN_CASE_TACT", 20)),
        step=1.0,
        key="trace_agent_reopen_case_tact"
    )

    trace_agent["CMOD_REPORT_MONITORING_TACT"] = st.number_input(
        "CMOD Report Monitoring & Closure – TACT (mins)",
        value=float(trace_agent.get("CMOD_REPORT_MONITORING_TACT", 20)),
        step=1.0,
        key="trace_agent_cmod_report_monitoring_tact"
    )

# ==================================================
# COURIER CONFIG HEADER
# ==================================================

st.markdown("""
<div class="table-header-box">📦 Courier Configuration</div>
""", unsafe_allow_html=True)

with st.expander("COURIER – Admin Controls", expanded=False):

    if "COURIER" not in cfg:
        cfg["COURIER"] = {}

    courier_cfg = cfg.setdefault("COURIER", {})

    courier_cfg["COURIER_CAPACITY"] = st.number_input(
        "Courier Capacity (packages per courier)",
        value=int(courier_cfg.get("COURIER_CAPACITY", 250)),
        min_value=1,
        step=1,
        key="admin_courier_capacity"
    )

    courier_cfg["STANDARD_PRODUCTIVITY"] = st.number_input(
        "Standard Productivity (packages per courier reference)",
        value=int(courier_cfg.get("STANDARD_PRODUCTIVITY", 45)),
        min_value=1,
        step=1,
        key="admin_courier_standard_prod"
    )

    # Mirror courier on-call settings into COURIER group if present under OSA
    courier_cfg["COURIER_ONCALL_TACT"] = cfg.setdefault("OSA", {}).get("COURIER_ONCALL_TACT", courier_cfg.get("COURIER_ONCALL_TACT", 4))
    courier_cfg["COURIER_ONCALL_PCT_TOTAL"] = cfg.setdefault("OSA", {}).get("COURIER_ONCALL_PCT_TOTAL", courier_cfg.get("COURIER_ONCALL_PCT_TOTAL", 0.05))

# ==================================================
# SAVE
# ==================================================
if st.button("💾 Save Changes"):
    save_config(cfg)
    save_area_config(area_cfg)


# ==================================================
# USER MANAGEMENT
# ==================================================
st.markdown("---")
with st.expander("User Management — Create or Update User Accounts", expanded=False):
    from aero.auth.service import upsert_user as _upsert_user, list_users as _list_users, VALID_ROLES as _VALID_ROLES

    st.markdown("Use this form to create a new user or update the password / role of an existing user.")

    um_c1, um_c2 = st.columns(2)
    with um_c1:
        um_uid  = st.text_input("User ID (login name)", key="um_user_id")
        um_role = st.selectbox("Role", sorted(_VALID_ROLES), key="um_role")
    with um_c2:
        um_pwd  = st.text_input("Password", type="password", key="um_password")
        um_name = st.text_input("Display Name (optional)", key="um_display_name")

    if st.button("Create / Update User", key="um_submit_btn"):
        if um_uid and um_pwd:
            ok, msg = _upsert_user(um_uid, um_pwd, um_role, um_name)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        else:
            st.warning("User ID and Password are both required.")

    st.markdown("##### Current Users")
    _df_users = _list_users()
    if _df_users.empty:
        st.info("No users found.")
    else:
        st.dataframe(_df_users, use_container_width=True, hide_index=True)


# ---------------- LOGOUT BUTTON ----------------
col_c, col_btn = st.columns([8, 1])
with col_btn:
    if st.button("🚪 Logout", key="admin_logout_btn"):
        st.session_state.admin_logged_in = False
        st.rerun()