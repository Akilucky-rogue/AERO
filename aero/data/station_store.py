"""
station_store.py — Station-level CRUD operations on Excel workbooks.

Provides upsert, query, and master-sheet rebuild functionality for the
per-station planning workbook used by the Area / Resource / Courier planners.

Security notes
--------------
* Path traversal (SEC-007): every caller-supplied *excel_path* is normalised
  with os.path.normpath() and validated against the configured data root so
  a station name containing ../ cannot escape the data directory.
* Formula injection (SEC-006): string cell values are sanitized before being
  written to Excel — any value starting with =, +, -, @, |, % is prefixed
  with a single-quote so Excel treats it as text.
* Atomic writes (DL-008): an intermediate .tmp file + os.replace() swap
  ensures the workbook is never left in a corrupt/truncated state.
"""

import logging
import os
from datetime import datetime

import pandas as pd

from aero import DATA_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)

# Characters that Excel interprets as formula starters
_FORMULA_START_CHARS = frozenset("=+-@|%")


# ---------------------------------------------------------------------------
# Security helpers (SEC-006, SEC-007)
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


def _safe_path(excel_path: str) -> str:
    """Normalise and validate *excel_path* to prevent path traversal.

    Raises ValueError if the resolved path lies outside DATA_DIR or PROJECT_ROOT.
    Trusted roots: the data/ subdirectory and the project root (for master workbooks).
    """
    resolved = os.path.normpath(os.path.abspath(excel_path))
    data_root    = os.path.normpath(os.path.abspath(DATA_DIR))
    project_root = os.path.normpath(os.path.abspath(PROJECT_ROOT))
    in_data    = resolved.startswith(data_root + os.sep) or resolved == data_root
    in_project = resolved.startswith(project_root + os.sep) or resolved == project_root
    if not (in_data or in_project):
        raise ValueError(
            f"Attempted path traversal detected: {excel_path!r} resolves "
            f"outside the data directory ({data_root})."
        )
    return resolved


# ---------------------------------------------------------------------------
# Directory helper
# ---------------------------------------------------------------------------

def ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# Atomic Excel write helper (DL-008)
# ---------------------------------------------------------------------------

def _atomic_write_sheets(excel_path: str, sheets: dict) -> None:
    """Write *sheets* to *excel_path* atomically via a .tmp file + os.replace()."""
    tmp = excel_path + ".tmp"
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl", mode="w") as writer:
            for sheet_name, df in sheets.items():
                _sanitize_df(df).to_excel(writer, sheet_name=sheet_name, index=False)
        os.replace(tmp, excel_path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Core data operations
# ---------------------------------------------------------------------------

def rebuild_master_sheet(excel_path: str) -> pd.DataFrame:
    excel_path = _safe_path(excel_path)
    if not os.path.exists(excel_path):
        return pd.DataFrame()
    try:
        area_df = pd.DataFrame()
        resource_df = pd.DataFrame()
        courier_df = pd.DataFrame()
        try:
            area_df = pd.read_excel(excel_path, sheet_name="Area")
        except Exception as exc:
            logger.debug("rebuild_master_sheet: Area sheet not found: %s", exc)
        try:
            resource_df = pd.read_excel(excel_path, sheet_name="Resource")
        except Exception as exc:
            logger.debug("rebuild_master_sheet: Resource sheet not found: %s", exc)
        try:
            courier_df = pd.read_excel(excel_path, sheet_name="Courier")
        except Exception as exc:
            logger.debug("rebuild_master_sheet: Courier sheet not found: %s", exc)
        if area_df.empty:
            return pd.DataFrame()
        master_df = area_df.copy()
        if not resource_df.empty and "station_name" in resource_df.columns:
            resource_df = resource_df.rename(columns={"timestamp": "resource_timestamp"})
            master_df = master_df.merge(resource_df, on="station_name", how="left", suffixes=("", "_resource"))
        if not courier_df.empty and "station_name" in courier_df.columns:
            courier_df = courier_df.rename(columns={"timestamp": "courier_timestamp"})
            master_df = master_df.merge(courier_df, on="station_name", how="left", suffixes=("", "_courier"))
        if "timestamp" in master_df.columns:
            master_df = master_df.rename(columns={"timestamp": "area_timestamp"})
        return master_df
    except Exception as exc:
        logger.warning("rebuild_master_sheet: unexpected error: %s", exc)
        return pd.DataFrame()


def upsert_station_row(excel_path: str, station_name: str, data: dict, sheet_name: str = "Sheet1") -> bool:
    excel_path = _safe_path(excel_path)
    ensure_dir(excel_path)
    row = data.copy()
    row.setdefault("station_name", station_name)
    row.setdefault("timestamp", datetime.utcnow().isoformat())
    new_df = pd.DataFrame([row])
    if os.path.exists(excel_path):
        try:
            existing = pd.read_excel(excel_path, sheet_name=sheet_name)
        except Exception as exc:
            logger.warning("upsert_station_row: could not read sheet '%s': %s", sheet_name, exc)
            existing = pd.DataFrame()
        if not existing.empty and "station_name" in existing.columns:
            mask = existing["station_name"] == station_name
            if mask.any():
                idx = existing[mask].index[0]
                for k, v in row.items():
                    existing.at[idx, k] = v
                result = existing
            else:
                result = pd.concat([existing, new_df], ignore_index=True, sort=False)
        else:
            result = pd.concat([existing, new_df], ignore_index=True, sort=False)
    else:
        result = new_df

    try:
        if os.path.exists(excel_path):
            with pd.ExcelFile(excel_path) as xls:
                all_sheets = {
                    name: pd.read_excel(xls, sheet_name=name)
                    for name in xls.sheet_names
                    if name != sheet_name and name != "Master"
                }
            all_sheets[sheet_name] = result
            master_df = rebuild_master_sheet(excel_path)
            if not master_df.empty:
                all_sheets["Master"] = master_df
            ordered_sheets = {}
            if "Master" in all_sheets:
                ordered_sheets["Master"] = all_sheets.pop("Master")
            for sname in ["Area", "Resource", "Courier"]:
                if sname in all_sheets:
                    ordered_sheets[sname] = all_sheets.pop(sname)
            ordered_sheets.update(all_sheets)
            _atomic_write_sheets(excel_path, ordered_sheets)
        else:
            sheets = {sheet_name: result}
            if sheet_name == "Area":
                sheets["Master"] = result
            _atomic_write_sheets(excel_path, sheets)
    except ValueError:
        raise
    except Exception as exc:
        logger.error("upsert_station_row: write failed: %s", exc)
        raise
    return True


def get_station_info(excel_path: str, station_name: str) -> dict:
    try:
        excel_path = _safe_path(excel_path)
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path, sheet_name="Area")
            if not df.empty and "station_name" in df.columns:
                mask = df["station_name"] == station_name
                if mask.any():
                    row = df[mask].iloc[0].to_dict()
                    return {
                        "station_name": row.get("station_name", ""),
                        "loc_id":       row.get("loc_id", ""),
                    }
    except Exception as exc:
        logger.warning("get_station_info: %s", exc)
    return {}


def get_all_stations(excel_path: str) -> list:
    try:
        excel_path = _safe_path(excel_path)
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path, sheet_name="Area")
            if not df.empty and "station_name" in df.columns:
                return df["station_name"].dropna().unique().tolist()
    except Exception as exc:
        logger.warning("get_all_stations: %s", exc)
    return []
