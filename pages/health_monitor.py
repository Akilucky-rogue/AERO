# ============================================================
# IMPORTS & DEPENDENCIES
# ============================================================

import streamlit as st
import pandas as pd
import json
import os
import math
from aero.ui.components import render_section_header, render_status_cards
from aero.core.area_calculator import (
    calculate_area_requirements,
    calculate_area_status,
    get_status_summary_stats,
)
from aero.core.resource_calculator import (
    calculate_resource_requirements,
    calculate_resource_health_status,
    get_resource_summary_stats,
)
from aero.core.courier_calculator import (
    calculate_courier_requirements,
    calculate_courier_health_status,
    get_courier_summary_stats,
)
from aero.data.excel_store import (
    upsert_famis_upload,
    read_famis_uploads,
    save_health_reports,
    read_report_sheet,
)
# PostgreSQL FAMIS store (DB-first; falls back to excel_store when DB unavailable)
try:
    from aero.data.famis_store import (  # type: ignore
        db_available as _famis_db_available,
        ensure_famis_tables as _ensure_famis_tables,
        upsert_famis_data as _upsert_famis_db,
        load_famis_from_db as _load_famis_db,
        famis_row_count as _famis_row_count,
    )
    _FAMIS_STORE_OK = True
except Exception:
    _FAMIS_STORE_OK = False
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# ALLOWED HEADERS CONFIGURATION
# ============================================================
FAMIS_ALLOWED_HEADERS = {
    'date': 'DATE',
    'loc_id': 'LOC ID',
    'pk_gross_tot': 'PK GROSS TOT',
    'pk_gross_inb': 'PK GROSS INB',
    'pk_gross_outb': 'PK GROSS OUT',
    'pk_oda': 'PK ODA',
    'pk_opa': 'PK OPA',
    'pk_roc': 'PK ROC',
    'fte_tot': 'FTE TOT',
    'st_cr_or': 'ST/CR OR',
    'pk_fte': 'PK/FTE',
    'pk_cr_or': 'PK/CR OR'
}

MASTER_ALLOWED_HEADERS = {
    'date': 'DATE',
    'loc_id': 'LOC ID',
    'total_facility_area': 'TOTAL FACILITY AREA',
    'ops_area': 'OPS AREA',
    'current_total_osa': 'CURRENT TOTAL OSA',
    'current_total_couriers': 'CURRENT TOTAL COURIERS'
}
# ============================================================
# CONFIG LOAD (Task TACT and Parameter Values)
# ============================================================
from aero.config.settings import load_config

config = load_config()
osa = config.get("OSA", {})
lasa = config.get("LASA", {})
dispatcher = config.get("DISPATCHER", {})
trace_agent = config.get("TRACE_AGENT", {})

# ======= Helper functions for safe numeric coercion & formatting =======
def _to_float(value, default=0.0):
    try:
        # pandas NA handling
        if hasattr(value, "__float__") and (value is not None):
            # This will handle numeric types directly
            return float(value)
    except Exception:
        pass
    try:
        s = str(value).strip()
        if s == "" or s.lower() in ("nan", "none", "na", "n/a"):
            return default
        # remove common thousands separators
        s = s.replace(',', '')
        return float(s)
    except Exception:
        return default


def _fmt_area(value):
    """Format an area-like value safely as an integer with commas.

    Always coerces non-numeric inputs to 0 and returns a string like '1,234'.
    """
    val = _to_float(value, default=0.0)
    try:
        return f"{val:,.0f}"
    except Exception:
        return "0"


def _load_famis_df(file_bytes_or_path, filename: str) -> None:
    """Parse, validate and store FAMIS data in session state + Excel store."""
    from aero.data.inbox_loader import parse_famis_file
    valid_cols = list(FAMIS_ALLOWED_HEADERS.keys())
    famis_df = parse_famis_file(file_bytes_or_path)
    famis_df = famis_df[[c for c in famis_df.columns if c in valid_cols]]
    st.session_state["famis_data_raw"]  = famis_df.copy()
    st.session_state["famis_data"]      = famis_df
    st.session_state["famis_file_name"] = filename
    try:
        # Upsert to PostgreSQL first; fall back to Excel store
        if _FAMIS_STORE_OK:
            try:
                _ensure_famis_tables()
                _upsert_famis_db(famis_df, filename)
            except Exception as _dbe:
                logger.warning("FAMIS DB upsert failed, falling back to Excel: %s", _dbe)
                upsert_famis_upload(famis_df)
        else:
            upsert_famis_upload(famis_df)
    except Exception:
        pass


def render():
    """Render the Station Health Monitor content (called from station_planner.py tab)."""

    # ── Auto-load from inbox (runs once per session) ──────────────────────────
    if not st.session_state.get("_famis_inbox_checked"):
        st.session_state["_famis_inbox_checked"] = True
        try:
            from aero.data.inbox_loader import scan_famis_inbox
            inbox_files = scan_famis_inbox(auto_move=False)
            if inbox_files and st.session_state.get("famis_data") is None:
                newest = inbox_files[0]
                _load_famis_df(newest["path"], newest["filename"])
                n_rows = len(newest["df"])
                st.toast(f"📂 Auto-loaded FAMIS: {newest['filename']} "
                         f"({n_rows:,} station-week rows from inbox)", icon="✅")
        except Exception:
            pass  # non-blocking

    # ── Restore from persisted Excel store if still no data ───────────────────
    if st.session_state.get("famis_data") is None:
        try:
            # Try PostgreSQL first
            stored = None
            if _FAMIS_STORE_OK:
                try:
                    if _famis_db_available() and _famis_row_count() > 0:
                        stored = _load_famis_db()
                except Exception:
                    stored = None
            if stored is None or stored.empty:
                stored = read_famis_uploads()
            if stored is not None and not stored.empty:
                st.session_state["famis_data_raw"] = stored.copy()
                st.session_state["famis_data"]     = stored
        except Exception:
            pass

    upload_col1, upload_col2 = st.columns(2)

    with upload_col1:
        famis_file = st.file_uploader(
            "Upload Facility Volume Excel File",
            type=["xlsx"],
            key="famis_upload",
            help="Upload FAMIS REPORT xlsx — or drop it in aero/data/inbox/famis/ to skip this step."
        )

        if famis_file:
            try:
                _load_famis_df(famis_file.read(), famis_file.name)
                st.success(f"✅ Loaded {len(st.session_state['famis_data']):,} "
                           f"station-week rows from {famis_file.name}")
            except Exception as e:
                st.error(f"❌ Could not parse FAMIS file: {e}")

    with upload_col2:
        master_file = st.file_uploader(
            "Upload Facility Master Excel File",
            type=["xlsx"],
            key="master_upload",
            help="Upload facility master file with facility and staffing data"
        )

        if master_file:
            try:
                import re
                master_df = pd.read_excel(master_file)
                master_df.columns = (
                    master_df.columns
                    .str.strip()
                    .str.lower()
                    .str.replace(" ", "_")
                    .str.replace("/", "_")
                )

                # Try to map common variations of header names to the canonical keys
                valid_cols = list(MASTER_ALLOWED_HEADERS.keys())

                # helper to clean column names for fuzzy matching
                def _clean(name: str) -> str:
                    return re.sub(r'[^a-z0-9_]', '', name.lower())

                existing = list(master_df.columns)
                # mapping from expected -> actual column name (if found)
                col_map = {}
                for expected in valid_cols:
                    if expected in existing:
                        col_map[expected] = expected
                        continue
                    # fuzzy search: look for a column that contains the meaningful tokens
                    exp_tokens = [t for t in expected.split('_') if t]
                    found = None
                    for col in existing:
                        cleaned_col = _clean(col)
                        # require at least two tokens to match or the full expected to be substring
                        if _clean(expected) in cleaned_col:
                            found = col
                            break
                        matches = sum(1 for t in exp_tokens if t in cleaned_col)
                        if matches >= max(1, len(exp_tokens) - 1):
                            found = col
                            break
                    if found:
                        col_map[expected] = found

                # Rename found columns to canonical expected names
                if col_map:
                    master_df = master_df.rename(columns={v: k for k, v in col_map.items()})

                # Recompute available/invalid columns after mapping
                available_cols = [col for col in valid_cols if col in master_df.columns]
                invalid_cols = [col for col in master_df.columns if col not in valid_cols]

                # Minimum required column: loc_id
                if 'loc_id' in master_df.columns:
                    # Keep only allowed columns (and ignore extras)
                    master_df = master_df[[col for col in master_df.columns if col in valid_cols]]
                    st.session_state['master_data'] = master_df
                else:
                    st.error(" Missing required column: loc_id")
            except Exception as e:
                st.error(f" Error loading Master file: {str(e)}")

    # ============================================================
    # FAMIS FILE TYPE — Weekly / Monthly Volume Normalization
    # ============================================================
    if 'famis_data_raw' in st.session_state and st.session_state['famis_data_raw'] is not None:
        _file_type_options = ["Daily", "Weekly", "Monthly"]
        _saved_file_type = st.session_state.get('famis_file_type_saved', 'Daily')
        _default_idx = _file_type_options.index(_saved_file_type) if _saved_file_type in _file_type_options else 0
        file_type = st.selectbox(
            "📊 FAMIS File Type",
            _file_type_options,
            index=_default_idx,
            key='famis_file_type',
            help="Select the time period of the uploaded FAMIS file. Weekly volumes will be divided by 6, Monthly by 26 to get daily averages."
        )
        st.session_state['famis_file_type_saved'] = file_type

        _divisor_map = {'Daily': 1, 'Weekly': 6, 'Monthly': 26}
        _divisor = _divisor_map[file_type]
        _raw_df = st.session_state['famis_data_raw'].copy()
        _volume_cols = ['pk_gross_tot', 'pk_gross_inb', 'pk_gross_outb', 'pk_oda', 'pk_opa', 'pk_roc']
        if _divisor > 1:
            for _vc in _volume_cols:
                if _vc in _raw_df.columns:
                    _raw_df[_vc] = pd.to_numeric(_raw_df[_vc], errors='coerce').fillna(0) / _divisor

        # Clear stale tracker widget caches when file type changes
        _prev_file_type = st.session_state.get('_famis_file_type_prev', None)
        if _prev_file_type is not None and _prev_file_type != file_type:
            for _stale_key in ['area_volume_from_famis', 'area_daily_volume']:
                st.session_state.pop(_stale_key, None)
        st.session_state['_famis_file_type_prev'] = file_type

        st.session_state['famis_data'] = _raw_df
    st.markdown("---")
    # ============================================================
    # Date Range Selector (From / To)
    # ============================================================
    if 'famis_data' in st.session_state and st.session_state['famis_data'] is not None:
        famis_df = st.session_state['famis_data']
        if 'date' in famis_df.columns:
            available_dates = sorted(famis_df['date'].unique(), reverse=True)

            # Initialize session defaults
            if 'selected_date' not in st.session_state or st.session_state['selected_date'] not in available_dates:
                st.session_state['selected_date'] = available_dates[0]

                st.markdown(f"""
                <div style="
                    background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
                    border-left: 6px solid var(--fc-purple);
                    border-radius: 8px;
                    padding: 12px 16px;
                    margin-bottom: 16px;
                ">
                    <div style="font-weight:700;color:var(--gray-80);font-size:15px; font-family:'DM Sans',sans-serif;">Select Date</div>
                </div>
                """, unsafe_allow_html=True)

            selected_date = st.selectbox(
                "Active Date",
                available_dates,
                format_func=lambda x: x.strftime('%Y-%m-%d'),
                index=available_dates.index(st.session_state['selected_date']),
                key='date_selector_card'
            )
            st.session_state['selected_date'] = selected_date
        else:
            st.error("⚠️ Date column not found in FAMIS data")
    else:
        st.markdown("""
        <div style="
            background: var(--info-bg);
            border-left: 6px solid var(--fc-purple);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: var(--info-text);
        ">
            <div style="font-weight:700;font-size:15px;">📤 Upload a FAMIS/Volume file to enable date selection</div>
        </div>
        """, unsafe_allow_html=True)
        st.session_state['selected_date'] = None

    # ============================================================
    # TABS: AREA - RESOURCE - COURIER - ANALYTICS
    # ============================================================
    _all_tabs = st.tabs(["AREA MONITOR", "STATION AGENT MONITOR", "COURIER MONITOR", "ANALYTICS"])
    tab1 = _all_tabs[0]
    tab2 = _all_tabs[1]
    tab3 = _all_tabs[2]
    tab4 = _all_tabs[3]
    st.markdown("---")

    # ============================================================
    # TAB 1: AREA MONITOR
    # ============================================================
    with tab1:
        st.session_state['health_active_tab'] = 'AREA'
        # ========== HEALTH SUMMARY SECTION ==========
        if 'famis_data' in st.session_state and st.session_state['famis_data'] is not None and st.session_state.get('selected_date'):
            famis_df = st.session_state['famis_data']
            master_df = st.session_state.get('master_data', None)
            selected_date = st.session_state['selected_date']

            # Filter data for selected date
            date_famis = famis_df[famis_df['date'] == selected_date].copy()

            if not date_famis.empty and master_df is not None and not master_df.empty:
                # ========== AREA PARAMETERS (inherited from Area Tracker) ==========
                area_packs_per_pallet = st.session_state.get('area_packs_per_pallet', 15)
                area_max_volume = st.session_state.get('area_max_volume', 55.0)
                area_sorting_percent = st.session_state.get('area_sorting_percent', 60.0)
                area_aisle_percent = st.session_state.get('area_aisle_percent', 15.0)
                area_cage_percent = st.session_state.get('area_cage_percent', 10.0)

                st.markdown("---")
                # Calculate area requirements for all stations on selected date
                station_statuses = []

                for idx, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    total_packs = int(row.get('pk_gross_tot', 0))

                    # Get additional area (non-healthcare) from area tracker session
                    additional_area = float(st.session_state.get(f'area_additional_{loc_id}', 0))
                    # Include healthcare if user selected it in Area Tracker for this LOC
                    healthcare_selected = bool(st.session_state.get(f'add_healthcare_{loc_id}', False))
                    healthcare_val = float(st.session_state.get(f'area_healthcare_{loc_id}', 0) or 0) if healthcare_selected else 0.0
                    # Include DG (dangerous goods) if user selected it in Area Tracker for this LOC
                    dg_selected = bool(st.session_state.get(f'add_dg_{loc_id}', False))
                    dg_val = float(st.session_state.get(f'area_dg_{loc_id}', 0) or 0) if dg_selected else 0.0

                    # Get master ops area
                    master_row = master_df[master_df['loc_id'] == loc_id]
                    master_ops_area = master_row['ops_area'].iloc[0] if (not master_row.empty and 'ops_area' in master_row.columns) else 0
                    master_ops_float = _to_float(master_ops_area, 0.0)

                    # Handle zero volume: status is UNKNOWN / NO DATA
                    if total_packs == 0:
                        status = {
                            'status': 'UNKNOWN',
                            'deviation_percent': 0,
                            'color': '#8E8E8E',
                            'emoji': '⚪',
                            'label': 'No Data'
                        }
                        status['loc_id'] = loc_id
                        status['operational_base'] = 0
                        status['additional'] = additional_area
                        status['total_calculated'] = 0
                        status['master_area'] = master_ops_float
                        station_statuses.append(status)
                        continue

                    # Calculate area requirements WITH additional areas included
                    calcs = calculate_area_requirements(
                        total_packs=total_packs,
                        packs_per_pallet=area_packs_per_pallet,
                        max_volume_percent=area_max_volume,
                        sorting_area_percent=area_sorting_percent,
                        cage_percent=area_cage_percent,
                        aisle_percent=area_aisle_percent,
                        additional_area_value=additional_area
                    )

                    # Operational area (excluding non-healthcare additional, including healthcare + DG)
                    operational_area = (calcs['total_operational_area'] - additional_area) + healthcare_val + dg_val

                    # Calculate status by comparing calculated operational area against master ops area
                    status = calculate_area_status(
                        calculated_total_area=operational_area,
                        master_facility_area=master_ops_float
                    )
                    status['loc_id'] = loc_id
                    status['operational_base'] = operational_area
                    status['additional'] = additional_area
                    status['total_calculated'] = operational_area
                    status['master_area'] = master_ops_float

                    station_statuses.append(status)

                # Get summary stats
                summary_stats = get_status_summary_stats(station_statuses)

                # Store results in session state for publish
                st.session_state['area_health_results'] = station_statuses
                st.session_state['area_tab_computed'] = True
                # ========== SUMMARY TABLE ==========
                st.markdown("""
                <div style="
                    background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
                    border-left: 6px solid #4D148C;
                    border-radius: 8px;
                    padding: 12px 16px;
                    margin-bottom: 16px;
                ">
                    <div style="font-weight:700;color:#333333;font-size:16px;">🗂️ AREA ANALYSIS</div>
                </div>
                """, unsafe_allow_html=True)

                # 4 Status Cards (all same size) 
                card_col1, card_col2, card_col3, card_col4 = st.columns(4)

                # Card height and style consistent (compact)
                card_height_style = "height:120px; min-height:85px; box-sizing:border-box; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:8px;"

                # Card 1: Healthy (compact)
                with card_col1:
                    st.markdown(f"""
                    <div style="
                        background: var(--status-healthy-bg);
                        border: 1px solid var(--status-healthy-border);
                        border-radius: 8px;
                        text-align: center;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
                        {card_height_style}
                    ">
                        <div style="font-size:20px; margin-bottom:4px;">✅</div>
                        <div style="color: var(--status-healthy-text); font-weight:700; font-size:20px;">{summary_stats['healthy_count']}</div>
                        <div style="color: var(--status-healthy-subtext); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Healthy</div>
                        <div style="color: var(--status-healthy-subtext-2); font-size:11px; margin-top:6px; font-weight:600;">Range: 0-10%</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Card 2: Review Needed (compact)
                with card_col2:
                    st.markdown(f"""
                    <div style="
                        background: var(--status-review-bg);
                        border: 1px solid var(--status-review-border);
                        border-radius: 8px;
                        text-align: center;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
                        {card_height_style}
                    ">
                        <div style="font-size:20px; margin-bottom:4px;">⚠️</div>
                        <div style="color: var(--status-review-text); font-weight:700; font-size:20px;">{summary_stats['review_needed_count']}</div>
                        <div style="color: var(--status-review-subtext); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Review</div>
                        <div style="color: var(--status-review-subtext-2); font-size:11px; margin-top:6px; font-weight:600;">Range: 10-20%</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Card 3: Critical 
                with card_col3:
                    st.markdown(f"""
                    <div style="
                        background: var(--status-critical-bg);
                        border: 1px solid var(--status-critical-border);
                        border-radius: 8px;
                        text-align: center;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
                        {card_height_style}
                    ">
                        <div style="font-size:20px; margin-bottom:4px;">🚨</div>
                        <div style="color: var(--status-critical-text); font-weight:700; font-size:20px;">{summary_stats['critical_count']}</div>
                        <div style="color: var(--status-critical-subtext); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px;">Critical</div>
                        <div style="color: var(--status-critical-subtext-2); font-size:11px; margin-top:6px; font-weight:600;">Range: &gt;20%</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Card 4: Most Negatively Deviated Station (only show deficits)
                with card_col4:
                    most_affected = summary_stats.get('most_affected')
                    if most_affected is None:

                        st.markdown(f"""
                        <div style="
                            background: var(--status-neutral-bg);
                            border: 1px solid var(--status-neutral-border);
                            border-radius: 8px;
                            padding: 20px;
                            text-align: center;
                            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
                            {card_height_style}
                        ">
                            <div style="font-size:28px; margin-bottom:8px;">✅</div>
                            <div style="color: var(--status-neutral-text); font-weight:700; font-size:16px;">All Stations Sufficient</div>
                            <div style="color: var(--status-neutral-subtext); font-size:11px; font-weight:600; margin-top:6px;">No negative deviations found</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        most_affected_emoji = most_affected.get('emoji', '❓')
                        most_affected_loc = most_affected.get('loc_id', 'N/A')
                        most_affected_deviation = most_affected.get('deviation_percent', 0)
                        # Only display the maximum negative deviation (deficit)
                        st.markdown(f"""
                        <div style="
                            background: var(--status-most-affected-bg);
                            border: 1px solid var(--status-most-affected-border);
                            border-radius: 8px;
                            padding: 18px;
                            text-align: center;
                            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
                            {card_height_style}
                        ">
                            <div style="font-size:26px; margin-bottom:6px;">{most_affected_emoji}</div>
                            <div style="color: var(--status-neutral-text); font-weight:700; font-size:16px;">{most_affected_loc}</div>
                            <div style="color: var(--status-critical-subtext); font-size:12px; font-weight:700; margin-top:6px;">Max Negative Deviation: {most_affected_deviation:+.1f}%</div>
                        </div>
                        """, unsafe_allow_html=True)

                # Create detailed summary dataframe — DATE | LOC ID | VOLUME | CALCULATED AREA | CURRENT AREA | STATUS
                summary_data = []

                for idx, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    total_packs = int(row.get('pk_gross_tot', 0))

                    # Get additional/healthcare/DG areas
                    additional_area = float(st.session_state.get(f'area_additional_{loc_id}', 0))
                    healthcare_selected = bool(st.session_state.get(f'add_healthcare_{loc_id}', False))
                    healthcare_val = float(st.session_state.get(f'area_healthcare_{loc_id}', 0) or 0) if healthcare_selected else 0.0
                    dg_selected = bool(st.session_state.get(f'add_dg_{loc_id}', False))
                    dg_val = float(st.session_state.get(f'area_dg_{loc_id}', 0) or 0) if dg_selected else 0.0

                    # Get master ops area (current facility area)
                    master_row = master_df[master_df['loc_id'] == loc_id]
                    master_ops = master_row['ops_area'].iloc[0] if (not master_row.empty and 'ops_area' in master_row.columns) else 0
                    master_ops_float = _to_float(master_ops, 0.0)

                    date_str = selected_date.strftime('%Y-%m-%d') if hasattr(selected_date, 'strftime') else str(selected_date)

                    # If any of the key values are zero (volume, calculated area, or current/master area)
                    # then show NO DATA for this station.

                    # Calculate current-volume based area
                    calcs = calculate_area_requirements(
                        total_packs=total_packs,
                        packs_per_pallet=area_packs_per_pallet,
                        max_volume_percent=area_max_volume,
                        sorting_area_percent=area_sorting_percent,
                        cage_percent=area_cage_percent,
                        aisle_percent=area_aisle_percent,
                        additional_area_value=additional_area
                    )
                    calculated_area = (calcs['total_operational_area'] - additional_area) + healthcare_val + dg_val

                    # If any primary value is zero or non-positive, mark as NO DATA
                    if (total_packs == 0) or (calculated_area <= 0) or (master_ops_float <= 0):
                        summary_data.append({
                            'DATE': date_str,
                            'LOC ID': loc_id,
                            'VOLUME': '0' if total_packs == 0 else f"{total_packs:,}",
                            'CALCULATED AREA': '-' if calculated_area <= 0 else _fmt_area(calculated_area),
                            'CURRENT AREA': '-' if master_ops_float <= 0 else _fmt_area(master_ops),
                            'STATUS': '⚪ NO DATA'
                        })
                    else:
                        status_info = calculate_area_status(
                            calculated_total_area=calculated_area,
                            master_facility_area=master_ops_float
                        )
                        deviation = status_info['deviation_percent']
                        emoji = status_info['emoji']

                        summary_data.append({
                            'DATE': date_str,
                            'LOC ID': loc_id,
                            'VOLUME': f"{total_packs:,}",
                            'CALCULATED AREA': _fmt_area(calculated_area),
                            'CURRENT AREA': _fmt_area(master_ops),
                            'STATUS': f"{emoji} {deviation:+.1f}%"
                        })

                summary_df = pd.DataFrame(summary_data)

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.dataframe(
                    summary_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        'DATE':            st.column_config.TextColumn('DATE', width=110),
                        'LOC ID':          st.column_config.TextColumn('LOC ID', width=90),
                        'VOLUME':          st.column_config.TextColumn('VOLUME', width=100),
                        'CALCULATED AREA': st.column_config.TextColumn('CALCULATED AREA (sqft)', width=170),
                        'CURRENT AREA':    st.column_config.TextColumn('CURRENT AREA (sqft)', width=160),
                        'STATUS':          st.column_config.TextColumn('STATUS', width=120)
                    }
                )

            else:  
                if master_df is None or master_df.empty:
                    st.warning("📤 Please upload a Station Master file to see detailed analysis")
                else:
                    st.info("📅 Select a date with FAMIS data to view area requirements")
        else:
            st.markdown("""
            <div style="
                background: var(--info-bg);
                border-left: 6px solid var(--fc-purple);
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 16px;
                color: var(--info-text);
            ">
                <div style="font-weight:700;">📤 Upload FAMIS/Volume file to enable area monitoring for selected date</div>
            </div>
            """, unsafe_allow_html=True)

    # ============================================================
    # TAB 2: RESOURCE MONITOR
    # ============================================================
    with tab2:
        st.session_state['health_active_tab'] = 'RESOURCE'

        # ========== RESOURCE REQUIREMENT SUMMARY SECTION ===========
        if 'famis_data' in st.session_state and st.session_state['famis_data'] is not None and st.session_state.get('selected_date'):
            famis_df = st.session_state['famis_data']
            master_df = st.session_state.get('master_data', None)
            selected_date = st.session_state['selected_date']

            # Filter data for selected date
            date_famis = famis_df[famis_df['date'] == selected_date].copy()

            if not date_famis.empty and master_df is not None and not master_df.empty:
                # ========== RESOURCE PARAMETERS (inherited from Resource Tracker) ==========

                st.markdown("---")

                # Read parameters (convert percentage inputs to fractional values where required by calculations)
                SHIFT_HOURS = float(st.session_state.get('resource_shift_hours', 9.0))
                ABSENTEEISM_PCT = float(st.session_state.get('resource_absenteeism_pct', 11.0)) / 100.0
                TRAINING_PCT = 0.0
                ROSTER_BUFFER_PCT = float(st.session_state.get('resource_roster_buffer_pct', 11.0)) / 100.0
                ON_CALL_PICKUP = int(st.session_state.get('resource_on_call_pickup', 80))
                DEX_PCT = 0.05
                CSBIV_PCT = 0.80
                ROD_PCT = 0.30

                # Calculate resource requirements for all stations using shared calculation function
                station_resource_statuses = []

                for idx, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    gross_vol = int(row.get('pk_gross_tot', 0))
                    ib_vol = int(row.get('pk_gross_inb', 0))
                    ob_vol = int(row.get('pk_gross_outb', 0))
                    # ROC from FAMIS goes to ASP, ROC placeholder is 0
                    roc_from_famis = int(row.get('pk_roc', 0))
                    roc_vol = int(roc_from_famis * 0.25)
                    asp_vol = roc_from_famis - roc_vol

                    # Call shared calculation function
                    resource_reqs = calculate_resource_requirements(
                        total_volume=gross_vol,
                        ib_volume=ib_vol,
                        ob_volume=ob_vol,
                        roc_volume=roc_vol,
                        asp_volume=asp_vol,
                        shift_hours=SHIFT_HOURS,
                        absenteeism_pct=ABSENTEEISM_PCT,
                        training_pct=TRAINING_PCT,
                        roster_buffer_pct=ROSTER_BUFFER_PCT,
                        on_call_pickup=ON_CALL_PICKUP,
                        dex_pct=DEX_PCT,
                        csbiv_pct=CSBIV_PCT,
                        rod_pct=ROD_PCT
                    )

                    # Get total calculated agents
                    calculated_agents = resource_reqs['total_agents']

                    # Get master agents
                    master_row = master_df[master_df['loc_id'] == loc_id]
                    master_agents = 0
                    if not master_row.empty and 'current_total_agents' in master_row.columns:
                        master_agents = float(master_row['current_total_agents'].iloc[0])
                    elif not master_row.empty and 'current_total_osa' in master_row.columns:
                        master_agents = float(master_row['current_total_osa'].iloc[0])

                    # Calculate status
                    status = calculate_resource_health_status(
                        calculated_agents,
                        master_agents
                    )
                    status['loc_id'] = loc_id
                    status['calculated_agents'] = calculated_agents
                    status['master_agents'] = master_agents
                    status['base_agents'] = resource_reqs.get('base_agents', 0)
                    status['osa_agents'] = resource_reqs['osa_agents']
                    status['lasa_agents'] = resource_reqs['lasa_agents']
                    status['dispatcher_agents'] = resource_reqs['dispatcher_agents']
                    status['trace_agents'] = resource_reqs['trace_agents']

                    station_resource_statuses.append(status)

                # Get summary stats
                resource_summary = get_resource_summary_stats(station_resource_statuses)

                # Store results in session state for publish
                st.session_state['resource_health_results'] = station_resource_statuses
                st.session_state['resource_tab_computed'] = True

                # ========== RESOURCE REQUIREMENT SUMMARY (Header + Status Cards) ==========
                render_section_header("RESOURCE ANALYSIS")
                render_status_cards(resource_summary)

                # ========== RESOURCE SUMMARY TABLE ==========

                # Create summary table — DATE | LOC ID | VOLUME | CALCULATED AGENTS | CURRENT AGENTS | STATUS
                resource_summary_data = []

                for idx, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    gross_vol = int(row.get('pk_gross_tot', 0))

                    station_status = next((s for s in station_resource_statuses if s['loc_id'] == loc_id), None)
                    master_agents = station_status['master_agents'] if station_status else 0

                    date_str = selected_date.strftime('%Y-%m-%d') if hasattr(selected_date, 'strftime') else str(selected_date)

                    # Use already-computed values from station_resource_statuses
                    calculated_agents = station_status['calculated_agents'] if station_status else 0
                    deviation = station_status['deviation_percent'] if station_status else 0
                    emoji = station_status['emoji'] if station_status else '❓'

                    # If any primary value is zero or non-positive, mark as NO DATA
                    if (gross_vol == 0) or (calculated_agents <= 0) or (master_agents <= 0):
                        resource_summary_data.append({
                            'DATE': date_str,
                            'LOC ID': loc_id,
                            'VOLUME': '0' if gross_vol == 0 else f"{gross_vol:,}",
                            'CALCULATED AGENTS': '-' if calculated_agents <= 0 else f"{calculated_agents:.1f}",
                            'CURRENT AGENTS': '-' if master_agents <= 0 else f"{master_agents:.0f}",
                            'STATUS': '⚪ NO DATA'
                        })
                    else:
                        resource_summary_data.append({
                            'DATE': date_str,
                            'LOC ID': loc_id,
                            'VOLUME': f"{gross_vol:,}",
                            'CALCULATED AGENTS': f"{calculated_agents:.1f}",
                            'CURRENT AGENTS': f"{master_agents:.0f}",
                            'STATUS': f"{emoji} {deviation:+.1f}%"
                        })

                resource_summary_df = pd.DataFrame(resource_summary_data)

                st.dataframe(
                    resource_summary_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        'DATE':              st.column_config.TextColumn('DATE', width=110),
                        'LOC ID':            st.column_config.TextColumn('LOC ID', width=90),
                        'VOLUME':            st.column_config.TextColumn('VOLUME', width=100),
                        'CALCULATED AGENTS': st.column_config.TextColumn('CALCULATED AGENTS', width=160),
                        'CURRENT AGENTS':    st.column_config.TextColumn('CURRENT AGENTS', width=140),
                        'STATUS':            st.column_config.TextColumn('STATUS', width=120)
                    }
                )

                st.markdown("---")

                # Allow user to select a station for detailed calculations
                _res_locs = sorted(date_famis['loc_id'].unique())
                selected_loc_id = st.selectbox(
                    "Select Station for Detailed Resource Calculations",
                    _res_locs,
                    key='resource_detail_loc'
                )

                # Build detail inputs for the selected station
                _detail_row = date_famis[date_famis['loc_id'] == selected_loc_id].iloc[0]
                gross_vol = int(_detail_row.get('pk_gross_tot', 0))
                ib_vol = int(_detail_row.get('pk_gross_inb', 0))
                ob_vol = int(_detail_row.get('pk_gross_outb', 0))
                roc_from_famis = int(_detail_row.get('pk_roc', 0))
                roc_vol = int(roc_from_famis * 0.25)
                asp_vol = roc_from_famis - roc_vol

                # Calculate detailed requirements for the selected station (current volumes)
                detail_reqs = calculate_resource_requirements(
                    total_volume=gross_vol,
                    ib_volume=ib_vol,
                    ob_volume=ob_vol,
                    roc_volume=roc_vol,
                    asp_volume=asp_vol,
                    shift_hours=SHIFT_HOURS,
                    absenteeism_pct=ABSENTEEISM_PCT,
                    training_pct=TRAINING_PCT,
                    roster_buffer_pct=ROSTER_BUFFER_PCT,
                    on_call_pickup=ON_CALL_PICKUP,
                    dex_pct=DEX_PCT,
                    csbiv_pct=CSBIV_PCT,
                    rod_pct=ROD_PCT
                )

                staff_col1, staff_col2, staff_col3, staff_col4 = st.columns(4)

                # Match Resource Tracker logic: use configured absenteeism percentage (post-calculation)
                absenteeism_post_pct = st.session_state.get('resource_absenteeism_pct', 15.0) / 100.0

                with staff_col1:
                    st.metric("Base Agents", f"{detail_reqs['base_agents']:.2f}")

                with staff_col2:
                    absenteeism_add = detail_reqs['base_agents'] * absenteeism_post_pct
                    st.metric(f"Absenteeism ({st.session_state.get('resource_absenteeism_pct', 15.0):.0f}%)", f"{absenteeism_add:.2f}")

                with staff_col3:
                    roster_add = detail_reqs['base_agents'] * (st.session_state.get('resource_roster_buffer_pct', 11.0) / 100.0)
                    st.metric("Roster Buffer Addition", f"{roster_add:.2f}")

                with staff_col4:
                    # Final = base + absenteeism (configured) + roster buffer
                    final_agents = detail_reqs['base_agents'] + absenteeism_add + roster_add
                    st.metric("Total Agents (Final)", f"{math.ceil(final_agents)}")

                st.markdown("---")

                # ========== FORMULAS EXPANDER ==========
                with st.expander("📐 CALCULATION FORMULAS & METHODOLOGY", expanded=False):
                    st.markdown("""
                    <div style="background:#F2F2F2; padding:12px; border-radius:6px; margin-bottom:12px;">
                    <strong>Resource Calculation Methodology</strong><br>
                    All calculations follow the exact formulas used in the Resource Tracker page to ensure parity.
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("""
                    **1️⃣ TIME CALCULATION (Per Role)**

                    For each role (OSA, LASA, Dispatcher, Trace), we sum task-level time:
                    ```
                    Role_Time_Minutes = Σ(TACT_i × Parameter_i) for all tasks in role
                    ```

                    Example: OSA time = (IB/OB Scan TACT × Total Volume) + (Damage Scan TACT × Damage Count) + ... + (Station Open/Close TACT × 1)
                    """)

                    st.markdown("""
                    **2️⃣ CONVERT TO HOURS**

                    ```
                    Hourly = Role_Time_Minutes / 60
                    ```
                    """)

                    st.markdown("""
                    **3️⃣ BASE AGENTS (Per Role, Before SHARP)**

                    ```
                    Role_Base_Agents = Role_Hours / Shift_Hours
                    ```

                    Where Shift Hours = """ + str(SHIFT_HOURS) + """ (configurable in parameters)
                    """)

                    st.markdown("""
                    **4️⃣ SHARP ADJUSTMENT (Per Role)**

                    SHARP = Strategic Hours for Advanced Program Recognition

                    ```
                    Sharp_Hours_Role = CEILING(Role_Base_Agents) × 0.25 hours
                    Role_Total_Hours_with_Sharp = Role_Hours + Sharp_Hours_Role
                    Role_Agents_with_Sharp = Role_Total_Hours_with_Sharp / Shift_Hours
                    ```
                    """)

                    st.markdown("""
                    **5️⃣ BASE TOTAL AGENTS (Across All Roles)**

                    ```
                    Base_Total_Agents = OSA_Agents_with_Sharp + LASA_Agents_with_Sharp 
                                      + Dispatcher_Agents_with_Sharp + Trace_Agents_with_Sharp
                    ```
                    """)

                    st.markdown("""
                    **6️⃣ ABSENTEEISM ADDITION (Post-Calculation - Configured)**

                    ⚠️ **IMPORTANT:** Absenteeism is applied post-calculation using the configured percentage from parameters.

                    ```
                    Absenteeism_Additional = Base_Total_Agents × Absenteeism% (configured) = """ + f"{detail_reqs['base_agents'] * absenteeism_post_pct:.2f}" + """
                    ```
                    """)

                    st.markdown("""
                    **7️⃣ ROSTER BUFFER ADDITION (5-day working)**

                    ```
                    Roster_Buffer_Additional = Base_Total_Agents × """ + str(st.session_state.get('resource_roster_buffer_pct', 11.0)) + """% = """ + f"{detail_reqs['base_agents'] * (st.session_state.get('resource_roster_buffer_pct', 11.0) / 100.0):.2f}" + """
                    ```
                    """)

                    st.markdown("""
                    **8️⃣ TOTAL AGENTS (FINAL)**

                    ```
                    Total_Agents = Base_Total_Agents 
                                  + Absenteeism_Additional (configured)
                                  + Roster_Buffer_Additional
                              = """ + f"{detail_reqs['base_agents']:.2f}" + " + " + f"{detail_reqs['base_agents'] * absenteeism_post_pct:.2f}" + " + " + f"{detail_reqs['base_agents'] * (st.session_state.get('resource_roster_buffer_pct', 11.0) / 100.0):.2f}" + """
                              = """ + f"{detail_reqs['base_agents'] + (detail_reqs['base_agents'] * absenteeism_post_pct) + (detail_reqs['base_agents'] * (st.session_state.get('resource_roster_buffer_pct', 11.0) / 100.0)):.2f}" + """
                    ```

                    ✅ **This formula uses configured absenteeism and roster buffer parameters.**
                    """)

                    st.markdown("""
                    **PARAMETERS USED FOR THIS CALCULATION:**
                    - Shift Hours: """ + str(SHIFT_HOURS) + """ hrs/day
                    - Absenteeism: """ + str(st.session_state.get('resource_absenteeism_pct', 15.0)) + """%
                    - Roster Buffer: """ + str(st.session_state.get('resource_roster_buffer_pct', 11.0)) + """%
                    - On-Call Pickup: """ + str(ON_CALL_PICKUP) + """ packages
                    - ASP (default): """ + str(st.session_state.get('resource_asp', 150)) + """ packages
                    """)

                    st.markdown("---")

                    # ========== AGENTS DETAILED TASK-WISE BREAKDOWN ==========
                    with st.expander("📋 AGENTS DETAILED TASK-WISE CALCULATIONS", expanded=False):
                        st.markdown("""
                        <div style="color: #565656; font-size: 13px; margin-bottom: 12px;">
                        Complete task-wise breakdown for all 4 agents showing individual task times, parameters used from FAMIS, and total staffing requirements.
                        </div>
                        """, unsafe_allow_html=True)

                        # ========== PARAMETERS APPLIED ==========
                        st.markdown("##### 📊 PARAMETERS APPLIED FOR SELECTED LOC ID: " + selected_loc_id)

                        # Display note about placeholder values
                        if asp_vol == 150:
                            st.warning("📌 **NOTE**: Using placeholder standard values for missing data:\n- ASP Volume (Placeholder) = 150 pkg\n- On-Call Pickup (Placeholder) = 80 pkg")

                        param_col1, param_col2, param_col3, param_col4 = st.columns(4)

                        with param_col1:
                            st.metric("Shift Hours", f"{SHIFT_HOURS} hrs")
                        with param_col2:
                            st.metric("On-Call Pickup", f"{ON_CALL_PICKUP} pkg")
                        with param_col3:
                            st.metric("ASP Volume (from FAMIS ROC)", f"{asp_vol} pkg")
                        with param_col4:
                            st.metric("Roster Buffer", f"{st.session_state.get('resource_roster_buffer_pct', 11.0):.1f}%")

                        st.markdown("---")

                        st.markdown("##### 📈 VOLUME DATA (FAMIS): " + selected_loc_id)
                        vol_col1, vol_col2, vol_col3, vol_col4 = st.columns(4)

                        with vol_col1:
                            st.metric("Gross Volume", f"{gross_vol:,}")
                        with vol_col2:
                            st.metric("IB Volume", f"{ib_vol:,}")
                        with vol_col3:
                            st.metric("OB Volume", f"{ob_vol:,}")
                        with vol_col4:
                            st.metric("ASP Volume", f"{asp_vol:,}")

                        st.markdown("---")

                        # ========== OSA TASK-WISE CALCULATION ==========
                        st.markdown("#### 👩‍💻 OSA – OPERATIONAL SUPPORT ASSISTANT")
                        osa_tasks_detail = [
                            ("IB / OB Scan", osa.get("IB_OB_SCAN_TACT", 0.12), gross_vol, "Gross Volume"),
                            ("Damage Scan & Reporting", osa.get("DAMAGE_SCAN_TACT", 3), ib_vol * osa.get("DAMAGE_SCAN_PCT_IB", 0.005), f"IB × {osa.get('DAMAGE_SCAN_PCT_IB', 0.005)*100:.1f}%"),
                            ("Compliance Report", osa.get("COMPLIANCE_TACT", 5), osa.get("COMPLIANCE_FIXED_COUNT", 2), "Fixed Count"),
                            ("ROD Invoice & BOE", osa.get("ROD_BOE_TACT", 1), ib_vol * ROD_PCT, f"IB × ROD {ROD_PCT*100:.1f}%"),
                            ("Queries Handling Emails", osa.get("EMAIL_QUERY_TACT", 1.5), ib_vol * osa.get("EMAIL_QUERY_PCT_IB", 0.15), f"IB × 15%"),
                            ("NEXT App Actioning", osa.get("NEXT_APP_ACTION_TACT", 4), ib_vol * osa.get("NEXT_APP_ACTION_PCT_IB", 0.015), f"IB × 1.5%"),
                            ("Courier On-Call Support", osa.get("COURIER_ONCALL_TACT", 4), gross_vol * osa.get("COURIER_ONCALL_PCT_TOTAL", 0.05), "Gross × 5%"),
                            ("Incomplete MPS / Holiday", osa.get("INCOMPLETE_MPS_TACT", 0.12), ib_vol * osa.get("INCOMPLETE_MPS_PCT_IB", 0.40), "IB × 40%"),
                            ("Incomplete Report", osa.get("INCOMPLETE_REPORT_TACT", 20), osa.get("INCOMPLETE_REPORT_COUNT", 1), "Fixed Count"),
                            ("Cage Monitoring", osa.get("CAGE_MONITORING_TACT", 2), ib_vol * osa.get("CAGE_MONITORING_PCT_IB", 0.10), "IB × 10%"),
                            ("DEX Monitoring", osa.get("DEX_MONITORING_TACT", 1.2), ib_vol * DEX_PCT, f"IB × DEX {DEX_PCT*100:.1f}%"),
                            ("ROC Activities", osa.get("ROC_ACTIVITIES_TACT", 6), max(roc_vol, 0), f"ROC Volume={roc_vol} pkg"),
                            ("DEX Handling", osa.get("DEX_HANDLING_TACT", 4), ib_vol * DEX_PCT, f"IB × DEX {DEX_PCT*100:.1f}%"),
                            ("Pickup Shipment Handover", osa.get("PICKUP_HANDOVER_TACT", 0.25), max(ob_vol - asp_vol, 0), f"OB({ob_vol})-ASP({asp_vol})={max(ob_vol - asp_vol, 0)}"),
                            ("FAMIS Report", osa.get("FAMIS_TACT", 30), 1, "Fixed Count"),
                            ("Outbound Scan & Load", osa.get("OB_SCAN_LOAD_TACT", 0.1), ob_vol, "OB Volume"),
                            ("IPHP Pre-alert", osa.get("IPHP_PREALERT_TACT", 0.2), CSBIV_PCT * ob_vol, f"CSBIV {CSBIV_PCT*100:.1f}% × OB"),
                            ("IPHP Checking", osa.get("IPHP_CHECKING_TACT", 15), 1, "Fixed Count"),
                            ("InControl Report OB", osa.get("INCONTROL_OB_TACT", 20), 1, "Fixed Count"),
                            ("EGNSL Failure", osa.get("EGNSL_TACT", 15), 1, "Fixed Count"),
                            ("PAR Report", osa.get("PAR_TACT", 10), 1, "Fixed Count(1) → 10×1=10min"),
                            ("ASP Handling", osa.get("ASP_HANDLING_TACT", 0.5), asp_vol, f"ASP Volume (Placeholder)={asp_vol} pkg"),

                            ("REX Application", osa.get("REX_APPLICATION_TACT", 0.2), 0.9 * ob_vol, "0.9 × OB"),
                            ("PPWK Imaging", osa.get("PPWK_IMAGING_TACT", 0.1), 0.8 * ob_vol, "0.8 × OB"),
                            ("Gatekeeper IB & OB", osa.get("GATEKEEPER_TACT", 30), 1, "Fixed Count"),
                            ("KYC", osa.get("KYC_TACT", 2), ib_vol * osa.get("KYC_PCT_IB", 0.02), "IB × 2%"),
                            ("Station Opening & Closing", osa.get("STATION_OPEN_CLOSE_TACT", 10), 1, "Fixed Count"),
                        ]

                        osa_rows_detail = [[name, tact, round(param, 2), round(tact * param, 2)] for name, tact, param, _ in osa_tasks_detail]
                        df_osa_detail = pd.DataFrame(osa_rows_detail, columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)"])
                        total_osa_detail = df_osa_detail["Total Time (mins)"].sum()
                        st.table(df_osa_detail)
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Total OSA Time", f"{total_osa_detail:.0f} min")
                        with c2:
                            st.metric("OSA Hours", f"{total_osa_detail/60:.2f} hrs")
                        with c3:
                            st.metric("OSA Agents Required", f"{(total_osa_detail/60)/SHIFT_HOURS:.2f}")

                        st.markdown("---")

                        # ========== LASA TASK-WISE CALCULATION ==========
                        st.markdown("#### 📋 LASA – LOCATION ADMINISTRATIVE SUPPORT ASSISTANT")
                        lasa_tasks_detail = [
                            ("Mailing ROD Invoice & BOE Copy", lasa.get("MAILING_ROD_BOE_TACT", 1.0), ib_vol * ROD_PCT, f"IB × ROD {ROD_PCT*100:.1f}%"),
                            ("Banking Activities", lasa.get("BANKING_ACTIVITIES_TACT", 15.0), 1, "Fixed Count"),
                            ("Review of AR / OR File Closure", lasa.get("AR_OR_FILE_REVIEW_TACT", 1.5), ib_vol * 0.10, "IB × 10%"),
                            ("Checking Emails & Attending Customer Queries", lasa.get("CHECK_EMAILS_CUSTOMER_QUERIES_TACT", 1.0), (0.25 * ib_vol) + (0.02 * ob_vol), "(0.25 × IB) + (0.02 × OB)"),
                            ("Closure of GCCS for All Open Cases", lasa.get("GCCS_CLOSURE_TACT", 1.0), (0.25 * ib_vol) + (0.05 * (ob_vol - asp_vol)), "(0.25 × IB) + (0.05 × OB-ASP)"),
                            ("Review of Invoice Payment", lasa.get("INVOICE_PAYMENT_REVIEW_TACT", 15.0), 1, "Fixed Count"),
                            ("Preparing Vendor Invoice", lasa.get("PREPARING_VENDOR_INVOICE_TACT", 30.0), 1, "Fixed Count"),
                            ("Raising PO for Utilities & Maintenance", lasa.get("PO_UTILITIES_MAINTENANCE_TACT", 10.0), 1, "Fixed Count"),
                            ("Provision File Submission to Manager", lasa.get("PROVISION_FILE_SUBMISSION_TACT", 5.0), 1, "Fixed Count"),
                            ("Preparing Agreement Draft", lasa.get("AGREEMENT_DRAFT_TACT", 5.0), 1, "Fixed Count"),
                            ("EOD Closure, Tallying and Check", lasa.get("EOD_CLOSURE_TACT", 25.0), 1, "Fixed Count"),
                            ("Other Activities", lasa.get("OTHER_ACTIVITIES_TACT", 20.0), 1, "Fixed Count"),
                        ]

                        lasa_rows_detail = [[name, tact, round(param, 2), round(tact * param, 2)] for name, tact, param, _ in lasa_tasks_detail]
                        df_lasa_detail = pd.DataFrame(lasa_rows_detail, columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)"])
                        total_lasa_detail = df_lasa_detail["Total Time (mins)"].sum()
                        st.table(df_lasa_detail)
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Total LASA Time", f"{total_lasa_detail:.0f} min")
                        with c2:
                            st.metric("LASA Hours", f"{total_lasa_detail/60:.2f} hrs")
                        with c3:
                            st.metric("LASA Agents Required", f"{(total_lasa_detail/60)/SHIFT_HOURS:.2f}")

                        st.markdown("---")

                        # ========== DISPATCHER TASK-WISE CALCULATION ==========
                        st.markdown("#### 📦 DISPATCHER")
                        dispatcher_tasks_detail = [
                            ("Push Dispatch to Couriers as per Route", dispatcher.get("PUSH_DISPATCH_TACT", 1.5), ON_CALL_PICKUP, "On-Call Pickup"),
                            ("Monitoring of Live DEX", dispatcher.get("LIVE_DEX_MONITORING_TACT", 0.5), DEX_PCT * ib_vol, f"DEX {DEX_PCT*100:.1f}% × IB"),
                            ("Monitoring GDP SIMs", dispatcher.get("GDP_SIMS_MONITORING_TACT", 10), 1, "Fixed Count"),
                            ("EDI Updation of Cash and BCN Pickup", dispatcher.get("EDI_CASH_BCN_PICKUP_TACT", 0.5), 0.20 * ob_vol, "OB × 20%"),
                            ("Checking Emails & Responding to Queries", dispatcher.get("EMAIL_QUERY_HANDLING_TACT", 2), 0.03 * gross_vol, "Gross × 3%"),
                            ("Coordinating with Customers", dispatcher.get("CUSTOMER_COORDINATION_TACT", 1), 0.15 * (ob_vol - asp_vol), "15% × (OB-ASP)"),
                            ("Check Account Status in e-ICS", dispatcher.get("EICS_ACCOUNT_STATUS_CHECK_TACT", 5), 1, "Fixed Count"),
                            ("Fraudulent Account Misuse", dispatcher.get("FRAUD_ACCOUNT_MISUSE_TACT", 5), 2, "Fixed Count"),
                            ("Closing Dispatch and EOD Business", dispatcher.get("CLOSE_DISPATCH_EOD_TACT", 0.5), ON_CALL_PICKUP, "On-Call Pickup"),
                        ]

                        dispatcher_rows_detail = [[name, tact, round(param, 2), round(tact * param, 2)] for name, tact, param, _ in dispatcher_tasks_detail]
                        df_dispatcher_detail = pd.DataFrame(dispatcher_rows_detail, columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)"])
                        total_dispatcher_detail = df_dispatcher_detail["Total Time (mins)"].sum()
                        st.table(df_dispatcher_detail)
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Total Dispatcher Time", f"{total_dispatcher_detail:.0f} min")
                        with c2:
                            st.metric("Dispatcher Hours", f"{total_dispatcher_detail/60:.2f} hrs")
                        with c3:
                            st.metric("Dispatcher Agents Required", f"{(total_dispatcher_detail/60)/SHIFT_HOURS:.2f}")

                        st.markdown("---")

                        # ========== TRACE AGENT TASK-WISE CALCULATION ==========
                        st.markdown("#### 🔎 TRACE AGENT")
                        trace_tasks_detail = [
                            ("Calling Customer & Informing Courier for Reattempt", trace_agent.get("CUSTOMER_CALL_REATTEMPT_TACT", 2), 0.02 * gross_vol, "Gross × 2%"),
                            ("Work on Cage Ageing Shipment", trace_agent.get("CAGE_AGEING_SHIPMENT_TACT", 3), 0.02 * gross_vol, "Gross × 2%"),
                            ("Coordinating with Customers and Sales Team", trace_agent.get("CUSTOMER_SALES_COORDINATION_TACT", 2), 0.01 * ob_vol, "OB × 1%"),
                            ("Work on CMOD", trace_agent.get("CMOD_WORK_TACT", 2), 0.02 * gross_vol, "Gross × 2%"),
                            ("Assess Open Cases and Work on Closure", trace_agent.get("OPEN_CASES_CLOSURE_TACT", 3), 0.02 * gross_vol, "Gross × 2%"),
                            ("Reopen Case if Issue Not Resolved", trace_agent.get("REOPEN_CASES_TACT", 20), 1, "Fixed Count"),
                            ("CMOD Report Monitoring and Closure", trace_agent.get("CMOD_REPORT_CLOSURE_TACT", 20), 1, "Fixed Count"),
                        ]

                        trace_rows_detail = [[name, tact, round(param, 2), round(tact * param, 2)] for name, tact, param, _ in trace_tasks_detail]
                        df_trace_detail = pd.DataFrame(trace_rows_detail, columns=["Task", "TACT (mins)", "Parameter Used", "Total Time (mins)"])
                        total_trace_detail = df_trace_detail["Total Time (mins)"].sum()
                        st.table(df_trace_detail)
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Total Trace Time", f"{total_trace_detail:.0f} min")
                        with c2:
                            st.metric("Trace Hours", f"{total_trace_detail/60:.2f} hrs")
                        with c3:
                            st.metric("Trace Agents Required", f"{(total_trace_detail/60)/SHIFT_HOURS:.2f}")

                        st.markdown("---")

                        # ========== SUMMARY ==========
                        st.markdown("#### 📊 TOTAL STAFFING SUMMARY")
                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

                        with summary_col1:
                            total_time_all = total_osa_detail + total_lasa_detail + total_dispatcher_detail + total_trace_detail
                            total_hours_all = total_time_all / 60
                            st.metric("Total Hours (All)", f"{total_hours_all:.2f} hrs")

                        with summary_col2:
                            total_base_agents = (total_osa_detail/60 + total_lasa_detail/60 + total_dispatcher_detail/60 + total_trace_detail/60) / SHIFT_HOURS
                            st.metric("Base Agents Total", f"{total_base_agents:.2f}")

                        with summary_col3:
                            absenteeism_param = st.session_state.get('resource_absenteeism_pct', 15.0) / 100.0
                            absenteeism_amt = total_base_agents * absenteeism_param
                            st.metric(f"Absenteeism ({st.session_state.get('resource_absenteeism_pct', 15.0):.0f}%)", f"{absenteeism_amt:.2f}")

                        with summary_col4:
                            roster_buffer_pct = st.session_state.get('resource_roster_buffer_pct', 11.0) / 100.0
                            roster_add = total_base_agents * roster_buffer_pct
                            st.metric("Roster Buffer", f"{roster_add:.2f}")

                        final_total = total_base_agents + absenteeism_amt + roster_add
                        st.metric("🎯 FINAL TOTAL AGENTS", f"{math.ceil(final_total)}")

            else:
                if master_df is None or master_df.empty:
                    st.warning("📤 Please upload a Station Master file to see detailed resource analysis")
                else:
                    st.info("📅 Select a date with FAMIS data to view resource requirements")
        else:
            st.markdown("""
            <div style="
                background: var(--info-bg);
                border-left: 6px solid var(--fc-purple);
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 16px;
                color: var(--info-text);
            ">
                <div style="font-weight:700;">📤 Upload FAMIS/Volume file to enable OSA monitoring for selected date</div>
            </div>
            """, unsafe_allow_html=True)

    # ============================================================
    # TAB 3: COURIER MONITOR
    # ============================================================
    with tab3:
        st.session_state['health_active_tab'] = 'COURIER'
        # ========== COURIER REQUIREMENT SUMMARY SECTION ===========
        if 'famis_data' in st.session_state and st.session_state['famis_data'] is not None and st.session_state.get('selected_date'):
            famis_df = st.session_state['famis_data']
            master_df = st.session_state.get('master_data', None)
            selected_date = st.session_state['selected_date']

            # Filter data for selected date
            date_famis = famis_df[famis_df['date'] == selected_date].copy()

            if not date_famis.empty and master_df is not None and not master_df.empty:
                # ========== COURIER PARAMETERS ==========
                st.markdown("---")

                pk_st_or = float(st.session_state.get('courier_pk_st_or', 1.5))
                st_hr_or = float(st.session_state.get('courier_st_hr_or', 8.0))
                productivity_hrs = float(st.session_state.get('courier_productivity_hrs', 7.0))
                absenteeism_pct = float(st.session_state.get('courier_absenteeism_pct', 16.0))
                training_pct = float(st.session_state.get('courier_training_pct', 11.0))
                working_days = int(st.session_state.get('courier_working_days', 5))


                # Calculate courier requirements for all stations on selected date
                station_courier_statuses = []

                for idx, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    total_packages = int(row.get('pk_gross_tot', 0))

                    # Use configured PK/ST and ST/HR values (do not fetch from uploaded FAMIS file)
                    pk_st_or_val = pk_st_or
                    st_hr_or_val = st_hr_or

                    # Get courier available from master
                    master_row = master_df[master_df['loc_id'] == loc_id]
                    couriers_available = 0
                    if not master_row.empty:
                        # Look for courier-related columns
                        candidate_cols = ['current_total_couriers', 'couriers_available', 'existing_couriers']
                        for col in candidate_cols:
                            if col in master_row.columns:
                                try:
                                    couriers_available = int(master_row[col].iloc[0])
                                    break
                                except (ValueError, TypeError):
                                    pass

                    # Calculate courier requirements using shared function
                    courier_reqs = calculate_courier_requirements(
                        total_packages,
                        pk_st_or_val,
                        st_hr_or_val,
                        productivity_hrs,
                        couriers_available,
                        absenteeism_pct,
                        training_pct,
                        working_days
                    )

                    # Get total couriers required
                    couriers_required = courier_reqs['total_required_with_training']

                    # Calculate status
                    status = calculate_courier_health_status(
                        couriers_required,
                        couriers_available
                    )
                    status['loc_id'] = loc_id
                    status['couriers_required'] = couriers_required
                    status['couriers_available'] = couriers_available
                    # PK/ST and ST/HR values are intentionally not stored per-station (use configured defaults)

                    station_courier_statuses.append(status)

                # Get summary stats
                courier_summary = get_courier_summary_stats(station_courier_statuses)

                # Store results in session state for publish
                st.session_state['courier_health_results'] = station_courier_statuses
                st.session_state['courier_tab_computed'] = True

                # Display HEADER + STATUS CARDS: 📦 COURIER ANALYSIS
                render_section_header("COURIER ANALYSIS", icon="📦", gradient_end="#FFF6E8", border_color="#FF6200")
                render_status_cards(courier_summary)

                # ========== COURIER SUMMARY TABLE ==========

                # Create summary table
                courier_summary_data = []

                for idx, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    gross_vol = int(row.get('pk_gross_tot', 0))

                    # Get pre-calculated status from station_courier_statuses
                    station_status = next((s for s in station_courier_statuses if s['loc_id'] == loc_id), None)

                    if station_status:
                        couriers_req = station_status['couriers_required']
                        couriers_avail = station_status['couriers_available']
                        deviation = station_status['deviation_percent']
                        emoji = station_status['emoji']
                    else:
                        couriers_req = 0
                        couriers_avail = 0
                        deviation = 0
                        emoji = '❓'

                    # If any primary value is zero or non-positive, show NO DATA
                    if (gross_vol == 0) or (couriers_req <= 0) or (couriers_avail <= 0):
                        courier_summary_data.append({
                            'DATE': selected_date.strftime('%Y-%m-%d'),
                            'LOC ID': loc_id,
                            'VOLUME': '0' if gross_vol == 0 else f"{gross_vol:,}",
                            'CALCULATED COURIERS': '-' if couriers_req <= 0 else f"{couriers_req:.1f}",
                            'CURRENT COURIERS': '-' if couriers_avail <= 0 else f"{couriers_avail:.0f}",
                            'STATUS': '⚪ NO DATA'
                        })
                    else:
                        courier_summary_data.append({
                                'DATE': selected_date.strftime('%Y-%m-%d'),
                                'LOC ID': loc_id,
                                'VOLUME': f"{gross_vol:,}",
                                'CALCULATED COURIERS': f"{couriers_req:.1f}",
                                'CURRENT COURIERS': f"{couriers_avail:.0f}",
                                'STATUS': f"{emoji} {deviation:+.1f}%"
                        })

                courier_summary_df = pd.DataFrame(courier_summary_data)

                # small spacer between cards and table
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                # Display table
                st.dataframe(
                    courier_summary_df,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        'DATE': st.column_config.TextColumn('DATE', width=80),
                        'LOC ID': st.column_config.TextColumn('LOC ID', width=80),
                            'VOLUME': st.column_config.TextColumn('VOLUME', width=90),
                            'CALCULATED COURIERS': st.column_config.TextColumn('CALCULATED COURIERS', width=140),
                            'CURRENT COURIERS': st.column_config.TextColumn('CURRENT COURIERS', width=130),
                            'STATUS': st.column_config.TextColumn('STATUS', width=120)
                    }
                )

            else:
                if master_df is None or master_df.empty:
                    st.warning("📤 Please upload a Station Master file to see detailed courier analysis")
                else:
                    st.info("📅 Select a date with FAMIS data to view courier requirements")
        else:
            st.markdown("""
            <div style="
                background: var(--info-bg);
                border-left: 6px solid var(--fc-purple);
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 16px;
                color: var(--info-text);
            ">
                <div style="font-weight:700;">📤 Upload FAMIS/Volume file to enable courier monitoring for selected date</div>
            </div>
            """, unsafe_allow_html=True)

    # ============================================================
    # UNIFIED PROJECTION SECTION (shared across all monitors)
    # ============================================================
    if 'famis_data' in st.session_state and st.session_state['famis_data'] is not None and st.session_state.get('selected_date'):
        _proj_famis_df = st.session_state['famis_data']
        _proj_master_df = st.session_state.get('master_data', None)
        _proj_selected_date = st.session_state['selected_date']
        _proj_date_famis = _proj_famis_df[_proj_famis_df['date'] == _proj_selected_date].copy()

        if not _proj_date_famis.empty and _proj_master_df is not None and not _proj_master_df.empty:
            # Hide unified projections while viewing Analytics tab
            if st.session_state.get('health_active_tab') != 'ANALYTICS':
                with st.expander("📈 VOLUME PROJECTIONS", expanded=False):
                    _proj_col1, _proj_col2 = st.columns([1, 1])
                    with _proj_col1:
                        _proj_pct = st.number_input(
                            "Projected Volume Increase (%)",
                            min_value=0.0, max_value=500.0,
                            value=st.session_state.get('unified_proj_pct', 10.0),
                            step=1.0, key='unified_proj_pct_input',
                            help="Enter projected percentage increase in volume"
                        )
                        st.session_state['unified_proj_pct'] = _proj_pct
                    with _proj_col2:
                        _proj_type = st.selectbox(
                            "Select Projection Type",
                            ["AREA", "RESOURCE", "COURIER"],
                            index=["AREA", "RESOURCE", "COURIER"].index(
                                st.session_state.get('unified_proj_type', 'AREA')
                            ),
                            key='unified_proj_type_input'
                        )
                        st.session_state['unified_proj_type'] = _proj_type

                    _proj_vol_mult = 1 + (_proj_pct / 100.0)

                    # -------- AREA PROJECTION --------
                    if _proj_type == "AREA":
                        _ap_packs_per_pallet = st.session_state.get('area_packs_per_pallet', 15)
                        _ap_max_volume = st.session_state.get('area_max_volume', 55.0)
                        _ap_sorting_percent = st.session_state.get('area_sorting_percent', 60.0)
                        _ap_aisle_percent = st.session_state.get('area_aisle_percent', 15.0)
                        _ap_cage_percent = st.session_state.get('area_cage_percent', 10.0)

                        _ap_proj_statuses = []
                        _ap_proj_rows = []
                        for _idx, _row in _proj_date_famis.iterrows():
                            _loc = _row['loc_id']
                            _cur_vol = int(_row.get('pk_gross_tot', 0))
                            _prj_vol = int(_cur_vol * _proj_vol_mult)

                            _additional = float(st.session_state.get(f'area_additional_{_loc}', 0))
                            _hc_sel = bool(st.session_state.get(f'add_healthcare_{_loc}', False))
                            _hc_val = float(st.session_state.get(f'area_healthcare_{_loc}', 0) or 0) if _hc_sel else 0.0
                            _dg_sel = bool(st.session_state.get(f'add_dg_{_loc}', False))
                            _dg_val = float(st.session_state.get(f'area_dg_{_loc}', 0) or 0) if _dg_sel else 0.0

                            _prj_calcs = calculate_area_requirements(
                                total_packs=_prj_vol, packs_per_pallet=_ap_packs_per_pallet,
                                max_volume_percent=_ap_max_volume, sorting_area_percent=_ap_sorting_percent,
                                cage_percent=_ap_cage_percent, aisle_percent=_ap_aisle_percent,
                                additional_area_value=_additional
                            )
                            _prj_total = _prj_calcs['total_operational_area'] + _hc_val + _dg_val

                            _m_row = _proj_master_df[_proj_master_df['loc_id'] == _loc]
                            _m_ops = _m_row['ops_area'].iloc[0] if (not _m_row.empty and 'ops_area' in _m_row.columns) else 0
                            _m_ops_f = _to_float(_m_ops, 0.0)

                            _prj_st = calculate_area_status(_prj_total, _m_ops_f)
                            _prj_st['loc_id'] = _loc
                            _ap_proj_statuses.append(_prj_st)

                            _ap_proj_rows.append({
                                'LOC ID': _loc,
                                'VOLUME': f"{_cur_vol:,}",
                                'PROJECTED VOLUME': f"{_prj_vol:,}",
                                'CALCULATED PROJECTED AREA (sqft)': _fmt_area(_prj_total),
                                'CURRENT AREA (sqft)': _fmt_area(_m_ops),
                                'STATUS': f"{_prj_st['emoji']} {_prj_st['deviation_percent']:+.1f}%"
                            })

                        _ap_proj_summary = get_status_summary_stats(_ap_proj_statuses)
                        _proj_card_h = "height:100px; min-height:70px; box-sizing:border-box; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:8px;"
                        _pc1, _pc2, _pc3 = st.columns(3)
                        with _pc1:
                            st.markdown(f"""
                            <div style="background:#ECFDF5;border:1px solid #E6F4E6;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">✅</div>
                                <div style="color:#047857;font-weight:700;font-size:20px;">{_ap_proj_summary['healthy_count']}</div>
                                <div style="color:#059669;font-size:11px;font-weight:600;text-transform:uppercase;">Healthy</div>
                                <div style="font-size:12px;color:#4B5563;margin-top:8px;font-weight:600;">Range: 0-10%</div>

                            </div>
                            """, unsafe_allow_html=True)
                        with _pc2:
                            st.markdown(f"""
                            <div style="background:#FFFBEB;border:1px solid #FEE3C3;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">⚠️</div>
                                <div style="color:#D97706;font-weight:700;font-size:20px;">{_ap_proj_summary['review_needed_count']}</div>
                                <div style="color:#B45309;font-size:11px;font-weight:600;text-transform:uppercase;">Review</div>
                                <div style="font-size:12px;color:#4B5563;margin-top:8px;font-weight:600;">Range: 10-20%</div>

                            </div>
                            """, unsafe_allow_html=True)
                        with _pc3:
                            st.markdown(f"""
                            <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">🚨</div>
                                <div style="color:#DC2626;font-weight:700;font-size:20px;">{_ap_proj_summary['critical_count']}</div>
                                <div style="color:#991B1B;font-size:11px;font-weight:600;text-transform:uppercase;">Critical</div>
                                <div style="font-size:12px;color:#4B5563;margin-top:8px;font-weight:600;">Range: &gt;20%</div>

                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("")
                        st.dataframe(
                            pd.DataFrame(_ap_proj_rows),
                            use_container_width=True, hide_index=True,
                            column_config={
                                'LOC ID': st.column_config.TextColumn('LOC ID', width=90),
                                'VOLUME': st.column_config.TextColumn('VOLUME', width=110),
                                'PROJECTED VOLUME': st.column_config.TextColumn('PROJECTED VOLUME', width=130),
                                'CALCULATED PROJECTED AREA (sqft)': st.column_config.TextColumn('CALCULATED PROJECTED AREA (sqft)', width=220),
                                'CURRENT AREA (sqft)': st.column_config.TextColumn('CURRENT AREA (sqft)', width=160),
                                'STATUS': st.column_config.TextColumn('STATUS', width=110)
                            }
                        )

                        # -------- AREA PROJECTION DETAIL DROPDOWN --------
                        st.markdown("---")
                        _ap_locs = sorted(_proj_date_famis['loc_id'].unique())
                        _ap_detail_loc = st.selectbox(
                            "Select Station for Detailed Area Breakdown",
                            _ap_locs,
                            key='proj_area_detail_loc'
                        )

                        _ap_detail_row = _proj_date_famis[_proj_date_famis['loc_id'] == _ap_detail_loc].iloc[0]
                        _ap_d_cur_vol = int(_ap_detail_row.get('pk_gross_tot', 0))
                        _ap_d_prj_vol = int(_ap_d_cur_vol * _proj_vol_mult)

                        _ap_d_additional = float(st.session_state.get(f'area_additional_{_ap_detail_loc}', 0))
                        _ap_d_hc_sel = bool(st.session_state.get(f'add_healthcare_{_ap_detail_loc}', False))
                        _ap_d_hc_val = float(st.session_state.get(f'area_healthcare_{_ap_detail_loc}', 0) or 0) if _ap_d_hc_sel else 0.0
                        _ap_d_dg_sel = bool(st.session_state.get(f'add_dg_{_ap_detail_loc}', False))
                        _ap_d_dg_val = float(st.session_state.get(f'area_dg_{_ap_detail_loc}', 0) or 0) if _ap_d_dg_sel else 0.0

                        _ap_d_calcs = calculate_area_requirements(
                            total_packs=_ap_d_prj_vol,
                            packs_per_pallet=_ap_packs_per_pallet,
                            max_volume_percent=_ap_max_volume,
                            sorting_area_percent=_ap_sorting_percent,
                            cage_percent=_ap_cage_percent,
                            aisle_percent=_ap_aisle_percent,
                            additional_area_value=_ap_d_additional
                        )
                        _ap_d_total = _ap_d_calcs['total_operational_area'] + _ap_d_hc_val + _ap_d_dg_val

                        _ap_d_m_row = _proj_master_df[_proj_master_df['loc_id'] == _ap_detail_loc]
                        _ap_d_m_ops = _ap_d_m_row['ops_area'].iloc[0] if (not _ap_d_m_row.empty and 'ops_area' in _ap_d_m_row.columns) else 0
                        _ap_d_m_ops_f = _to_float(_ap_d_m_ops, 0.0)

                        st.markdown(f"##### 📍 {_ap_detail_loc} — Projected Area Breakdown (Volume: {_ap_d_cur_vol:,} → {_ap_d_prj_vol:,})")

                        _ap_d_metrics = [
                            ["Total Projected Packages", f"{_ap_d_prj_vol:,}", "Input volume after projection increase"],
                            ["Pallets Required", f"{_ap_d_calcs['pallets_required']}", f"ceil({_ap_d_prj_vol} / {_ap_packs_per_pallet})"],
                            ["Avg Hourly Pallets", f"{_ap_d_calcs['avg_hourly_pallets']}", f"ceil(Pallets × {_ap_max_volume}%)"],
                            ["Base Area (sqft)", _fmt_area(_ap_d_calcs['area_required']), "Hourly Pallets × Pallet Area (16 sqft)"],
                            ["Area with Aisle (sqft)", _fmt_area(_ap_d_calcs['area_with_aisle']), f"Base × (1 + {_ap_aisle_percent}%)"],
                            ["Sorting Area (sqft)", _fmt_area(_ap_d_calcs['sorting_area']), f"Area with Aisle × {_ap_sorting_percent}%"],
                            ["Cage Area (sqft)", _fmt_area(_ap_d_calcs['cage_area_required']), "Model-based (volume tier)"],
                            ["Equipment Area (sqft)", _fmt_area(_ap_d_calcs['equipment_area']), "VMeasure + HPT + ROC + LEO + Scale + Forklift + Cage"],
                            ["Additional Area (sqft)", _fmt_area(_ap_d_calcs['additional_area']), "User-configured"],
                        ]
                        if _ap_d_hc_sel:
                            _ap_d_metrics.append(["Healthcare Area (sqft)", _fmt_area(_ap_d_hc_val), "User-configured"])
                        if _ap_d_dg_sel:
                            _ap_d_metrics.append(["DG Area (sqft)", _fmt_area(_ap_d_dg_val), "User-configured"])
                        _ap_d_metrics.append(["TOTAL PROJECTED AREA (sqft)", _fmt_area(_ap_d_total), "Sum of all components"])
                        _ap_d_metrics.append(["CURRENT AREA (sqft)", _fmt_area(_ap_d_m_ops_f), "From Station Master"])

                        _ap_d_df = pd.DataFrame(_ap_d_metrics, columns=["Component", "Value", "Formula / Source"])
                        st.table(_ap_d_df)

                    # -------- RESOURCE PROJECTION --------
                    elif _proj_type == "RESOURCE":
                        _rp_shift = float(st.session_state.get('resource_shift_hours', 9.0))
                        _rp_abs_pct = float(st.session_state.get('resource_absenteeism_pct', 11.0)) / 100.0
                        _rp_train = 0.0
                        _rp_roster = float(st.session_state.get('resource_roster_buffer_pct', 11.0)) / 100.0
                        _rp_oncall = int(st.session_state.get('resource_on_call_pickup', 80))
                        _rp_dex = 0.05
                        _rp_csbiv = 0.80
                        _rp_rod = 0.30

                        _rp_proj_statuses = []
                        _rp_proj_rows = []
                        for _idx, _row in _proj_date_famis.iterrows():
                            _loc = _row['loc_id']
                            _cur_vol = int(_row.get('pk_gross_tot', 0))
                            _prj_vol = int(_cur_vol * _proj_vol_mult)

                            _ib = int(_row.get('pk_gross_inb', 0))
                            _ob = int(_row.get('pk_gross_outb', 0))
                            _roc_f = int(_row.get('pk_roc', 0))
                            _roc_v = int(_roc_f * 0.25)
                            _asp_v = _roc_f - _roc_v

                            # Projected volumes for IB/OB scale proportionally
                            _prj_ib = int(_ib * _proj_vol_mult)
                            _prj_ob = int(_ob * _proj_vol_mult)

                            _prj_reqs = calculate_resource_requirements(
                                total_volume=_prj_vol, ib_volume=_prj_ib, ob_volume=_prj_ob,
                                roc_volume=_roc_v, asp_volume=_asp_v,
                                shift_hours=_rp_shift, absenteeism_pct=_rp_abs_pct,
                                training_pct=_rp_train, roster_buffer_pct=_rp_roster,
                                on_call_pickup=_rp_oncall, dex_pct=_rp_dex,
                                csbiv_pct=_rp_csbiv, rod_pct=_rp_rod
                            )
                            _prj_base = _prj_reqs.get('base_agents', 0)
                            _abs_post = st.session_state.get('resource_absenteeism_pct', 15.0) / 100.0
                            _rb_post = st.session_state.get('resource_roster_buffer_pct', 11.0) / 100.0
                            _prj_agents = _prj_base + (_prj_base * _abs_post) + (_prj_base * _rb_post)

                            _m_row = _proj_master_df[_proj_master_df['loc_id'] == _loc]
                            _master_agents = 0
                            if not _m_row.empty and 'current_total_osa' in _m_row.columns:
                                _master_agents = _to_float(_m_row['current_total_osa'].iloc[0], 0.0)

                            _prj_st = calculate_resource_health_status(_prj_agents, _master_agents)
                            _prj_st['loc_id'] = _loc
                            _rp_proj_statuses.append(_prj_st)

                            _rp_proj_rows.append({
                                'LOC ID': _loc,
                                'VOLUME': f"{_cur_vol:,}",
                                'PROJECTED VOLUME': f"{_prj_vol:,}",
                                'CALCULATED PROJECTED RESOURCES': f"{_prj_agents:.2f}",
                                'CURRENT STATION AGENTS': f"{_master_agents:.0f}",
                                'STATUS': f"{_prj_st['emoji']} {_prj_st['deviation_percent']:+.1f}%"
                            })

                        _rp_proj_summary = get_resource_summary_stats(_rp_proj_statuses)
                        _proj_card_h = "height:100px; min-height:70px; box-sizing:border-box; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:8px;"
                        _pc1, _pc2, _pc3 = st.columns(3)
                        with _pc1:
                            st.markdown(f"""
                            <div style="background:#ECFDF5;border:1px solid #E6F4E6;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">✅</div>
                                <div style="color:#047857;font-weight:700;font-size:20px;">{_rp_proj_summary['healthy_count']}</div>
                                <div style="color:#059669;font-size:11px;font-weight:600;text-transform:uppercase;">Healthy</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with _pc2:
                            st.markdown(f"""
                            <div style="background:#FFFBEB;border:1px solid #FEE3C3;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">⚠️</div>
                                <div style="color:#D97706;font-weight:700;font-size:20px;">{_rp_proj_summary['review_needed_count']}</div>
                                <div style="color:#B45309;font-size:11px;font-weight:600;text-transform:uppercase;">Review</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with _pc3:
                            st.markdown(f"""
                            <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">🚨</div>
                                <div style="color:#DC2626;font-weight:700;font-size:20px;">{_rp_proj_summary['critical_count']}</div>
                                <div style="color:#991B1B;font-size:11px;font-weight:600;text-transform:uppercase;">Critical</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("")
                        st.dataframe(
                            pd.DataFrame(_rp_proj_rows),
                            use_container_width=True, hide_index=True,
                            column_config={
                                'LOC ID': st.column_config.TextColumn('LOC ID', width=90),
                                'VOLUME': st.column_config.TextColumn('VOLUME', width=110),
                                'PROJECTED VOLUME': st.column_config.TextColumn('PROJECTED VOLUME', width=130),
                                'CALCULATED PROJECTED RESOURCES': st.column_config.TextColumn('CALCULATED PROJECTED RESOURCES', width=220),
                                'CURRENT STATION AGENTS': st.column_config.TextColumn('CURRENT STATION AGENTS', width=170),
                                'STATUS': st.column_config.TextColumn('STATUS', width=110)
                            }
                        )

                        # -------- RESOURCE PROJECTION DETAIL DROPDOWN --------
                        st.markdown("---")
                        _rp_locs = sorted(_proj_date_famis['loc_id'].unique())
                        _rp_detail_loc = st.selectbox(
                            "Select Station for Detailed Resource Breakdown",
                            _rp_locs,
                            key='proj_resource_detail_loc'
                        )

                        _rp_d_row = _proj_date_famis[_proj_date_famis['loc_id'] == _rp_detail_loc].iloc[0]
                        _rp_d_cur_vol = int(_rp_d_row.get('pk_gross_tot', 0))
                        _rp_d_prj_vol = int(_rp_d_cur_vol * _proj_vol_mult)
                        _rp_d_ib = int(int(_rp_d_row.get('pk_gross_inb', 0)) * _proj_vol_mult)
                        _rp_d_ob = int(int(_rp_d_row.get('pk_gross_outb', 0)) * _proj_vol_mult)
                        _rp_d_roc_f = int(_rp_d_row.get('pk_roc', 0))
                        _rp_d_roc_v = int(_rp_d_roc_f * 0.25)
                        _rp_d_asp_v = _rp_d_roc_f - _rp_d_roc_v

                        _rp_d_reqs = calculate_resource_requirements(
                            total_volume=_rp_d_prj_vol,
                            ib_volume=_rp_d_ib,
                            ob_volume=_rp_d_ob,
                            roc_volume=_rp_d_roc_v,
                            asp_volume=_rp_d_asp_v,
                            shift_hours=_rp_shift,
                            absenteeism_pct=_rp_abs_pct,
                            training_pct=_rp_train,
                            roster_buffer_pct=_rp_roster,
                            on_call_pickup=_rp_oncall,
                            dex_pct=_rp_dex,
                            csbiv_pct=_rp_csbiv,
                            rod_pct=_rp_rod
                        )

                        st.markdown(f"##### \U0001f4cd {_rp_detail_loc} — Projected Resource Breakdown (Volume: {_rp_d_cur_vol:,} → {_rp_d_prj_vol:,})")

                        # Time breakdown per role
                        _rp_d_time_data = [
                            ["OSA", f"{_rp_d_reqs['osa_time_minutes']:.0f} min", f"{_rp_d_reqs['osa_hours']:.2f} hrs", f"{_rp_d_reqs['osa_agents']:.2f}", f"{_rp_d_reqs['osa_agents_with_sharp']:.2f}"],
                            ["LASA", f"{_rp_d_reqs['lasa_time_minutes']:.0f} min", f"{_rp_d_reqs['lasa_hours']:.2f} hrs", f"{_rp_d_reqs['lasa_agents']:.2f}", f"{_rp_d_reqs['lasa_agents_with_sharp']:.2f}"],
                            ["Dispatcher", f"{_rp_d_reqs['dispatcher_time_minutes']:.0f} min", f"{_rp_d_reqs['dispatcher_hours']:.2f} hrs", f"{_rp_d_reqs['dispatcher_agents']:.2f}", f"{_rp_d_reqs['dispatcher_agents_with_sharp']:.2f}"],
                            ["Trace", f"{_rp_d_reqs['trace_time_minutes']:.0f} min", f"{_rp_d_reqs['trace_hours']:.2f} hrs", f"{_rp_d_reqs['trace_agents']:.2f}", f"{_rp_d_reqs['trace_agents_with_sharp']:.2f}"],
                        ]
                        _rp_d_time_df = pd.DataFrame(_rp_d_time_data, columns=["Role", "Total Time", "Hours", "Base Agents", "Agents (with SHARP)"])
                        st.table(_rp_d_time_df)

                        # Staffing summary
                        _rp_d_base = _rp_d_reqs['base_agents']
                        _rp_d_abs = _rp_d_base * _rp_abs_pct
                        _rp_d_rost = _rp_d_base * _rp_roster
                        _rp_d_final = _rp_d_base + _rp_d_abs + _rp_d_rost

                        _rp_d_staff = [
                            ["Base Agents (sum of all roles with SHARP)", f"{_rp_d_base:.2f}"],
                            [f"Absenteeism ({st.session_state.get('resource_absenteeism_pct', 11.0):.0f}%)", f"{_rp_d_abs:.2f}"],
                            [f"Roster Buffer ({st.session_state.get('resource_roster_buffer_pct', 11.0):.0f}%)", f"{_rp_d_rost:.2f}"],
                            ["TOTAL PROJECTED AGENTS", f"{_rp_d_final:.2f}"],
                        ]
                        _rp_d_staff_df = pd.DataFrame(_rp_d_staff, columns=["Component", "Value"])
                        st.table(_rp_d_staff_df)

                    # -------- COURIER PROJECTION --------
                    elif _proj_type == "COURIER":
                        _cp_pk_st = float(st.session_state.get('courier_pk_st_or', 1.5))
                        _cp_st_hr = float(st.session_state.get('courier_st_hr_or', 8.0))
                        _cp_prod = float(st.session_state.get('courier_productivity_hrs', 7.0))
                        _cp_abs = float(st.session_state.get('courier_absenteeism_pct', 16.0))
                        _cp_train = float(st.session_state.get('courier_training_pct', 11.0))
                        _cp_wd = int(st.session_state.get('courier_working_days', 5))

                        _cp_proj_statuses = []
                        _cp_proj_rows = []
                        for _idx, _row in _proj_date_famis.iterrows():
                            _loc = _row['loc_id']
                            _cur_vol = int(_row.get('pk_gross_tot', 0))
                            _prj_vol = int(_cur_vol * _proj_vol_mult)

                            # Use configured PK/ST and ST/HR values for projections (do not read from FAMIS)
                            _pk_st_val = _cp_pk_st
                            _st_hr_val = _cp_st_hr

                            # Master couriers
                            _m_row = _proj_master_df[_proj_master_df['loc_id'] == _loc]
                            _couriers_avail = 0
                            if not _m_row.empty:
                                for _col in ['current_total_couriers', 'couriers_available', 'existing_couriers']:
                                    if _col in _m_row.columns:
                                        try:
                                            _couriers_avail = int(_m_row[_col].iloc[0])
                                            break
                                        except (ValueError, TypeError):
                                            pass

                            _prj_cour_reqs = calculate_courier_requirements(
                                _prj_vol, _pk_st_val, _st_hr_val,
                                _cp_prod, _couriers_avail,
                                _cp_abs, _cp_train,
                                _cp_wd
                            )
                            _prj_couriers = _prj_cour_reqs['total_required_with_training']

                            _prj_st = calculate_courier_health_status(_prj_couriers, _couriers_avail)
                            _prj_st['loc_id'] = _loc
                            _cp_proj_statuses.append(_prj_st)

                            _cp_proj_rows.append({
                                'LOC ID': _loc,
                                'VOLUME': f"{_cur_vol:,}",
                                'PROJECTED VOLUME': f"{_prj_vol:,}",
                                'CALCULATED PROJECTED COURIERS': f"{_prj_couriers:.1f}",
                                'CURRENT COURIERS': f"{_couriers_avail:.0f}",
                                'STATUS': f"{_prj_st['emoji']} {_prj_st['deviation_percent']:+.1f}%"
                            })

                        _cp_proj_summary = get_courier_summary_stats(_cp_proj_statuses)
                        _proj_card_h = "height:100px; min-height:70px; box-sizing:border-box; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:8px;"
                        _pc1, _pc2, _pc3 = st.columns(3)
                        with _pc1:
                            st.markdown(f"""
                            <div style="background:#ECFDF5;border:1px solid #E6F4E6;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">✅</div>
                                <div style="color:#047857;font-weight:700;font-size:20px;">{_cp_proj_summary['healthy_count']}</div>
                                <div style="color:#059669;font-size:11px;font-weight:600;text-transform:uppercase;">Healthy</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with _pc2:
                            st.markdown(f"""
                            <div style="background:#FFFBEB;border:1px solid #FEE3C3;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">⚠️</div>
                                <div style="color:#D97706;font-weight:700;font-size:20px;">{_cp_proj_summary['review_needed_count']}</div>
                                <div style="color:#B45309;font-size:11px;font-weight:600;text-transform:uppercase;">Review</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with _pc3:
                            st.markdown(f"""
                            <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,0.04);{_proj_card_h}">
                                <div style="font-size:18px;">🚨</div>
                                <div style="color:#DC2626;font-weight:700;font-size:20px;">{_cp_proj_summary['critical_count']}</div>
                                <div style="color:#991B1B;font-size:11px;font-weight:600;text-transform:uppercase;">Critical</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("")
                        st.dataframe(
                            pd.DataFrame(_cp_proj_rows),
                            use_container_width=True, hide_index=True,
                            column_config={
                                'LOC ID': st.column_config.TextColumn('LOC ID', width=90),
                                'VOLUME': st.column_config.TextColumn('VOLUME', width=110),
                                'PROJECTED VOLUME': st.column_config.TextColumn('PROJECTED VOLUME', width=130),
                                'CALCULATED PROJECTED COURIERS': st.column_config.TextColumn('CALCULATED PROJECTED COURIERS', width=220),
                                'CURRENT COURIERS': st.column_config.TextColumn('CURRENT COURIERS', width=160),
                                'STATUS': st.column_config.TextColumn('STATUS', width=110)
                            }
                        )

                        # ── DETAILED PER-LOCATION BREAKDOWN ──
                        st.markdown("")
                        with st.expander("📋 COURIER PROJECTION — DETAILED BREAKDOWN", expanded=False):
                            _cp_locs = sorted(_proj_date_famis['loc_id'].unique())
                            _cp_detail_loc = st.selectbox(
                                "Select Station for Detailed Courier Breakdown",
                                _cp_locs,
                                key='proj_courier_detail_loc'
                            )

                            _row2 = _proj_date_famis[_proj_date_famis['loc_id'] == _cp_detail_loc].iloc[0]
                            _loc2 = _row2['loc_id']
                            _cur_vol2 = int(_row2.get('pk_gross_tot', 0))
                            _prj_vol2 = int(_cur_vol2 * _proj_vol_mult)

                            # Use configured PK/ST and ST/HR values (do not read from FAMIS)
                            _pk_st_v2 = _cp_pk_st
                            _st_hr_v2 = _cp_st_hr

                            _m_row2 = _proj_master_df[_proj_master_df['loc_id'] == _loc2]
                            _c_avail2 = 0
                            if not _m_row2.empty:
                                for _col2 in ['current_total_couriers', 'couriers_available', 'existing_couriers']:
                                    if _col2 in _m_row2.columns:
                                        try:
                                            _c_avail2 = int(_m_row2[_col2].iloc[0])
                                            break
                                        except (ValueError, TypeError):
                                            pass

                            _cr2 = calculate_courier_requirements(
                                _prj_vol2, _pk_st_v2, _st_hr_v2,
                                _cp_prod, _c_avail2,
                                _cp_abs, _cp_train,
                                _cp_wd
                            )
                            _cs2 = calculate_courier_health_status(_cr2['total_required_with_training'], _c_avail2)

                            _prod_per_hr = _pk_st_v2 * _st_hr_v2 * _cp_prod
                            _is_optimal = _prod_per_hr > 0 and _prj_vol2 <= (_c_avail2 * _prod_per_hr)

                            st.markdown(
                                f'<div style="font-weight:700;color:#4D148C;font-size:14px;margin:12px 0 6px 0;'
                                f'border-bottom:2px solid #4D148C;padding-bottom:4px;'>
                                f'📍 {_loc2}</div>',
                                unsafe_allow_html=True
                            )
                            _d1, _d2, _d3, _d4 = st.columns(4)
                            with _d1:
                                st.metric("Curr Volume", f"{_cur_vol2:,}")
                            with _d2:
                                st.metric("Proj Volume", f"{_prj_vol2:,}")
                            with _d3:
                                st.metric("PK/ST (FAMIS)", f"{_pk_st_v2:.2f}")
                            with _d4:
                                st.metric("ST/H (FAMIS)", f"{_st_hr_v2:.2f}")

                            _d5, _d6, _d7, _d8 = st.columns(4)
                            with _d5:
                                st.metric("Prod. per Hr", f"{_prod_per_hr:.1f} pkgs")
                            with _d6:
                                st.metric("Couriers Required", f"{_cr2['total_required_with_training']:.1f}")
                            with _d7:
                                st.metric("Couriers Available", f"{_c_avail2}")
                            with _d8:
                                _delta_v = _c_avail2 - _cr2['total_required_with_training']
                                st.metric("Delta", f"{_delta_v:+.1f}")

                            _opt_label = "✅ OPTIMAL" if _is_optimal else "⚠️ NOT OPTIMAL"
                            _opt_color = "#008A00" if _is_optimal else "#DE002E"
                            st.markdown(
                                f'<div style="display:inline-block;padding:4px 12px;border-radius:4px;'
                                f'background:{"#E8F5E8" if _is_optimal else "#FDE8EC"};'
                                f'color:{_opt_color};font-weight:700;font-size:12px;margin-bottom:8px;'>
                                f'Productivity at projected volume: {_opt_label} '
                                f'| Status: {_cs2["emoji"]} {_cs2["deviation_percent"]:+.1f}%</div>',
                                unsafe_allow_html=True
                            )

                    st.markdown("---")

        # ============================================================
    # TAB 4: ANALYTICS
    # ============================================================
    with tab4:
        st.session_state['health_active_tab'] = 'ANALYTICS'
        st.markdown("""
        <div style="
            background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
            border-left: 6px solid #4D148C;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
        ">
            <div style="font-weight:700;color:#333333;font-size:16px;">📊 ANALYTICS DASHBOARD</div>
            <div style="color:#565656; font-size:13px; margin-top:4px;">Visual insights from published health reports</div>
        </div>
        """, unsafe_allow_html=True)

        # Load saved/published report data for analytics
        area_report = read_report_sheet("AREA HEALTH SUMMARY")
        resource_report = read_report_sheet("RESOURCE HEALTH SUMMARY")
        courier_report = read_report_sheet("COURIER HEALTH SUMMARY")

        has_report_data = not area_report.empty or not resource_report.empty or not courier_report.empty

        if has_report_data:
            # Use area report as primary source for volume trends
            _primary = area_report if not area_report.empty else (resource_report if not resource_report.empty else courier_report)
            _primary = _primary.copy()
            _primary['date'] = pd.to_datetime(_primary['DATE']).dt.normalize()
            _primary['volume_num'] = pd.to_numeric(
                _primary['VOLUME'].astype(str).str.replace(',', '', regex=False),
                errors='coerce'
            ).fillna(0)

            all_dates_sorted = sorted(_primary['date'].unique())

            # ---- Date range filter ----
            an_col1, an_col2, an_col3 = st.columns([1, 1, 1])
            with an_col1:
                an_date_from = st.selectbox(
                    "From", all_dates_sorted,
                    format_func=lambda x: x.strftime('%Y-%m-%d'),
                    index=0, key='analytics_from'
                )
            with an_col2:
                an_date_to = st.selectbox(
                    "To", all_dates_sorted,
                    format_func=lambda x: x.strftime('%Y-%m-%d'),
                    index=len(all_dates_sorted) - 1, key='analytics_to'
                )
            with an_col3:
                an_timeframe = st.radio(
                    "Timeframe", ["DAILY", "WEEKLY", "MONTHLY"],
                    horizontal=True, key='analytics_timeframe'
                )

            mask = (_primary['date'] >= an_date_from) & (_primary['date'] <= an_date_to)
            filtered_df = _primary[mask].copy()

            # Helper: resample / aggregate a date-indexed DataFrame by chosen timeframe
            def _resample_by_timeframe(df, date_col, value_cols, agg='sum'):
                """Group *df* by the chosen timeframe and aggregate *value_cols*.
                Returns a DataFrame with a new 'period_label' column for the x-axis.
                """
                _tmp = df.copy()
                _tmp[date_col] = pd.to_datetime(_tmp[date_col])
                if an_timeframe == 'DAILY':
                    # Normalize to calendar day to avoid splits by time-of-day
                    _tmp['_period'] = _tmp[date_col].dt.normalize()
                    _tmp['period_label'] = _tmp['_period'].dt.strftime('%Y-%m-%d')
                elif an_timeframe == 'WEEKLY':
                    _tmp['_period'] = _tmp[date_col].dt.to_period('W').apply(lambda p: p.start_time)
                    _tmp['period_label'] = _tmp['_period'].dt.strftime('W/C %Y-%m-%d')
                else:  # MONTHLY
                    _tmp['_period'] = _tmp[date_col].dt.to_period('M').apply(lambda p: p.start_time)
                    _tmp['period_label'] = _tmp['_period'].dt.strftime('%b %Y')
                grp = _tmp.groupby(['_period', 'period_label'], as_index=False)
                if agg == 'sum':
                    out = grp[value_cols].sum()
                else:
                    out = grp[value_cols].mean()
                return out.sort_values('_period').reset_index(drop=True)

            if filtered_df.empty:
                st.warning("\u26a0\ufe0f No data in the selected date range.")
            else:
                # ==========================================================
                # CHART 1 \u2014 Volume Trend Over Time (Line + Area)
                # ==========================================================
                st.markdown("---")
                st.markdown("""
                <div style="font-weight:900;color:#4D148C;font-size:20px;margin-bottom:6px;letter-spacing:-0.3px;font-family:'DM Sans',sans-serif;text-transform:uppercase;">\U0001f4c8 1. VOLUME TREND OVER TIMELINE</div>
                """, unsafe_allow_html=True)

                # Prefer using persisted FAMIS upload totals (pk_gross_tot / pk_gross_inb / pk_gross_outb)
                # because uploaded files contain raw gross counts. If no persisted upload exists,
                # fall back to the saved report sheet aggregation.
                _famis_raw = read_famis_uploads()
                if not _famis_raw.empty and 'date' in _famis_raw.columns and 'pk_gross_tot' in _famis_raw.columns:
                    _famis_raw['date'] = pd.to_datetime(_famis_raw['date']).dt.normalize()
                    for _nc in ['pk_gross_tot', 'pk_gross_inb', 'pk_gross_outb']:
                        if _nc in _famis_raw.columns:
                            _famis_raw[_nc] = pd.to_numeric(_famis_raw[_nc], errors='coerce').fillna(0)
                    _famis_filt = _famis_raw[(_famis_raw['date'] >= an_date_from) & (_famis_raw['date'] <= an_date_to)]
                    _vol_daily = _famis_filt.groupby('date', as_index=False).agg(
                        TOTAL_VOLUME=('pk_gross_tot', 'sum'),
                        INBOUND=('pk_gross_inb', 'sum'),
                        OUTBOUND=('pk_gross_outb', 'sum')
                    )
                else:
                    # Fallback: aggregate from published report sheet
                    _vol_daily = (
                        filtered_df
                        .groupby('date', as_index=False)
                        .agg(TOTAL_VOLUME=('volume_num', 'sum'))
                    )

                    # Load persisted FAMIS upload data for IB/OB breakdown (optional enrichment)
                    if not _famis_raw.empty and 'date' in _famis_raw.columns:
                        _famis_raw['date'] = pd.to_datetime(_famis_raw['date']).dt.normalize()
                        for _nc in ['pk_gross_inb', 'pk_gross_outb']:
                            if _nc in _famis_raw.columns:
                                _famis_raw[_nc] = pd.to_numeric(_famis_raw[_nc], errors='coerce').fillna(0)
                        _famis_filt = _famis_raw[(_famis_raw['date'] >= an_date_from) & (_famis_raw['date'] <= an_date_to)]
                        _ib_ob_daily = _famis_filt.groupby('date', as_index=False).agg(
                            INBOUND=('pk_gross_inb', 'sum'),
                            OUTBOUND=('pk_gross_outb', 'sum')
                        )
                        _vol_daily = _vol_daily.merge(_ib_ob_daily[['date', 'INBOUND', 'OUTBOUND']], on='date', how='left')
                        _vol_daily['INBOUND'] = _vol_daily['INBOUND'].fillna(0)
                        _vol_daily['OUTBOUND'] = _vol_daily['OUTBOUND'].fillna(0)
                    else:
                        _vol_daily['INBOUND'] = 0
                        _vol_daily['OUTBOUND'] = 0

                vol_trend = _resample_by_timeframe(_vol_daily, 'date', ['TOTAL_VOLUME', 'INBOUND', 'OUTBOUND'], agg='sum')

                fig_vol = go.Figure()
                fig_vol.add_trace(go.Scatter(
                    x=vol_trend['period_label'], y=vol_trend['TOTAL_VOLUME'],
                    mode='lines+markers', name='Total Volume',
                    line=dict(color='#4D148C', width=3),
                    marker=dict(size=8, color='#4D148C'),
                    fill='tozeroy', fillcolor='rgba(77,20,140,0.08)'
                ))
                fig_vol.add_trace(go.Scatter(
                    x=vol_trend['period_label'], y=vol_trend['INBOUND'],
                    mode='lines+markers', name='Inbound',
                    line=dict(color='#FF6200', width=2, dash='dot'),
                    marker=dict(size=6, color='#FF6200')
                ))
                fig_vol.add_trace(go.Scatter(
                    x=vol_trend['period_label'], y=vol_trend['OUTBOUND'],
                    mode='lines+markers', name='Outbound',
                    line=dict(color='#008A00', width=2, dash='dash'),
                    marker=dict(size=6, color='#008A00')
                ))
                fig_vol.update_layout(
                    template='plotly_white',
                    height=380,
                    margin=dict(l=40, r=20, t=30, b=40),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
                    xaxis_title=an_timeframe.title() + ' Period', yaxis_title='Packages',
                    font=dict(family='DM Sans, Inter, sans-serif', size=12)
                )
                st.plotly_chart(fig_vol, width="stretch")

                # --- Adjust Y-axis to an "assumed" zoomed range to better show trend variations
                try:
                    _vals = vol_trend[['TOTAL_VOLUME', 'INBOUND', 'OUTBOUND']].fillna(0)
                    _vmin = float(_vals.min().min())
                    _vmax = float(_vals.max().max())
                    _span = _vmax - _vmin
                    if _span <= 0:
                        _y0 = max(0, _vmin * 0.9)
                        _y1 = _vmax * 1.1 if _vmax > 0 else 1
                    else:
                        # Use padding = max(20% of span, 3% of max) to avoid over-zoom
                        _pad = max(_span * 0.20, _vmax * 0.03)
                        _y0 = max(0, _vmin - _pad)
                        _y1 = _vmax + _pad

                    # Only apply zoomed axis when it meaningfully reduces total range
                    if _y1 - _y0 < (_vmax * 0.98):
                        fig_vol.update_yaxes(range=[_y0, _y1])
                except Exception:
                    pass

                # ==========================================================
                # CHART 2 \u2014 Facility Performance Ranking
                # ==========================================================
                st.markdown("---")
                st.markdown("""
                <div style="font-weight:900;color:#4D148C;font-size:20px;margin-bottom:8px;letter-spacing:-0.3px;font-family:'DM Sans',sans-serif;text-transform:uppercase;">\U0001f3c6 2. FACILITY PERFORMANCE RANKING</div>
                """, unsafe_allow_html=True)

                perf_metric = st.selectbox(
                    "Select metric to rank facilities by",
                    ["AREA", "RESOURCE", "COURIER"],
                    key='perf_metric_select'
                )

                _perf_sheet_map = {"AREA": area_report, "RESOURCE": resource_report, "COURIER": courier_report}
                _perf_report = _perf_sheet_map[perf_metric].copy()

                if _perf_report.empty:
                    st.info(f"No published {perf_metric.lower()} report data available.")
                else:
                    import re as _re_mod
                    _perf_report['date'] = pd.to_datetime(_perf_report['DATE']).dt.normalize()
                    _perf_filtered = _perf_report[
                        (_perf_report['date'] >= an_date_from) & (_perf_report['date'] <= an_date_to)
                    ]

                    if _perf_filtered.empty:
                        st.info("No data found for the selected date range.")
                    else:
                        # Aggregate by chosen timeframe
                        def _parse_deviation(status_str):
                            m = _re_mod.search(r'([+-]?\d+\.?\d*)%', str(status_str))
                            return float(m.group(1)) if m else None

                        _perf_filtered['Deviation %'] = _perf_filtered['STATUS'].apply(_parse_deviation)
                        _perf_valid = _perf_filtered[_perf_filtered['Deviation %'].notna()].copy()

                        # Aggregate Deviation % per LOC across the selected date range.
                        # Use mean across the chosen from/to window so users see effects of their selection.
                        _perf_valid['date'] = pd.to_datetime(_perf_valid['date']).dt.normalize()
                        _perf_agg = _perf_valid.groupby('LOC ID', as_index=False)['Deviation %'].mean()

                        _perf_rows_df = _perf_agg[
                            _perf_agg['Deviation %'].notna() & (_perf_agg['Deviation %'] != 0.0)
                        ].copy()
                        _perf_rows_df['Deviation %'] = _perf_rows_df['Deviation %'].round(1)

                        if _perf_rows_df.empty:
                            st.info("No ranking data available for this metric and date.")
                        else:
                            # Best = highest positive deviations; Worst = most negative deviations
                            perf_df_desc = _perf_rows_df.sort_values('Deviation %', ascending=False).reset_index(drop=True)
                            top5_best = perf_df_desc.head(5)
                            perf_df_asc = _perf_rows_df.sort_values('Deviation %', ascending=True).reset_index(drop=True)
                            top5_worst = perf_df_asc.head(5)

                            def _bar_color(v):
                                # Positive deviations = sufficient (good) => green; negative => red
                                try:
                                    v = float(v)
                                except Exception:
                                    return '#888888'
                                return '#008A00' if v >= 0 else '#DE002E'

                            rank_col1, rank_col2 = st.columns(2)
                            with rank_col1:
                                st.markdown(
                                    '<div style="font-weight:700;color:#008A00;font-size:13px;margin-bottom:6px;">'
                                    '\U0001f3c5 TOP 5 BEST PERFORMING FACILITIES</div>',
                                    unsafe_allow_html=True
                                )
                                fig_best = go.Figure(go.Bar(
                                    y=top5_best['LOC ID'], x=top5_best['Deviation %'],
                                    orientation='h',
                                    marker_color=[_bar_color(v) for v in top5_best['Deviation %']],
                                    text=[f"{v:+.1f}%" for v in top5_best['Deviation %']],
                                    textposition='outside',
                                    textfont=dict(size=12, color='#222222')
                                ))
                                fig_best.update_layout(
                                    template='plotly_white', height=300,
                                    margin=dict(l=10, r=70, t=10, b=30),
                                    xaxis_title='Deviation %', yaxis_title='',
                                    xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='#ccc',
                                               tickfont=dict(size=13, color='#222222', family='DM Sans, Inter, sans-serif')),
                                    yaxis=dict(tickfont=dict(size=13, color='#222222', family='DM Sans, Inter, sans-serif')),
                                    font=dict(family='DM Sans, Inter, sans-serif', size=12)
                                )
                                st.plotly_chart(fig_best, width="stretch")

                            with rank_col2:
                                st.markdown(
                                    '<div style="font-weight:700;color:#DE002E;font-size:13px;margin-bottom:6px;">'
                                    '\u26a0\ufe0f TOP 5 LOWEST PERFORMING FACILITIES</div>',
                                    unsafe_allow_html=True
                                )
                                fig_worst = go.Figure(go.Bar(
                                    y=top5_worst['LOC ID'], x=top5_worst['Deviation %'],
                                    orientation='h',
                                    marker_color=[_bar_color(v) for v in top5_worst['Deviation %']],
                                    text=[f"{v:+.1f}%" for v in top5_worst['Deviation %']],
                                    textposition='outside',
                                    textfont=dict(size=12, color='#222222')
                                ))
                                fig_worst.update_layout(
                                    template='plotly_white', height=300,
                                    margin=dict(l=10, r=70, t=10, b=30),
                                    xaxis_title='Deviation %', yaxis_title='',
                                    xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='#ccc',
                                               tickfont=dict(size=13, color='#222222', family='DM Sans, Inter, sans-serif')),
                                    yaxis=dict(tickfont=dict(size=13, color='#222222', family='DM Sans, Inter, sans-serif')),
                                    font=dict(family='DM Sans, Inter, sans-serif', size=12)
                                )
                                st.plotly_chart(fig_worst, width="stretch")

                # ==========================================================
                # CHART 3 — Courier Productivity Trends (ST/H, PK/ST, PK/FTE)
                # ==========================================================
                st.markdown("---")
                st.markdown("""
                <div style="font-weight:900;color:#4D148C;font-size:20px;margin-bottom:6px;letter-spacing:-0.3px;font-family:'DM Sans',sans-serif;text-transform:uppercase;">📦 3. COURIER PRODUCTIVITY TRENDS</div>
                """, unsafe_allow_html=True)

                _prod_famis = read_famis_uploads()
                _prod_metrics_available = []
                if not _prod_famis.empty:
                    _prod_famis['date'] = pd.to_datetime(_prod_famis['date']).dt.normalize()
                    _prod_famis = _prod_famis[(_prod_famis['date'] >= an_date_from) & (_prod_famis['date'] <= an_date_to)]

                    # Robust column detection: map common FAMIS column names to internal keys
                    import re as _local_re

                    _patterns = {
                        'st_hr_or': ['sthr', 'sthror', 'sthor', 'sthoror', 'sthor'],
                        'pk_st_or': ['pkst', 'pkstor', 'pkstor'],
                        'pk_fte_or': ['pkfte', 'pkfteor', 'pkfte'],
                        'st_cr_or': ['stcr', 'stcror'],
                        'pk_cr_or': ['pkcr', 'pkcrr', 'pkcror']
                    }

                    # Normalize column name for matching
                    def _norm_col(c):
                        return _local_re.sub(r'[^a-z0-9]', '', str(c).lower())

                    _col_map = {}
                    for _col in _prod_famis.columns:
                        _n = _norm_col(_col)
                        for _k, _pats in _patterns.items():
                            if _k in _col_map:
                                continue
                            if any(_pat in _n for _pat in _pats):
                                _col_map[_k] = _col
                                break

                    # Convert mapped columns to numeric and expose as internal keys
                    for _ikey, _orig in _col_map.items():
                        try:
                            _prod_famis[_ikey] = pd.to_numeric(_prod_famis[_orig], errors='coerce')
                            if _prod_famis[_ikey].notna().any():
                                _prod_metrics_available.append(_ikey)
                        except Exception:
                            # Skip if conversion fails
                            pass

                    # Note: PK/HR derivation has been disabled — analytics will not show PK/HR

                if _prod_famis.empty or not _prod_metrics_available:
                    st.info("📭 No courier productivity data available in FAMIS uploads for the selected range.")
                else:
                    _metric_labels = {
                        'st_hr_or': 'ST/H (Stops per Hour)',
                        'pk_st_or': 'PK/ST (Packages per Stop)',
                        'pk_fte_or': 'PK/FTE (Packages per FTE)',
                        'st_cr_or': 'ST/CR (Stops per Crew)',
                        'pk_cr_or': 'PK/CR (Packages per Crew)'
                    }

                    _prod_fac_list = sorted(_prod_famis['loc_id'].dropna().unique().tolist())
                    _pc1, _pc2 = st.columns([1, 2])
                    with _pc1:
                        _prod_view = st.radio(
                            "View", ["ALL FACILITIES (AVG)", "BY FACILITY"],
                            horizontal=True, key='prod_view_toggle'
                        )
                    with _pc2:
                        _prod_selected_metrics = st.multiselect(
                            "Metrics", _prod_metrics_available,
                            default=_prod_metrics_available[:3],
                            format_func=lambda x: _metric_labels.get(x, x),
                            key='prod_metric_select'
                        )

                    _prod_selected_fac = None
                    if _prod_view == "BY FACILITY":
                        _prod_selected_fac = st.selectbox(
                            "Facility", _prod_fac_list, key='prod_fac_select'
                        )

                    if not _prod_selected_metrics:
                        st.warning("Select at least one metric to plot.")
                    else:
                        if _prod_view == "BY FACILITY" and _prod_selected_fac:
                            _prod_src = _prod_famis[_prod_famis['loc_id'] == _prod_selected_fac]
                        else:
                            _prod_src = _prod_famis

                        # Aggregate by date first, then resample
                        _prod_daily = _prod_src.groupby('date', as_index=False)[_prod_selected_metrics].mean()
                        _prod_trend = _resample_by_timeframe(_prod_daily, 'date', _prod_selected_metrics, agg='mean')

                        _prod_colors = ['#4D148C', '#FF6200', '#008A00', '#007AB7']
                        _prod_dashes = ['solid', 'dot', 'dash', 'dashdot']

                        fig_prod = go.Figure()
                        for _i, _mc in enumerate(_prod_selected_metrics):
                            fig_prod.add_trace(go.Scatter(
                                x=_prod_trend['period_label'],
                                y=_prod_trend[_mc].round(2),
                                mode='lines+markers',
                                name=_metric_labels.get(_mc, _mc),
                                line=dict(
                                    color=_prod_colors[_i % len(_prod_colors)],
                                    width=2,
                                    dash=_prod_dashes[_i % len(_prod_dashes)]
                                ),
                                marker=dict(size=6, color=_prod_colors[_i % len(_prod_colors)])
                            ))
                        _chart_title = (
                            f"Productivity — {_prod_selected_fac}" if _prod_selected_fac
                            else "Productivity — All Facilities (Average)"
                        )
                        fig_prod.update_layout(
                            template='plotly_white', height=400,
                            margin=dict(l=40, r=20, t=40, b=40),
                            title=dict(text=_chart_title, font=dict(size=14, family='DM Sans', color='#333')),
                            legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='center', x=0.5),
                            xaxis_title=an_timeframe.title() + ' Period',
                            yaxis_title='Metric Value',
                            font=dict(family='DM Sans, Inter, sans-serif', size=12)
                        )
                        st.plotly_chart(fig_prod, width="stretch")

                        # --- Apply an "assumed" Y-axis zoom for selected productivity metrics
                        try:
                            _prod_vals = _prod_trend[_prod_selected_metrics].dropna()
                            if not _prod_vals.empty:
                                _pmin = float(_prod_vals.min().min())
                                _pmax = float(_prod_vals.max().max())
                                _pspan = _pmax - _pmin
                                # If metrics have very different magnitude, skip zoom (avoid compressing small series)
                                if _pmin > 0 and (_pmax / max(_pmin, 1e-9)) > 12:
                                    pass
                                else:
                                    if _pspan <= 0:
                                        _py0 = max(0, _pmin * 0.9)
                                        _py1 = _pmax * 1.1 if _pmax > 0 else 1
                                    else:
                                        _ppad = max(_pspan * 0.20, _pmax * 0.03)
                                        _py0 = max(0, _pmin - _ppad)
                                        _py1 = _pmax + _ppad
                                    if _py1 - _py0 < (_pmax * 0.98):
                                        fig_prod.update_yaxes(range=[_py0, _py1])
                        except Exception:
                            pass

        else:
            st.info("\U0001f4e4 No published reports found. Use 'PUBLISH TO EXCEL' to save health reports before viewing analytics.")

    # ============================================================
    # PUBLISH REPORTS TO EXCEL
    # ============================================================
    _save_col1, _save_col2 = st.columns(2)

    with _save_col1:
        if st.button("📤  PUBLISH TO EXCEL", type="secondary", use_container_width=True):
            try:
                famis_df_save = st.session_state.get('famis_data')
                master_df_save = st.session_state.get('master_data')
                sel_date_save = st.session_state.get('selected_date')

                if famis_df_save is None or sel_date_save is None:
                    st.warning("⚠️ Upload FAMIS data and select a date first.")
                else:
                    date_famis_save = famis_df_save[famis_df_save['date'] == sel_date_save].copy()

                    # --- Area rows ---
                    area_report_rows = []
                    for _, r in date_famis_save.iterrows():
                        loc_id = r['loc_id']
                        vol = int(r.get('pk_gross_tot', 0))
                        area_st = next((s for s in st.session_state.get('area_health_results', []) if s.get('loc_id') == loc_id), None)
                        if area_st:
                            area_report_rows.append({
                                'DATE': sel_date_save.strftime('%Y-%m-%d'),
                                'LOC ID': loc_id,
                                'VOLUME': f"{vol:,}",
                                'CALCULATED OPERATIONAL AREA': _fmt_area(area_st.get('total_calculated', 0)),
                                'CURRENT OPERATIONAL AREA': _fmt_area(area_st.get('master_area', 0)),
                                'STATUS': f"{area_st.get('emoji', '⚪')} {area_st.get('deviation_percent', 0):+.1f}%"
                            })

                    # --- Resource rows ---
                    resource_report_rows = []
                    for _, r in date_famis_save.iterrows():
                        loc_id = r['loc_id']
                        vol = int(r.get('pk_gross_tot', 0))
                        res_st = next((s for s in st.session_state.get('resource_health_results', []) if s.get('loc_id') == loc_id), None)
                        if res_st:
                            resource_report_rows.append({
                                'DATE': sel_date_save.strftime('%Y-%m-%d'),
                                'LOC ID': loc_id,
                                'VOLUME': f"{vol:,}",
                                'TOTAL AGENTS CALCULATED': f"{res_st.get('calculated_agents', 0):.2f}",
                                'CURRENT BASE AGENTS': f"{res_st.get('master_agents', 0):.1f}",
                                'STATUS': f"{res_st.get('emoji', '⚪')} {res_st.get('deviation_percent', 0):+.1f}%"
                            })

                    # --- Courier rows ---
                    courier_report_rows = []
                    for _, r in date_famis_save.iterrows():
                        loc_id = r['loc_id']
                        vol = int(r.get('pk_gross_tot', 0))
                        cour_st = next((s for s in st.session_state.get('courier_health_results', []) if s.get('loc_id') == loc_id), None)
                        if cour_st:
                            courier_report_rows.append({
                                'DATE': sel_date_save.strftime('%Y-%m-%d'),
                                'LOC ID': loc_id,
                                'VOLUME': f"{vol:,}",
                                'TOTAL COURIERS REQUIRED': f"{cour_st.get('couriers_required', 0):.1f}",
                                'TOTAL COURIERS IN MASTER': f"{cour_st.get('couriers_available', 0):.0f}",
                                'STATUS': f"{cour_st.get('emoji', '⚪')} {cour_st.get('deviation_percent', 0):+.1f}%"
                            })

                    save_health_reports(area_report_rows, resource_report_rows, courier_report_rows,
                                        report_date=sel_date_save.strftime('%Y-%m-%d'))
                    st.success("✅ Reports saved to FAMIS_REPORT_DATA.xlsx")
            except PermissionError:
                st.error("❌ **Permission denied** — please close FAMIS_REPORT_DATA.xlsx in Excel and try again.")
            except Exception as e:
                st.error(f"❌ Error saving reports: {e}")

    with _save_col2:
        if st.button("📤  PUBLISH TO DATABASE", type="primary", use_container_width=True):
            try:
                from aero.data.postgres import (
                    ensure_tables,
                    insert_upload_record,
                    upsert_health_data,
                    _POSTGRES_AVAILABLE,
                )
                if not _POSTGRES_AVAILABLE:
                    st.warning(
                        "⚙️ **PostgreSQL not configured.** "
                        "Set POSTGRES_PASSWORD in your .env file and create the "
                        "`aero_planner` database, then restart the app.",
                        icon="🗄️",
                    )
                    st.stop()

                famis_df = st.session_state['famis_data']

                records = []
                all_dates = famis_df['date'].unique()

                progress = st.progress(0, text="Processing...")

                # ============================================================
                # BACKEND CALCULATION  (real service functions)
                # ============================================================
                master_df_pub = st.session_state.get('master_data')

                # --- Area parameters (mirror UI defaults) ---
                _area_ppp  = float(st.session_state.get('area_packs_per_pallet', 15))
                _area_mv   = float(st.session_state.get('area_max_volume', 55.0))
                _area_sp   = float(st.session_state.get('area_sorting_percent', 60.0))
                _area_cp   = float(st.session_state.get('area_cage_percent', 10.0))
                _area_ap   = float(st.session_state.get('area_aisle_percent', 15.0))

                # --- Resource parameters ---
                _res_shift   = float(st.session_state.get('resource_shift_hours', 9.0))
                _res_absent  = float(st.session_state.get('resource_absenteeism_pct', 15.0)) / 100.0
                _res_train   = 0.0
                _res_roster  = float(st.session_state.get('resource_roster_buffer_pct', 11.0)) / 100.0
                _res_oncall  = int(st.session_state.get('resource_on_call_pickup', 80))
                _res_dex     = 0.05
                _res_csbiv   = 0.80
                _res_rod     = 0.30

                # --- Courier parameters ---
                _cour_pk_st   = float(st.session_state.get('courier_pk_st_or', 1.5))
                _cour_st_hr   = float(st.session_state.get('courier_st_hr_or', 8.0))
                _cour_prod    = float(st.session_state.get('courier_productivity_hrs', 7.0))
                _cour_absent  = float(st.session_state.get('courier_absenteeism_pct', 16.0))
                _cour_train   = float(st.session_state.get('courier_training_pct', 11.0))
                _cour_wdays   = int(st.session_state.get('courier_working_days', 5))

                # ============================================================
                # BUILD RECORDS  (one pass per date × station)
                # ============================================================
                for i, dt in enumerate(all_dates):
                    df = famis_df[famis_df['date'] == dt]

                    for _, row in df.iterrows():
                        loc = row.get("loc_id")
                        total_packages = int(row.get("pk_gross_tot", 0) or 0)
                        ib_vol  = int(row.get('pk_gross_inb', 0) or 0)
                        ob_vol  = int(row.get('pk_gross_outb', 0) or 0)
                        roc_raw = int(row.get('pk_roc', 0) or 0)
                        roc_vol = int(roc_raw * 0.25)
                        asp_vol = roc_raw - roc_vol

                        # --- Master data lookups ---
                        m_row = (master_df_pub[master_df_pub['loc_id'] == loc]
                                 if master_df_pub is not None else pd.DataFrame())
                        master_ops   = 0.0
                        master_agents = 0.0
                        couriers_avail = 0
                        if not m_row.empty:
                            if 'ops_area' in m_row.columns:
                                master_ops = float(m_row['ops_area'].iloc[0] or 0)
                            if 'current_total_agents' in m_row.columns:
                                master_agents = float(m_row['current_total_agents'].iloc[0] or 0)
                            elif 'current_total_osa' in m_row.columns:
                                master_agents = float(m_row['current_total_osa'].iloc[0] or 0)
                            for _col in ('current_total_couriers',
                                         'couriers_available', 'existing_couriers'):
                                if _col in m_row.columns:
                                    try:
                                        couriers_avail = int(m_row[_col].iloc[0])
                                        break
                                    except (ValueError, TypeError):
                                        pass

                        # -------- AREA --------
                        add_area = float(st.session_state.get(
                            f'area_additional_{loc}', 0))
                        hc_on = bool(st.session_state.get(
                            f'add_healthcare_{loc}', False))
                        hc_val = (float(st.session_state.get(
                            f'area_healthcare_{loc}', 0) or 0)
                            if hc_on else 0.0)
                        dg_on = bool(st.session_state.get(
                            f'add_dg_{loc}', False))
                        dg_val = (float(st.session_state.get(
                            f'area_dg_{loc}', 0) or 0)
                            if dg_on else 0.0)

                        if total_packages == 0:
                            calc_area = 0.0
                            area_lbl  = "UNKNOWN"
                        else:
                            _ac = calculate_area_requirements(
                                total_packs=total_packages,
                                packs_per_pallet=_area_ppp,
                                max_volume_percent=_area_mv,
                                sorting_area_percent=_area_sp,
                                cage_percent=_area_cp,
                                aisle_percent=_area_ap,
                                additional_area_value=add_area,
                            )
                            calc_area = ((_ac['total_operational_area']
                                          - add_area) + hc_val + dg_val)
                            _as = calculate_area_status(
                                calculated_total_area=calc_area,
                                master_facility_area=master_ops)
                            area_lbl = _as.get('status', 'UNKNOWN')

                        # -------- RESOURCE --------
                        if total_packages == 0:
                            calc_agents = 0.0
                            res_lbl     = "UNKNOWN"
                        else:
                            _rr = calculate_resource_requirements(
                                total_volume=total_packages,
                                ib_volume=ib_vol,
                                ob_volume=ob_vol,
                                roc_volume=roc_vol,
                                asp_volume=asp_vol,
                                shift_hours=_res_shift,
                                absenteeism_pct=_res_absent,
                                training_pct=_res_train,
                                roster_buffer_pct=_res_roster,
                                on_call_pickup=_res_oncall,
                                dex_pct=_res_dex,
                                csbiv_pct=_res_csbiv,
                                rod_pct=_res_rod,
                            )
                            calc_agents = _rr['total_agents']
                            _rs = calculate_resource_health_status(
                                calc_agents,
                                master_agents)
                            res_lbl = _rs.get('status', 'UNKNOWN')

                        # -------- COURIER --------
                        # Use configured courier metrics (do not read PK/ST or ST/H from uploaded FAMIS)
                        pk_st_val = _cour_pk_st
                        st_hr_val = _cour_st_hr

                        if total_packages == 0:
                            calc_couriers = 0.0
                            cour_lbl      = "UNKNOWN"
                        else:
                            _cr = calculate_courier_requirements(
                                total_packages,
                                pk_st_val,
                                st_hr_val,
                                _cour_prod,
                                couriers_avail,
                                _cour_absent,
                                _cour_train,
                                _cour_wdays,
                            )
                            calc_couriers = _cr['total_required_with_training']
                            _cs = calculate_courier_health_status(
                                calc_couriers,
                                couriers_avail)
                            cour_lbl = _cs.get('status', 'UNKNOWN')

                        records.append({
                            "loc_id": loc,
                            "report_date": dt,
                            "pk_gross_tot": row.get("pk_gross_tot"),
                            "calculated_area": calc_area,
                            "area_status": area_lbl,
                            "calculated_agents": calc_agents,
                            "resource_status": res_lbl,
                            "calculated_couriers": calc_couriers,
                            "courier_status": cour_lbl,
                        })

                    progress.progress((i + 1) / len(all_dates))

                progress.empty()

                # ======================
                # DATABASE FLOW
                # ======================

                ensure_tables()

                file_name = st.session_state.get("famis_file_name", "unknown.csv")

                upload_id = insert_upload_record(
                    file_name=file_name,
                    total_records=len(records),
                    stations_count=famis_df["loc_id"].nunique(),
                    date_from=famis_df["date"].min(),
                    date_to=famis_df["date"].max()
                )

                row_count = upsert_health_data(records, upload_id)

                st.success(f"✅ Published {row_count} rows (Upload ID: {upload_id})")

            except Exception as e:
                st.error(f"❌ Error: {e}")
