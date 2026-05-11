"""
excel_store.py — FAMIS upload and report data persistence.

Two workbooks live under data/:
  1. FAMIS_UPLOADED_FILES.xlsx — raw FAMIS rows upserted on every user upload
  2. FAMIS_REPORT_DATA.xlsx   — computed health-monitor reports (4 sheets)

Security notes
--------------
* All DataFrames are sanitized with _sanitize_df() before being written to
  Excel to prevent formula injection (SEC-006): any string cell value that
  begins with =, +, -, @, |, or % is prefixed with a single-quote so that
  Excel/openpyxl treats it as plain text rather than a formula.
* Writes use an atomic temp-file swap (os.replace) so a crash mid-write
  never leaves a corrupt or truncated workbook (DL-008).
"""

import logging
import os
from datetime import datetime

import pandas as pd

from aero import DATA_DIR

logger = logging.getLogger(__name__)

FAMIS_UPLOAD_PATH = os.path.join(DATA_DIR, "FAMIS_UPLOADED_FILES.xlsx")
FAMIS_REPORT_PATH = os.path.join(DATA_DIR, "FAMIS_REPORT_DATA.xlsx")

# Characters that Excel interprets as formula starters
_FORMULA_START_CHARS = frozenset("=+-@|%")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Formula injection prevention (SEC-006)
# ---------------------------------------------------------------------------

def _sanitize_cell(value: object) -> object:
    """Prefix dangerous formula-starter characters so Excel treats them as text."""
    if isinstance(value, str) and value and value[0] in _FORMULA_START_CHARS:
        return "'" + value
    return value


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cell-level formula injection sanitization to all string columns."""
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].map(_sanitize_cell)
    return df


# ---------------------------------------------------------------------------
# Atomic Excel writes (DL-008)
# ---------------------------------------------------------------------------

def _atomic_write(path: str, sheets: dict[str, pd.DataFrame]) -> None:
    """Write *sheets* to *path* atomically using a .tmp file + os.replace().

    Guarantees that a crash mid-write never corrupts the existing file —
    the target is only replaced once the new file is fully flushed.
    """
    tmp = path + ".tmp"
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl", mode="w") as writer:
            for sheet_name, df in sheets.items():
                _sanitize_df(df).to_excel(writer, sheet_name=sheet_name, index=False)
        os.replace(tmp, path)
    except Exception:
        # Clean up the temp file on failure to avoid stale artefacts.
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


# ===================================================================
# 1. FAMIS UPLOADED DATA
# ===================================================================

def upsert_famis_upload(new_df: pd.DataFrame) -> int:
    """Upsert rows into FAMIS_UPLOADED_FILES.xlsx. Key: date + loc_id."""
    _ensure_dir()

    new_df = new_df.copy()
    if "date" in new_df.columns:
        new_df["date"] = pd.to_datetime(new_df["date"]).dt.normalize()

    new_df["uploaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if os.path.exists(FAMIS_UPLOAD_PATH):
        try:
            existing = pd.read_excel(FAMIS_UPLOAD_PATH, sheet_name="FAMIS_DATA")
        except Exception as exc:
            logger.warning("upsert_famis_upload: could not read existing file: %s", exc)
            existing = pd.DataFrame()

        if not existing.empty and "date" in existing.columns and "loc_id" in existing.columns:
            existing["date"] = pd.to_datetime(existing["date"]).dt.normalize()
            merge_keys = ["date", "loc_id"]
            merged = existing.merge(new_df[merge_keys].drop_duplicates(), on=merge_keys, how="left", indicator=True)
            keep = existing[merged["_merge"] == "left_only"].copy()
            result = pd.concat([keep, new_df], ignore_index=True, sort=False)
        else:
            result = pd.concat([existing, new_df], ignore_index=True, sort=False)
    else:
        result = new_df

    _atomic_write(FAMIS_UPLOAD_PATH, {"FAMIS_DATA": result})
    return len(new_df)


def read_famis_uploads() -> pd.DataFrame:
    if not os.path.exists(FAMIS_UPLOAD_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_excel(FAMIS_UPLOAD_PATH, sheet_name="FAMIS_DATA")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df
    except Exception as exc:
        logger.warning("read_famis_uploads: could not read file: %s", exc)
        return pd.DataFrame()


# ===================================================================
# 2. FAMIS REPORT DATA
# ===================================================================

def save_health_reports(
    area_rows: list[dict],
    resource_rows: list[dict],
    courier_rows: list[dict],
    report_date: str | None = None,
) -> bool:
    _ensure_dir()

    area_df = pd.DataFrame(area_rows) if area_rows else pd.DataFrame()
    resource_df = pd.DataFrame(resource_rows) if resource_rows else pd.DataFrame()
    courier_df = pd.DataFrame(courier_rows) if courier_rows else pd.DataFrame()

    total_df = _build_total_summary(area_df, resource_df, courier_df)

    if os.path.exists(FAMIS_REPORT_PATH):
        try:
            existing_area = pd.read_excel(FAMIS_REPORT_PATH, sheet_name="AREA HEALTH SUMMARY")
        except Exception as exc:
            logger.warning("save_health_reports: could not read AREA sheet: %s", exc)
            existing_area = pd.DataFrame()
        try:
            existing_resource = pd.read_excel(FAMIS_REPORT_PATH, sheet_name="RESOURCE HEALTH SUMMARY")
        except Exception as exc:
            logger.warning("save_health_reports: could not read RESOURCE sheet: %s", exc)
            existing_resource = pd.DataFrame()
        try:
            existing_courier = pd.read_excel(FAMIS_REPORT_PATH, sheet_name="COURIER HEALTH SUMMARY")
        except Exception as exc:
            logger.warning("save_health_reports: could not read COURIER sheet: %s", exc)
            existing_courier = pd.DataFrame()

        area_df = _upsert_report_df(existing_area, area_df)
        resource_df = _upsert_report_df(existing_resource, resource_df)
        courier_df = _upsert_report_df(existing_courier, courier_df)
        total_df = _build_total_summary(area_df, resource_df, courier_df)

    _atomic_write(FAMIS_REPORT_PATH, {
        "TOTAL SUMMARY":           total_df,
        "AREA HEALTH SUMMARY":     area_df,
        "RESOURCE HEALTH SUMMARY": resource_df,
        "COURIER HEALTH SUMMARY":  courier_df,
    })
    return True


def read_report_sheet(sheet_name: str) -> pd.DataFrame:
    if not os.path.exists(FAMIS_REPORT_PATH):
        return pd.DataFrame()
    try:
        return pd.read_excel(FAMIS_REPORT_PATH, sheet_name=sheet_name)
    except Exception as exc:
        logger.warning("read_report_sheet('%s'): %s", sheet_name, exc)
        return pd.DataFrame()


def _upsert_report_df(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if new.empty:
        return existing
    if existing.empty:
        return new
    keys = [c for c in ["DATE", "LOC ID"] if c in existing.columns and c in new.columns]
    if not keys:
        return pd.concat([existing, new], ignore_index=True, sort=False)
    merged = existing.merge(new[keys].drop_duplicates(), on=keys, how="left", indicator=True)
    keep = existing[merged["_merge"] == "left_only"].copy()
    return pd.concat([keep, new], ignore_index=True, sort=False)


def _build_total_summary(area_df: pd.DataFrame, resource_df: pd.DataFrame, courier_df: pd.DataFrame) -> pd.DataFrame:
    if area_df.empty and resource_df.empty and courier_df.empty:
        return pd.DataFrame()

    keys = ["DATE", "LOC ID"]
    total = area_df.copy() if not area_df.empty else pd.DataFrame(columns=keys)

    if not resource_df.empty:
        total = total.merge(resource_df, on=keys, how="outer", suffixes=("", " (RES)"))

    if not courier_df.empty:
        total = total.merge(courier_df, on=keys, how="outer", suffixes=("", " (COUR)"))

    return total

