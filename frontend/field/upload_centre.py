# ============================================================
# AERO — Field Data Upload Centre  [frontend/field/upload_centre.py]
# Handles FAMIS volume data and Facility Master uploads.
# Auto-upserts to PostgreSQL (with Excel fallback).
# Saves a local copy to docs/ for archival.
# NO publish / save buttons — all persistence is automatic.
# ============================================================
import io
import os
import sys
import logging
from datetime import datetime

# Ensure project root is on path (needed when Streamlit runs this directly)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.ui.components import render_info_banner, render_kpi_card, _PURPLE, _ORANGE, _GREEN, _RED
from aero.data.inbox_loader import parse_famis_file
from aero.data.excel_store import upsert_famis_upload, read_famis_uploads

logger = logging.getLogger(__name__)

# Local archive directory (always relative to project root)
_DOCS_DIR = os.path.join(_PROJECT_ROOT, "docs")
os.makedirs(_DOCS_DIR, exist_ok=True)

# ── DB layer (optional) ───────────────────────────────────────────────────────
try:
    from aero.data.famis_store import (  # type: ignore
        db_available as _famis_db_available,
        ensure_famis_tables as _ensure_famis_tables,
        upsert_famis_data as _upsert_famis_db,
        load_famis_from_db as _load_famis_db,
        famis_row_count as _famis_row_count,
        get_famis_upload_log as _get_famis_upload_log,
    )
    _FAMIS_DB_OK = True
except Exception:
    _FAMIS_DB_OK = False


# ── Helpers ───────────────────────────────────────────────────────────────────
def _save_local(data: bytes, filename: str, subfolder: str) -> str:
    """Save raw bytes to docs/<subfolder>/<timestamp>_<filename>."""
    folder = os.path.join(_DOCS_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(folder, f"{ts}_{filename}")
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def _sync_session(df: pd.DataFrame, filename: str) -> None:
    """Push FAMIS data into all expected session-state keys."""
    st.session_state["famis_data"]      = df
    st.session_state["famis_data_raw"]  = df.copy()
    st.session_state["famis_df"]        = df          # area_planner compat
    st.session_state["famis_file_name"] = filename
    st.session_state["famis_file_id"]   = filename
    # Reset downstream selections so they re-derive from new data
    st.session_state.pop("selected_date", None)
    st.session_state.pop("_famis_inbox_checked", None)


def _process_famis(file_bytes: bytes, filename: str, file_type: str):
    """Parse → upsert DB → upsert Excel → sync session."""
    df = parse_famis_file(io.BytesIO(file_bytes))
    df["file_type"] = file_type

    # Save local archive
    _save_local(file_bytes, filename, "famis")

    # Upsert to PostgreSQL (preferred)
    db_ok = False
    if _FAMIS_DB_OK:
        try:
            _ensure_famis_tables()
            if _famis_db_available():
                meta = _upsert_famis_db(df, filename)
                logger.info("FAMIS upserted %d rows to DB", meta["rows_upserted"])
                db_ok = True
        except Exception as exc:
            logger.warning("FAMIS DB upsert failed: %s", exc)

    # Always upsert to Excel store as fallback backup
    try:
        upsert_famis_upload(df)
    except Exception as exc:
        logger.warning("FAMIS Excel upsert failed: %s", exc)

    _sync_session(df, filename)
    return df, db_ok


# ── Page render ───────────────────────────────────────────────────────────────
render_header(
    "DATA UPLOAD CENTRE",
    "Upload & Manage FAMIS Volume Data and Facility Master Files",
    logo_height=80,
    badge="FIELD",
)

st.markdown("<br>", unsafe_allow_html=True)

# ── Connection status banner ──────────────────────────────────────────────────
_db_live = _FAMIS_DB_OK and _famis_db_available() if _FAMIS_DB_OK else False
_row_cnt = 0
if _db_live:
    try:
        _row_cnt = _famis_row_count()
    except Exception:
        _row_cnt = 0
    render_info_banner(
        "PostgreSQL Active",
        f"Database connected · <b>{_row_cnt:,}</b> FAMIS records stored · "
        "All uploads are automatically persisted to PostgreSQL and archived to <code>docs/famis/</code>.",
        accent=_GREEN,
    )
else:
    render_info_banner(
        "Local Storage Mode",
        "PostgreSQL not configured — uploads saved to <code>data/FAMIS_UPLOADED_FILES.xlsx</code> "
        "and archived to <code>docs/famis/</code>. "
        "Configure PostgreSQL for full historical analytics.",
        accent=_ORANGE,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── KPI Row ───────────────────────────────────────────────────────────────────
famis_in_session  = st.session_state.get("famis_data")
master_in_session = st.session_state.get("master_data")

kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
with kpi_c1:
    if famis_in_session is not None and not famis_in_session.empty:
        n_rows     = len(famis_in_session)
        n_stations = famis_in_session["loc_id"].nunique() if "loc_id" in famis_in_session.columns else 0
        render_kpi_card("FAMIS Records", f"{n_rows:,}", f"{n_stations} stations", color=_GREEN)
    else:
        render_kpi_card("FAMIS Records", "—", "No data loaded", color=_ORANGE)
with kpi_c2:
    if _db_live:
        render_kpi_card("DB Records", f"{_row_cnt:,}", "PostgreSQL", color=_PURPLE)
    else:
        render_kpi_card("DB Status", "Offline", "Not configured", color="#888")
with kpi_c3:
    if famis_in_session is not None and "date" in famis_in_session.columns:
        latest = pd.to_datetime(famis_in_session["date"]).max()
        render_kpi_card("Latest Date", latest.strftime("%d %b %Y"), "in loaded data", color=_PURPLE)
    else:
        render_kpi_card("Latest Date", "—", "No data loaded", color="#888")
with kpi_c4:
    render_kpi_card(
        "Master Data",
        "Loaded" if master_in_session is not None else "Not Loaded",
        "station_planner_master.xlsx",
        color=_GREEN if master_in_session is not None else _ORANGE,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FAMIS Volume Upload
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(90deg,#4D148C 0%,#7B2FBE 100%);
    border-radius:10px;padding:14px 20px;margin-bottom:16px;">
    <div style="color:#fff;font-size:16px;font-weight:700;letter-spacing:0.4px;">
        📥&nbsp;&nbsp;FAMIS VOLUME DATA
    </div>
    <div style="color:#E8D5FF;font-size:12px;margin-top:4px;">
        Weekly FAMIS REPORT (.xlsx) · Daily or Monthly volume exports (.xlsx / .csv / .txt)
    </div>
</div>
""", unsafe_allow_html=True)

f_col1, f_col2 = st.columns([3, 1])
with f_col2:
    file_type = st.selectbox(
        "File Type",
        ["Weekly", "Daily", "Monthly"],
        key="upload_file_type",
        help="Select the reporting period of the file being uploaded.",
    )
with f_col1:
    famis_file = st.file_uploader(
        "Upload FAMIS file",
        type=["xlsx", "xls", "csv", "txt"],
        key="famis_uploader",
        label_visibility="collapsed",
    )

if famis_file is not None:
    file_bytes = famis_file.read()
    with st.spinner(f"Processing {famis_file.name} …"):
        try:
            df, db_ok = _process_famis(file_bytes, famis_file.name, file_type)
            n_rows     = len(df)
            n_stations = df["loc_id"].nunique() if "loc_id" in df.columns else 0
            date_min   = pd.to_datetime(df["date"]).min().strftime("%d %b %Y") if "date" in df.columns else "—"
            date_max   = pd.to_datetime(df["date"]).max().strftime("%d %b %Y") if "date" in df.columns else "—"
            storage    = "PostgreSQL" if db_ok else "Excel store"
            st.success(
                f"✅ **{famis_file.name}** processed — "
                f"**{n_rows:,}** rows · **{n_stations}** stations · "
                f"**{date_min} → {date_max}** · Saved to {storage}"
            )
        except Exception as exc:
            st.error(f"❌ Could not parse file: {exc}")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Facility Master Upload
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(90deg,#1A5276 0%,#2874A6 100%);
    border-radius:10px;padding:14px 20px;margin-bottom:16px;">
    <div style="color:#fff;font-size:16px;font-weight:700;letter-spacing:0.4px;">
        🗂️&nbsp;&nbsp;FACILITY MASTER DATA
    </div>
    <div style="color:#D6EAF8;font-size:12px;margin-top:4px;">
        Station capacity, agent counts and area baselines (.xlsx / .csv)
    </div>
</div>
""", unsafe_allow_html=True)

_MASTER_VALID = {
    "loc_id", "total_facility_area", "ops_area",
    "current_total_osa", "current_total_agents",
    "current_total_couriers", "couriers_available",
    "station_name", "region",
}

master_file = st.file_uploader(
    "Upload Facility Master file",
    type=["xlsx", "xls", "csv"],
    key="master_uploader",
    label_visibility="collapsed",
)

if master_file is not None:
    try:
        raw = master_file.read()
        _save_local(raw, master_file.name, "master")
        mdf = pd.read_csv(io.BytesIO(raw)) if master_file.name.endswith(".csv") else pd.read_excel(io.BytesIO(raw))
        # Normalise columns
        mdf.columns = (
            mdf.columns.astype(str).str.strip().str.lower()
            .str.replace(r"[\s/\\]+", "_", regex=True)
            .str.replace(r"[#%]", "", regex=True)
            .str.strip("_")
        )
        _ALIASES = {
            "location_id": "loc_id", "location": "loc_id",
            "total_agents": "current_total_agents",
            "total_couriers": "current_total_couriers",
            "facility_area": "total_facility_area",
        }
        mdf = mdf.rename(columns={k: v for k, v in _ALIASES.items() if k in mdf.columns})

        if "loc_id" not in mdf.columns:
            st.error("❌ Master file must contain a **loc_id** column.")
        else:
            st.session_state["master_data"] = mdf
            shown_cols = ", ".join(c for c in mdf.columns if c in _MASTER_VALID)
            st.success(
                f"✅ **{master_file.name}** loaded — **{len(mdf)}** stations · Columns: {shown_cols}"
            )
    except Exception as exc:
        st.error(f"❌ Could not parse master file: {exc}")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Upload History
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(90deg,#145A32 0%,#1E8449 100%);
    border-radius:10px;padding:14px 20px;margin-bottom:16px;">
    <div style="color:#fff;font-size:16px;font-weight:700;letter-spacing:0.4px;">
        🕒&nbsp;&nbsp;UPLOAD HISTORY
    </div>
    <div style="color:#D5F5E3;font-size:12px;margin-top:4px;">
        Last 10 FAMIS uploads stored in PostgreSQL or local Excel store
    </div>
</div>
""", unsafe_allow_html=True)

if _db_live:
    try:
        log = _get_famis_upload_log(10)
        if log:
            log_df = pd.DataFrame(log)
            log_df["uploaded_at"] = pd.to_datetime(log_df["uploaded_at"]).dt.strftime("%d %b %Y %H:%M")
            log_df = log_df.rename(columns={
                "filename": "File", "rows_upserted": "Rows Upserted",
                "total_rows_db": "Total in DB", "uploaded_at": "Uploaded At",
            })
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info("No upload history yet.")
    except Exception:
        st.info("Upload history unavailable.")
else:
    try:
        hist_df = read_famis_uploads()
        if not hist_df.empty:
            st.info(f"📂 Local store has **{len(hist_df):,}** FAMIS rows across "
                    f"**{hist_df['loc_id'].nunique() if 'loc_id' in hist_df.columns else '?'}** stations.")
        else:
            st.info("No previous uploads found in local store.")
    except Exception:
        st.info("No upload history available.")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Template Downloads
# ════════════════════════════════════════════════════════════════════════════
with st.expander("⬇️  Download Data Templates", expanded=False):
    dl1, dl2 = st.columns(2)
    with dl1:
        st.markdown("**FAMIS Volume Data Template**")
        st.caption("date · loc_id · pk_gross_tot · pk_gross_inb · pk_gross_outb · pk_oda · pk_opa · pk_roc · fte_tot")
        tpl = pd.DataFrame(
            [["2025-01-01", "ABCD", 1000, 600, 400, 50, 30, 200, 10]],
            columns=["date", "loc_id", "pk_gross_tot", "pk_gross_inb", "pk_gross_outb",
                     "pk_oda", "pk_opa", "pk_roc", "fte_tot"],
        )
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            tpl.to_excel(w, index=False, sheet_name="FAMIS")
        st.download_button(
            "⬇️ FAMIS Template", buf.getvalue(), "FAMIS_Template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with dl2:
        st.markdown("**Facility Master Data Template**")
        st.caption("loc_id · total_facility_area · ops_area · current_total_agents · current_total_couriers")
        tpl2 = pd.DataFrame(
            [["ABCD", 50000, 35000, 25, 12]],
            columns=["loc_id", "total_facility_area", "ops_area",
                     "current_total_agents", "current_total_couriers"],
        )
        buf2 = io.BytesIO()
        with pd.ExcelWriter(buf2, engine="openpyxl") as w:
            tpl2.to_excel(w, index=False, sheet_name="Master")
        st.download_button(
            "⬇️ Master Template", buf2.getvalue(), "Master_Template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

render_footer("FIELD")
