"""Hub Area Tracker — mirrors area_planner.py with hub_ session namespace."""
import streamlit as st
import pandas as pd
from aero.core.area_calculator import (
    calculate_area_requirements,
    get_caging_supplies_area,
    PREDEFINED_AREAS,
)
from aero.config.settings import load_area_config

_P = "hub_"

def _ss(key, default=None):
    return st.session_state.get(f"{_P}{key}", default)

def _ss_set(key, value):
    st.session_state[f"{_P}{key}"] = value


def render():
    """Render Hub Area Tracker (called from hub_planner.py tab)."""
    st.markdown("""
    <div style="background:linear-gradient(90deg,#FFFFFF 0%,#F3E8FF 100%);
        border-left:6px solid #DE002E;border-radius:8px;padding:12px 16px;margin-bottom:8px;">
        <div style="font-weight:700;color:#333333;font-size:16px;">📍 Hub Information</div>
    </div>""", unsafe_allow_html=True)

    # Load area config
    AREA_CFG = load_area_config()
    AREA_CONSTANTS = AREA_CFG.get("AREA_CONSTANTS", {})
    PALLET_AREA = AREA_CONSTANTS.get("PALLET_AREA", 16)
    AISLE_PERCENT = AREA_CONSTANTS.get("AISLE_PERCENT", 0.15)
    HPT_AREA = 50
    ROC_AREA = 100

    # Auto-populate from hub FAMIS data
    famis_data = _ss('famis_data')
    if famis_data is not None and not famis_data.empty:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#FAFAFA 0%,#FFFFFF 100%);border-left:4px solid #4D148C;
            border-radius:8px;padding:1rem 1.25rem;margin:0.5rem 0 1rem 0;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <span style="color:#4D148C;font-weight:600;">✅ Hub FAMIS Data Loaded</span>
            <span style="color:#565656;"> — Select a hub to auto-fill volume</span>
        </div>""", unsafe_allow_html=True)

        hub_stations = sorted(famis_data['loc_id'].dropna().unique().tolist())
        hub_dates = sorted(famis_data['date'].unique(), reverse=True)

        hc1, hc2 = st.columns(2)
        with hc1:
            sel_hub = st.selectbox("📍 Select Hub", options=[""] + hub_stations, index=0,
                key="hub_area_famis_station", help="Auto-populate volume from Hub FAMIS data")
        with hc2:
            sel_date = st.selectbox("📅 Date", options=hub_dates,
                format_func=lambda x: pd.to_datetime(x).strftime('%Y-%m-%d'),
                key="hub_area_famis_date")

        if sel_hub:
            sdata = famis_data[(famis_data['loc_id'] == sel_hub) & (famis_data['date'] == sel_date)]
            if not sdata.empty:
                vol = int(sdata['pk_gross_tot'].iloc[0]) if 'pk_gross_tot' in sdata.columns else 0
                _ss_set('area_volume_from_famis', vol)
                _ss_set('area_daily_volume', vol)
                _ss_set('area_famis_station', sel_hub)
                st.success(f"📦 Auto-filled: **{vol:,}** packs for hub **{sel_hub}**")
    else:
        st.markdown("""<div style="background:var(--info-bg);border-left:6px solid var(--fc-purple);
            border-radius:8px;padding:12px 16px;margin-bottom:16px;color:var(--info-text);">
            <div style="font-weight:700;">💡 Upload Hub Volume data in the <strong>Health Monitor</strong> tab to enable auto-population</div>
        </div>""", unsafe_allow_html=True)

    loc_id = _ss('area_famis_station', '')

    # ── Parameters ──────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:linear-gradient(90deg,#FFFFFF 0%,#F3E8FF 100%);
        border-left:6px solid #4D148C;border-radius:8px;padding:12px 16px;margin:12px 0 8px 0;">
        <div style="font-weight:700;color:#333333;font-size:15px;">⚙️ Area Parameters</div>
    </div>""", unsafe_allow_html=True)

    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        daily_volume = st.number_input("Daily Volume (Packs)", min_value=0, value=_ss('area_daily_volume', 0),
            step=1, key='hub_area_daily_volume_input')
        _ss_set('area_daily_volume', daily_volume)
    with pc2:
        packs_per_pallet = st.number_input("Packs per Pallet", min_value=1, value=_ss('area_packs_per_pallet', 15),
            step=1, key='hub_area_packs_per_pallet_input')
        _ss_set('area_packs_per_pallet', packs_per_pallet)
    with pc3:
        max_volume = st.number_input("Max Volume % (Peak Hour)", min_value=1.0, max_value=100.0,
            value=_ss('area_max_volume', 55.0), step=1.0, key='hub_area_max_volume_input')
        _ss_set('area_max_volume', max_volume)

    pc4, pc5 = st.columns(2)
    with pc4:
        sorting_pct = st.number_input("Sorting Area %", min_value=0.0, max_value=100.0,
            value=_ss('area_sorting_percent', 60.0), step=1.0, key='hub_area_sorting_input')
        _ss_set('area_sorting_percent', sorting_pct)
    with pc5:
        aisle_pct = st.number_input("Aisle %", min_value=0.0, max_value=100.0,
            value=_ss('area_aisle_percent', 15.0), step=0.5, key='hub_area_aisle_input')
        _ss_set('area_aisle_percent', aisle_pct)

    # ── Calculation ─────────────────────────────────────────────────────────
    if daily_volume > 0:
        calcs = calculate_area_requirements(
            total_packs=daily_volume,
            packs_per_pallet=packs_per_pallet,
            max_volume_percent=max_volume,
            sorting_area_percent=sorting_pct,
            cage_percent=10.0,
            aisle_percent=aisle_pct,
        )
        cs = get_caging_supplies_area(daily_volume)

        st.markdown("---")
        st.markdown("""
        <div style="background:linear-gradient(90deg,#FFFFFF 0%,#F3E8FF 100%);
            border-left:6px solid #008A00;border-radius:8px;padding:12px 16px;margin-bottom:12px;">
            <div style="font-weight:700;color:#333333;font-size:15px;">📊 Hub Area Calculation Results</div>
        </div>""", unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Pallets Required", f"{calcs['pallets_required']:,}")
        with m2: st.metric("Avg Hourly Pallets", f"{calcs['avg_hourly_pallets']:,}")
        with m3: st.metric("Base Area (sqft)", f"{calcs['area_required']:,.0f}")
        with m4: st.metric("Area + Aisle (sqft)", f"{calcs['area_with_aisle']:,.0f}")

        m5, m6, m7, m8 = st.columns(4)
        with m5: st.metric("Sorting Area (sqft)", f"{calcs['sorting_area']:,.0f}")
        with m6: st.metric(f"Cage Area (sqft) — Model {cs['model']}", f"{calcs['cage_area_required']:,.0f}")
        with m7: st.metric("Equipment Area (sqft)", f"{calcs['equipment_area']:,.0f}")
        with m8: st.metric("🎯 Total Operational Area", f"{calcs['total_operational_area']:,.0f}")

        # Additional areas
        st.markdown("---")
        st.markdown("""
        <div style="background:linear-gradient(90deg,#FFFFFF 0%,#FFF6E8 100%);
            border-left:6px solid #FF6200;border-radius:8px;padding:12px 16px;margin-bottom:8px;">
            <div style="font-weight:700;color:#333333;font-size:15px;">➕ Additional Area Components</div>
        </div>""", unsafe_allow_html=True)

        add_cols = st.columns(len(PREDEFINED_AREAS))
        additional_total = 0.0
        for idx, (area_name, default_val) in enumerate(PREDEFINED_AREAS.items()):
            with add_cols[idx % len(add_cols)]:
                key_add = f"hub_area_pred_{area_name.replace(' ', '_').lower()}"
                if default_val is not None:
                    st.metric(area_name, f"{default_val} sqft")
                    additional_total += default_val
                else:
                    user_val = st.number_input(area_name, min_value=0, value=0, step=10, key=key_add)
                    additional_total += user_val

        grand_total = calcs['total_operational_area'] + additional_total
        st.markdown("---")
        st.metric("🏭 HUB GRAND TOTAL AREA (sqft)", f"{grand_total:,.0f}",
            help="Operational area + all additional components")
    else:
        st.info("Enter a daily volume above to calculate area requirements.")
