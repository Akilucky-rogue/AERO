"""
health.py — Shared health status and summary statistics.

Consolidates the duplicate health-status calculation and summary-stats
logic that was previously repeated across area_calculator, resource_calculator,
and courier_calculator.
"""


def calculate_health_status(calculated, available):
    """Determine health status by comparing calculated requirement vs available capacity.

    Used for both resource (agents) and courier health checks.
    Deviation formula: ((available - calculated) / calculated) * 100

    Returns a dict with status, deviation_percent, color, emoji, and label.
    """
    try:
        calculated = float(calculated)
    except (TypeError, ValueError):
        return {
            "status": "UNKNOWN",
            "deviation_percent": 0,
            "color": "#8E8E8E",
            "emoji": "❓",
            "label": "No Data",
        }

    try:
        available = float(available)
    except (TypeError, ValueError):
        available = 0.0

    if calculated <= 0:
        return {
            "status": "UNKNOWN",
            "deviation_percent": 0,
            "color": "#8E8E8E",
            "emoji": "❓",
            "label": "No Data",
        }

    if available <= 0:
        return {
            "status": "NO DATA",
            "deviation_percent": 0,
            "color": "#8E8E8E",
            "emoji": "⚪",
            "label": "No Data (Master = 0)",
        }

    deviation_percent = ((available - calculated) / calculated) * 100

    if deviation_percent >= 0:
        status = "HEALTHY"
        color = "#008A00"
        emoji = "✅"
        label = f"Healthy ({deviation_percent:+.1f}%)"
    elif abs(deviation_percent) <= 10:
        status = "HEALTHY"
        color = "#008A00"
        emoji = "✅"
        label = f"Healthy ({deviation_percent:+.1f}%)"
    elif abs(deviation_percent) <= 20:
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


def get_summary_stats(station_statuses):
    """Compute summary statistics from a list of station health-status dicts.

    Returns counts for healthy / review-needed / critical stations,
    plus the single most-negatively-affected station (if any).
    """
    healthy = sum(1 for s in station_statuses if s.get("status") == "HEALTHY")
    review = sum(1 for s in station_statuses if s.get("status") == "REVIEW_NEEDED")
    critical = sum(1 for s in station_statuses if s.get("status") == "CRITICAL")

    most_affected = None
    negatives = [s for s in station_statuses if s.get("deviation_percent", 0) < 0]
    if negatives:
        most_affected = min(negatives, key=lambda x: x.get("deviation_percent", 0))

    return {
        "healthy_count": healthy,
        "review_needed_count": review,
        "critical_count": critical,
        "most_affected": most_affected,
    }
