# ============================================================
# AERO — Field Data Upload Centre  [frontend/field/upload_centre.py]
# Handles FAMIS volume data and Facility Master uploads.
# Auto-upserts to PostgreSQL (with Excel fallback).
# Saves a local copy to docs/ for archival.
# Auto-loads Station Master from persisted storage on startup.
# Maintains upload registry showing all uploaded files.
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
# pyrefly: ignore [missing-import]
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.ui.components import render_info_banner, render_kpi_card, _PURPLE, _ORANGE, _GREEN, _RED
from aero.data.inbox_loader import parse_famis_file
from aero.data.excel_store import (
    upsert_famis_upload,
    read_famis_uploads,
    upsert_famis_registry,
    read_famis_registry,
    upsert_master_data,
    read_master_data,
)

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


# ── Styling helpers ───────────────────────────────────────────────────────────
def _section_header(icon: str, title: str, subtitle: str, bg: str = "#4D148C", bg2: str = "#7B2FBE") -> None:
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,{bg} 0%,{bg2} 100%);
        border-radius:10px;padding:14px 20px;margin-bottom:16px;">
        <div style="color:#fff;font-size:16px;font-weight:700;letter-spacing:0.4px;">
            {icon}&nbsp;&nbsp;{title}
        </div>
        <div style="color:rgba(255,255,255,0.80);font-size:12px;margin-top:4px;">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _active_file_badge(filename: str, file_type: str, date_min: str, date_max: str, rows: int, stations: int) -> None:
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#F0FFF4 0%,#E6FFED 100%);
        border-left:5px solid #1E8449;
        border-radius:8px;
        padding:12px 16px;
        margin-bottom:12px;
    ">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <span style="font-size:18px;">✅</span>
            <span style="font-weight:700;color:#145A32;font-size:14px;">Active FAMIS Data</span>
            <span style="background:#1E8449;color:#fff;font-size:11px;font-weight:600;
                padding:2px 8px;border-radius:10px;margin-left:4px;">{file_type.upper()}</span>
        </div>
        <div style="font-family:monospace;font-size:13px;color:#1A5276;font-weight:600;">{filename}</div>
        <div style="color:#555;font-size:12px;margin-top:4px;">
            📅 {date_min} → {date_max} &nbsp;|&nbsp;
            📦 <b>{rows:,}</b> rows &nbsp;|&nbsp;
            📍 <b>{stations}</b> stations
        </div>
    </div>
    """, unsafe_allow_html=True)


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


def _make_display_name(original: str, file_type: str) -> str:
    """Generate a professional display name: FAMIS-12May2025-Daily."""
    try:
        # Try to extract date from filename if present (e.g. 2025-05-12, 20250512, 12-May-25)
        import re
        patterns = [
            r"(\d{4})[_\-]?(\d{2})[_\-]?(\d{2})",  # YYYY-MM-DD or YYYYMMDD
        ]
        for pat in patterns:
            m = re.search(pat, original)
            if m:
                y, mo, d = m.groups()
                from datetime import date as _date
                dt = _date(int(y), int(mo), int(d))
                label = dt.strftime("%d%b%Y")
                return f"FAMIS-{label}-{file_type}"
    except Exception:
        pass
    # Fall back to today's date
    label = datetime.now().strftime("%d%b%Y")
    return f"FAMIS-{label}-{file_type}"


def _sync_session(df: pd.DataFrame, filename: str, display_name: str) -> None:
    """Push FAMIS data into all expected session-state keys."""
    st.session_state["famis_data"]      = df
    st.session_state["famis_data_raw"]  = df.copy()
    st.session_state["famis_df"]        = df          # area_planner compat
    st.session_state["famis_file_name"] = display_name
    st.session_state["famis_file_id"]   = filename
    # Reset downstream selections so they re-derive from new data
    st.session_state.pop("selected_date", None)
    st.session_state.pop("_famis_inbox_checked", None)


def _process_famis(file_bytes: bytes, filename: str, file_type: str):
    """Parse → upsert DB → upsert Excel → update registry → sync session."""
    df = parse_famis_file(file_bytes)   # parse_famis_file wraps bytes in BytesIO internally
    df["file_type"] = file_type

    # Professional display name
    display_name = _make_display_name(filename, file_type)

    # Save local archive
    _save_local(file_bytes, filename, "famis")

    # Build metadata for registry
    date_min = pd.to_datetime(df["date"]).min().strftime("%d %b %Y") if "date" in df.columns else "—"
    date_max = pd.to_datetime(df["date"]).max().strftime("%d %b %Y") if "date" in df.columns else "—"
    n_stations = int(df["loc_id"].nunique()) if "loc_id" in df.columns else 0
    metadata = {
        "display_name":  display_name,
        "filename":      filename,
        "file_type":     file_type,
        "date_min":      date_min,
        "date_max":      date_max,
        "rows":          len(df),
        "stations":      n_stations,
        "uploaded_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

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

    # Update upload registry (always)
    try:
        upsert_famis_registry(metadata)
        # Invalidate cached registry in session so table refreshes
        st.session_state["famis_upload_registry"] = None
    except Exception as exc:
        logger.warning("FAMIS registry update failed: %s", exc)

    _sync_session(df, filename, display_name)
    return df, db_ok, metadata


def _load_registry() -> pd.DataFrame:
    """Return the upload registry, using session cache to avoid repeated I/O."""
    if st.session_state.get("famis_upload_registry") is not None:
        return st.session_state["famis_upload_registry"]
    try:
        reg = read_famis_registry()
    except Exception:
        reg = pd.DataFrame()
    st.session_state["famis_upload_registry"] = reg
    return reg


def _auto_load_master() -> None:
    """On first page load, restore master_data from persisted Excel if not in session."""
    if st.session_state.get("master_data") is not None:
        return  # already in session
    try:
        mdf = read_master_data()
        if not mdf.empty:
            st.session_state["master_data"] = mdf
            logger.info("Auto-loaded Station Master from FAMIS_META.xlsx (%d rows)", len(mdf))
    except Exception as exc:
        logger.warning("Auto-load master failed: %s", exc)


# ── Run auto-loads before rendering ──────────────────────────────────────────
_auto_load_master()

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
    if master_in_session is not None and not master_in_session.empty:
        master_stations = master_in_session["loc_id"].nunique() if "loc_id" in master_in_session.columns else len(master_in_session)
        render_kpi_card("Station Master", f"{master_stations} stations", "Auto-loaded", color=_GREEN)
    else:
        render_kpi_card("Master Data", "Not Loaded", "Upload below", color=_ORANGE)

st.markdown("<br>", unsafe_allow_html=True)

# ── Active file badge (when FAMIS data is in session) ────────────────────────
if famis_in_session is not None and not famis_in_session.empty:
    _fn   = st.session_state.get("famis_file_name") or st.session_state.get("famis_file_id") or "Unknown"
    _ft   = famis_in_session["file_type"].iloc[0] if "file_type" in famis_in_session.columns else "—"
    _dmin = pd.to_datetime(famis_in_session["date"]).min().strftime("%d %b %Y") if "date" in famis_in_session.columns else "—"
    _dmax = pd.to_datetime(famis_in_session["date"]).max().strftime("%d %b %Y") if "date" in famis_in_session.columns else "—"
    _nst  = int(famis_in_session["loc_id"].nunique()) if "loc_id" in famis_in_session.columns else 0
    _active_file_badge(_fn, _ft, _dmin, _dmax, len(famis_in_session), _nst)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FAMIS Volume Upload
# ════════════════════════════════════════════════════════════════════════════
_section_header("📥", "FAMIS VOLUME DATA",
                "Weekly FAMIS REPORT (.xlsx) · Daily or Monthly volume exports (.xlsx / .csv / .txt)")

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
            df, db_ok, meta = _process_famis(file_bytes, famis_file.name, file_type)
            storage = "PostgreSQL" if db_ok else "Excel store"
            st.success(
                f"✅ **{meta['display_name']}** uploaded — "
                f"**{meta['rows']:,}** rows · **{meta['stations']}** stations · "
                f"**{meta['date_min']} → {meta['date_max']}** · Saved to {storage}"
            )
        except Exception as exc:
            st.error(f"❌ Could not parse file: {exc}")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Facility Master Upload
# ════════════════════════════════════════════════════════════════════════════
_section_header("🗂️", "FACILITY MASTER DATA",
                "Station capacity, agent counts and area baselines (.xlsx / .csv)",
                bg="#1A5276", bg2="#2874A6")

# Show currently-loaded master info
if master_in_session is not None and not master_in_session.empty:
    _ms = master_in_session["loc_id"].nunique() if "loc_id" in master_in_session.columns else len(master_in_session)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#E8F8F5 0%,#D1F2EB 100%);
        border-left:5px solid #1ABC9C;border-radius:8px;padding:10px 14px;margin-bottom:12px;">
        <span style="color:#1A5276;font-weight:700;">✅ Station Master Active</span>
        &nbsp;—&nbsp;
        <span style="color:#555;">{_ms} stations loaded · Upload a new file to replace</span>
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
            # Persist to Excel so it survives app restarts
            try:
                upsert_master_data(mdf)
            except Exception as exc:
                logger.warning("Could not persist master data: %s", exc)

            st.session_state["master_data"] = mdf
            shown_cols = ", ".join(c for c in mdf.columns if c in _MASTER_VALID)
            st.success(
                f"✅ **{master_file.name}** loaded — **{len(mdf)}** stations · "
                f"Saved to local store · Columns: {shown_cols}"
            )
    except Exception as exc:
        st.error(f"❌ Could not parse master file: {exc}")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — FAMIS Upload Registry (full visibility table)
# ════════════════════════════════════════════════════════════════════════════
_section_header("📋", "UPLOAD REGISTRY",
                "All FAMIS files uploaded — names, formats, date ranges, record counts",
                bg="#145A32", bg2="#1E8449")

reg_df = _load_registry()

if reg_df.empty:
    # Try showing summary from the FAMIS data store as fallback
    try:
        hist_df = read_famis_uploads()
        if not hist_df.empty:
            st.info(f"📂 Local store has **{len(hist_df):,}** FAMIS rows across "
                    f"**{hist_df['loc_id'].nunique() if 'loc_id' in hist_df.columns else '?'}** stations. "
                    "Upload a new file to begin building the registry.")
        else:
            st.info("No FAMIS files uploaded yet. Use the uploader above to get started.")
    except Exception:
        st.info("No upload history available.")
else:
    # Rename columns for clean display
    display_cols = {
        "display_name": "File Name",
        "file_type":    "Format",
        "date_min":     "From",
        "date_max":     "To",
        "rows":         "Records",
        "stations":     "Stations",
        "uploaded_at":  "Uploaded At",
    }
    show_df = reg_df[[c for c in display_cols if c in reg_df.columns]].rename(columns=display_cols)

    # Format uploaded_at nicely
    if "Uploaded At" in show_df.columns:
        try:
            show_df["Uploaded At"] = pd.to_datetime(show_df["Uploaded At"]).dt.strftime("%d %b %Y %H:%M")
        except Exception:
            pass

    st.dataframe(show_df, width="stretch", hide_index=True)

    # DB upload log (if available) in expander
    if _db_live:
        with st.expander("🗄️ PostgreSQL Upload Log", expanded=False):
            try:
                log = _get_famis_upload_log(10)
                if log:
                    log_df = pd.DataFrame(log)
                    log_df["uploaded_at"] = pd.to_datetime(log_df["uploaded_at"]).dt.strftime("%d %b %Y %H:%M")
                    log_df = log_df.rename(columns={
                        "filename": "File", "rows_upserted": "Rows Upserted",
                        "total_rows_db": "Total in DB", "uploaded_at": "Uploaded At",
                    })
                    st.dataframe(log_df, width="stretch", hide_index=True)
                else:
                    st.info("No PostgreSQL upload history yet.")
            except Exception:
                st.info("PostgreSQL upload history unavailable.")

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
