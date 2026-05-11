"""
courier_calculator.py — Courier requirement calculations.

Computes courier staffing requirements using productivity metrics,
standard productivity benchmarks, training buffers, and health thresholds.
"""

import math

from aero.config.settings import load_config

_CONFIG = load_config()
COURIER_CONFIG = _CONFIG.get("COURIER", {})
STANDARD_PRODUCTIVITY = int(COURIER_CONFIG.get("STANDARD_PRODUCTIVITY", 45))


def calculate_courier_requirements(
    total_packages,
    pk_st_or=0.0,
    st_hr_or=0.0,
    productivity_hrs=7.0,
    couriers_available=0,
    absenteeism_pct=16.0,
    training_pct=11.0,
    working_days=5,
):
    productivity_as_per_hrs = pk_st_or * st_hr_or * productivity_hrs
    courier_required_as_per_productivity = math.ceil(
        total_packages / productivity_as_per_hrs if productivity_as_per_hrs > 0 else 0
    )
    courier_required_with_standard = math.ceil(
        total_packages / STANDARD_PRODUCTIVITY if total_packages > 0 else 0
    )
    total_working_days_plus_training = courier_required_with_standard + (
        courier_required_with_standard * training_pct / 100
    )
    final_delta = couriers_available - total_working_days_plus_training
    return {
        "total_packages": round(total_packages, 2),
        "pk_st_or": round(pk_st_or, 2),
        "st_hr_or": round(st_hr_or, 2),
        "productivity_hrs": round(productivity_hrs, 2),
        "productivity_as_per_hrs": round(productivity_as_per_hrs, 2),
        "courier_required_as_per_productivity": round(courier_required_as_per_productivity, 2),
        "courier_required_with_standard": round(courier_required_with_standard, 2),
        "training_additional": round(courier_required_with_standard * training_pct / 100, 2),
        "total_required_with_training": round(total_working_days_plus_training, 2),
        "couriers_available": couriers_available,
        "final_delta": round(final_delta, 2),
    }


# Backward-compatible aliases — logic consolidated in health.py
from aero.core.health import calculate_health_status as calculate_courier_health_status  # noqa: E402
from aero.core.health import get_summary_stats as get_courier_summary_stats  # noqa: E402
