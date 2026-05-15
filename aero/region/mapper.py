"""
aero/region/mapper.py
──────────────────────────────────────────────────────────────────────────────
Region intelligence for Indian FedEx stations.
Maps loc_id (airport-code prefixed) → South / West / North.

Region definitions
──────────────────
• South : BLR, HYD, MAA and related stations
          (Bangalore, Hyderabad, Chennai, Cochin, Trivandrum…)
• West  : BOM, AMD, STV, PNQ and related stations
          (Mumbai, Ahmedabad, Surat, Pune, Nagpur…)
• North : everything else  (Delhi, Lucknow, Patna, Jaipur, Kolkata…)
          NOTE: No separate East region — all eastern stations roll into North.

Handles common loc_id patterns:
  "BLR-VS"  "BLRVS"  "BLR_STN"  "BLR"  " BLR-12 "  "blr-vs"  etc.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re
import pandas as pd

# ── Region seed codes ─────────────────────────────────────────────────────────
# Each set contains 3-letter IATA / FedEx station codes for the region.

_SOUTH_CODES: frozenset[str] = frozenset({
    # Karnataka
    "BLR", "MYQ",
    # Telangana / Andhra Pradesh
    "HYD", "BPM", "RJA", "VGA", "VTZ",
    # Tamil Nadu
    "MAA", "TRZ", "MDU", "IXM", "CJB", "TCR",
    # Kerala
    "COK", "CCJ", "TRV",
    # Karnataka coast
    "IXE",
    # Pondicherry
    "PNY",
})

_WEST_CODES: frozenset[str] = frozenset({
    # Maharashtra
    "BOM", "PNQ", "NAG",
    # Gujarat
    "AMD", "STV", "BHJ", "RAJ", "BRC", "VDY",
    # Goa
    "GOI",
    # Rajasthan (west)
    "UDR", "JDH",
    # Madhya Pradesh (west cluster)
    "IDR",
})

# North = everything not South or West (includes East, NE, Central)

# ── Regex extractor ───────────────────────────────────────────────────────────
# Extracts the leading alphabetic characters (2–4 chars) from a loc_id string,
# then caps at 3 to match IATA codes.
_CODE_RE = re.compile(r"^[^A-Za-z]*([A-Za-z]{2,4})", re.ASCII)


def _extract_code(loc_id: str) -> str:
    """Return the normalised 3-char uppercase code extracted from *loc_id*."""
    if not isinstance(loc_id, str):
        return ""
    m = _CODE_RE.match(loc_id.strip())
    if not m:
        return ""
    return m.group(1).upper()[:3]   # IATA codes are 3-char


# ── Public API ────────────────────────────────────────────────────────────────

def get_region(loc_id: str) -> str:
    """
    Return the region string for a given loc_id.

    Returns one of: ``'South'``, ``'West'``, ``'North'``, ``'Unknown'``.
    ``'Unknown'`` is only returned when the loc_id is completely unrecognisable
    (empty string, NaN, pure numeric, etc.).
    """
    code = _extract_code(loc_id)
    if not code:
        return "Unknown"
    if code in _SOUTH_CODES:
        return "South"
    if code in _WEST_CODES:
        return "West"
    return "North"


def classify_dataframe(
    df: pd.DataFrame,
    loc_col: str = "loc_id",
) -> pd.DataFrame:
    """
    Add a ``'region'`` column to *df* based on *loc_col*.

    Returns a **copy** — the original DataFrame is never mutated.
    If *loc_col* is absent the region column is filled with ``'Unknown'``.
    """
    out = df.copy()
    if loc_col not in out.columns:
        out["region"] = "Unknown"
    else:
        out["region"] = out[loc_col].apply(get_region)
    return out


def region_order() -> list[str]:
    """Canonical display order used across all region-aware pages."""
    return ["South", "West", "North", "Unknown"]


def region_color(region: str) -> str:
    """Brand-aligned colour for each region (hex)."""
    return {
        "South":   "#FF6200",   # FedEx orange
        "West":    "#4D148C",   # FedEx purple
        "North":   "#0066CC",   # blue
        "Unknown": "#888888",
    }.get(region, "#888888")


def get_stations_by_region(df: pd.DataFrame, loc_col: str = "loc_id") -> dict[str, list[str]]:
    """
    Return a dict mapping region → sorted list of unique loc_id values.

    Useful for building region-level filter widgets.
    """
    classified = classify_dataframe(df, loc_col)
    result: dict[str, list[str]] = {}
    for region in region_order():
        stations = sorted(
            classified.loc[classified["region"] == region, loc_col].dropna().unique().tolist()
        )
        if stations:
            result[region] = stations
    return result
