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
    upsert_station_nsl_data,
    read_station_nsl_data,
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


def _auto_load_nsl() -> None:
    """On first page load, restore station_nsl_data from persisted Excel if not in session."""
    if st.session_state.get("station_nsl_data") is not None:
        return  # already in session
    try:
        nsl_df = read_station_nsl_data()
        if not nsl_df.empty:
            st.session_state["station_nsl_data"] = nsl_df
            logger.info("Auto-loaded Station NSL from FAMIS_META.xlsx (%d rows)", len(nsl_df))
    except Exception as exc:
        logger.warning("Auto-load NSL failed: %s", exc)


# ── Run auto-loads before rendering ──────────────────────────────────────────
_auto_load_master()
_auto_load_nsl()

# ── Page render ───────────────────────────────────────────────────────────────
render_header(
    "DATA UPLOAD CENTRE",
    "Upload & Manage FAMIS Volume Data, Facility Master Files and Station NSL Data",
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

    # ── Generate HTML analytics report after successful upload ────────────
    famis_in_session_now = st.session_state.get("famis_data")
    if famis_in_session_now is not None and not famis_in_session_now.empty:
        try:
            from aero.report.html_generator import generate_famis_report
            with st.spinner("⚙️ Generating AERO Analytics Report (HTML) …"):
                _master = st.session_state.get("master_data")
                _nsl    = st.session_state.get("station_nsl_data")
                _dname  = st.session_state.get("famis_file_name", "AERO_Report")
                _user   = st.session_state.get("aero_user", {}).get("display_name", "AERO Platform")
                _html_bytes = generate_famis_report(
                    famis_df=famis_in_session_now,
                    master_df=_master,
                    nsl_df=_nsl,
                    report_title=f"AERO Analytics · {_dname}",
                    generated_by=_user,
                )
                st.session_state["_aero_html_report"]      = _html_bytes
                st.session_state["_aero_html_report_name"] = _dname
        except Exception as _html_exc:
            logger.warning("HTML report generation failed: %s", _html_exc)

# ── HTML Report download button (shown after any FAMIS upload in this session) ──
if st.session_state.get("_aero_html_report"):
    _rpt_bytes = st.session_state["_aero_html_report"]
    _rpt_name  = st.session_state.get("_aero_html_report_name", "AERO_Report")
    st.markdown("""
    <div style="background:linear-gradient(90deg,#4D148C 0%,#671CAA 100%);
        border-radius:10px;padding:14px 20px;margin-top:8px;">
        <div style="color:#fff;font-size:15px;font-weight:700;margin-bottom:4px;">
            📊 AERO Analytics Report Ready
        </div>
        <div style="color:rgba(255,255,255,0.80);font-size:12px;">
            Interactive HTML report — hover charts, sort tables, explore all tabs.
            Works offline after first load.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.download_button(
        label="⬇️  Download AERO Analytics Report (HTML)",
        data=_rpt_bytes,
        file_name=f"AERO_{_rpt_name}_Analytics.html",
        mime="text/html",
        use_container_width=True,
        type="primary",
    )

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
# SECTION 3 — Station-Level NSL Data Upload
# ════════════════════════════════════════════════════════════════════════════
_section_header("📊", "STATION-LEVEL NSL DATA",
                "Network Service Level performance data (.xlsx / .xls / .csv)",
                bg="#1B4F72", bg2="#2E86C1")

# Show currently-loaded NSL info
nsl_in_session = st.session_state.get("station_nsl_data")
if nsl_in_session is not None and not nsl_in_session.empty:
    _nsl_stations = nsl_in_session["orig_loc_cd"].nunique() if "orig_loc_cd" in nsl_in_session.columns else len(nsl_in_session)
    _nsl_rows = len(nsl_in_session)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#EBF5FB 0%,#D6EAF8 100%);
        border-left:5px solid #2E86C1;border-radius:8px;padding:10px 14px;margin-bottom:12px;">
        <span style="color:#1B4F72;font-weight:700;">✅ Station NSL Data Active</span>
        &nbsp;—&nbsp;
        <span style="color:#555;">{_nsl_rows:,} records · {_nsl_stations} origin stations loaded · Upload a new file to replace</span>
    </div>
    """, unsafe_allow_html=True)

nsl_file = st.file_uploader(
    "Upload Station-Level NSL file",
    type=["xlsx", "xls", "csv"],
    key="nsl_uploader",
    label_visibility="collapsed",
)

if nsl_file is not None:
    try:
        with st.spinner("Parsing and aggregating Station-Level NSL file (this may take up to a minute for large files)..."):
            nsl_raw = nsl_file.read()
            _save_local(nsl_raw, nsl_file.name, "nsl")

            # Parse the file
            if nsl_file.name.lower().endswith(".csv"):
                nsl_df = pd.read_csv(io.BytesIO(nsl_raw))
            else:
                nsl_df = pd.read_excel(io.BytesIO(nsl_raw), sheet_name=0)

            # Normalise column names (lowercase + underscores)
            nsl_df.columns = (
                nsl_df.columns.astype(str).str.strip().str.lower()
                .str.replace(r"[\s/\\]+", "_", regex=True)
                .str.replace(r"[#%]", "", regex=True)
                .str.strip("_")
            )

            # Try to parse date columns
            for dcol in ["month_date", "weekending_dt"]:
                if dcol in nsl_df.columns:
                    nsl_df[dcol] = pd.to_datetime(nsl_df[dcol], errors="coerce")

            # Aggregate to station-level by month/week to keep storage and reload instant
            grp_cols = []
            for c in ["month_date", "weekending_dt", "orig_loc_cd", "orig_station", "orig_region", "mbg_class", "service", "product"]:
                if c in nsl_df.columns:
                    grp_cols.append(c)

            sum_cols = ["tot_vol", "nsl_ot_vol", "nsl_f_vol", "mbg_ot_vol", "mbg_f_vol"]
            sum_cols = [c for c in sum_cols if c in nsl_df.columns]

            for c in sum_cols:
                nsl_df[c] = pd.to_numeric(nsl_df[c], errors="coerce").fillna(0)

            if grp_cols:
                nsl_df = nsl_df.groupby(grp_cols, dropna=False)[sum_cols].sum().reset_index()

            # Persist to Excel so it survives app restarts
            try:
                upsert_station_nsl_data(nsl_df)
            except Exception as exc:
                logger.warning("Could not persist NSL data: %s", exc)

            # Store in session state
            st.session_state["station_nsl_data"] = nsl_df
            st.session_state["station_nsl_file_name"] = nsl_file.name

            # Build summary info
            n_rows = len(nsl_df)
            n_stations = int(nsl_df["orig_loc_cd"].nunique()) if "orig_loc_cd" in nsl_df.columns else 0
            date_info = ""
            if "month_date" in nsl_df.columns and nsl_df["month_date"].notna().any():
                d_min = nsl_df["month_date"].min().strftime("%d %b %Y")
                d_max = nsl_df["month_date"].max().strftime("%d %b %Y")
                date_info = f" · **{d_min} → {d_max}**"

            st.success(
                f"✅ **{nsl_file.name}** uploaded & aggregated — "
                f"**{n_rows:,}** station-period records stored · **{n_stations}** origin stations"
                f"{date_info} · Archived to docs/nsl/"
            )
    except Exception as exc:
        st.error(f"❌ Could not parse NSL file: {exc}")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — FAMIS Upload Registry (full visibility table)
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
# SECTION 5 — Template Downloads
# ════════════════════════════════════════════════════════════════════════════
with st.expander("⬇️  Download Data Templates", expanded=False):
    dl1, dl2, dl3 = st.columns(3)
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
    with dl3:
        st.markdown("**Station NSL Data Template**")
        st.caption("month_date · orig_loc_cd · orig_region · Service · Product · NSL_OT_VOL · NSL_F_VOL · TOT_VOL")
        tpl3 = pd.DataFrame(
            [["2026-05-01", "ABCD", "MEISA", "Priority", "Parcel", 1, 0, 1]],
            columns=["month_date", "orig_loc_cd", "orig_region", "Service",
                     "Product", "NSL_OT_VOL", "NSL_F_VOL", "TOT_VOL"],
        )
        buf3 = io.BytesIO()
        with pd.ExcelWriter(buf3, engine="openpyxl") as w:
            tpl3.to_excel(w, index=False, sheet_name="NSL")
        st.download_button(
            "⬇️ NSL Template", buf3.getvalue(), "NSL_Template.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
