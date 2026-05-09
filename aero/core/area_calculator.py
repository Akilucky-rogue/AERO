"""
area_calculator.py — Area requirement calculations.

Computes sorting area, equipment footprint, caging/supplies, aisle buffers,
and total operational area from FAMIS volume data.
"""

import math

from aero.config.settings import load_area_config


# ============================================================
# AREA CONSTANTS
# ============================================================
def load_area_constants():
    """Load area constants from area.json configuration."""
    cfg = load_area_config()
    return cfg.get("AREA_CONSTANTS", get_default_constants())


def get_default_constants():
    """Return default area constants."""
    return {
        "PALLET_AREA": 16,
        "AISLE_PERCENT": 0.15,
        "CAGE_PALLET_AREA": 25,
        "STACKING_PER_PALLET": 20,
    }


EQUIPMENT_CONSTANTS = {
    "VMEASURE_AREA": 30,
    "HPT_AREA": 50,
    "ROC_AREA": 100,
    "SUPPLIES_PERCENT": 0.10,
}

PREDEFINED_AREAS = {
    "IT ROOM": 100,
    "UPS AREA": 80,
    "LEO+ MUFASA": 10,
    "CABIN": 80,
    "WEIGHING MACHINE": 10,
    "WASHROOM + CHANGING": 150,
    "CAFETERIA": 100,
    "MEETING ROOM": 80,
    "FORKLIFT": 80,
    "OFFICE AREA": None,
}


def get_caging_supplies_area(total_packs):
    """
    Return fixed Caging & Supplies area (sq.ft) based on facility model.
    Model A (<=500 APPD): 80, B (501-1500): 100, C (1501-3500): 150, D (3501+): 200.
    """
    if total_packs <= 500:
        model = "A"
        area = 80
    elif total_packs <= 1500:
        model = "B"
        area = 100
    elif total_packs <= 3500:
        model = "C"
        area = 150
    else:
        model = "D"
        area = 200
    return {"model": model, "area": area}


def calculate_area_requirements(
    total_packs,
    packs_per_pallet=15,
    max_volume_percent=55.0,
    sorting_area_percent=60.0,
    cage_percent=10.0,
    aisle_percent=15.0,
    additional_area_value=0,
):
    CONSTANTS = load_area_constants()
    PALLET_AREA = CONSTANTS.get("PALLET_AREA", 16)
    pallets_required = math.ceil(total_packs / packs_per_pallet) if packs_per_pallet > 0 else 0
    avg_hourly_pallets = math.ceil(pallets_required * (max_volume_percent / 100))
    area_required = avg_hourly_pallets * PALLET_AREA
    area_with_aisle = area_required * (1 + (aisle_percent / 100))
    sorting_area = round(area_with_aisle * (sorting_area_percent / 100))
    cs = get_caging_supplies_area(total_packs)
    cage_area_required = cs["area"]
    supplies_area = 0
    cage_pallets = 0
    fixed_equipment = (
        EQUIPMENT_CONSTANTS["VMEASURE_AREA"]
        + EQUIPMENT_CONSTANTS["HPT_AREA"]
        + EQUIPMENT_CONSTANTS["ROC_AREA"]
    )
    leo_area = PREDEFINED_AREAS.get("LEO+ MUFASA", 0) or 0
    weighing_area = PREDEFINED_AREAS.get("WEIGHING MACHINE", 0) or 0
    forklift_area = PREDEFINED_AREAS.get("FORKLIFT", 0) or 0
    fixed_equipment = fixed_equipment + float(leo_area) + float(weighing_area) + float(forklift_area)
    additional_total = float(additional_area_value) if additional_area_value else 0.0
    total_operational_area = (
        area_with_aisle + sorting_area + fixed_equipment + supplies_area + cage_area_required + additional_total
    )
    return {
        "total_packs": total_packs,
        "pallets_required": pallets_required,
        "avg_hourly_pallets": avg_hourly_pallets,
        "area_required": round(area_required, 2),
        "area_with_aisle": round(area_with_aisle, 2),
        "sorting_area": round(sorting_area, 2),
        "cage_pallets": cage_pallets,
        "cage_area_required": round(cage_area_required, 2),
        "supplies_area": round(supplies_area, 2),
        "equipment_area": fixed_equipment + round(cage_area_required, 2),
        "additional_area": round(additional_total, 2),
        "total_operational_area": round(total_operational_area, 2),
    }


def calculate_area_status(calculated_total_area, master_facility_area):
    """Determine health status based on calculated vs master area."""
    try:
        master = float(master_facility_area)
    except Exception:
        master = 0.0

    try:
        calculated = float(calculated_total_area)
    except Exception:
        calculated = 0.0

    if master <= 0:
        return {
            "status": "UNKNOWN",
            "deviation_percent": 0,
            "color": "#8E8E8E",
            "emoji": "❓",
            "label": "No Master Area",
        }

    deviation_percent = ((master - calculated) / master) * 100

    if deviation_percent >= -10:
        status = "HEALTHY"
        color = "#008A00"
        emoji = "✅"
        label = f"Healthy ({deviation_percent:+.1f}%)"
    elif deviation_percent >= -20:
        status = "REVIEW_NEEDED"
        color = "#F7B118"
        emoji = "⚠️"
        label = f"Review Needed ({deviation_percent:+.1f}%)"
    else:
        status = "CRITICAL"
        color = "#DE002E"
        emoji = "🔴"
        label = f"Critical ({deviation_percent:+.1f}%)"

    return {
        "status": status,
        "deviation_percent": round(deviation_percent, 2),
        "color": color,
        "emoji": emoji,
        "label": label,
    }


# Backward-compatible alias — logic consolidated in health.py
from aero.core.health import get_summary_stats as get_status_summary_stats  # noqa: E402
