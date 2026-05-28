"""
courier_calculator.py — Courier requirement calculations.

Computes courier staffing requirements using productivity metrics,
standard productivity benchmarks, training buffers, and health thresholds.

Formula chain (BUG-FIX: absenteeism was previously accepted but ignored):
  1. productivity_as_per_hrs  = pk_st_or × st_hr_or × productivity_hrs
                                (packages a single courier can deliver per day)
  2. If productivity = 0 (FAMIS metrics missing) → fall back to STANDARD_PRODUCTIVITY
  3. courier_required_as_per_productivity = ceil(total_packages / effective_productivity)
  4. courier_required_with_absenteeism    = ceil(base / (1 - absenteeism_pct / 100))
                                           inflates headcount to cover absent couriers
  5. training_additional                 = ceil(absenteeism_adj × training_pct / 100)
  6. total_required_with_training        = absenteeism_adj + training_additional
  7. final_delta                         = couriers_available − total_required_with_training
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
    # ── Step 1: Daily productivity per courier ──────────────────────────────
    productivity_as_per_hrs = pk_st_or * st_hr_or * productivity_hrs

    # ── Step 2: Base headcount — FAMIS productivity or STANDARD fallback ────
    if productivity_as_per_hrs > 0 and total_packages > 0:
        courier_required_as_per_productivity = math.ceil(
            total_packages / productivity_as_per_hrs
        )
    elif total_packages > 0:
        # No FAMIS metrics supplied — use the network standard benchmark
        courier_required_as_per_productivity = math.ceil(
            total_packages / STANDARD_PRODUCTIVITY
        )
    else:
        courier_required_as_per_productivity = 0

    # ── Step 3: Absenteeism inflation ───────────────────────────────────────
    # e.g. 16% absent → need ceil(base / 0.84) couriers rostered
    absenteeism_factor = max(1.0 - (absenteeism_pct / 100.0), 0.01)  # floor at 1% to avoid ÷0
    courier_required_with_absenteeism = (
        math.ceil(courier_required_as_per_productivity / absenteeism_factor)
        if courier_required_as_per_productivity > 0
        else 0
    )

    # ── Step 4: Training buffer on top of absenteeism-adjusted headcount ────
    training_additional = math.ceil(
        courier_required_with_absenteeism * training_pct / 100
    )
    total_required_with_training = courier_required_with_absenteeism + training_additional

    # ── Step 5: Delta (positive = surplus, negative = deficit) ─────────────
    final_delta = couriers_available - total_required_with_training

    # Backward-compat alias kept so any caller using the old key still works
    courier_required_with_standard = math.ceil(
        total_packages / STANDARD_PRODUCTIVITY if total_packages > 0 else 0
    )

    return {
        "total_packages":                      round(total_packages, 2),
        "pk_st_or":                            round(pk_st_or, 2),
        "st_hr_or":                            round(st_hr_or, 2),
        "productivity_hrs":                    round(productivity_hrs, 2),
        "productivity_as_per_hrs":             round(productivity_as_per_hrs, 2),
        "courier_required_as_per_productivity": round(courier_required_as_per_productivity, 2),
        "courier_required_with_absenteeism":   round(courier_required_with_absenteeism, 2),  # NEW — correct key
        "courier_required_with_standard":      round(courier_required_with_standard, 2),     # legacy alias
        "absenteeism_pct":                     round(absenteeism_pct, 2),
        "training_pct":                        round(training_pct, 2),
        "training_additional":                 round(training_additional, 2),
        "total_required_with_training":        round(total_required_with_training, 2),
        "couriers_available":                  couriers_available,
        "final_delta":                         round(final_delta, 2),
    }


# Backward-compatible aliases — logic consolidated in health.py
from aero.core.health import calculate_health_status as calculate_courier_health_status  # noqa: E402
from aero.core.health import get_summary_stats as get_courier_summary_stats  # noqa: E402
