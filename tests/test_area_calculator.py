"""
tests/test_area_calculator.py — Unit tests for aero.core.area_calculator.

Tests calculate_area_requirements() across facility models (A/B/C/D) and
calculate_area_status() for all three health branches.
Pure functions: no Streamlit, no filesystem.
"""

import pytest

from unittest.mock import patch

# Patch load_area_config to return a fixed config so tests are deterministic
# and don't depend on the real area.json file content.
_MOCK_AREA_CONFIG = {
    "AREA_CONSTANTS": {
        "PALLET_AREA": 16,
        "AISLE_PERCENT": 0.15,
        "CAGE_PALLET_AREA": 25,
        "STACKING_PER_PALLET": 20,
    }
}


@pytest.fixture(autouse=True)
def patch_config():
    with patch("aero.core.area_calculator.load_area_config", return_value=_MOCK_AREA_CONFIG):
        yield


from aero.core.area_calculator import (
    calculate_area_requirements,
    calculate_area_status,
    get_caging_supplies_area,
)


# ---------------------------------------------------------------------------
# get_caging_supplies_area — facility model selection
# ---------------------------------------------------------------------------

class TestGetCagingSuppliesArea:

    def test_model_a_boundary(self):
        result = get_caging_supplies_area(500)
        assert result["model"] == "A"
        assert result["area"] == 80

    def test_model_b(self):
        result = get_caging_supplies_area(501)
        assert result["model"] == "B"
        assert result["area"] == 100

    def test_model_b_upper(self):
        result = get_caging_supplies_area(1500)
        assert result["model"] == "B"

    def test_model_c(self):
        result = get_caging_supplies_area(1501)
        assert result["model"] == "C"
        assert result["area"] == 150

    def test_model_d(self):
        result = get_caging_supplies_area(3501)
        assert result["model"] == "D"
        assert result["area"] == 200


# ---------------------------------------------------------------------------
# calculate_area_requirements — output structure and key relationships
# ---------------------------------------------------------------------------

class TestCalculateAreaRequirements:

    def test_returns_all_required_keys(self):
        result = calculate_area_requirements(total_packs=1000)
        expected_keys = {
            "total_packs", "pallets_required", "avg_hourly_pallets",
            "area_required", "area_with_aisle", "sorting_area",
            "cage_area_required", "supplies_area", "equipment_area",
            "additional_area", "total_operational_area",
        }
        assert expected_keys.issubset(result.keys())

    def test_total_packs_echoed(self):
        result = calculate_area_requirements(total_packs=750)
        assert result["total_packs"] == 750

    def test_pallets_ceil(self):
        # 100 packs / 15 packs-per-pallet = 6.67 → ceil → 7
        result = calculate_area_requirements(total_packs=100, packs_per_pallet=15)
        assert result["pallets_required"] == 7

    def test_zero_packs(self):
        result = calculate_area_requirements(total_packs=0)
        assert result["pallets_required"] == 0
        assert result["total_operational_area"] >= 0

    def test_additional_area_included(self):
        result_no_extra = calculate_area_requirements(total_packs=1000, additional_area_value=0)
        result_extra    = calculate_area_requirements(total_packs=1000, additional_area_value=200)
        assert result_extra["total_operational_area"] == pytest.approx(
            result_no_extra["total_operational_area"] + 200, abs=0.01
        )

    def test_total_operational_area_positive(self):
        result = calculate_area_requirements(total_packs=500)
        assert result["total_operational_area"] > 0


# ---------------------------------------------------------------------------
# calculate_area_status — all three health branches
# ---------------------------------------------------------------------------

class TestCalculateAreaStatus:

    def test_healthy_surplus(self):
        # Master > calculated → healthy
        result = calculate_area_status(calculated_total_area=800, master_facility_area=1000)
        assert result["status"] == "HEALTHY"

    def test_healthy_within_10_percent(self):
        # Master=1000, calculated=950 → deviation = (1000-950)/1000*100 = 5% → HEALTHY
        result = calculate_area_status(calculated_total_area=950, master_facility_area=1000)
        assert result["status"] == "HEALTHY"

    def test_review_needed(self):
        # Master=1000, calculated=1150 → deviation = (1000-1150)/1000*100 = -15% → REVIEW
        result = calculate_area_status(calculated_total_area=1150, master_facility_area=1000)
        assert result["status"] == "REVIEW_NEEDED"

    def test_critical(self):
        # Master=1000, calculated=1400 → deviation = -40% → CRITICAL
        result = calculate_area_status(calculated_total_area=1400, master_facility_area=1000)
        assert result["status"] == "CRITICAL"

    def test_unknown_when_master_zero(self):
        result = calculate_area_status(calculated_total_area=500, master_facility_area=0)
        assert result["status"] == "UNKNOWN"

    def test_unknown_on_non_numeric_master(self):
        result = calculate_area_status(calculated_total_area=500, master_facility_area="N/A")
        assert result["status"] == "UNKNOWN"
