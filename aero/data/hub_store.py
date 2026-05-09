"""
hub_store.py — Hub upload and report data persistence.

Two workbooks live under data/:
  1. HUB_UPLOADED_FILES.xlsx — raw hub FAMIS rows upserted on every user upload
  2. HUB_REPORT_DATA.xlsx   — computed hub health-monitor reports (4 sheets)

Mirrors the structure and security controls of excel_store.py.
"""

import logging
import os
from datetime import datetime

import pandas as pd

from aero import DATA_DIR

logger = logging.getLogger(__name__)

HUB_UPLOAD_PATH = os.path.join(DATA_DIR, "HUB_UPLOADED_FILES.xlsx")
HUB_REPORT_PATH = os.path.join(DATA_DIR, "HUB_REPORT_DATA.xlsx")

_FORMULA_START_CHARS = frozenset("=+-@|%")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _sanitize_cell(value: object) -> object:
    if isinstance(value, str) and value and value[0] in _FORMULA_START_CHARS:
        return "'" + value
    return value


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].map(_sanitize_cell)
    return df


def _atomic_write(path: str, sheets: dict) -> None:
    tmp = path + ".tmp"
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl", mode="w") as writer:
            for sheet_name, df in sheets.items():
                _sanitize_df(df).to_excel(writer, sheet_name=sheet_name, index=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


# ===================================================================
# 1. HUB UPLOADED DATA
# ===================================================================

def upsert_hub_upload(new_df: pd.DataFrame) -> int:
    """Upsert rows into HUB_UPLOADED_FILES.xlsx. Key: date + loc_id."""
    _ensure_dir()

    new_df = new_df.copy()
    if "date" in new_df.columns:
        new_df["date"] = pd.to_datetime(new_df["date"]).dt.normalize()

    new_df["uploaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if os.path.exists(HUB_UPLOAD_PATH):
        try:
            existing = pd.read_excel(HUB_UPLOAD_PATH, sheet_name="HUB_DATA")
        except Exception as exc:
            logger.warning("upsert_hub_upload: could not read existing file: %s", exc)
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

    _atomic_write(HUB_UPLOAD_PATH, {"HUB_DATA": result})
    return len(new_df)


def read_hub_uploads() -> pd.DataFrame:
    if not os.path.exists(HUB_UPLOAD_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_excel(HUB_UPLOAD_PATH, sheet_name="HUB_DATA")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df
    except Exception as exc:
        logger.warning("read_hub_uploads: could not read file: %s", exc)
        return pd.DataFrame()


# ===================================================================
# 2. HUB REPORT DATA
# ===================================================================

def save_hub_reports(
    area_rows: list,
    resource_rows: list,
    courier_rows: list,
    report_date: str = None,
) -> bool:
    _ensure_dir()

    area_df = pd.DataFrame(area_rows) if area_rows else pd.DataFrame()
    resource_df = pd.DataFrame(resource_rows) if resource_rows else pd.DataFrame()
    courier_df = pd.DataFrame(courier_rows) if courier_rows else pd.DataFrame()

    total_df = _build_total_summary(area_df, resource_df, courier_df)

    if os.path.exists(HUB_REPORT_PATH):
        try:
            existing_area = pd.read_excel(HUB_REPORT_PATH, sheet_name="AREA HEALTH SUMMARY")
        except Exception as exc:
            logger.warning("save_hub_reports: could not read AREA sheet: %s", exc)
            existing_area = pd.DataFrame()
        try:
            existing_resource = pd.read_excel(HUB_REPORT_PATH, sheet_name="RESOURCE HEALTH SUMMARY")
        except Exception as exc:
            logger.warning("save_hub_reports: could not read RESOURCE sheet: %s", exc)
            existing_resource = pd.DataFrame()
        try:
            existing_courier = pd.read_excel(HUB_REPORT_PATH, sheet_name="COURIER HEALTH SUMMARY")
        except Exception as exc:
            logger.warning("save_hub_reports: could not read COURIER sheet: %s", exc)
            existing_courier = pd.DataFrame()

        area_df = _upsert_report_df(existing_area, area_df)
        resource_df = _upsert_report_df(existing_resource, resource_df)
        courier_df = _upsert_report_df(existing_courier, courier_df)
        total_df = _build_total_summary(area_df, resource_df, courier_df)

    _atomic_write(HUB_REPORT_PATH, {
        "TOTAL SUMMARY":           total_df,
        "AREA HEALTH SUMMARY":     area_df,
        "RESOURCE HEALTH SUMMARY": resource_df,
        "COURIER HEALTH SUMMARY":  courier_df,
    })
    return True


def read_hub_report_sheet(sheet_name: str) -> pd.DataFrame:
    if not os.path.exists(HUB_REPORT_PATH):
        return pd.DataFrame()
    try:
        return pd.read_excel(HUB_REPORT_PATH, sheet_name=sheet_name)
    except Exception as exc:
        logger.warning("read_hub_report_sheet('%s'): %s", sheet_name, exc)
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


def _build_total_summary(area_df, resource_df, courier_df):
    rows = []
    if not area_df.empty and "DATE" in area_df.columns and "LOC ID" in area_df.columns:
        for _, r in area_df.iterrows():
            rows.append({
                "DATE": r.get("DATE", ""),
                "LOC ID": r.get("LOC ID", ""),
                "VOLUME": r.get("VOLUME", ""),
                "AREA STATUS": r.get("STATUS", ""),
                "RESOURCE STATUS": "",
                "COURIER STATUS": "",
            })
    if not resource_df.empty and "DATE" in resource_df.columns and "LOC ID" in resource_df.columns:
        for _, r in resource_df.iterrows():
            match = next((i for i, row in enumerate(rows) if row["DATE"] == r.get("DATE") and row["LOC ID"] == r.get("LOC ID")), None)
            if match is not None:
                rows[match]["RESOURCE STATUS"] = r.get("STATUS", "")
            else:
                rows.append({
                    "DATE": r.get("DATE", ""),
                    "LOC ID": r.get("LOC ID", ""),
                    "VOLUME": r.get("VOLUME", ""),
                    "AREA STATUS": "",
                    "RESOURCE STATUS": r.get("STATUS", ""),
                    "COURIER STATUS": "",
                })
    if not courier_df.empty and "DATE" in courier_df.columns and "LOC ID" in courier_df.columns:
        for _, r in courier_df.iterrows():
            match = next((i for i, row in enumerate(rows) if row["DATE"] == r.get("DATE") and row["LOC ID"] == r.get("LOC ID")), None)
            if match is not None:
                rows[match]["COURIER STATUS"] = r.get("STATUS", "")
            else:
                rows.append({
                    "DATE": r.get("DATE", ""),
                    "LOC ID": r.get("LOC ID", ""),
                    "VOLUME": r.get("VOLUME", ""),
                    "AREA STATUS": "",
                    "RESOURCE STATUS": "",
                    "COURIER STATUS": r.get("STATUS", ""),
                })
    return pd.DataFrame(rows) if rows else pd.DataFrame()
