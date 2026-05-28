import streamlit as st
import math
import os
from datetime import datetime
import json
import pandas as pd
from aero.core.courier_calculator import calculate_courier_requirements


def render():
    """Render the Station Courier Tracker content (called from station_planner.py tab)."""

    # Station information block (compact confined card)
    st.markdown("""
    <div style="
        background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
        border-left: 6px solid #4D148C;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 0px;
        display:flex; align-items:center; gap:10px;
    ">
        <div style="font-size:18px;">📍</div>
        <div>
            <div style="font-weight:700;color:#333333;font-size:15px;">Station Information</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Load courier-related config so admin changes reflect here
    from aero.config.settings import load_config as _load_cfg

    _cfg = _load_cfg()
    _cour = _cfg.get("COURIER", {})
    STANDARD_PRODUCTIVITY = int(_cour.get("STANDARD_PRODUCTIVITY", 45))

    # ============================================
    # STATION IDENTIFICATION
    # ============================================
    from aero.data.station_store import get_all_stations, get_station_info

    EXCEL_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "station_planner_master.xlsx")

    # (Removed boxed Station Identification header per request)

    # Get available stations from Area sheet
    available_stations = get_all_stations(EXCEL_DB)

    _, c2, _ = st.columns([1, 200, 1])
    with c2:
        # Only render a free-text LOC-ID if FAMIS data is loaded or a station_name exists in session.
        # This prevents the LOC-ID box from appearing before upload (matches desired UI).
        # LOC-ID input removed from Courier tab per UX requirement; station selection is handled
        # via the FAMIS selector below. Keep session key cleared when not present.
        if "station_loc_id" not in st.session_state:
            st.session_state.station_loc_id = ""


    # ============================================
    # FAMIS STATION SELECTION (Auto-populate courier metrics)
    # ============================================
    famis_data = st.session_state.get('famis_data', None)

    # When no FAMIS data is present show a prominent upload hint.
    if famis_data is None or famis_data.empty:
        # Use the same hint style as other pages
        st.markdown("""
        <div style="
            background: var(--info-bg);
            border-left: 6px solid var(--fc-purple);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: var(--info-text);
        ">
            <div style="font-weight:700;">💡 Upload FAMIS/Volume data in the <strong>Health Monitor</strong> tab to enable auto-population of volumes</div>
        </div>
        """, unsafe_allow_html=True)

    else:
        # Match the loaded banner markup used on the Resource page for consistency
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
            border-left: 4px solid #4D148C;
            border-radius: 8px;
            padding: 1rem 1.25rem;
            margin: 0.5rem 0 1rem 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        ">
            <span style="color: #4D148C; font-weight: 600;">✅ FAMIS Data Loaded</span>
            <span style="color: #565656;"> — Select a station to auto-fill volumes (Gross Total, IB, OB, ROC)</span>
        </div>
        """, unsafe_allow_html=True)

        # Get unique stations and dates
        famis_stations = sorted(famis_data['loc_id'].dropna().unique().tolist())
        famis_dates = sorted(famis_data['date'].unique(), reverse=True)

        famis_col1, famis_col2 = st.columns(2)

        with famis_col1:
            selected_famis_station = st.selectbox(
                "📍 Select FedEx Station",
                options=[""] + famis_stations,
                index=0,
                help="Select a station to auto-populate courier metrics from FAMIS data",
                key="courier_famis_station"
            )

        with famis_col2:
            selected_famis_date = st.selectbox(
                "📅 Select FAMIS Date",
                options=famis_dates,
                format_func=lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x),
                help="Select the date for courier data",
                key="courier_famis_date"
            )

        # Auto-fill courier metrics when station is selected
        if selected_famis_station:
            station_data = famis_data[
                (famis_data['loc_id'] == selected_famis_station) & 
                (famis_data['date'] == selected_famis_date)
            ]
            if not station_data.empty:
                row = station_data.iloc[0]
                # Get courier columns from FAMIS
                emp_reported_pct = float(row.get('emp_reported_pct', 0)) if pd.notna(row.get('emp_reported_pct')) else 0.0
                st_cr_or = float(row.get('st_cr_or', 0)) if pd.notna(row.get('st_cr_or')) else 0.0
                st_hr_or = float(row.get('st_h_or', 0)) if pd.notna(row.get('st_h_or')) else 0.0
                pk_st_or = float(row.get('pk_st_or', 0)) if pd.notna(row.get('pk_st_or')) else 0.0
                pk_fte_or = float(row.get('pk_fte', 0)) if pd.notna(row.get('pk_fte')) else 0.0

                # Also get daily packages if available
                daily_packages = float(row.get('pk_gross_tot', 0)) if pd.notna(row.get('pk_gross_tot')) else 0.0

                # Also fetch current_total_couriers from the master file (best-effort)
                master_couriers_val = 0
                _master = st.session_state.get('master_data', None)
                if _master is not None and not _master.empty:
                    cols = [c.lower() for c in _master.columns]
                    candidate = None
                    for c in ['current_total_couriers','couriers_available','existing_couriers']:
                        if c in cols:
                            candidate = _master.columns[cols.index(c)]
                            break
                    if candidate is not None:
                        try:
                            # try to find matching loc row
                            loccol = None
                            for lc in ['loc_id','loc','locid']:
                                if lc in cols:
                                    loccol = _master.columns[cols.index(lc)]
                                    break
                            if loccol is not None:
                                mrow = _master[_master[loccol].astype(str).str.strip() == str(selected_famis_station).strip()]
                                if not mrow.empty:
                                    master_couriers_val = int(mrow.iloc[0].get(candidate,0) or 0)
                        except Exception:
                            master_couriers_val = 0

                # Store in session state for auto-population
                st.session_state['courier_data_from_famis'] = {
                    'emp_reported_pct': emp_reported_pct,
                    'st_cr_or': st_cr_or,
                    'st_hr_or': st_hr_or,
                    'pk_st_or': pk_st_or,
                    'pk_fte_or': pk_fte_or,
                    'daily_packages': daily_packages,
                    'master_couriers': master_couriers_val
                }

                # Update station identifiers so downstream master lookup also works
                st.session_state.station_name = selected_famis_station
                st.session_state['courier_famis_loc'] = selected_famis_station

                # ── Seed couriers_available ONLY when the station changes ─────────────
                # Do NOT force-set on every rerun — that resets whatever the user typed.
                _prev_cour_station = st.session_state.get('_courier_last_station', None)
                if selected_famis_station != _prev_cour_station:
                    st.session_state['couriers_available'] = master_couriers_val
                    st.session_state['_courier_last_station'] = selected_famis_station
                # ─────────────────────────────────────────────────────────────────────

                st.success(f"📦 Auto-filled for **{selected_famis_station}**: EMP%={emp_reported_pct:.1f} | ST/CR OR={st_cr_or:.2f} | ST/HR OR={st_hr_or:.2f} | PK/ST={pk_st_or:.2f}")

    # ============================================
    # VOLUME DETAILS (compact FedEx-themed header)
    # ============================================
    st.markdown("""
    <div style="
        background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
        border-left: 6px solid #4D148C;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">📦 Volume Details</div>
    </div>
    """, unsafe_allow_html=True)

    # Get FAMIS courier data if available
    famis_courier = st.session_state.get('courier_data_from_famis', {})
    default_packages = float(famis_courier.get('daily_packages', 0)) if famis_courier.get('daily_packages') else 0.0

    total_packages = st.number_input(
        "Total Packages on the Road",
        min_value=0.0,
        value=default_packages,
        step=1.0,
        format="%.2f",
        help="Auto-populated from FAMIS if loaded"
    )

    # ============================================
    # FAMIS COURIER METRICS
    # ============================================
    default_productivity_hrs = float(famis_courier.get('productivity_hrs') or _cour.get('PRODUCTIVITY_HRS', 7.0))
    default_st_cr_or         = float(famis_courier.get('st_cr_or') or 0.0)
    default_st_hr_or         = float(famis_courier.get('st_hr_or') or _cour.get('ST_HR_OR', 4.0))
    default_pk_st            = float(famis_courier.get('pk_st_or') or _cour.get('PK_ST_OR', 2.5))

    with st.expander("⚙️ FAMIS Courier Metrics", expanded=False):
        fm1, fm2, fm3, fm4 = st.columns(4)

        with fm1:
            productivity_hrs = st.number_input("Productivity Hrs", min_value=0.0, value=default_productivity_hrs, step=0.1, format="%.2f")
        with fm2:
            st_cr_or = st.number_input("ST/CR OR", min_value=0.0, value=default_st_cr_or, step=0.01, format="%.2f")
        with fm3:
            st_hr_or = st.number_input("ST/HR OR", min_value=0.0, value=default_st_hr_or, step=0.01, format="%.2f")
        with fm4:
            pk_st_or = st.number_input("PK/ST OR", min_value=0.0, value=default_pk_st, step=0.01, format="%.2f")

    # Removed duplicate Route & Courier Details card (now only in expander)


    with st.expander("🛣️ Route & Courier Details", expanded=True):
        # The widget's session-state key 'couriers_available' is the single source of truth.
        # It is seeded (once) when a station is first selected; after that the user's manual
        # edits are preserved across reruns because we no longer force-overwrite it.
        couriers_available = st.number_input(
            "Couriers Available at the Station",
            min_value=0,
            step=1,
            value=st.session_state.get('couriers_available', 0),
            key='couriers_available',
            help="Auto-filled from Facility Master when you select a station above. You can override this manually.",
        )

        # MANPOWER ASSUMPTIONS
        absenteeism_pct = st.number_input("Absentism %", min_value=0.0, step=0.1, value=16.0, format="%.2f")
        working_days = st.number_input("Working Days", min_value=0, step=1, value=5)
        training_pct = st.number_input("Training %", min_value=0.0, step=0.1, value=11.0, format="%.2f")

        st.session_state['courier_pk_st_or'] = pk_st_or
        st.session_state['courier_st_hr_or'] = st_hr_or
        st.session_state['courier_productivity_hrs'] = productivity_hrs
        st.session_state['courier_absenteeism_pct'] = absenteeism_pct
        st.session_state['courier_training_pct'] = training_pct
        st.session_state['courier_working_days'] = working_days

    # CALCULATIONS
    courier_reqs = calculate_courier_requirements(
        total_packages=total_packages,
        pk_st_or=pk_st_or,
        st_hr_or=st_hr_or,
        productivity_hrs=productivity_hrs,
        couriers_available=couriers_available,
        absenteeism_pct=absenteeism_pct,
        training_pct=training_pct,
        working_days=working_days
    )

    productivity_as_per_hrs = courier_reqs.get('productivity_as_per_hrs', 0)
    courier_required_as_per_productivity = courier_reqs.get('courier_required_as_per_productivity', 0)
    courier_required_with_absentism = courier_reqs.get('courier_required_with_absenteeism', 0)
    total_working_days_plus_training = courier_reqs.get('total_required_with_training', 0)
    final_delta = courier_reqs.get('final_delta', 0)

    # NO DATA condition — only suppress display when there is literally zero volume.
    # Calculated values (required couriers, delta) are meaningful even when
    # couriers_available=0 (it just means a large deficit), so we must NOT hide them.
    no_volume = (total_packages == 0)

    if no_volume:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#FFF8F0 0%,#FFFFFF 100%);
            border-left:5px solid #FF6200;border-radius:10px;
            padding:14px 18px;margin:10px 0 14px 0;
            box-shadow:0 1px 3px rgba(0,0,0,0.06);">
            <div style="font-weight:800;color:#FF6200;font-size:13px;
                text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">
                💡 How to see courier calculations
            </div>
            <div style="color:#555;font-size:13px;line-height:1.65;">
                Enter a <b>Total Packages</b> value above to activate all KPI metrics.<br>
                <b>Suggested test values:</b> Packages=<b>500</b> | PK/ST OR=<b>2.5</b> |
                ST/HR OR=<b>4.0</b> | Productivity Hrs=<b>7.0</b> | Couriers Available=<b>20</b>
                → Expected: Productivity=<b>70</b> | Required=<b>8</b> |
                With Absenteeism=<b>10</b> | Total=<b>12</b> | Delta=<b>+8 ✅ Surplus</b>
            </div>
        </div>""", unsafe_allow_html=True)

    # Individual metric visibility flags
    _prod   = productivity_as_per_hrs
    _req_p  = courier_required_as_per_productivity
    _req_a  = courier_required_with_absentism
    _total  = total_working_days_plus_training
    _delta  = final_delta

    # Helper: format a numeric value; show "—" only when no volume at all
    def _fmt(v, decimals=0):
        if no_volume:
            return "—"
        if decimals:
            return f"{v:.{decimals}f}"
        return str(int(round(v))) if isinstance(v, float) else str(v)

    # Delta classification (surplus / balanced / deficit)
    if no_volume:
        _delta_label = ""
        _delta_color = "normal"
    elif _delta > 0:
        _delta_label = "Surplus"
        _delta_color = "normal"
    elif _delta == 0:
        _delta_label = "Balanced"
        _delta_color = "off"
    else:
        _delta_label = "Deficit"
        _delta_color = "inverse"

    # OUTPUT METRICS
    o1, o2, o3, o4, o5 = st.columns(5)

    with o1:
        st.metric("Productivity (hrs)", _fmt(_prod, 2))
    with o2:
        st.metric("Required (Productivity)", _fmt(_req_p))
    with o3:
        st.metric("Required (+ Absenteeism)", _fmt(_req_a))
    with o4:
        st.metric("Required (+ Training)", _fmt(_total))
    with o5:
        if no_volume:
            st.metric("Delta", "—", delta="No volume", delta_color="normal")
        else:
            st.metric(
                "Delta",
                _fmt(_delta),
                delta=_delta_label,
                delta_color=_delta_color,
            )

    # ── Summary card ────────────────────────────────────────────────────────
    _avail_str    = str(couriers_available) if not no_volume else "—"
    _req_str      = _fmt(_req_a)
    _delta_str    = _fmt(_delta)

    # Choose accent colour based on delta: green=surplus, amber=balanced, red=deficit
    if no_volume:
        _card_bg = "linear-gradient(135deg, #888 0%, #666 100%)"
    elif _delta > 0:
        _card_bg = "linear-gradient(135deg, #1E8449 0%, #27AE60 100%)"
    elif _delta == 0:
        _card_bg = "linear-gradient(135deg, #B7770D 0%, #D4AC0D 100%)"
    else:
        _card_bg = "linear-gradient(135deg, #FF6200 0%, #E45528 100%)"

    st.markdown(f"""
    <div style="
        background: {_card_bg};
        border-radius: 10px;
        padding: 0.6rem 1rem;
        margin: 0.8rem 0;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.18);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap:wrap;">
            <div style="color: #FFFFFF;">
                <div style="font-size: 11px; opacity: 0.90; text-transform: uppercase; letter-spacing: 0.4px;">Courier Summary</div>
                <div style="font-size: 18px; font-weight: 700; margin-top: 4px;">
                    {_avail_str} Available &nbsp;|&nbsp; {_req_str} Required
                </div>
            </div>
            <div style="background: rgba(255,255,255,0.15); padding: 0.4rem 0.8rem; border-radius: 6px; min-width:72px; text-align:center;">
                <div style="color: rgba(255,255,255,0.90); font-size: 11px; text-transform:uppercase; letter-spacing:0.3px;">Final Delta</div>
                <div style="color: #FFFFFF; font-size: 22px; font-weight: 800;">{_delta_str}</div>
                <div style="color: rgba(255,255,255,0.80); font-size: 10px;">{_delta_label if not no_volume else 'Upload volume'}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
