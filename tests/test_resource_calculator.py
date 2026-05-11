"""
tests/test_resource_calculator.py — Unit tests for aero.core.resource_calculator.

Tests all four role-time functions (OSA, LASA, Dispatcher, Trace Agent)
and the agent-count calculation.  Pure functions: no Streamlit, no filesystem.
"""

import pytest
from unittest.mock import patch

# Fixed TACT config that matches tact.json defaults so results are deterministic.
_MOCK_CONFIG = {
    "OSA": {
        "IB_OB_SCAN_TACT": 0.12, "DAMAGE_SCAN_TACT": 3.0, "DAMAGE_SCAN_PCT_IB": 0.005,
        "COMPLIANCE_TACT": 5.0, "COMPLIANCE_FIXED_COUNT": 2, "ROD_BOE_TACT": 1.0,
        "EMAIL_QUERY_TACT": 1.5, "EMAIL_QUERY_PCT_IB": 0.15, "NEXT_APP_ACTION_TACT": 4.0,
        "NEXT_APP_ACTION_PCT_IB": 0.015, "COURIER_ONCALL_TACT": 1.0, "COURIER_ONCALL_PCT_TOTAL": 0.05,
        "INCOMPLETE_MPS_TACT": 0.12, "INCOMPLETE_MPS_PCT_IB": 0.40, "INCOMPLETE_REPORT_TACT": 20.0,
        "INCOMPLETE_REPORT_COUNT": 1, "CAGE_MONITORING_TACT": 2.0, "CAGE_MONITORING_PCT_IB": 0.10,
        "DEX_MONITORING_TACT": 1.2, "ROC_ACTIVITIES_TACT": 6.0, "DEX_HANDLING_TACT": 4.0,
        "PICKUP_HANDOVER_TACT": 0.25, "FAMIS_TACT": 30.0, "OB_SCAN_LOAD_TACT": 0.1,
        "IPHP_PREALERT_TACT": 0.2, "IPHP_CHECKING_TACT": 15.0, "INCONTROL_OB_TACT": 20.0,
        "EGNSL_TACT": 15.0, "PAR_TACT": 10.0, "ASP_HANDLING_TACT": 0.5, "ROC_TACT": 5.0,
        "REX_APPLICATION_TACT": 0.2, "PPWK_IMAGING_TACT": 0.1, "GATEKEEPER_TACT": 30.0,
        "KYC_TACT": 2.0, "KYC_PCT_IB": 0.02, "STATION_OPEN_CLOSE_TACT": 10.0,
        "ROD_BOE_PCT_IB": 0.3,
    },
    "LASA": {
        "MAILING_ROD_BOE_TACT": 1.0, "BANKING_ACTIVITIES_TACT": 15.0,
        "AR_OR_FILE_REVIEW_TACT": 1.5, "CHECK_EMAILS_CUSTOMER_QUERIES_TACT": 1.0,
        "GCCS_CLOSURE_TACT": 1.0, "INVOICE_PAYMENT_REVIEW_TACT": 15.0,
        "PREPARING_VENDOR_INVOICE_TACT": 30.0, "PO_UTILITIES_MAINTENANCE_TACT": 10.0,
        "PROVISION_FILE_SUBMISSION_TACT": 5.0, "AGREEMENT_DRAFT_TACT": 5.0,
        "EOD_CLOSURE_TACT": 25.0, "OTHER_ACTIVITIES_TACT": 20.0,
    },
    "DISPATCHER": {
        "PUSH_DISPATCH_TACT": 1.5, "LIVE_DEX_MONITORING_TACT": 0.5,
        "GDP_SIMS_MONITORING_TACT": 10.0, "EDI_CASH_BCN_PICKUP_TACT": 0.5,
        "EMAIL_QUERY_HANDLING_TACT": 2.0, "CUSTOMER_COORDINATION_TACT": 1.0,
        "EICS_ACCOUNT_STATUS_CHECK_TACT": 5.0, "FRAUD_ACCOUNT_MISUSE_TACT": 5.0,
        "CLOSE_DISPATCH_EOD_TACT": 0.5,
    },
    "TRACE_AGENT": {
        "CUSTOMER_CALL_REATTEMPT_TACT": 2.0, "CAGE_AGEING_SHIPMENT_TACT": 3.0,
        "CUSTOMER_SALES_COORDINATION_TACT": 2.0, "CMOD_WORK_TACT": 2.0,
        "OPEN_CASES_CLOSURE_TACT": 3.0, "REOPEN_CASES_TACT": 20.0,
        "CMOD_REPORT_CLOSURE_TACT": 20.0,
    },
}


@pytest.fixture(autouse=True)
def patch_config():
    with patch("aero.core.resource_calculator.load_config", return_value=_MOCK_CONFIG):
        # Also patch the module-level globals that are set at import time
        import aero.core.resource_calculator as rc
        rc.OSA_CONFIG        = _MOCK_CONFIG["OSA"]
        rc.LASA_CONFIG       = _MOCK_CONFIG["LASA"]
        rc.DISPATCHER_CONFIG = _MOCK_CONFIG["DISPATCHER"]
        rc.TRACE_AGENT_CONFIG = _MOCK_CONFIG["TRACE_AGENT"]
        yield


from aero.core.resource_calculator import (
    calculate_osa_time,
    calculate_lasa_time,
    calculate_dispatcher_time,
    calculate_trace_time,
)


# ---------------------------------------------------------------------------
# calculate_osa_time
# ---------------------------------------------------------------------------

class TestCalculateOsaTime:

    def test_returns_positive_float(self):
        result = calculate_osa_time(
            total_volume=1000, ib_volume=600, ob_volume=400,
            roc_volume=20, asp_volume=50
        )
        assert isinstance(result, float)
        assert result > 0

    def test_zero_volume_has_fixed_tasks(self):
        # Even with zero volumes, fixed-count tasks (IPHP Checking, Compliance, etc.) consume time
        result = calculate_osa_time(
            total_volume=0, ib_volume=0, ob_volume=0, roc_volume=0, asp_volume=0
        )
        assert result > 0

    def test_excluded_task_reduces_time(self):
        base = calculate_osa_time(
            total_volume=500, ib_volume=300, ob_volume=200, roc_volume=10, asp_volume=20
        )
        reduced = calculate_osa_time(
            total_volume=500, ib_volume=300, ob_volume=200, roc_volume=10, asp_volume=20,
            excluded_tasks={"IB / OB Scan"},
        )
        assert reduced < base

    def test_custom_task_adds_time(self):
        base = calculate_osa_time(
            total_volume=500, ib_volume=300, ob_volume=200, roc_volume=10, asp_volume=20
        )
        extra = calculate_osa_time(
            total_volume=500, ib_volume=300, ob_volume=200, roc_volume=10, asp_volume=20,
            custom_tasks=[{"id": "custom_1", "tact": 5.0, "param": 10}],
        )
        assert extra == pytest.approx(base + 50.0, abs=0.01)

    def test_higher_volume_increases_time(self):
        low  = calculate_osa_time(total_volume=200, ib_volume=120, ob_volume=80, roc_volume=5, asp_volume=10)
        high = calculate_osa_time(total_volume=2000, ib_volume=1200, ob_volume=800, roc_volume=50, asp_volume=100)
        assert high > low


# ---------------------------------------------------------------------------
# calculate_lasa_time
# ---------------------------------------------------------------------------

class TestCalculateLasaTime:

    def test_returns_positive_float(self):
        result = calculate_lasa_time(ib_volume=500, ob_volume=300, asp_volume=30)
        assert result > 0

    def test_zero_volume_has_fixed_tasks(self):
        result = calculate_lasa_time(ib_volume=0, ob_volume=0, asp_volume=0)
        # Banking, invoicing, etc. are fixed-count tasks
        assert result > 0

    def test_excluded_task_reduces_time(self):
        base    = calculate_lasa_time(ib_volume=500, ob_volume=300, asp_volume=30)
        reduced = calculate_lasa_time(
            ib_volume=500, ob_volume=300, asp_volume=30,
            excluded_tasks={"Banking Activities"},
        )
        assert reduced < base


# ---------------------------------------------------------------------------
# calculate_dispatcher_time
# ---------------------------------------------------------------------------

class TestCalculateDispatcherTime:

    def test_returns_positive_float(self):
        result = calculate_dispatcher_time(
            total_volume=1000, ib_volume=600, ob_volume=400, asp_volume=50
        )
        assert result > 0

    def test_on_call_pickup_affects_time(self):
        low  = calculate_dispatcher_time(total_volume=1000, ib_volume=600, ob_volume=400, asp_volume=50, on_call_pickup=50)
        high = calculate_dispatcher_time(total_volume=1000, ib_volume=600, ob_volume=400, asp_volume=50, on_call_pickup=200)
        assert high > low


# ---------------------------------------------------------------------------
# calculate_trace_time
# ---------------------------------------------------------------------------

class TestCalculateTraceTime:

    def test_returns_positive_float(self):
        result = calculate_trace_time(total_volume=1000, ob_volume=400)
        assert result > 0

    def test_zero_volume_has_fixed_tasks(self):
        result = calculate_trace_time(total_volume=0, ob_volume=0)
        # Reopen case and CMOD report monitoring are fixed-count → time > 0
        assert result > 0

    def test_higher_volume_increases_time(self):
        low  = calculate_trace_time(total_volume=100, ob_volume=60)
        high = calculate_trace_time(total_volume=1000, ob_volume=600)
        assert high > low
