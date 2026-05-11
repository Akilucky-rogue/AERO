"""
postgres.py — PostgreSQL connector for AERO health data persistence.

Reads connection parameters from environment variables.  All required
variables must be set; a RuntimeError is raised at module load if any
are missing, so misconfiguration is caught before the first DB call.

Connection pooling (DL-003): a ThreadedConnectionPool (min=1, max=5) is
shared across Streamlit reruns, avoiding the cost of a fresh TCP handshake
on every user interaction.
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime

from dotenv import load_dotenv

# psycopg2 is optional — app runs in Excel-only mode without it.
# The lazy import in health_monitor.py is also guarded with try/except.
try:
    import psycopg2  # type: ignore
    from psycopg2 import pool as pg_pool  # type: ignore
    from psycopg2.extras import execute_values  # type: ignore
    _PG_AVAILABLE = True
except ImportError:
    psycopg2 = None  # type: ignore
    pg_pool = None  # type: ignore
    execute_values = None  # type: ignore
    _PG_AVAILABLE = False

load_dotenv()

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")


# ---------------------------------------------------------------------------
# Environment validation (SEC-004, SEC-012)
# ---------------------------------------------------------------------------

def _validate_db_config() -> dict:
    """Read and validate all required DB env vars.

    Raises RuntimeError with a descriptive message if POSTGRES_PASSWORD is
    absent or empty, so misconfiguration surfaces immediately rather than
    silently connecting with an empty password.
    """
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD environment variable is not set or is empty. "
            "Add it to your .env file before starting the application.  "
            "See .env.example for the full list of required variables."
        )
    port_str = os.getenv("POSTGRES_PORT", "5432")
    try:
        port = int(port_str)
    except ValueError as exc:
        raise RuntimeError(
            f"POSTGRES_PORT must be an integer, got: {port_str!r}"
        ) from exc
    return {
        "host":     os.getenv("POSTGRES_HOST", "localhost"),
        "port":     port,
        "dbname":   os.getenv("POSTGRES_DB",   "aero_planner"),
        "user":     os.getenv("POSTGRES_USER",  "postgres"),
        "password": password,
    }


# Build config once at module import.  The app continues without Postgres
# (Excel-only mode) when the password is absent; the error is logged so
# operators know what to fix for full functionality.
try:
    _DB_CONFIG: dict = _validate_db_config()
    _POSTGRES_AVAILABLE: bool = True
except RuntimeError as _cfg_err:
    logger.warning("PostgreSQL unavailable: %s", _cfg_err)
    _DB_CONFIG = {}
    _POSTGRES_AVAILABLE = False


# ---------------------------------------------------------------------------
# Connection pool (DL-003)
# ---------------------------------------------------------------------------

_pool: pg_pool.ThreadedConnectionPool | None = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not _POSTGRES_AVAILABLE:
            raise RuntimeError(
                "PostgreSQL is not configured.  Set POSTGRES_PASSWORD (and other "
                "POSTGRES_* vars) in your .env file.  See .env.example."
            )
        _pool = pg_pool.ThreadedConnectionPool(1, 5, **_DB_CONFIG)
    return _pool


@contextmanager
def _connection():
    """Context manager: borrow a pooled connection, commit on exit, rollback on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_connection():
    """Return a raw connection from the pool.  Caller must call putconn() when done."""
    return _get_pool().getconn()


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------

def run_schema() -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
                sql = f.read()
            cur.execute(sql)


def ensure_tables() -> None:
    run_schema()


# ---------------------------------------------------------------------------
# Data operations
# ---------------------------------------------------------------------------

def insert_upload_record(
    file_name: str,
    total_records: int,
    stations_count: int,
    date_from,
    date_to,
) -> int:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO upload_history
                    (file_name, total_records, stations_count, date_range_from, date_range_to)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING upload_id;
                """,
                (file_name, total_records, stations_count, date_from, date_to),
            )
            return cur.fetchone()[0]


def upsert_health_data(records: list, upload_id: int) -> int:
    if not records:
        return 0

    rows = []
    for r in records:
        report_date = r.get("report_date")
        if isinstance(report_date, str):
            report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        rows.append((
            r.get("loc_id"),
            report_date,
            upload_id,
            r.get("pk_gross_tot") or 0,
            r.get("calculated_area") or 0,
            r.get("area_status") or "UNKNOWN",
            r.get("calculated_agents") or 0,
            r.get("resource_status") or "UNKNOWN",
            r.get("calculated_couriers") or 0,
            r.get("courier_status") or "UNKNOWN",
            datetime.utcnow(),
        ))

    with _connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO station_health (
                    loc_id, report_date, upload_id,
                    pk_gross_tot,
                    calculated_area, area_status,
                    calculated_agents, resource_status,
                    calculated_couriers, courier_status,
                    published_at
                ) VALUES %s
                ON CONFLICT (loc_id, report_date)
                DO UPDATE SET
                    upload_id = EXCLUDED.upload_id,
                    pk_gross_tot = EXCLUDED.pk_gross_tot,
                    calculated_area = EXCLUDED.calculated_area,
                    area_status = EXCLUDED.area_status,
                    calculated_agents = EXCLUDED.calculated_agents,
                    resource_status = EXCLUDED.resource_status,
                    calculated_couriers = EXCLUDED.calculated_couriers,
                    courier_status = EXCLUDED.courier_status,
                    published_at = EXCLUDED.published_at;
            """, rows)
    return len(rows)
ulated_agents = EXCLUDED.calculated_agents,
                    resource_status = EXCLUDED.resource_status,
                    calculated_couriers = EXCLUDED.calculated_couriers,
                    courier_status = EXCLUDED.courier_status,
                    published_at = EXCLUDED.published_at;
            """, rows)
    return len(rows)
rows)
