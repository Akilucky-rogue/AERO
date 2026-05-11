# ============================================================
# AERO — Hub Health Monitor
# Mirrors station health_monitor.py with hub-namespaced session
# state keys (prefix "hub_") and hub-specific Excel store.
# ============================================================
import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aero.core.area_calculator import (
    calculate_area_requirements,
    calculate_area_status,
    get_status_summary_stats,
)
from aero.core.courier_calculator import (
    calculate_courier_health_status,
    calculate_courier_requirements,
    get_courier_summary_stats,
)
from aero.core.resource_calculator import (
    calculate_resource_health_status,
    calculate_resource_requirements,
    get_resource_summary_stats,
)
from aero.data.hub_store import (
    read_hub_report_sheet,
    read_hub_uploads,
    save_hub_reports,
    upsert_hub_upload,
)
from aero.ui.components import render_section_header, render_status_cards

from aero.config.settings import load_config

_config = load_config()
_osa = _config.get("OSA", {})
_lasa = _config.get("LASA", {})
_dispatcher = _config.get("DISPATCHER", {})
_trace_agent = _config.get("TRACE_AGENT", {})

HUB_ALLOWED_HEADERS = {
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
    'pk_cr_or': 'PK/CR OR',
}

HUB_MASTER_HEADERS = {
    'date': 'DATE',
    'loc_id': 'LOC ID',
    'total_facility_area': 'TOTAL FACILITY AREA',
    'ops_area': 'OPS AREA',
    'current_total_osa': 'CURRENT TOTAL OSA',
    'current_total_couriers': 'CURRENT TOTAL COURIERS',
}


def _to_float(value, default=0.0):
    try:
        if hasattr(value, "__float__") and value is not None:
            return float(value)
    except Exception:
        pass
    try:
        s = str(value).strip()
        if s == "" or s.lower() in ("nan", "none", "na", "n/a"):
            return default
        return float(s.replace(',', ''))
    except Exception:
        return default


def _fmt_area(value):
    val = _to_float(value, 0.0)
    try:
        return f"{val:,.0f}"
    except Exception:
        return "0"


# ── session-state key helpers ─────────────────────────────────────────────────
_P = "hub_"   # session-state namespace prefix


def _ss(key, default=None):
    return st.session_state.get(f"{_P}{key}", default)


def _ss_set(key, value):
    st.session_state[f"{_P}{key}"] = value


# ─────────────────────────────────────────────────────────────────────────────
# RENDER ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render():
    """Render the Hub Health Monitor content (called from hub_planner.py tab)."""

    upload_col1, upload_col2 = st.columns(2)

    # ── FAMIS / Volume upload ────────────────────────────────────────────────
    with upload_col1:
        famis_file = st.file_uploader(
            "Upload Hub Volume Excel File",
            type=["xlsx"],
            key="hub_famis_upload",
            help="Upload the Hub Volume data file (FAMIS format)"
        )

        if famis_file:
            try:
                famis_df = pd.read_excel(famis_file)
                famis_df.columns = (
                    famis_df.columns
                    .str.strip().str.lower()
                    .str.replace(" ", "_").str.replace("/", "_")
                )
                valid_cols = list(HUB_ALLOWED_HEADERS.keys())
                REQUIRED_COLS = ['date', 'loc_id', 'pk_gross_tot']
                has_required = all(col in famis_df.columns for col in REQUIRED_COLS)

                if has_required:
                    famis_df['date'] = pd.to_datetime(famis_df['date']).dt.normalize()
                    famis_df = famis_df[[col for col in famis_df.columns if col in valid_cols]]
                    _ss_set('famis_data_raw', famis_df.copy())
                    _ss_set('famis_data', famis_df)
                    try:
                        upsert_hub_upload(famis_df)
                        _ss_set('famis_file_name', famis_file.name)
                    except Exception:
                        pass
                else:
                    missing = set(REQUIRED_COLS) - set(famis_df.columns)
                    st.error(f"Missing required columns: {', '.join(missing)}")
            except Exception as e:
                st.error(f"Error loading Hub Volume file: {str(e)}")

    # ── Master upload ────────────────────────────────────────────────────────
    with upload_col2:
        master_file = st.file_uploader(
            "Upload Hub Master Excel File",
            type=["xlsx"],
            key="hub_master_upload",
            help="Upload hub master file with facility and staffing data"
        )

        if master_file:
            try:
                master_df = pd.read_excel(master_file)
                master_df.columns = (
                    master_df.columns
                    .str.strip().str.lower()
                    .str.replace(" ", "_").str.replace("/", "_")
                )
                valid_cols = list(HUB_MASTER_HEADERS.keys())

                def _clean(name):
                    return re.sub(r'[^a-z0-9_]', '', name.lower())

                existing = list(master_df.columns)
                col_map = {}
                for expected in valid_cols:
                    if expected in existing:
                        col_map[expected] = expected
                        continue
                    exp_tokens = [t for t in expected.split('_') if t]
                    found = None
                    for col in existing:
                        cc = _clean(col)
                        if _clean(expected) in cc:
                            found = col
                            break
                        if sum(1 for t in exp_tokens if t in cc) >= max(1, len(exp_tokens) - 1):
                            found = col
                            break
                    if found:
                        col_map[expected] = found

                if col_map:
                    master_df = master_df.rename(columns={v: k for k, v in col_map.items()})

                if 'loc_id' in master_df.columns:
                    master_df = master_df[[col for col in master_df.columns if col in valid_cols]]
                    _ss_set('master_data', master_df)
                else:
                    st.error("Missing required column: loc_id")
            except Exception as e:
                st.error(f"Error loading Hub Master file: {str(e)}")

    # ── File-type selector / normalization ──────────────────────────────────
    if _ss('famis_data_raw') is not None:
        _opts = ["Daily", "Weekly", "Monthly"]
        _saved = _ss('famis_file_type_saved', 'Daily')
        _idx = _opts.index(_saved) if _saved in _opts else 0
        file_type = st.selectbox(
            "📊 Hub FAMIS File Type",
            _opts, index=_idx, key='hub_famis_file_type',
            help="Weekly volumes divided by 6, Monthly by 26"
        )
        _ss_set('famis_file_type_saved', file_type)

        _div = {'Daily': 1, 'Weekly': 6, 'Monthly': 26}[file_type]
        _raw = _ss('famis_data_raw').copy()
        _vcols = ['pk_gross_tot', 'pk_gross_inb', 'pk_gross_outb', 'pk_oda', 'pk_opa', 'pk_roc']
        if _div > 1:
            for _vc in _vcols:
                if _vc in _raw.columns:
                    _raw[_vc] = pd.to_numeric(_raw[_vc], errors='coerce').fillna(0) / _div

        _prev = _ss('_famis_file_type_prev')
        if _prev is not None and _prev != file_type:
            for _k in ['area_volume_from_famis', 'area_daily_volume']:
                st.session_state.pop(f"{_P}{_k}", None)
        _ss_set('_famis_file_type_prev', file_type)
        _ss_set('famis_data', _raw)

    st.markdown("---")

    # ── Date selector ────────────────────────────────────────────────────────
    famis_df_ss = _ss('famis_data')
    if famis_df_ss is not None:
        if 'date' in famis_df_ss.columns:
            available_dates = sorted(famis_df_ss['date'].unique(), reverse=True)
            if _ss('selected_date') not in available_dates:
                _ss_set('selected_date', available_dates[0])
            selected_date = st.selectbox(
                "Active Date",
                available_dates,
                format_func=lambda x: x.strftime('%Y-%m-%d'),
                index=available_dates.index(_ss('selected_date')),
                key='hub_date_selector_card'
            )
            _ss_set('selected_date', selected_date)
        else:
            st.error("Date column not found in hub volume data")
    else:
        st.markdown("""
        <div style="background:var(--info-bg);border-left:6px solid var(--fc-purple);border-radius:8px;
            padding:12px 16px;margin-bottom:16px;color:var(--info-text);">
            <div style="font-weight:700;">📤 Upload a Hub Volume file to enable date selection</div>
        </div>
        """, unsafe_allow_html=True)
        _ss_set('selected_date', None)

    # ── Monitor tabs ──────────────────────────────────────────────────────────
    _all_tabs = st.tabs(["AREA MONITOR", "HUB AGENT MONITOR", "COURIER MONITOR", "ANALYTICS"])
    tab1, tab2, tab3, tab4 = _all_tabs
    st.markdown("---")

    # ── Quick helper to access hub session state ─────────────────────────────
    famis_df_cur = _ss('famis_data')
    master_df_cur = _ss('master_data')
    sel_date = _ss('selected_date')

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1: AREA MONITOR
    # ════════════════════════════════════════════════════════════════════════
    with tab1:
        _ss_set('active_tab', 'AREA')
        if famis_df_cur is not None and sel_date is not None:
            date_famis = famis_df_cur[famis_df_cur['date'] == sel_date].copy()

            if not date_famis.empty and master_df_cur is not None and not master_df_cur.empty:
                area_packs_per_pallet = _ss('area_packs_per_pallet', 15)
                area_max_volume = _ss('area_max_volume', 55.0)
                area_sorting_percent = _ss('area_sorting_percent', 60.0)
                area_aisle_percent = _ss('area_aisle_percent', 15.0)
                area_cage_percent = _ss('area_cage_percent', 10.0)

                st.markdown("---")
                station_statuses = []

                for _, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    total_packs = int(row.get('pk_gross_tot', 0))
                    additional_area = float(_ss(f'area_additional_{loc_id}', 0))
                    hc_sel = bool(_ss(f'add_healthcare_{loc_id}', False))
                    hc_val = float(_ss(f'area_healthcare_{loc_id}', 0) or 0) if hc_sel else 0.0
                    dg_sel = bool(_ss(f'add_dg_{loc_id}', False))
                    dg_val = float(_ss(f'area_dg_{loc_id}', 0) or 0) if dg_sel else 0.0

                    master_row = master_df_cur[master_df_cur['loc_id'] == loc_id]
                    master_ops = master_row['ops_area'].iloc[0] if (not master_row.empty and 'ops_area' in master_row.columns) else 0
                    master_ops_f = _to_float(master_ops, 0.0)

                    if total_packs == 0:
                        status = {'status': 'UNKNOWN', 'deviation_percent': 0, 'color': '#8E8E8E', 'emoji': '⚪', 'label': 'No Data'}
                        status['loc_id'] = loc_id
                        status['total_calculated'] = 0
                        status['master_area'] = master_ops_f
                        station_statuses.append(status)
                        continue

                    calcs = calculate_area_requirements(
                        total_packs=total_packs, packs_per_pallet=area_packs_per_pallet,
                        max_volume_percent=area_max_volume, sorting_area_percent=area_sorting_percent,
                        cage_percent=area_cage_percent, aisle_percent=area_aisle_percent,
                        additional_area_value=additional_area
                    )
                    operational_area = (calcs['total_operational_area'] - additional_area) + hc_val + dg_val
                    status = calculate_area_status(operational_area, master_ops_f)
                    status['loc_id'] = loc_id
                    status['total_calculated'] = operational_area
                    status['master_area'] = master_ops_f
                    station_statuses.append(status)

                summary_stats = get_status_summary_stats(station_statuses)
                _ss_set('area_health_results', station_statuses)
                _ss_set('area_tab_computed', True)

                st.markdown("""
                <div style="background:linear-gradient(90deg,#FFFFFF 0%,#F3E8FF 100%);
                    border-left:6px solid #4D148C;border-radius:8px;padding:12px 16px;margin-bottom:16px;">
                    <div style="font-weight:700;color:#333333;font-size:16px;">📐 HUB AREA ANALYSIS</div>
                </div>""", unsafe_allow_html=True)

                card_h = "height:120px;min-height:85px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:8px;"
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"""<div style="background:var(--status-healthy-bg);border:1px solid var(--status-healthy-border);border-radius:8px;text-align:center;{card_h}">
                        <div style="font-size:20px;">✅</div>
                        <div style="color:var(--status-healthy-text);font-weight:700;font-size:20px;">{summary_stats['healthy_count']}</div>
                        <div style="color:var(--status-healthy-subtext);font-size:11px;font-weight:600;text-transform:uppercase;margin-top:4px;">Healthy</div>
                        <div style="color:var(--status-healthy-subtext-2);font-size:11px;margin-top:6px;font-weight:600;">Range: 0-10%</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""<div style="background:var(--status-review-bg);border:1px solid var(--status-review-border);border-radius:8px;text-align:center;{card_h}">
                        <div style="font-size:20px;">⚠️</div>
                        <div style="color:var(--status-review-text);font-weight:700;font-size:20px;">{summary_stats['review_needed_count']}</div>
                        <div style="color:var(--status-review-subtext);font-size:11px;font-weight:600;text-transform:uppercase;margin-top:4px;">Review</div>
                        <div style="color:var(--status-review-subtext-2);font-size:11px;margin-top:6px;font-weight:600;">Range: 10-20%</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""<div style="background:var(--status-critical-bg);border:1px solid var(--status-critical-border);border-radius:8px;text-align:center;{card_h}">
                        <div style="font-size:20px;">🚨</div>
                        <div style="color:var(--status-critical-text);font-weight:700;font-size:20px;">{summary_stats['critical_count']}</div>
                        <div style="color:var(--status-critical-subtext);font-size:11px;font-weight:600;text-transform:uppercase;margin-top:4px;">Critical</div>
                        <div style="color:var(--status-critical-subtext-2);font-size:11px;margin-top:6px;font-weight:600;">Range: &gt;20%</div>
                    </div>""", unsafe_allow_html=True)
                with c4:
                    ma = summary_stats.get('most_affected')
                    if ma is None:
                        st.markdown(f"""<div style="background:var(--status-neutral-bg);border:1px solid var(--status-neutral-border);border-radius:8px;text-align:center;{card_h}">
                            <div style="font-size:28px;">✅</div>
                            <div style="color:var(--status-neutral-text);font-weight:700;font-size:16px;">All Hubs Sufficient</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div style="background:var(--status-most-affected-bg);border:1px solid var(--status-most-affected-border);border-radius:8px;text-align:center;{card_h}">
                            <div style="font-size:26px;">{ma.get('emoji','❓')}</div>
                            <div style="color:var(--status-neutral-text);font-weight:700;font-size:16px;">{ma.get('loc_id','N/A')}</div>
                            <div style="color:var(--status-critical-subtext);font-size:12px;font-weight:700;margin-top:6px;">Max Neg Dev: {ma.get('deviation_percent',0):+.1f}%</div>
                        </div>""", unsafe_allow_html=True)

                # Summary table
                summary_data = []
                for _, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    total_packs = int(row.get('pk_gross_tot', 0))
                    additional_area = float(_ss(f'area_additional_{loc_id}', 0))
                    hc_sel = bool(_ss(f'add_healthcare_{loc_id}', False))
                    hc_val = float(_ss(f'area_healthcare_{loc_id}', 0) or 0) if hc_sel else 0.0
                    dg_sel = bool(_ss(f'add_dg_{loc_id}', False))
                    dg_val = float(_ss(f'area_dg_{loc_id}', 0) or 0) if dg_sel else 0.0

                    master_row = master_df_cur[master_df_cur['loc_id'] == loc_id]
                    master_ops = master_row['ops_area'].iloc[0] if (not master_row.empty and 'ops_area' in master_row.columns) else 0
                    master_ops_f = _to_float(master_ops, 0.0)
                    date_str = sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else str(sel_date)

                    calcs = calculate_area_requirements(
                        total_packs=total_packs, packs_per_pallet=area_packs_per_pallet,
                        max_volume_percent=area_max_volume, sorting_area_percent=area_sorting_percent,
                        cage_percent=area_cage_percent, aisle_percent=area_aisle_percent,
                        additional_area_value=additional_area
                    )
                    calc_area = (calcs['total_operational_area'] - additional_area) + hc_val + dg_val

                    if total_packs == 0 or calc_area <= 0 or master_ops_f <= 0:
                        summary_data.append({'DATE': date_str, 'LOC ID': loc_id, 'VOLUME': f"{total_packs:,}",
                            'CALCULATED AREA': '-' if calc_area <= 0 else _fmt_area(calc_area),
                            'CURRENT AREA': '-' if master_ops_f <= 0 else _fmt_area(master_ops_f), 'STATUS': '⚪ NO DATA'})
                    else:
                        st_info = calculate_area_status(calc_area, master_ops_f)
                        summary_data.append({'DATE': date_str, 'LOC ID': loc_id, 'VOLUME': f"{total_packs:,}",
                            'CALCULATED AREA': _fmt_area(calc_area), 'CURRENT AREA': _fmt_area(master_ops_f),
                            'STATUS': f"{st_info['emoji']} {st_info['deviation_percent']:+.1f}%"})

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True,
                    column_config={
                        'DATE': st.column_config.TextColumn('DATE', width=110),
                        'LOC ID': st.column_config.TextColumn('LOC ID', width=90),
                        'VOLUME': st.column_config.TextColumn('VOLUME', width=100),
                        'CALCULATED AREA': st.column_config.TextColumn('CALCULATED AREA (sqft)', width=170),
                        'CURRENT AREA': st.column_config.TextColumn('CURRENT AREA (sqft)', width=160),
                        'STATUS': st.column_config.TextColumn('STATUS', width=120),
                    })

                # ── Publish button ────────────────────────────────────────
                st.markdown("---")
                if st.button("📤 PUBLISH HUB AREA REPORT", key="hub_publish_area", type="primary"):
                    area_rows = [{'DATE': (sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else str(sel_date)),
                        'LOC ID': s['loc_id'], 'VOLUME': str(int(_to_float(
                            date_famis[date_famis['loc_id'] == s['loc_id']]['pk_gross_tot'].iloc[0] if not date_famis[date_famis['loc_id'] == s['loc_id']].empty else 0
                        ))),
                        'CALCULATED AREA': _fmt_area(s.get('total_calculated', 0)),
                        'CURRENT AREA': _fmt_area(s.get('master_area', 0)),
                        'STATUS': f"{s.get('emoji','')}{s.get('deviation_percent',0):+.1f}%"
                    } for s in station_statuses]
                    try:
                        save_hub_reports(area_rows, [], [], report_date=sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else None)
                        st.success("✅ Hub Area report published to HUB_REPORT_DATA.xlsx")
                    except Exception as e:
                        st.error(f"Error publishing report: {e}")

            else:
                if master_df_cur is None or master_df_cur.empty:
                    st.warning("📤 Upload a Hub Master file to see detailed area analysis")
                else:
                    st.info("📅 Select a date with volume data")
        else:
            st.markdown("""<div style="background:var(--info-bg);border-left:6px solid var(--fc-purple);
                border-radius:8px;padding:12px 16px;margin-bottom:16px;color:var(--info-text);">
                <div style="font-weight:700;">📤 Upload Hub Volume file to enable area monitoring</div>
            </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2: HUB AGENT MONITOR
    # ════════════════════════════════════════════════════════════════════════
    with tab2:
        _ss_set('active_tab', 'RESOURCE')
        if famis_df_cur is not None and sel_date is not None:
            date_famis = famis_df_cur[famis_df_cur['date'] == sel_date].copy()

            if not date_famis.empty and master_df_cur is not None and not master_df_cur.empty:
                st.markdown("---")
                SHIFT_HOURS = float(_ss('resource_shift_hours', 9.0))
                ABSENTEEISM_PCT = float(_ss('resource_absenteeism_pct', 11.0)) / 100.0
                ROSTER_BUFFER_PCT = float(_ss('resource_roster_buffer_pct', 11.0)) / 100.0
                ON_CALL_PICKUP = int(_ss('resource_on_call_pickup', 80))

                station_resource_statuses = []
                for _, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    gross_vol = int(row.get('pk_gross_tot', 0))
                    ib_vol = int(row.get('pk_gross_inb', 0))
                    ob_vol = int(row.get('pk_gross_outb', 0))
                    roc_f = int(row.get('pk_roc', 0))
                    roc_vol = int(roc_f * 0.25)
                    asp_vol = roc_f - roc_vol

                    reqs = calculate_resource_requirements(
                        total_volume=gross_vol, ib_volume=ib_vol, ob_volume=ob_vol,
                        roc_volume=roc_vol, asp_volume=asp_vol,
                        shift_hours=SHIFT_HOURS, absenteeism_pct=ABSENTEEISM_PCT,
                        training_pct=0.0, roster_buffer_pct=ROSTER_BUFFER_PCT,
                        on_call_pickup=ON_CALL_PICKUP, dex_pct=0.05, csbiv_pct=0.80, rod_pct=0.30
                    )
                    calc_agents = reqs['total_agents']

                    master_row = master_df_cur[master_df_cur['loc_id'] == loc_id]
                    master_agents = 0.0
                    if not master_row.empty:
                        for _col in ['current_total_agents', 'current_total_osa']:
                            if _col in master_row.columns:
                                try:
                                    master_agents = float(master_row[_col].iloc[0])
                                    break
                                except Exception:
                                    pass

                    status = calculate_resource_health_status(calc_agents, master_agents)
                    status['loc_id'] = loc_id
                    status['calculated_agents'] = calc_agents
                    status['master_agents'] = master_agents
                    status['base_agents'] = reqs.get('base_agents', 0)
                    status['osa_agents'] = reqs['osa_agents']
                    status['lasa_agents'] = reqs['lasa_agents']
                    status['dispatcher_agents'] = reqs['dispatcher_agents']
                    status['trace_agents'] = reqs['trace_agents']
                    station_resource_statuses.append(status)

                resource_summary = get_resource_summary_stats(station_resource_statuses)
                _ss_set('resource_health_results', station_resource_statuses)
                _ss_set('resource_tab_computed', True)

                render_section_header("HUB RESOURCE ANALYSIS")
                render_status_cards(resource_summary)

                res_data = []
                for _, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    gross_vol = int(row.get('pk_gross_tot', 0))
                    s_status = next((s for s in station_resource_statuses if s['loc_id'] == loc_id), None)
                    calc_ag = s_status['calculated_agents'] if s_status else 0
                    mast_ag = s_status['master_agents'] if s_status else 0
                    dev = s_status['deviation_percent'] if s_status else 0
                    emo = s_status['emoji'] if s_status else '❓'
                    date_str = sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else str(sel_date)

                    if gross_vol == 0 or calc_ag <= 0 or mast_ag <= 0:
                        res_data.append({'DATE': date_str, 'LOC ID': loc_id, 'VOLUME': f"{gross_vol:,}",
                            'CALCULATED AGENTS': '-' if calc_ag <= 0 else f"{calc_ag:.1f}",
                            'CURRENT AGENTS': '-' if mast_ag <= 0 else f"{mast_ag:.0f}", 'STATUS': '⚪ NO DATA'})
                    else:
                        res_data.append({'DATE': date_str, 'LOC ID': loc_id, 'VOLUME': f"{gross_vol:,}",
                            'CALCULATED AGENTS': f"{calc_ag:.1f}", 'CURRENT AGENTS': f"{mast_ag:.0f}",
                            'STATUS': f"{emo} {dev:+.1f}%"})

                st.dataframe(pd.DataFrame(res_data), use_container_width=True, hide_index=True,
                    column_config={
                        'DATE': st.column_config.TextColumn('DATE', width=110),
                        'LOC ID': st.column_config.TextColumn('LOC ID', width=90),
                        'VOLUME': st.column_config.TextColumn('VOLUME', width=100),
                        'CALCULATED AGENTS': st.column_config.TextColumn('CALCULATED AGENTS', width=160),
                        'CURRENT AGENTS': st.column_config.TextColumn('CURRENT AGENTS', width=140),
                        'STATUS': st.column_config.TextColumn('STATUS', width=120),
                    })

                st.markdown("---")
                _res_locs = sorted(date_famis['loc_id'].unique())
                sel_loc = st.selectbox("Select Hub for Detailed Resource Calculations", _res_locs,
                    key='hub_resource_detail_loc')

                detail_row = date_famis[date_famis['loc_id'] == sel_loc].iloc[0]
                gv = int(detail_row.get('pk_gross_tot', 0))
                iv = int(detail_row.get('pk_gross_inb', 0))
                ov = int(detail_row.get('pk_gross_outb', 0))
                rf = int(detail_row.get('pk_roc', 0))
                rv = int(rf * 0.25)
                av = rf - rv

                detail_reqs = calculate_resource_requirements(
                    total_volume=gv, ib_volume=iv, ob_volume=ov,
                    roc_volume=rv, asp_volume=av,
                    shift_hours=SHIFT_HOURS, absenteeism_pct=ABSENTEEISM_PCT,
                    training_pct=0.0, roster_buffer_pct=ROSTER_BUFFER_PCT,
                    on_call_pickup=ON_CALL_PICKUP, dex_pct=0.05, csbiv_pct=0.80, rod_pct=0.30
                )

                sc1, sc2, sc3, sc4 = st.columns(4)
                abs_post = _ss('resource_absenteeism_pct', 15.0) / 100.0
                roster_post = _ss('resource_roster_buffer_pct', 11.0) / 100.0
                base = detail_reqs['base_agents']
                abs_add = base * abs_post
                ros_add = base * roster_post
                final = math.ceil(base + abs_add + ros_add)

                with sc1: st.metric("Base Agents", f"{base:.2f}")
                with sc2: st.metric(f"Absenteeism ({_ss('resource_absenteeism_pct',15.0):.0f}%)", f"{abs_add:.2f}")
                with sc3: st.metric("Roster Buffer", f"{ros_add:.2f}")
                with sc4: st.metric("Total Agents (Final)", f"{final}")

                st.markdown("---")
                if st.button("📤 PUBLISH HUB RESOURCE REPORT", key="hub_publish_resource", type="primary"):
                    res_rows = [{'DATE': (sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else str(sel_date)),
                        'LOC ID': s['loc_id'],
                        'VOLUME': str(int(_to_float(date_famis[date_famis['loc_id'] == s['loc_id']]['pk_gross_tot'].iloc[0] if not date_famis[date_famis['loc_id'] == s['loc_id']].empty else 0))),
                        'CALCULATED AGENTS': f"{s.get('calculated_agents',0):.1f}",
                        'CURRENT AGENTS': f"{s.get('master_agents',0):.0f}",
                        'STATUS': f"{s.get('emoji','')}{s.get('deviation_percent',0):+.1f}%"
                    } for s in station_resource_statuses]
                    try:
                        save_hub_reports([], res_rows, [], report_date=sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else None)
                        st.success("✅ Hub Resource report published to HUB_REPORT_DATA.xlsx")
                    except Exception as e:
                        st.error(f"Error publishing report: {e}")
            else:
                if master_df_cur is None:
                    st.warning("📤 Upload a Hub Master file to see resource analysis")
                else:
                    st.info("📅 Select a date with volume data")
        else:
            st.markdown("""<div style="background:var(--info-bg);border-left:6px solid var(--fc-purple);
                border-radius:8px;padding:12px 16px;margin-bottom:16px;color:var(--info-text);">
                <div style="font-weight:700;">📤 Upload Hub Volume file to enable resource monitoring</div>
            </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3: COURIER MONITOR
    # ════════════════════════════════════════════════════════════════════════
    with tab3:
        _ss_set('active_tab', 'COURIER')
        if famis_df_cur is not None and sel_date is not None:
            date_famis = famis_df_cur[famis_df_cur['date'] == sel_date].copy()

            if not date_famis.empty and master_df_cur is not None and not master_df_cur.empty:
                st.markdown("---")
                pk_st_or = float(_ss('courier_pk_st_or', 1.5))
                st_hr_or = float(_ss('courier_st_hr_or', 8.0))
                productivity_hrs = float(_ss('courier_productivity_hrs', 7.0))
                absenteeism_pct = float(_ss('courier_absenteeism_pct', 16.0))
                training_pct = float(_ss('courier_training_pct', 11.0))
                working_days = int(_ss('courier_working_days', 5))

                station_courier_statuses = []
                for _, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    total_packages = int(row.get('pk_gross_tot', 0))

                    master_row = master_df_cur[master_df_cur['loc_id'] == loc_id]
                    couriers_available = 0
                    if not master_row.empty:
                        for col in ['current_total_couriers', 'couriers_available', 'existing_couriers']:
                            if col in master_row.columns:
                                try:
                                    couriers_available = int(master_row[col].iloc[0])
                                    break
                                except Exception:
                                    pass

                    cour_reqs = calculate_courier_requirements(
                        total_packages, pk_st_or, st_hr_or,
                        productivity_hrs, couriers_available,
                        absenteeism_pct, training_pct, working_days
                    )
                    couriers_req = cour_reqs['total_required_with_training']
                    status = calculate_courier_health_status(couriers_req, couriers_available)
                    status['loc_id'] = loc_id
                    status['couriers_required'] = couriers_req
                    status['couriers_available'] = couriers_available
                    station_courier_statuses.append(status)

                courier_summary = get_courier_summary_stats(station_courier_statuses)
                _ss_set('courier_health_results', station_courier_statuses)
                _ss_set('courier_tab_computed', True)

                render_section_header("HUB COURIER ANALYSIS", icon="📦", gradient_end="#FFF6E8", border_color="#FF6200")
                render_status_cards(courier_summary)

                cour_data = []
                for _, row in date_famis.iterrows():
                    loc_id = row['loc_id']
                    gross_vol = int(row.get('pk_gross_tot', 0))
                    s_status = next((s for s in station_courier_statuses if s['loc_id'] == loc_id), None)
                    cour_req = s_status['couriers_required'] if s_status else 0
                    cour_avail = s_status['couriers_available'] if s_status else 0
                    dev = s_status['deviation_percent'] if s_status else 0
                    emo = s_status['emoji'] if s_status else '❓'
                    date_str = sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else str(sel_date)

                    if gross_vol == 0 or cour_req <= 0 or cour_avail <= 0:
                        cour_data.append({'DATE': date_str, 'LOC ID': loc_id, 'VOLUME': f"{gross_vol:,}",
                            'CALCULATED COURIERS': '-' if cour_req <= 0 else f"{cour_req:.1f}",
                            'CURRENT COURIERS': '-' if cour_avail <= 0 else f"{cour_avail:.0f}", 'STATUS': '⚪ NO DATA'})
                    else:
                        cour_data.append({'DATE': date_str, 'LOC ID': loc_id, 'VOLUME': f"{gross_vol:,}",
                            'CALCULATED COURIERS': f"{cour_req:.1f}", 'CURRENT COURIERS': f"{cour_avail:.0f}",
                            'STATUS': f"{emo} {dev:+.1f}%"})

                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(cour_data), use_container_width=True, hide_index=True,
                    column_config={
                        'DATE': st.column_config.TextColumn('DATE', width=80),
                        'LOC ID': st.column_config.TextColumn('LOC ID', width=80),
                        'VOLUME': st.column_config.TextColumn('VOLUME', width=90),
                        'CALCULATED COURIERS': st.column_config.TextColumn('CALCULATED COURIERS', width=160),
                        'CURRENT COURIERS': st.column_config.TextColumn('CURRENT COURIERS', width=130),
                        'STATUS': st.column_config.TextColumn('STATUS', width=120),
                    })

                st.markdown("---")
                if st.button("📤 PUBLISH HUB COURIER REPORT", key="hub_publish_courier", type="primary"):
                    cour_rows = [{'DATE': (sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else str(sel_date)),
                        'LOC ID': s['loc_id'],
                        'VOLUME': str(int(_to_float(date_famis[date_famis['loc_id'] == s['loc_id']]['pk_gross_tot'].iloc[0] if not date_famis[date_famis['loc_id'] == s['loc_id']].empty else 0))),
                        'CALCULATED COURIERS': f"{s.get('couriers_required',0):.1f}",
                        'CURRENT COURIERS': f"{s.get('couriers_available',0):.0f}",
                        'STATUS': f"{s.get('emoji','')}{s.get('deviation_percent',0):+.1f}%"
                    } for s in station_courier_statuses]
                    try:
                        save_hub_reports([], [], cour_rows, report_date=sel_date.strftime('%Y-%m-%d') if hasattr(sel_date, 'strftime') else None)
                        st.success("✅ Hub Courier report published to HUB_REPORT_DATA.xlsx")
                    except Exception as e:
                        st.error(f"Error publishing report: {e}")
            else:
                if master_df_cur is None:
                    st.warning("📤 Upload a Hub Master file to see courier analysis")
                else:
                    st.info("📅 Select a date with volume data")
        else:
            st.markdown("""<div style="background:var(--info-bg);border-left:6px solid var(--fc-purple);
                border-radius:8px;padding:12px 16px;margin-bottom:16px;color:var(--info-text);">
                <div style="font-weight:700;">📤 Upload Hub Volume file to enable courier monitoring</div>
            </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 4: ANALYTICS
    # ════════════════════════════════════════════════════════════════════════
    with tab4:
        _ss_set('active_tab', 'ANALYTICS')
        st.markdown("""
        <div style="background:linear-gradient(90deg,#FFFFFF 0%,#F3E8FF 100%);
            border-left:6px solid #4D148C;border-radius:8px;padding:12px 16px;margin-bottom:16px;">
            <div style="font-weight:700;color:#333333;font-size:16px;">📊 HUB ANALYTICS DASHBOARD</div>
            <div style="color:#565656;font-size:13px;margin-top:4px;">Visual insights from published hub health reports</div>
        </div>""", unsafe_allow_html=True)

        area_report = read_hub_report_sheet("AREA HEALTH SUMMARY")
        resource_report = read_hub_report_sheet("RESOURCE HEALTH SUMMARY")
        courier_report = read_hub_report_sheet("COURIER HEALTH SUMMARY")

        has_data = not area_report.empty or not resource_report.empty or not courier_report.empty

        if has_data:
            primary = (area_report if not area_report.empty else
                       resource_report if not resource_report.empty else courier_report).copy()
            primary['date'] = pd.to_datetime(primary['DATE']).dt.normalize()
            primary['volume_num'] = pd.to_numeric(
                primary['VOLUME'].astype(str).str.replace(',', '', regex=False), errors='coerce'
            ).fillna(0)

            all_dates = sorted(primary['date'].unique())

            dc1, dc2, dc3 = st.columns([1, 1, 1])
            with dc1:
                an_from = st.selectbox("From", all_dates, format_func=lambda x: x.strftime('%Y-%m-%d'),
                    index=0, key='hub_analytics_from')
            with dc2:
                an_to = st.selectbox("To", all_dates, format_func=lambda x: x.strftime('%Y-%m-%d'),
                    index=len(all_dates)-1, key='hub_analytics_to')
            with dc3:
                an_tf = st.radio("Timeframe", ["DAILY", "WEEKLY", "MONTHLY"],
                    horizontal=True, key='hub_analytics_timeframe')

            mask = (primary['date'] >= an_from) & (primary['date'] <= an_to)
            filtered = primary[mask].copy()

            def _resample(df, date_col, val_cols, agg='sum'):
                _t = df.copy()
                _t[date_col] = pd.to_datetime(_t[date_col])
                if an_tf == 'DAILY':
                    _t['_p'] = _t[date_col].dt.normalize()
                    _t['label'] = _t['_p'].dt.strftime('%Y-%m-%d')
                elif an_tf == 'WEEKLY':
                    _t['_p'] = _t[date_col].dt.to_period('W').apply(lambda p: p.start_time)
                    _t['label'] = _t['_p'].dt.strftime('W/C %Y-%m-%d')
                else:
                    _t['_p'] = _t[date_col].dt.to_period('M').apply(lambda p: p.start_time)
                    _t['label'] = _t['_p'].dt.strftime('%b %Y')
                grp = _t.groupby(['_p', 'label'], as_index=False)
                out = grp[val_cols].sum() if agg == 'sum' else grp[val_cols].mean()
                return out.sort_values('_p').reset_index(drop=True)

            if not filtered.empty:
                # Chart 1: Volume trend
                st.markdown("---")
                st.markdown("""<div style="font-weight:900;color:#4D148C;font-size:18px;margin-bottom:6px;
                    letter-spacing:-0.3px;text-transform:uppercase;">📈 1. HUB VOLUME TREND</div>""",
                    unsafe_allow_html=True)

                raw_hub = read_hub_uploads()
                if not raw_hub.empty and 'date' in raw_hub.columns and 'pk_gross_tot' in raw_hub.columns:
                    raw_hub['date'] = pd.to_datetime(raw_hub['date']).dt.normalize()
                    for _nc in ['pk_gross_tot', 'pk_gross_inb', 'pk_gross_outb']:
                        if _nc in raw_hub.columns:
                            raw_hub[_nc] = pd.to_numeric(raw_hub[_nc], errors='coerce').fillna(0)
                    raw_filt = raw_hub[(raw_hub['date'] >= an_from) & (raw_hub['date'] <= an_to)]
                    vol_daily = raw_filt.groupby('date', as_index=False).agg(
                        TOTAL_VOLUME=('pk_gross_tot', 'sum'),
                        INBOUND=('pk_gross_inb', 'sum'),
                        OUTBOUND=('pk_gross_outb', 'sum')
                    )
                else:
                    vol_daily = filtered.groupby('date', as_index=False).agg(TOTAL_VOLUME=('volume_num', 'sum'))
                    vol_daily['INBOUND'] = 0
                    vol_daily['OUTBOUND'] = 0

                vol_trend = _resample(vol_daily, 'date', ['TOTAL_VOLUME', 'INBOUND', 'OUTBOUND'])
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Scatter(x=vol_trend['label'], y=vol_trend['TOTAL_VOLUME'],
                    mode='lines+markers', name='Total Volume',
                    line=dict(color='#4D148C', width=3), fill='tozeroy', fillcolor='rgba(77,20,140,0.08)',
                    marker=dict(size=8)))
                fig_vol.add_trace(go.Scatter(x=vol_trend['label'], y=vol_trend['INBOUND'],
                    mode='lines+markers', name='Inbound',
                    line=dict(color='#FF6200', width=2, dash='dot'), marker=dict(size=6)))
                fig_vol.add_trace(go.Scatter(x=vol_trend['label'], y=vol_trend['OUTBOUND'],
                    mode='lines+markers', name='Outbound',
                    line=dict(color='#008A00', width=2, dash='dash'), marker=dict(size=6)))
                fig_vol.update_layout(template='plotly_white', height=360,
                    margin=dict(l=40, r=20, t=30, b=40),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
                    xaxis_title=an_tf.title() + ' Period', yaxis_title='Packages',
                    font=dict(family='FedExSansArabic, DM Sans, Inter, sans-serif', size=12))
                st.plotly_chart(fig_vol, use_container_width=True)

                # Chart 2: Per-hub status breakdown
                st.markdown("---")
                st.markdown("""<div style="font-weight:900;color:#4D148C;font-size:18px;margin-bottom:8px;
                    letter-spacing:-0.3px;text-transform:uppercase;">🏆 2. HUB PERFORMANCE RANKING</div>""",
                    unsafe_allow_html=True)

                perf_metric = st.selectbox("Rank by metric", ["AREA", "RESOURCE", "COURIER"],
                    key='hub_perf_metric')
                sheet_map = {"AREA": area_report, "RESOURCE": resource_report, "COURIER": courier_report}
                perf_rep = sheet_map[perf_metric].copy()

                if not perf_rep.empty:
                    perf_rep['date'] = pd.to_datetime(perf_rep['DATE']).dt.normalize()
                    pf = perf_rep[(perf_rep['date'] >= an_from) & (perf_rep['date'] <= an_to)]
                    if not pf.empty:
                        def _parse_dev(s):
                            m = re.search(r'([+-]?\d+\.?\d*)%', str(s))
                            return float(m.group(1)) if m else None
                        pf = pf.copy()
                        pf['Deviation %'] = pf['STATUS'].apply(_parse_dev)
                        pf_valid = pf[pf['Deviation %'].notna()].copy()
                        if not pf_valid.empty:
                            pf_agg = pf_valid.groupby('LOC ID', as_index=False)['Deviation %'].mean()
                            pf_agg['Deviation %'] = pf_agg['Deviation %'].round(1)
                            pf_agg = pf_agg[pf_agg['Deviation %'] != 0.0]

                            if not pf_agg.empty:
                                pf_agg_sorted = pf_agg.sort_values('Deviation %', ascending=True)
                                bar_colors = ['#008A00' if v >= -10 else '#F7B118' if v >= -20 else '#DE002E'
                                              for v in pf_agg_sorted['Deviation %']]
                                fig_bar = go.Figure(go.Bar(
                                    x=pf_agg_sorted['LOC ID'], y=pf_agg_sorted['Deviation %'],
                                    marker_color=bar_colors,
                                    text=[f"{v:+.1f}%" for v in pf_agg_sorted['Deviation %']],
                                    textposition='outside'))
                                fig_bar.add_hline(y=-10, line_dash='dot', line_color='#F7B118', line_width=1.5,
                                    annotation_text='-10% Review threshold', annotation_position='bottom right')
                                fig_bar.add_hline(y=-20, line_dash='dot', line_color='#DE002E', line_width=1.5,
                                    annotation_text='-20% Critical threshold', annotation_position='bottom right')
                                fig_bar.update_layout(template='plotly_white', height=380,
                                    margin=dict(l=40, r=20, t=40, b=60),
                                    xaxis_title='Hub (LOC ID)', yaxis_title='Avg Deviation %',
                                    font=dict(family='FedExSansArabic, DM Sans, Inter, sans-serif', size=12))
                                st.plotly_chart(fig_bar, use_container_width=True)

                # Chart 3: Status distribution pie
                st.markdown("---")
                st.markdown("""<div style="font-weight:900;color:#4D148C;font-size:18px;margin-bottom:8px;
                    letter-spacing:-0.3px;text-transform:uppercase;">🥧 3. STATUS DISTRIBUTION</div>""",
                    unsafe_allow_html=True)

                pie_col1, pie_col2, pie_col3 = st.columns(3)
                for _col, _rep, _title in [
                    (pie_col1, area_report, "Area"),
                    (pie_col2, resource_report, "Resource"),
                    (pie_col3, courier_report, "Courier")
                ]:
                    with _col:
                        if not _rep.empty:
                            _rep2 = _rep.copy()
                            def _status_cat(s):
                                s = str(s)
                                if '✅' in s or 'HEALTHY' in s.upper():
                                    return 'Healthy'
                                elif '⚠️' in s or 'REVIEW' in s.upper():
                                    return 'Review'
                                elif '🔴' in s or 'CRITICAL' in s.upper():
                                    return 'Critical'
                                else:
                                    return 'Unknown'
                            _rep2['cat'] = _rep2['STATUS'].apply(_status_cat)
                            _counts = _rep2['cat'].value_counts()
                            _colors_map = {'Healthy': '#008A00', 'Review': '#F7B118', 'Critical': '#DE002E', 'Unknown': '#8E8E8E'}
                            _colors = [_colors_map.get(c, '#8E8E8E') for c in _counts.index]
                            fig_pie = go.Figure(go.Pie(
                                labels=_counts.index, values=_counts.values,
                                marker_colors=_colors, hole=0.35,
                                textinfo='percent+label'))
                            fig_pie.update_layout(title=f"{_title} Status", height=280,
                                margin=dict(l=10, r=10, t=40, b=10),
                                font=dict(family='FedExSansArabic, DM Sans, Inter, sans-serif', size=11),
                                showlegend=False)
                            st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            st.info(f"No {_title.lower()} report data yet. Publish a report first.")
        else:
            st.markdown("""
            <div style="background:var(--info-bg);border-left:6px solid var(--fc-purple);border-radius:8px;
                padding:16px 20px;margin-top:16px;color:var(--info-text);">
                <div style="font-weight:700;font-size:15px;">📊 No Hub Analytics Data Yet</div>
                <div style="margin-top:8px;font-size:13px;">
                    Upload Hub Volume and Master files, then use the <strong>PUBLISH</strong> button in the
                    Area / Resource / Courier tabs to generate analytics data.
                </div>
            </div>""", unsafe_allow_html=True)
