"""
nsl_store.py — PostgreSQL persistence layer for NSL Analytics data.

Public API
----------
ensure_nsl_tables()          → create tables + indexes if absent
upsert_nsl_data(df, filename, user) → bulk upsert; returns metadata dict
load_nsl_from_db()           → return full DataFrame from DB
get_nsl_upload_log(n)        → last n upload records
nsl_row_count()              → total rows currently in DB
db_available()               → True if psycopg2 + connection work
"""

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# ── column map: DataFrame col → DB col ───────────────────────────────────────
_COL_MAP = {
    "shp_trk_nbr":            "shp_trk_nbr",
    "month_date":             "month_date",
    "weekending_dt":          "weekending_dt",
    "svc_commit_dt":          "svc_commit_dt",
    "shp_dt":                 "shp_dt",
    "pckup_scan_dt":          "pckup_scan_dt",
    "pod_scan_dt":            "pod_scan_dt",
    "shpr_co_nm":             "shpr_co_nm",
    "orig_loc_cd":            "orig_loc_cd",
    "dest_loc_cd":            "dest_loc_cd",
    "orig_region":            "orig_region",
    "dest_region":            "dest_region",
    "orig_market_cd":         "orig_market_cd",
    "dest_market_cd":         "dest_market_cd",
    "orig_subregion":         "orig_subregion",
    "dest_subregion":         "dest_subregion",
    "Service":                "service",
    "Service_Detail":         "service_detail",
    "Product":                "product",
    "Bucket":                 "bucket",
    "pof_cause":              "pof_cause",
    "MBG_Class":              "mbg_class",
    "NSL_OT_VOL":             "nsl_ot_vol",
    "MBG_OT_VOL":             "mbg_ot_vol",
    "NSL_F_VOL":              "nsl_f_vol",
    "MBG_F_VOL":              "mbg_f_vol",
    "TOT_VOL":                "tot_vol",
    "pkg_pckup_scan_typ_cd":  "pkg_pckup_scan_typ_cd",
    "pkg_pckup_excp_typ_cd":  "pkg_pckup_excp_typ_cd",
    "pckup_stop_typ_cd":      "pckup_stop_typ_cd",
    "pof_region_cd":          "pof_region_cd",
    "pof_loc_cd":             "pof_loc_cd",
}

_DB_COLS = list(_COL_MAP.values())          # ordered DB column names
_DF_COLS = list(_COL_MAP.keys())            # matching DataFrame column names

_UPSERT_SQL = f"""
INSERT INTO nsl_shipments ({", ".join(_DB_COLS)}, updated_at)
VALUES %s
ON CONFLICT (shp_trk_nbr) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in _DB_COLS if c != "shp_trk_nbr")},
    updated_at = NOW()
"""

_BATCH_SIZE = 50_000   # rows per execute_values call


def db_available() -> bool:
    """Return True if psycopg2 is installed and a test connection succeeds."""
    try:
        from aero.data.postgres import get_connection  # type: ignore
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        logger.debug("DB not available: %s", e)
        return False


def ensure_nsl_tables() -> None:
    """Apply the NSL portion of schema.sql (idempotent — IF NOT EXISTS)."""
    import os
    from aero.data.postgres import get_connection  # type: ignore

    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    ddl = open(schema_path).read()

    # Extract only the NSL section to avoid re-running the full schema
    marker = "-- NSL ANALYTICS TABLES"
    idx = ddl.find(marker)
    nsl_ddl = ddl[idx:] if idx != -1 else ddl

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(nsl_ddl)
        conn.commit()
    logger.info("NSL tables ensured")


def upsert_nsl_data(df: pd.DataFrame, filename: str,
                     uploaded_by: str = "system") -> dict:
    """Upsert all rows in *df* into nsl_shipments.

    Returns a metadata dict:
        rows_upserted, total_rows_db, uploaded_at, filename
    """
    from aero.data.postgres import get_connection  # type: ignore
    try:
        from psycopg2.extras import execute_values  # type: ignore
    except ImportError as e:
        raise RuntimeError("psycopg2 not installed") from e

    # ── select + rename only the columns we have ─────────────────────────────
    present_df_cols = [c for c in _DF_COLS if c in df.columns]
    present_db_cols = [_COL_MAP[c] for c in present_df_cols]

    sub = df[present_df_cols].copy()
    sub.columns = present_db_cols

    # Ensure shp_trk_nbr is present and non-null
    if "shp_trk_nbr" not in sub.columns:
        raise ValueError("shp_trk_nbr column missing — cannot upsert without a primary key")
    sub = sub[sub["shp_trk_nbr"].notna()].copy()
    sub["shp_trk_nbr"] = sub["shp_trk_nbr"].astype(str).str.strip()
    sub = sub[sub["shp_trk_nbr"] != ""]

    # Convert object columns to Python-native types for psycopg2
    for col in sub.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        sub[col] = sub[col].dt.date.where(sub[col].notna(), None)
    for col in sub.select_dtypes(include=["float64", "float32"]).columns:
        sub[col] = sub[col].where(sub[col].notna(), None)

    # Build ordered column list matching _UPSERT_SQL
    upsert_cols = [c for c in _DB_COLS if c in sub.columns]
    upsert_sql = f"""
    INSERT INTO nsl_shipments ({", ".join(upsert_cols)}, updated_at)
    VALUES %s
    ON CONFLICT (shp_trk_nbr) DO UPDATE SET
        {", ".join(f"{c} = EXCLUDED.{c}" for c in upsert_cols if c != "shp_trk_nbr")},
        updated_at = NOW()
    """

    rows_upserted = 0
    now = datetime.utcnow()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Batch upsert
            for start in range(0, len(sub), _BATCH_SIZE):
                batch = sub.iloc[start:start + _BATCH_SIZE]
                records = [
                    tuple(row[c] if c in row.index else None for c in upsert_cols) + (now,)
                    for _, row in batch.iterrows()
                ]
                execute_values(cur, upsert_sql, records, page_size=5_000)
                rows_upserted += len(records)

            # Update upload log
            cur.execute(
                """
                INSERT INTO nsl_upload_log (filename, rows_upserted, total_rows_db, uploaded_by)
                VALUES (%s, %s,
                    (SELECT COUNT(*) FROM nsl_shipments),
                    %s)
                RETURNING id, uploaded_at, total_rows_db
                """,
                (filename, rows_upserted, uploaded_by),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "rows_upserted": rows_upserted,
        "total_rows_db": row[2],
        "uploaded_at":   row[1],
        "filename":      filename,
    }


def load_nsl_from_db() -> pd.DataFrame:
    """Load all NSL shipment rows from the DB into a DataFrame."""
    from aero.data.postgres import get_connection  # type: ignore

    sql = f"SELECT {', '.join(_DB_COLS)}, updated_at FROM nsl_shipments"
    with get_connection() as conn:
        df = pd.read_sql(sql, conn)

    # Rename DB cols back to app-expected names
    reverse_map = {v: k for k, v in _COL_MAP.items()}
    df = df.rename(columns=reverse_map)

    # Parse dates
    for col in ["month_date", "weekending_dt", "svc_commit_dt",
                "shp_dt", "pckup_scan_dt", "pod_scan_dt"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def nsl_row_count() -> int:
    """Return the number of rows currently in nsl_shipments."""
    from aero.data.postgres import get_connection  # type: ignore
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM nsl_shipments")
            return cur.fetchone()[0]


def get_nsl_upload_log(n: int = 10) -> list:
    """Return the last *n* upload log entries as a list of dicts."""
    from aero.data.postgres import get_connection  # type: ignore
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filename, rows_upserted, total_rows_db, uploaded_at, uploaded_by
                FROM nsl_upload_log
                ORDER BY uploaded_at DESC
                LIMIT %s
                """,
                (n,),
            )
            cols = ["filename", "rows_upserted", "total_rows_db", "uploaded_at", "uploaded_by"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
