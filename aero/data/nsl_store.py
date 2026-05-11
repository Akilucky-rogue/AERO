# ============================================================
# AERO — NSL Data Store
# Handles NSL file parsing, model persistence (JSON),
# and daily prediction result storage (Excel).
# ============================================================
from __future__ import annotations

import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from aero import DATA_DIR

# ── File paths ───────────────────────────────────────────────
NSL_MODEL_PATH  = os.path.join(DATA_DIR, "NSL_MODEL.json")
NSL_PRED_PATH   = os.path.join(DATA_DIR, "NSL_PREDICTIONS.xlsx")


# ────────────────────────────────────────────────────────────
# NSL column mapping
# Maps the raw NSL/AWB column names → internal normalised names
# ────────────────────────────────────────────────────────────
_NSL_COL_MAP = {
    # AWB
    "shp_trk_nbr":       "awb_number",
    "awb":               "awb_number",
    "tracking_number":   "awb_number",
    "awb_number":        "awb_number",
    # Dates
    "shp_dt":            "ship_date",
    "ship_date":         "ship_date",
    "ship_dt":           "ship_date",
    "svc_commit_dt":     "commit_date",
    "commit_date":       "commit_date",
    "service_commit_date": "commit_date",
    "pod_scan_dt":       "pod_date",
    "pod_date":          "pod_date",
    # Origin
    "orig_loc_cd":       "orig_loc",
    "orig_loc":          "orig_loc",
    "origin_loc":        "orig_loc",
    "origin":            "orig_loc",
    "orig_market_cd":    "orig_market",
    "orig_region":       "orig_region",
    "orig_subregion":    "orig_subregion",
    # Destination
    "dest_loc_cd":       "dest_loc",
    "dest_loc":          "dest_loc",
    "destination_loc":   "dest_loc",
    "destination":       "dest_loc",
    "dest_market_cd":    "dest_market",
    "dest_market":       "dest_market",
    "dest_region":       "dest_region",
    "dest_subregion":    "dest_subregion",
    # Service
    "service":           "service_type",
    "service_type":      "service_type",
    "svc":               "service_type",
    "service_detail":    "service_detail",
    # Performance
    "nsl_ot_vol":        "nsl_ot",
    "nsl_ot":            "nsl_ot",
    "mbg_ot_vol":        "mbg_ot",
    "mbg_ot":            "mbg_ot",
    "nsl_f_vol":         "nsl_fail_vol",
    "mbg_f_vol":         "mbg_fail_vol",
    "tot_vol":           "tot_vol",
    "mbg_class":         "mbg_class",
    "bucket":            "bucket",
    # POF
    "pof_cause":         "pof_cause",
    "pof_cat_cd":        "pof_cat",
    "cat_cause_cd":      "cat_cause",
    "pof_loc_cd":        "pof_loc",
    # Shipper / recipient
    "shpr_co_nm":        "shipper",
    "recp_co_nm":        "recipient",
}

# Columns required for model building (the rest are optional enrichment)
_REQUIRED_FOR_MODEL = {"orig_loc", "dest_loc", "nsl_ot"}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase column names and apply _NSL_COL_MAP."""
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns=_NSL_COL_MAP)
    return df


def _parse_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse raw file bytes into a DataFrame based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    elif ext in (".csv",):
        # Try comma first, then tab
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, low_memory=False)
            if df.shape[1] < 5:
                df = pd.read_csv(io.BytesIO(file_bytes), sep="\t", dtype=str, low_memory=False)
        except Exception:
            df = pd.read_csv(io.BytesIO(file_bytes), sep="\t", dtype=str, low_memory=False)
    elif ext in (".txt",):
        # NSL files are tab-separated with quoted fields
        try:
            df = pd.read_csv(
                io.BytesIO(file_bytes), sep="\t", dtype=str,
                quotechar='"', low_memory=False
            )
            if df.shape[1] < 5:
                df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, low_memory=False)
        except Exception:
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, low_memory=False)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Upload .txt, .csv, or .xlsx")
    return df


def _cast_dates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def _cast_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


# ────────────────────────────────────────────────────────────
# Public: parse NSL training file
# ────────────────────────────────────────────────────────────
def parse_nsl_file(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    """
    Parse an NSL upload (txt/csv/xlsx) into a clean DataFrame
    ready for delay_predictor.build_model().

    Returns (df, meta) where meta contains row counts and date range.
    """
    raw = _parse_bytes(file_bytes, filename)
    df  = _normalise_columns(raw.copy())

    # Check required columns
    missing = _REQUIRED_FOR_MODEL - set(df.columns)
    if missing:
        raise ValueError(
            f"NSL file is missing required columns: {', '.join(missing)}. "
            f"Found: {', '.join(df.columns[:10])}…"
        )

    # Cast types
    df = _cast_dates(df, ["ship_date", "commit_date", "pod_date"])
    df = _cast_numeric(df, ["nsl_ot", "mbg_ot", "nsl_fail_vol", "mbg_fail_vol", "tot_vol"])

    # nsl_ot: treat 1 = on-time, 0 = failed; NSL_OT_VOL can be 0 or 1
    # some files store raw volume counts — treat >0 as on-time
    if "nsl_ot" in df.columns:
        df["nsl_ot"] = (df["nsl_ot"] > 0).astype(int)
    if "mbg_ot" in df.columns:
        df["mbg_ot"] = (df["mbg_ot"] > 0).astype(int)

    # Fill blanks
    for col in ["orig_loc", "dest_loc", "dest_market", "service_type", "pof_cause"]:
        if col in df.columns:
            df[col] = df[col].fillna("").str.strip()
            df[col] = df[col].replace("", None)

    # Derive dest_market from dest_region if missing
    if "dest_market" not in df.columns and "dest_region" in df.columns:
        df["dest_market"] = df["dest_region"]

    total_rows = len(df)
    failed_rows = int(df["nsl_ot"].eq(0).sum()) if "nsl_ot" in df.columns else 0
    on_time = total_rows - failed_rows

    date_min = df["ship_date"].min() if "ship_date" in df.columns else None
    date_max = df["ship_date"].max() if "ship_date" in df.columns else None

    meta = {
        "filename":    filename,
        "total_rows":  total_rows,
        "on_time":     on_time,
        "failed":      failed_rows,
        "nsl_ot_pct":  round(on_time / total_rows * 100, 1) if total_rows else 0,
        "date_min":    str(date_min.date()) if date_min and pd.notna(date_min) else "—",
        "date_max":    str(date_max.date()) if date_max and pd.notna(date_max) else "—",
        "columns":     list(df.columns),
    }
    return df, meta


# ────────────────────────────────────────────────────────────
# Public: parse daily AWB file
# ────────────────────────────────────────────────────────────
def parse_awb_file(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    """
    Parse a daily AWB upload for prediction.

    Minimum required columns: orig_loc + dest_loc (or AWB number)
    Additional columns improve prediction accuracy.

    Returns (df, meta).
    """
    raw = _parse_bytes(file_bytes, filename)
    df  = _normalise_columns(raw.copy())

    # Must have at minimum one of these
    loc_cols = {"orig_loc", "dest_loc"}
    if not loc_cols.intersection(df.columns):
        raise ValueError(
            "AWB file must contain at least 'orig_loc_cd' and 'dest_loc_cd' columns "
            "(or 'origin' / 'destination'). "
            f"Found columns: {', '.join(df.columns[:12])}…"
        )

    # Cast dates
    df = _cast_dates(df, ["ship_date", "commit_date", "pod_date"])

    # Fill blanks
    for col in ["orig_loc", "dest_loc", "dest_market", "service_type", "pof_cause"]:
        if col in df.columns:
            df[col] = df[col].fillna("").str.strip().replace("", None)

    # Ensure awb_number column exists
    if "awb_number" not in df.columns:
        df["awb_number"] = [f"AWB-{i+1:05d}" for i in range(len(df))]

    meta = {
        "filename":   filename,
        "total_awbs": len(df),
        "columns":    list(df.columns),
    }
    return df, meta


# ────────────────────────────────────────────────────────────
# Model persistence (JSON)
# ────────────────────────────────────────────────────────────
def save_model(model: dict, meta: dict | None = None) -> None:
    """Persist model dict + optional training metadata to JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {
        "model": model,
        "trained_at": datetime.utcnow().isoformat(),
        "meta": meta or {},
    }
    # JSON can't serialise numpy types — convert
    payload = _json_safe(payload)
    with open(NSL_MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_model() -> tuple[dict | None, dict | None]:
    """
    Load model from JSON.
    Returns (model_dict, meta_dict) or (None, None) if not trained yet.
    """
    if not os.path.exists(NSL_MODEL_PATH):
        return None, None
    try:
        with open(NSL_MODEL_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        model = payload.get("model")
        meta  = {
            "trained_at": payload.get("trained_at", "—"),
            **(payload.get("meta") or {}),
        }
        return model, meta
    except Exception:
        return None, None


def model_trained() -> bool:
    return os.path.exists(NSL_MODEL_PATH)


def delete_model() -> None:
    if os.path.exists(NSL_MODEL_PATH):
        os.remove(NSL_MODEL_PATH)


# ────────────────────────────────────────────────────────────
# Prediction results persistence (Excel)
# ────────────────────────────────────────────────────────────
def save_prediction_results(results_df: pd.DataFrame, session_label: str = "") -> None:
    """
    Append a prediction run to NSL_PREDICTIONS.xlsx.
    Each run is stored as a new sheet named by date+session.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    sheet_name = (
        datetime.utcnow().strftime("%Y%m%d_%H%M")
        + (f"_{session_label[:10]}" if session_label else "")
    )
    sheet_name = sheet_name[:31]  # Excel max

    # Drop internal columns
    df_out = results_df.drop(columns=[c for c in results_df.columns if c.startswith("_")], errors="ignore")

    if os.path.exists(NSL_PRED_PATH):
        with pd.ExcelWriter(NSL_PRED_PATH, engine="openpyxl", mode="a", if_sheet_exists="new") as w:
            df_out.to_excel(w, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(NSL_PRED_PATH, engine="openpyxl") as w:
            df_out.to_excel(w, sheet_name=sheet_name, index=False)


def load_prediction_history() -> dict[str, pd.DataFrame]:
    """Load all past prediction sessions from Excel. Returns {sheet_name: df}."""
    if not os.path.exists(NSL_PRED_PATH):
        return {}
    try:
        xl = pd.ExcelFile(NSL_PRED_PATH)
        return {s: xl.parse(s) for s in xl.sheet_names}
    except Exception:
        return {}


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────
def _json_safe(obj: Any) -> Any:
    """Recursively convert numpy/pandas types to native Python for JSON serialisation."""
    import numpy as np  # local import — only when saving
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and (obj != obj):  # NaN
        return None
    return obj
