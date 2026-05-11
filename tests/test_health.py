"""
tests/test_health.py — Unit tests for aero.core.health.

Covers calculate_health_status() — all branches — and get_summary_stats().
Pure functions: no Streamlit, no filesystem, no network.
"""

import pytest

from aero.core.health import calculate_health_status, get_summary_stats


# ---------------------------------------------------------------------------
# calculate_health_status
# ---------------------------------------------------------------------------

class TestCalculateHealthStatus:

    def test_healthy_when_available_exceeds_calculated(self):
        result = calculate_health_status(calculated=100, available=110)
        assert result["status"] == "HEALTHY"
        assert result["deviation_percent"] > 0
        assert result["emoji"] == "✅"

    def test_healthy_when_available_equals_calculated(self):
        result = calculate_health_status(calculated=100, available=100)
        assert result["status"] == "HEALTHY"
        assert result["deviation_percent"] == 0.0

    def test_healthy_within_10_percent_deficit(self):
        # -8% deficit is still HEALTHY
        result = calculate_health_status(calculated=100, available=92)
        assert result["status"] == "HEALTHY"

    def test_review_needed_at_15_percent_deficit(self):
        # -15% deficit → REVIEW_NEEDED
        result = calculate_health_status(calculated=100, available=85)
        assert result["status"] == "REVIEW_NEEDED"
        assert result["emoji"] == "⚠️"

    def test_critical_beyond_20_percent_deficit(self):
        # -25% deficit → CRITICAL
        result = calculate_health_status(calculated=100, available=75)
        assert result["status"] == "CRITICAL"
        assert result["emoji"] == "🔴"

    def test_unknown_when_calculated_is_zero(self):
        result = calculate_health_status(calculated=0, available=50)
        assert result["status"] == "UNKNOWN"

    def test_no_data_when_available_is_zero(self):
        result = calculate_health_status(calculated=100, available=0)
        assert result["status"] == "NO DATA"

    def test_unknown_when_calculated_is_negative(self):
        result = calculate_health_status(calculated=-5, available=50)
        assert result["status"] == "UNKNOWN"

    def test_unknown_on_non_numeric_calculated(self):
        result = calculate_health_status(calculated="bad", available=50)
        assert result["status"] == "UNKNOWN"

    def test_deviation_percent_precision(self):
        result = calculate_health_status(calculated=200, available=150)
        # deviation = (150-200)/200 * 100 = -25%
        assert result["deviation_percent"] == pytest.approx(-25.0, abs=0.01)

    def test_result_contains_required_keys(self):
        result = calculate_health_status(calculated=100, available=100)
        for key in ("status", "deviation_percent", "color", "emoji", "label"):
            assert key in result


# ---------------------------------------------------------------------------
# get_summary_stats
# ---------------------------------------------------------------------------

class TestGetSummaryStats:

    def _make_status(self, status, deviation=0):
        return {"status": status, "deviation_percent": deviation}

    def test_counts_healthy(self):
        statuses = [self._make_status("HEALTHY") for _ in range(3)]
        stats = get_summary_stats(statuses)
        assert stats["healthy_count"] == 3
        assert stats["review_needed_count"] == 0
        assert stats["critical_count"] == 0

    def test_counts_review(self):
        statuses = [self._make_status("REVIEW_NEEDED")]
        stats = get_summary_stats(statuses)
        assert stats["review_needed_count"] == 1

    def test_counts_critical(self):
        statuses = [self._make_status("CRITICAL", deviation=-30)]
        stats = get_summary_stats(statuses)
        assert stats["critical_count"] == 1

    def test_most_affected_is_worst_negative(self):
        statuses = [
            self._make_status("CRITICAL", deviation=-30),
            self._make_status("REVIEW_NEEDED", deviation=-15),
            self._make_status("HEALTHY", deviation=5),
        ]
        stats = get_summary_stats(statuses)
        assert stats["most_affected"]["deviation_percent"] == -30

    def test_most_affected_none_when_all_positive(self):
        statuses = [self._make_status("HEALTHY", deviation=10)]
        stats = get_summary_stats(statuses)
        assert stats["most_affected"] is None

    def test_empty_list(self):
        stats = get_summary_stats([])
        assert stats["healthy_count"] == 0
        assert stats["review_needed_count"] == 0
        assert stats["critical_count"] == 0
        assert stats["most_affected"] is None
