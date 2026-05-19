"""
famis_store.py — PostgreSQL persistence layer for FAMIS volume data.

Public API
----------
db_available()               → True if psycopg2 + connection work
ensure_famis_tables()        → create tables + indexes if absent
upsert_famis_data(df, fname) → bulk upsert; returns metadata dict
load_famis_from_db()         → return full DataFrame from DB
famis_row_count()            → total rows currently in DB
get_famis_upload_log(n)      → last n upload records as list of dicts
"""

import logging
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical FAMIS columns (DataFrame name → DB column name)
_COL_MAP = {
    "loc_id":         "loc_id",
    "date":           "report_date",
    "pk_gross_tot":   "pk_gross_tot",
    "pk_gross_inb":   "pk_gross_inb",
    "pk_gross_outb":  "pk_gross_outb",
    "pk_oda":         "pk_oda",
    "pk_opa":         "pk_opa",
    "pk_roc":         "pk_roc",
    "fte_tot":        "fte_tot",
    "st_cr_or":       "st_cr_or",
    "pk_fte":         "pk_fte",
    "pk_cr_or":       "pk_cr_or",
}

_BATCH_SIZE = 10_000


def db_available() -> bool:
    """Return True if psycopg2 is installed and a connection succeeds."""
    try:
        from aero.data.postgres import _get_pool  # type: ignore
        pool = _get_pool()
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        pool.putconn(conn)
        return True
    except Exception as exc:
        logger.debug("FAMIS DB not available: %s", exc)
        return False


def ensure_famis_tables() -> None:
    """Apply the FAMIS section of schema.sql (idempotent)."""
    from aero.data.postgres import _get_pool  # type: ignore
    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    ddl = open(schema_path, encoding="utf-8").read()
    marker = "-- FAMIS VOLUME DATA"
    idx = ddl.find(marker)
    famis_ddl = ddl[idx:] if idx != -1 else ""
    if not famis_ddl.strip():
        logger.warning("FAMIS DDL section not found in schema.sql")
        return
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(famis_ddl)
        conn.commit()
        logger.info("FAMIS tables ensured")
    finally:
        pool.putconn(conn)


def upsert_famis_data(df: pd.DataFrame, filename: str = "unknown") -> dict:
    """Upsert all rows in *df* into famis_data.

    Returns a metadata dict:
        rows_upserted, total_rows_db, uploaded_at, filename
    """
    try:
        from psycopg2.extras import execute_values  # type: ignore
    except ImportError as exc:
        raise RuntimeError("psycopg2 not installed") from exc
    from aero.data.postgres import _get_pool  # type: ignore

    df = df.copy()

    # Normalise date column
    date_col = "date" if "date" in df.columns else None
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date
        df = df[df[date_col].notna()]

    if df.empty:
        return {"rows_upserted": 0, "total_rows_db": 0,
                "uploaded_at": datetime.utcnow(), "filename": filename}

    # Build column lists from what is actually present
    present_df  = [df_col for df_col, _ in _COL_MAP.items() if df_col in df.columns]
    present_db  = [_COL_MAP[c] for c in present_df]

    sub = df[present_df].copy()
    sub.columns = present_db

    # Convert numerics to Python native (psycopg2 requirement)
    for col in sub.select_dtypes(include=["float64", "float32"]).columns:
        sub[col] = sub[col].where(sub[col].notna(), None)

    upsert_cols = list(sub.columns)
    non_pk = [c for c in upsert_cols if c not in ("loc_id", "report_date")]

    upsert_sql = f"""
    INSERT INTO famis_data ({", ".join(upsert_cols)}, uploaded_at)
    VALUES %s
    ON CONFLICT (loc_id, report_date) DO UPDATE SET
        {", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)},
        uploaded_at = NOW()
    """

    now = datetime.utcnow()
    rows_upserted = 0
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            for start in range(0, len(sub), _BATCH_SIZE):
                batch = sub.iloc[start:start + _BATCH_SIZE]
                records = [
                    tuple(row[c] if c in row.index else None for c in upsert_cols) + (now,)
                    for _, row in batch.iterrows()
                ]
                execute_values(cur, upsert_sql, records, page_size=2_000)
                rows_upserted += len(records)

            cur.execute("SELECT COUNT(*) FROM famis_data")
            total = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO famis_upload_log (filename, rows_upserted, total_rows_db)
                VALUES (%s, %s, %s)
                RETURNING uploaded_at
                """,
                (filename, rows_upserted, total),
            )
            uploaded_at = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)

    return {
        "rows_upserted": rows_upserted,
        "total_rows_db": total,
        "uploaded_at":   uploaded_at,
        "filename":      filename,
    }


def load_famis_from_db() -> pd.DataFrame:
    """Load all FAMIS rows from the DB into a DataFrame."""
    from aero.data.postgres import _get_pool  # type: ignore
    sql = """
        SELECT loc_id, report_date AS date,
               pk_gross_tot, pk_gross_inb, pk_gross_outb,
               pk_oda, pk_opa, pk_roc, fte_tot, st_cr_or, pk_fte, pk_cr_or
        FROM famis_data
        ORDER BY report_date, loc_id
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        df = pd.read_sql(sql, conn)
    finally:
        pool.putconn(conn)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    return df


def famis_row_count() -> int:
    """Return the number of rows currently in famis_data."""
    from aero.data.postgres import _get_pool  # type: ignore
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM famis_data")
            return cur.fetchone()[0]
    finally:
        pool.putconn(conn)


def get_famis_upload_log(n: int = 10) -> list:
    """Return the last *n* upload log entries as a list of dicts."""
    from aero.data.postgres import _get_pool  # type: ignore
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filename, rows_upserted, total_rows_db, uploaded_at
                FROM famis_upload_log
                ORDER BY uploaded_at DESC
                LIMIT %s
                """,
                (n,),
            )
            cols = ["filename", "rows_upserted", "total_rows_db", "uploaded_at"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        pool.putconn(conn)
