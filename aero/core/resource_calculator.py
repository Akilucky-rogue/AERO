"""
resource_calculator.py — Resource (staffing) requirement calculations.

Computes time and agent requirements for OSA, LASA, Dispatcher, and Trace
roles using TACT values, SHARP adjustments, and facility model multipliers.
"""

import math

from aero.config.settings import load_config

_CONFIG = load_config()
OSA_CONFIG = _CONFIG.get("OSA", {})
LASA_CONFIG = _CONFIG.get("LASA", {})
DISPATCHER_CONFIG = _CONFIG.get("DISPATCHER", {})
TRACE_AGENT_CONFIG = _CONFIG.get("TRACE_AGENT", {})


# ============================================================
# INDIVIDUAL ROLE TIME CALCULATIONS
# ============================================================

def calculate_osa_time(
    total_volume,
    ib_volume,
    ob_volume,
    roc_volume,
    asp_volume,
    dex_pct=0.05,
    csbiv_pct=0.80,
    rod_pct=0.30,
    excluded_tasks=None,
    custom_tasks=None,
):
    if excluded_tasks is None:
        excluded_tasks = set()
    if custom_tasks is None:
        custom_tasks = []

    osa = OSA_CONFIG
    total_time = 0.0

    tasks = [
        ("IB / OB Scan", osa.get("IB_OB_SCAN_TACT", 0.12), total_volume, "TACT * Gross Total Volume"),
        ("Damage Scan & Reporting", osa.get("DAMAGE_SCAN_TACT", 3), ib_volume * osa.get("DAMAGE_SCAN_PCT_IB", 0.005), "TACT*(0.5% * IB Volume)"),
        ("Compliance Report", osa.get("COMPLIANCE_TACT", 5), osa.get("COMPLIANCE_FIXED_COUNT", 2), "TACT * Fixed Count(2)"),
        ("ROD Invoice & BOE", osa.get("ROD_BOE_TACT", 1), ib_volume * rod_pct, "TACT * (ROD%*IB)"),
        ("Queries Handling Emails", osa.get("EMAIL_QUERY_TACT", 1.5), ib_volume * osa.get("EMAIL_QUERY_PCT_IB", 0.15), "TACT * (15% * IB Volume)"),
        ("NEXT App Actioning", osa.get("NEXT_APP_ACTION_TACT", 4), ib_volume * osa.get("NEXT_APP_ACTION_PCT_IB", 0.015), "TACT * (1.5% * IB Volume)"),
        ("Courier On-Call Support", osa.get("COURIER_ONCALL_TACT", 4), total_volume * osa.get("COURIER_ONCALL_PCT_TOTAL", 0.05), "TACT * (5% * Total Volume)"),
        ("Incomplete MPS / Holiday", osa.get("INCOMPLETE_MPS_TACT", 0.12), ib_volume * osa.get("INCOMPLETE_MPS_PCT_IB", 0.40), "TACT * (40% * IB Volume)"),
        ("Incomplete Report", osa.get("INCOMPLETE_REPORT_TACT", 20), osa.get("INCOMPLETE_REPORT_COUNT", 1), "TACT * Fixed Count(1)"),
        ("Cage Monitoring", osa.get("CAGE_MONITORING_TACT", 2), ib_volume * osa.get("CAGE_MONITORING_PCT_IB", 0.10), "TACT * (10% * IB volume)"),
        ("DEX Monitoring", osa.get("DEX_MONITORING_TACT", 1.2), ib_volume * dex_pct, "TACT * DEX % of IB Volume"),
        ("ROC Activities", osa.get("ROC_ACTIVITIES_TACT", 6), roc_volume, "TACT * ROC Volume"),
        ("DEX Handling", osa.get("DEX_HANDLING_TACT", 4), ib_volume * dex_pct, "TACT * DEX % of IB Volume"),
        ("Pickup Shipment Handover", osa.get("PICKUP_HANDOVER_TACT", 0.25), ob_volume - asp_volume, "TACT * (OB - ASP Volume)"),
        ("FAMIS Report", osa.get("FAMIS_TACT", 30), 1, "TACT * Fixed Count(1)"),
        ("Outbound Scan & Load", osa.get("OB_SCAN_LOAD_TACT", 0.1), ob_volume, "TACT * OB Volume"),
        ("IPHP Pre-alert", osa.get("IPHP_PREALERT_TACT", 0.2), csbiv_pct * ob_volume, "TACT * (CSBIV% * OB Volume)"),
        ("IPHP Checking", osa.get("IPHP_CHECKING_TACT", 15), 1, "TACT * Fixed Count(1)"),
        ("InControl Report OB", osa.get("INCONTROL_OB_TACT", 20), 1, "TACT * Fixed Count(1)"),
        ("EGNSL Failure", osa.get("EGNSL_TACT", 15), 1, "TACT * Fixed Count(1)"),
        ("PAR Report", osa.get("PAR_TACT", 10), 1, "TACT * Fixed Count(1)"),
        ("ASP Handling", osa.get("ASP_HANDLING_TACT", 0.5), asp_volume, "TACT * ASP Volume"),
        ("ROC (Manpower)", osa.get("ROC_TACT", 5), roc_volume, "TACT * ROC Volume"),
        ("REX Application", osa.get("REX_APPLICATION_TACT", 0.2), 0.9 * ob_volume, "TACT * (0.9 * OB Volume)"),
        ("PPWK Imaging", osa.get("PPWK_IMAGING_TACT", 0.1), 0.8 * ob_volume, "TACT * (0.8 * OB Volume)"),
        ("Gatekeeper IB & OB", osa.get("GATEKEEPER_TACT", 30), 1, "TACT * Fixed Count(1)"),
        ("KYC", osa.get("KYC_TACT", 2), ib_volume * osa.get("KYC_PCT_IB", 0.02), "TACT * (2% * IB)"),
        ("Station Opening & Closing", osa.get("STATION_OPEN_CLOSE_TACT", 10), 1, "TACT * Fixed Count(1)"),
    ]

    for task_name, tact, param, formula in tasks:
        if task_name not in excluded_tasks:
            total_time += tact * param

    for task in custom_tasks:
        if task.get("id") not in excluded_tasks:
            total_time += task.get("tact", 0) * task.get("param", 0)

    return total_time


def calculate_lasa_time(
    ib_volume,
    ob_volume,
    asp_volume,
    rod_pct=0.30,
    excluded_tasks=None,
    custom_tasks=None,
):
    if excluded_tasks is None:
        excluded_tasks = set()
    if custom_tasks is None:
        custom_tasks = []

    lasa = LASA_CONFIG
    total_time = 0.0

    tasks = [
        ("Mailing ROD Invoice & BOE Copy", lasa.get("MAILING_ROD_BOE_TACT", 1.0), ib_volume * rod_pct, "TACT * (ROD% * IB)"),
        ("Banking Activities", lasa.get("BANKING_ACTIVITIES_TACT", 15.0), 1, "TACT * 1"),
        ("Review of AR / OR File Closure", lasa.get("AR_OR_FILE_REVIEW_TACT", 1.5), ib_volume * 0.10, "TACT * (IB * 0.10)"),
        ("Checking Emails & Attending Customer Queries", lasa.get("CHECK_EMAILS_CUSTOMER_QUERIES_TACT", 1.0), (0.25 * ib_volume) + (0.02 * ob_volume), "TACT * ((0.25 * IB) + (0.02 * OB))"),
        ("Closure of GCCS for All Open Cases", lasa.get("GCCS_CLOSURE_TACT", 1.0), (0.25 * ib_volume) + (0.05 * (ob_volume - asp_volume)), "TACT * ((0.25 * IB) + (0.05 * (OB - ASP)))"),
        ("Review of Invoice Payment", lasa.get("INVOICE_PAYMENT_REVIEW_TACT", 15.0), 1, "TACT * 1"),
        ("Preparing Vendor Invoice", lasa.get("PREPARING_VENDOR_INVOICE_TACT", 30.0), 1, "TACT * 1"),
        ("Raising PO for Utilities & Maintenance", lasa.get("PO_UTILITIES_MAINTENANCE_TACT", 10.0), 1, "TACT * 1"),
        ("Provision File Submission to Manager", lasa.get("PROVISION_FILE_SUBMISSION_TACT", 5.0), 1, "TACT * 1"),
        ("Preparing Agreement Draft", lasa.get("AGREEMENT_DRAFT_TACT", 5.0), 1, "TACT * 1"),
        ("EOD Closure, Tallying and Check", lasa.get("EOD_CLOSURE_TACT", 25.0), 1, "TACT * 1"),
        ("Other Activities", lasa.get("OTHER_ACTIVITIES_TACT", 20.0), 1, "TACT * 1"),
    ]

    for task_name, tact, param, formula in tasks:
        if task_name not in excluded_tasks:
            total_time += tact * param

    for task in custom_tasks:
        if task.get("id") not in excluded_tasks:
            total_time += task.get("tact", 0) * task.get("param", 0)

    return total_time


def calculate_dispatcher_time(
    total_volume,
    ib_volume,
    ob_volume,
    asp_volume,
    on_call_pickup=80,
    dex_pct=0.05,
    excluded_tasks=None,
    custom_tasks=None,
):
    if excluded_tasks is None:
        excluded_tasks = set()
    if custom_tasks is None:
        custom_tasks = []

    dispatcher = DISPATCHER_CONFIG
    total_time = 0.0

    tasks = [
        ("Push Dispatch to Couriers as per Route", dispatcher.get("PUSH_DISPATCH_TACT", 1.5), on_call_pickup, "TACT * PUP"),
        ("Monitoring of Live DEX", dispatcher.get("LIVE_DEX_MONITORING_TACT", 0.5), dex_pct * ib_volume, "TACT * (DEX% * IB)"),
        ("Monitoring GDP SIMs", dispatcher.get("GDP_SIMS_MONITORING_TACT", 10), 1, "TACT * 1"),
        ("EDI Updation of Cash and BCN Pickup", dispatcher.get("EDI_CASH_BCN_PICKUP_TACT", 0.5), 0.20 * ob_volume, "TACT * (20% * OB)"),
        ("Checking Emails & Responding to Queries", dispatcher.get("EMAIL_QUERY_HANDLING_TACT", 2), 0.03 * total_volume, "TACT * (3% * Gross Total Volume)"),
        ("Coordinating with Customers", dispatcher.get("CUSTOMER_COORDINATION_TACT", 1), 0.15 * (ob_volume - asp_volume), "TACT * 15%(OB - ASP)"),
        ("Check Account Status in e-ICS", dispatcher.get("EICS_ACCOUNT_STATUS_CHECK_TACT", 5), 1, "TACT * Fixed Count"),
        ("Fraudulent Account Misuse", dispatcher.get("FRAUD_ACCOUNT_MISUSE_TACT", 5), 2, "TACT * Fixed Count"),
        ("Closing Dispatch and EOD Business", dispatcher.get("CLOSE_DISPATCH_EOD_TACT", 0.5), on_call_pickup, "TACT * PUP"),
    ]

    for task_name, tact, param, formula in tasks:
        if task_name not in excluded_tasks:
            total_time += tact * param

    for task in custom_tasks:
        if task.get("id") not in excluded_tasks:
            total_time += task.get("tact", 0) * task.get("param", 0)

    return total_time


def calculate_trace_time(
    total_volume,
    ob_volume,
    excluded_tasks=None,
    custom_tasks=None,
):
    if excluded_tasks is None:
        excluded_tasks = set()
    if custom_tasks is None:
        custom_tasks = []

    trace = TRACE_AGENT_CONFIG
    total_time = 0.0

    tasks = [
        ("Calling Customer & Informing Courier for Reattempt", trace.get("CUSTOMER_CALL_REATTEMPT_TACT", 2), 0.02 * total_volume, "TACT * (2% * Gross Total Volume)"),
        ("Work on Cage Ageing Shipment", trace.get("CAGE_AGEING_SHIPMENT_TACT", 3), 0.02 * total_volume, "TACT * (2% * Gross Total Volume)"),
        ("Coordinating with Customers and Sales Team", trace.get("CUSTOMER_SALES_COORDINATION_TACT", 2), 0.01 * ob_volume, "TACT * (1% * OB)"),
        ("Work on CMOD", trace.get("CMOD_WORK_TACT", 2), 0.02 * total_volume, "TACT * (2% * Gross Total Volume)"),
        ("Assess Open Cases and Work on Closure", trace.get("OPEN_CASES_CLOSURE_TACT", 3), 0.02 * total_volume, "TACT * (2% * Gross Total Volume)"),
        ("Reopen Case if Issue Not Resolved", trace.get("REOPEN_CASES_TACT", 20), 1, "TACT * Fixed Count"),
        ("CMOD Report Monitoring and Closure", trace.get("CMOD_REPORT_CLOSURE_TACT", 20), 1, "TACT * Fixed Count"),
    ]

    for task_name, tact, param, formula in tasks:
        if task_name not in excluded_tasks:
            total_time += tact * param

    for task in custom_tasks:
        if task.get("id") not in excluded_tasks:
            total_time += task.get("tact", 0) * task.get("param", 0)

    return total_time


# ============================================================
# FACILITY MODEL CLASSIFICATION & ADJUSTMENTS
# ============================================================

def get_model_adjustments(total_volume):
    """Return multipliers for OSA, LASA, and Dispatcher agent counts
    based on the facility model derived from Average Packages Per Day (APPD).
    """
    if total_volume <= 500:
        return {"model": "A", "osa": 1.0, "lasa": 1.0, "dispatcher": 1.0}
    elif total_volume <= 1500:
        return {"model": "B", "osa": 1.0, "lasa": 1.0, "dispatcher": 1.0}
    elif total_volume <= 3500:
        return {"model": "C", "osa": 1.10, "lasa": 0.50, "dispatcher": 0.50}
    else:
        return {"model": "D", "osa": 1.20, "lasa": 0.50, "dispatcher": 0.50}


# ============================================================
# MAIN RESOURCE REQUIREMENTS CALCULATION
# ============================================================

def calculate_resource_requirements(
    total_volume,
    ib_volume=0,
    ob_volume=0,
    roc_volume=0,
    asp_volume=0,
    shift_hours=9.0,
    absenteeism_pct=0.15,
    training_pct=0.0165,
    roster_buffer_pct=0.11,
    on_call_pickup=80,
    dex_pct=0.05,
    csbiv_pct=0.80,
    rod_pct=0.30,
    excluded_tasks=None,
    custom_tasks=None,
):
    if excluded_tasks is None:
        excluded_tasks = set()
    if custom_tasks is None:
        custom_tasks = []

    # 1. TIME CALCULATIONS
    osa_minutes = calculate_osa_time(
        total_volume, ib_volume, ob_volume, roc_volume, asp_volume,
        dex_pct, csbiv_pct, rod_pct, excluded_tasks, custom_tasks,
    )
    lasa_minutes = calculate_lasa_time(
        ib_volume, ob_volume, asp_volume, rod_pct, excluded_tasks, custom_tasks,
    )
    dispatcher_minutes = calculate_dispatcher_time(
        total_volume, ib_volume, ob_volume, asp_volume,
        on_call_pickup, dex_pct, excluded_tasks, custom_tasks,
    )
    trace_minutes = calculate_trace_time(
        total_volume, ob_volume, excluded_tasks, custom_tasks,
    )

    # 2. CONVERT TO HOURS
    osa_hours = osa_minutes / 60.0
    lasa_hours = lasa_minutes / 60.0
    dispatcher_hours = dispatcher_minutes / 60.0
    trace_hours = trace_minutes / 60.0

    # 3. BASE AGENTS (without SHARP)
    osa_agents = osa_hours / shift_hours if shift_hours > 0 else 0
    lasa_agents = lasa_hours / shift_hours if shift_hours > 0 else 0
    dispatcher_agents = dispatcher_hours / shift_hours if shift_hours > 0 else 0
    trace_agents = trace_hours / shift_hours if shift_hours > 0 else 0

    # 4. SHARP CALCULATION (per role)
    osa_sharp_hours = math.ceil(osa_agents) * 0.25
    lasa_sharp_hours = math.ceil(lasa_agents) * 0.25
    dispatcher_sharp_hours = math.ceil(dispatcher_agents) * 0.25
    trace_sharp_hours = math.ceil(trace_agents) * 0.25

    osa_total_with_sharp_hours = osa_hours + osa_sharp_hours
    lasa_total_with_sharp_hours = lasa_hours + lasa_sharp_hours
    dispatcher_total_with_sharp_hours = dispatcher_hours + dispatcher_sharp_hours
    trace_total_with_sharp_hours = trace_hours + trace_sharp_hours

    osa_agents_with_sharp = osa_total_with_sharp_hours / shift_hours if shift_hours > 0 else 0
    lasa_agents_with_sharp = lasa_total_with_sharp_hours / shift_hours if shift_hours > 0 else 0
    dispatcher_agents_with_sharp = dispatcher_total_with_sharp_hours / shift_hours if shift_hours > 0 else 0
    trace_agents_with_sharp = trace_total_with_sharp_hours / shift_hours if shift_hours > 0 else 0

    # 4.5 FACILITY MODEL ADJUSTMENTS
    model_adj = get_model_adjustments(total_volume)
    osa_agents_with_sharp *= model_adj["osa"]
    lasa_agents_with_sharp *= model_adj["lasa"]
    dispatcher_agents_with_sharp *= model_adj["dispatcher"]

    # 5. BASE TOTAL
    base_total_agents = (
        osa_agents_with_sharp + lasa_agents_with_sharp
        + dispatcher_agents_with_sharp + trace_agents_with_sharp
    )

    # 6. ABSENTEEISM
    absenteeism_additional = base_total_agents * absenteeism_pct

    # 7. ROSTER BUFFER
    roster_additional = base_total_agents * roster_buffer_pct

    # 8. FINAL TOTAL
    final_total_agents = base_total_agents + absenteeism_additional + roster_additional

    return {
        "osa_time_minutes": round(osa_minutes, 2),
        "lasa_time_minutes": round(lasa_minutes, 2),
        "dispatcher_time_minutes": round(dispatcher_minutes, 2),
        "trace_time_minutes": round(trace_minutes, 2),
        "osa_hours": round(osa_hours, 2),
        "lasa_hours": round(lasa_hours, 2),
        "dispatcher_hours": round(dispatcher_hours, 2),
        "trace_hours": round(trace_hours, 2),
        "osa_agents": round(osa_agents, 2),
        "lasa_agents": round(lasa_agents, 2),
        "dispatcher_agents": round(dispatcher_agents, 2),
        "trace_agents": round(trace_agents, 2),
        "osa_agents_with_sharp": round(osa_agents_with_sharp, 2),
        "lasa_agents_with_sharp": round(lasa_agents_with_sharp, 2),
        "dispatcher_agents_with_sharp": round(dispatcher_agents_with_sharp, 2),
        "trace_agents_with_sharp": round(trace_agents_with_sharp, 2),
        "base_agents": round(base_total_agents, 2),
        "absenteeism_additional": round(absenteeism_additional, 2),
        "roster_additional": round(roster_additional, 2),
        "total_agents": round(final_total_agents, 2),
    }


# Backward-compatible aliases — logic consolidated in health.py
from aero.core.health import calculate_health_status as calculate_resource_health_status  # noqa: E402
from aero.core.health import get_summary_stats as get_resource_summary_stats  # noqa: E402
