import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from aero.core.area_calculator import calculate_area_requirements, get_caging_supplies_area, PREDEFINED_AREAS


def render():
    """Render the Station Area Tracker content (called from station_planner.py tab)."""

    # ================================
    # STATION INFORMATION
    # ================================

    # Station Information (confined card to match Area Calculations)
    st.markdown("""
    <div style="
        background: linear-gradient(90deg,#FFFFFF 0%, #F3E8FF 100%);
        border-left: 6px solid #DE002E;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">📍 Station Information</div>
    </div>
    """, unsafe_allow_html=True)

    # ================================
    # FAMIS STATION SELECTION (Auto-populate from Health Monitor)
    # ================================
    famis_data = st.session_state.get('famis_data', None)

    if famis_data is not None and not famis_data.empty:
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
            <span style="color: #565656;"> — Select a station to auto-fill volume</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Get unique stations and dates
        famis_stations = sorted(famis_data['loc_id'].dropna().unique().tolist())
        famis_dates = sorted(famis_data['date'].unique(), reverse=True)
        
        famis_col1, famis_col2 = st.columns(2)
        
        with famis_col1:
            selected_famis_station = st.selectbox(
                "📍 Select FEDEX Station",
                options=[""] + famis_stations,
                index=0,
                help="Select a station to auto-populate volume from FAMIS data"
            )
        
        with famis_col2:
            selected_famis_date = st.selectbox(
                "📅Date",
                options=famis_dates,
                format_func=lambda x: pd.to_datetime(x).strftime('%Y-%m-%d'),
                help="Select the date for volume data"
            )
        
        # Auto-fill volume when station is selected
        if selected_famis_station:
            station_data = famis_data[
                (famis_data['loc_id'] == selected_famis_station) & 
                (famis_data['date'] == selected_famis_date)
            ]
            if not station_data.empty:
                # Get total volume (pk_gross_tot column)
                famis_total_volume = int(station_data['pk_gross_tot'].iloc[0]) if 'pk_gross_tot' in station_data.columns else 0
                st.session_state['area_volume_from_famis'] = famis_total_volume
                # Also set the widget-backed daily volume so the number_input reflects the auto-fill
                st.session_state['area_daily_volume'] = famis_total_volume
                st.session_state['area_famis_station'] = selected_famis_station
                st.success(f"📦 Auto-filled: **{famis_total_volume:,}** packs from FAMIS/Volume data for station **{selected_famis_station}**")
            else:
                st.session_state['area_volume_from_famis'] = 0
                st.session_state['area_daily_volume'] = 0
    else:
        # Do not display the upload hint here; it will appear below the LOC-ID input for consistency
        pass

    # Use FAMIS station selection to determine LOC-ID. Do not render a free-text LOC-ID
    # when no FAMIS file is uploaded — this prevents duplicate/unnecessary LOC-ID showing.
    if famis_data is not None and not (hasattr(famis_data, 'empty') and famis_data.empty):
        # When a FAMIS station is selected earlier we populate session state 'area_famis_station'.
        loc_id = st.session_state.get('area_famis_station', '')
    else:
        # No FAMIS uploaded — don't prompt for a LOC-ID here; instruct user to upload instead.
        loc_id = ''
        st.markdown("""
        <div style="
            background: var(--info-bg);
            border-left: 6px solid var(--fc-purple);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: var(--info-text);
        ">
            <div style="font-weight:700;">💡 Upload FAMIS/Volume data in the <strong>Health Monitor</strong> tab to enable station selection and auto-population of volumes</div>
        </div>
        """, unsafe_allow_html=True)

    # ==================================================
    # LOAD AREA CONFIG
    # ==================================================
    from aero.config.settings import load_area_config
    AREA_CFG = load_area_config()
    AREA_CONSTANTS = AREA_CFG.get("AREA_CONSTANTS", {})

    # ---------- CONSTANTS (FROM AREA.JSON) ----------
    PALLET_AREA = AREA_CONSTANTS.get("PALLET_AREA", 16)
    AISLE_PERCENT = AREA_CONSTANTS.get("AISLE_PERCENT", 0.15)
    CAGE_PALLET_AREA = AREA_CONSTANTS.get("CAGE_PALLET_AREA", 25)
    STACKING_PER_PALLET = AREA_CONSTANTS.get("STACKING_PER_PALLET", 20)

    # ==================================================
    # EQUIPMENT OUTPUT CONSTANTS
    # ==================================================
    HPT_AREA = 50       # sq.ft per HPT unit
    ROC_AREA = 100      # sq.ft for ROC counter
    # Fixed Equipment Totals (HPT + ROC) — VMEASURE removed

    # PREDEFINED_AREAS imported from aero.core.area_calculator (single source of truth)

    # ==================================================
    # FILE PATH & DATABASE CONFIG
    # ==================================================
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EXCEL_DB = os.path.join(_BASE_DIR, "station_planner_master.xlsx")

    COLUMN_ORDER = [
        "timestamp",
        "station_name",
        "daily_volume",
        "pallets_required",
        "avg_hourly_pallets",
        "area_required",
        "area_with_aisle",
        "sorting_area",
        "cage_pallets",
        "cage_area_required",
        "stack_percent",
        "stacking_area",
        "total_operational_area"
    ]

    # ==================================================
    # FACILITY PLANNER
    # ==================================================

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
        border-left: 4px solid #4D148C;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1.5rem 0 1rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">🏭 Area Calculations</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⚙️ Calculation Parameters", expanded=False):
        c1, c2, c3, c4 = st.columns(4)

        # Get FAMIS volume if available
        famis_volume = st.session_state.get('area_volume_from_famis', 0)

        # Ensure session-state key exists before creating the widget.
        # This avoids passing a default `value=` while the same key is
        # already set via the Session State API (which triggers Streamlit's
        # warning). Initialize from FAMIS volume if present, otherwise 0.
        if 'area_daily_volume' not in st.session_state:
            st.session_state['area_daily_volume'] = st.session_state.get('area_volume_from_famis', 0)

        with c1:
            total_packs = st.number_input(
                "Daily Volume (packs)",
                min_value=0,
                key='area_daily_volume',
                help="Auto-populated from FAMIS if loaded"
            )

        with c2:
            packs_per_pallet = st.number_input("Packs / Pallet", min_value=1, value=15)

        with c3:
            max_volume_percent = st.number_input("Max Handling %", min_value=0.0, max_value=100.0, value=55.0)

        with c4:
            sorting_area_percent = st.number_input("Sorting Area %", min_value=0.0, max_value=100.0, value=60.0)

        c5, c6 = st.columns(2)

        with c5:
            cage_percent = st.number_input("Shipments to Cage (%)", min_value=0.0, max_value=100.0, value=10.0)

        with c6:
            aisle_percent = st.number_input("Aisle %", 0.0, 100.0, value=15.0, help="Percentage of additional space for aisles")

    # Persist area parameters to session state for Health Monitor inheritance
    st.session_state['area_packs_per_pallet'] = packs_per_pallet
    st.session_state['area_max_volume'] = max_volume_percent
    st.session_state['area_sorting_percent'] = sorting_area_percent
    st.session_state['area_aisle_percent'] = aisle_percent
    st.session_state['area_cage_percent'] = cage_percent

    # ==================================================
    # TOTAL OPERATIONAL AREA (UPDATED FORMULA)
    # staging + sorting + HPT + ROC + supplies
    # + LEO MUFASA + cage + forklift + weighing + healthcare (if added)
    # ==================================================

    # Compute base calcs (additional areas = 0) to populate UI cards consistently
    calcs_base = calculate_area_requirements(
        total_packs=total_packs,
        packs_per_pallet=packs_per_pallet,
        max_volume_percent=max_volume_percent,
        sorting_area_percent=sorting_area_percent,
        cage_percent=cage_percent,
        aisle_percent=aisle_percent,
        additional_area_value=0
    )

    # Base Processing Areas
    staging_area = calcs_base.get('area_with_aisle', 0)
    sorting_area_val = calcs_base.get('sorting_area', 0)
    # Model-based Caging & Supplies
    _cs_info = get_caging_supplies_area(total_packs)
    cage_area_val = _cs_info['area']
    supplies_area_val = 0  # included in model-based caging & supplies

    # Also expose legacy variable names used elsewhere in the page
    area_required = calcs_base.get('area_required', 0)
    area_with_aisle = calcs_base.get('area_with_aisle', 0)
    sorting_area = calcs_base.get('sorting_area', 0)
    cage_area_required = _cs_info['area']
    supplies_area = 0
    total_operational_area = calcs_base.get('total_operational_area', 0)
    equipment_area = calcs_base.get('equipment_area', 0)

    # Fixed Equipment Areas
    HPT_AREA = 50
    ROC_AREA = 100

    # Predefined Equipment
    leo_mufasa_area = PREDEFINED_AREAS.get("LEO+ MUFASA", 0) or 0
    forklift_area = PREDEFINED_AREAS.get("FORKLIFT", 0) or 0
    weighing_area = PREDEFINED_AREAS.get("WEIGHING MACHINE", 0) or 0
    # VMEASURE default (from config if present, otherwise 30 sq.ft)
    vmeasure_default = AREA_CONSTANTS.get("Vmeasure_AREA", 30)

    # Healthcare & DG (if selected) - include only when user explicitly checks the corresponding checkbox
    healthcare_area_val = 0.0
    checkbox_key = f"add_healthcare_{loc_id}"
    if st.session_state.get(checkbox_key, False):
        if loc_id:
            healthcare_area_val = float(st.session_state.get(f'area_healthcare_{loc_id}', 0) or 0)
        else:
            healthcare_area_val = float(st.session_state.get('healthcare_area', 0) or 0)

    dg_area_val = 0.0
    dg_checkbox_key = f"add_dg_{loc_id}"
    if st.session_state.get(dg_checkbox_key, False):
        if loc_id:
            dg_area_val = float(st.session_state.get(f'area_dg_{loc_id}', 0) or 0)
        else:
            dg_area_val = float(st.session_state.get('dg_area', 0) or 0)

    # Total Operational Area as per required formula (base, additional will be applied later)
    final_total_operational = (
        staging_area +
        sorting_area_val +
        HPT_AREA +
        ROC_AREA +
        cage_area_val +
        leo_mufasa_area +
        forklift_area +
        weighing_area +
        healthcare_area_val
    )
    # ==================================================
    # OUTPUTS
    # ==================================================

    # Section header for Facility Summary (matching Area Calculations card style)
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
        border-left: 4px solid #4D148C;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1.5rem 0 1rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">📊 Operational Area Summary</div>
    </div>
    """, unsafe_allow_html=True)

    # Facility summary - show remaining metrics in one row (removed 'Pallets / Day' and 'Cage Area' per request)
    sum_col1, sum_col2, sum_col3 = st.columns(3)

    with sum_col1:
        st.metric("Palletized Area Required", f"{round(area_required, 0):,.0f}")

    with sum_col2:
        st.metric("Staging Area Required", f"{round(area_with_aisle, 0):,.0f}")

    with sum_col3:
        st.metric("Sorting Area Required", f"{round(sorting_area, 0):,.0f}")

    # ==================================================
    # EQUIPMENT OUTPUT CARDS (Compact - 5 in a row)
    # ==================================================
    
    # Section header for Equipment Output
    # Insert compact CSS to reduce card sizes and add horizontal spacing between cards
    st.markdown("""
    <style>
    /* Compact card defaults - reduced size */
    .hm-card{ margin:6px; padding:10px 12px !important; background:#FFFFFF; border:1px solid #E3E3E3; border-left:3px solid #FF6200; border-radius:12px; box-shadow:0 1px 6px rgba(0,0,0,0.04); box-sizing:border-box; display:block; transition: transform 0.18s ease, box-shadow 0.22s ease; }
    .hm-card:hover{ transform:translateY(-1px); box-shadow:0 4px 12px rgba(0,0,0,0.06); }
    .hm-card .hm-title{ font-size:11px !important; font-weight:700; color:#565656; text-transform:uppercase; letter-spacing:0.35px; }
    .hm-card .hm-value{ font-size:18px !important; font-weight:800; color:#333333; font-family: 'DM Sans', sans-serif; }
    .hm-card div[style*="font-size:20px"]{ font-size:18px !important; }

    /* Gradient highlight cards (orange / purple) follow the 'Total Station Area' reference */
    /* Header (first child) */
    div[style*="linear-gradient(135deg, #FF6200"] > div:first-child,
    div[style*="linear-gradient(135deg, #4D148C"] > div:first-child {
        color: #FFFFFF !important; font-size:11px !important; font-weight:700 !important; text-transform:uppercase !important; letter-spacing:1px !important; margin-bottom:6px !important; opacity:0.95;
    }
    /* Main numeric value (second child) */
    div[style*="linear-gradient(135deg, #FF6200"] > div:nth-child(2),
    div[style*="linear-gradient(135deg, #4D148C"] > div:nth-child(2) {
        font-size:28px !important; font-weight:800 !important; font-family: 'DM Sans', sans-serif !important; line-height:1 !important;
    }
    /* Unit text (third child) */
    div[style*="linear-gradient(135deg, #FF6200"] > div:nth-child(3),
    div[style*="linear-gradient(135deg, #4D148C"] > div:nth-child(3) {
        color: #F2F2F2 !important; font-size:12px !important; font-weight:500 !important; margin-top:6px !important;
    }

    /* Reduce padding and spacing for prominent highlight cards (orange/purple) */
    div[style*="linear-gradient(135deg, #FF6200"]{ padding:10px !important; margin:8px 0 !important; border-radius:16px !important; box-shadow:0 8px 28px rgba(255,98,0,0.2) !important; text-align:center; }
    div[style*="linear-gradient(135deg, #4D148C"]{ padding:10px 12px !important; margin:8px 0 !important; border-radius:16px !important; box-shadow:0 8px 28px rgba(77,20,140,0.2) !important; text-align:center; }

    /* Small white summary cards spacing */
    div[style*="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:8px;padding"]{ margin:8px !important; font-family: 'DM Sans', sans-serif; border-radius:14px !important; border-left:4px solid #FF6200 !important; }
    div[style*="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:8px;padding"] .hm-title{ font-size:11px !important; }
    div[style*="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:8px;padding"] .hm-value{ font-size:22px !important; }
    /* Make the expander header visually match the compact hm-card so the header looks like the card */
    /* Multiple selectors to cover Streamlit class name variations across versions */
    .streamlit-expanderHeader, .stExpanderHeader, .st-expanderHeader, .st-expander > div[role="button"], details > summary {
        background: #FFFFFF !important;
        border-left: 4px solid #FF6200 !important;
        border-radius: 12px !important;
        padding: 10px 12px !important;
        margin: 8px 0 !important;
        box-shadow: 0 1px 6px rgba(0,0,0,0.04) !important;
        cursor: pointer !important;
    }
    /* Improve header appearance when expanded */
    details[open] > summary, .streamlit-expanderHeader[aria-expanded="true"] {
        box-shadow: 0 8px 28px rgba(255,98,0,0.12) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Make the Equipment Area header itself the expander (styled via CSS above)
    with st.expander("⚙️ Equipment Area", expanded=False):

        # Equipment cards - two rows: first row (6 cols): Processing, VMEASURE, HPT, ROC, SUPPLIES, LEO+ MUFASA
        eq_r1_c1, eq_r1_c2, eq_r1_c3, eq_r1_c4, eq_r1_c5, eq_r1_c6 = st.columns(6)

        # Processing Area card: now shows staging (area_with_aisle) + sorting area
        processing_area_calc = ((area_with_aisle + sorting_area) if ('area_with_aisle' in locals() and 'sorting_area' in locals()) else 0)
        with eq_r1_c1:
            st.markdown(f"""
            <div class="hm-card">
                <div style="font-size:18px; margin-bottom:4px;">📐</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">PROCESSING AREA</div>
                <div class="hm-value" title="Staging area + Sorting area" style="color:#333333; font-weight:700;">{round(processing_area_calc,0):,.0f}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # VMEASURE card (predefined)
        with eq_r1_c2:
            st.markdown(f"""
            <div class="hm-card">
                <div style="font-size:16px; margin-bottom:4px;">📏</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">VMEASURE</div>
                <div class="hm-value" style="color:#333333; font-weight:700;">{int(vmeasure_default):,}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # HPT
        with eq_r1_c3:
            st.markdown(f"""
            <div class="hm-card">
                <div style="font-size:18px; margin-bottom:4px;">🔧</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">HPT</div>
                <div class="hm-value" style="color:#333333; font-weight:700;">{HPT_AREA}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # ROC
        with eq_r1_c4:
            st.markdown(f"""
            <div class="hm-card">
                <div style="font-size:18px; margin-bottom:4px;">📐</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">ROC AREA</div>
                <div class="hm-value" style="color:#333333; font-weight:700;">{ROC_AREA}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # CAGING & SUPPLIES (model-based)
        with eq_r1_c5:
            st.markdown(f"""
            <div class="hm-card">
                <div style="font-size:18px; margin-bottom:4px;">🧰</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">CAGING & SUPPLIES</div>
                <div class="hm-value" style="color:#333333; font-weight:700;">{cage_area_required:.0f}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft (Model {_cs_info['model']})</span></div>
            </div>
            """, unsafe_allow_html=True)

        # LEO+ MUFASA card taken from PREDEFINED_AREAS
        leo_default = PREDEFINED_AREAS.get("LEO+ MUFASA", 0) or 0
        with eq_r1_c6:
            st.markdown(f"""
            <div class="hm-card" style="background:#FFFFFF; border:1px solid #E3E3E3; padding:8px;">
                <div style="font-size:20px; margin-bottom:4px;">🧩</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">LEO+ MUFASA</div>
                <div class="hm-value" style="color:#333333; font-size:20px; font-weight:700;">{leo_default}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # Second row (4 cols): FORKLIFT, WEIGHING MACHINE, HEALTHCARE, DG
        eq_r2_c1, eq_r2_c2, eq_r2_c3, eq_r2_c4 = st.columns(4)

        # Forklift card (predefined area)
        forklift_default = PREDEFINED_AREAS.get("FORKLIFT", 0) or 0
        with eq_r2_c1:
            st.markdown(f"""
            <div class="hm-card" style="background:#FFFFFF; border:1px solid #E3E3E3; padding:8px;">
                <div style="font-size:20px; margin-bottom:4px;">🚜</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">FORKLIFT</div>
                <div class="hm-value" style="color:#333333; font-size:20px; font-weight:700;">{forklift_default}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # Weighing Machine card
        weighing_default = PREDEFINED_AREAS.get("WEIGHING MACHINE", 0) or 0
        with eq_r2_c2:
            st.markdown(f"""
            <div class="hm-card" style="background:#FFFFFF; border:1px solid #E3E3E3; padding:8px;">
                <div style="font-size:20px; margin-bottom:4px;">⚖️</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">WEIGHING MACHINE AREA</div>
                <div class="hm-value" style="color:#333333; font-size:20px; font-weight:700;">{weighing_default}<span style="font-size:10px; font-weight:500; color:#565656;"> sq.ft</span></div>
            </div>
            """, unsafe_allow_html=True)

        # Healthcare card (user-selectable; prompts immediate manual entry)
        healthcare_default = PREDEFINED_AREAS.get("HEALTHCARE", None)
        with eq_r2_c3:
            st.markdown(f"""
            <div class="hm-card" style="background:#FFFFFF; border:1px solid #E3E3E3;">
                <div style="font-size:20px; margin-bottom:4px;">🩺</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">HEALTHCARE</div>
            """, unsafe_allow_html=True)

            # selection control for healthcare - when selected show immediate manual input
            healthcare_selected = st.checkbox("Add Healthcare area", value=False, key=f"add_healthcare_{loc_id}")
            healthcare_area = 0
            if healthcare_selected:
                healthcare_area = st.number_input("Healthcare area (sq.ft)", min_value=1.0, value=100.0 if healthcare_default is None else float(healthcare_default), step=1.0, help="Enter the required sq.ft for healthcare area", key=f"healthcare_input_{loc_id}")
                # persist per-station healthcare into session state so it survives reruns and is available to Health Monitor
                if loc_id:
                    st.session_state[f'area_healthcare_{loc_id}'] = float(healthcare_area)
                else:
                    st.session_state['healthcare_area'] = float(healthcare_area)
                # show the entered value inside the card visually (small inline markdown)
                st.markdown(f"<div style='margin-top:6px; color:#333333; font-weight:700;'>{int(healthcare_area)} <span style='color:#565656; font-weight:500; font-size:12px;'>sq.ft</span></div>", unsafe_allow_html=True)
            else:
                # clear stored healthcare for this loc when unselected
                if loc_id and f'area_healthcare_{loc_id}' in st.session_state:
                    st.session_state[f'area_healthcare_{loc_id}'] = 0
                st.markdown("", unsafe_allow_html=True)

        # DG card (user-selectable; prompts immediate manual entry)
        dg_default = PREDEFINED_AREAS.get("DG", None)
        with eq_r2_c4:
            st.markdown(f"""
            <div class="hm-card" style="background:#FFFFFF; border:1px solid #E3E3E3;">
                <div style="font-size:20px; margin-bottom:4px;">🧪</div>
                <div class="hm-title" style="color:#565656; text-transform:uppercase; letter-spacing:0.3px;">DG</div>
            """, unsafe_allow_html=True)

            # selection control for DG - when selected show immediate manual input
            dg_selected = st.checkbox("Add DG area", value=False, key=f"add_dg_{loc_id}")
            dg_area = 0
            if dg_selected:
                dg_area = st.number_input("DG area (sq.ft)", min_value=1.0, value=100.0 if dg_default is None else float(dg_default), step=1.0, help="Enter the required sq.ft for DG area", key=f"dg_input_{loc_id}")
                # persist per-station DG into session state so it survives reruns and is available to Health Monitor
                if loc_id:
                    st.session_state[f'area_dg_{loc_id}'] = float(dg_area)
                else:
                    st.session_state['dg_area'] = float(dg_area)
                # show the entered value inside the card visually (small inline markdown)
                st.markdown(f"<div style='margin-top:6px; color:#333333; font-weight:700;'>{int(dg_area)} <span style='color:#565656; font-weight:500; font-size:12px;'>sq.ft</span></div>", unsafe_allow_html=True)
            else:
                # clear stored DG for this loc when unselected
                if loc_id and f'area_dg_{loc_id}' in st.session_state:
                    st.session_state[f'area_dg_{loc_id}'] = 0
                st.markdown("", unsafe_allow_html=True)

    # NOTE: Additional areas (user-added items + healthcare) are collected below in
    # `st.session_state.other_areas` and via the healthcare input. To avoid UI re-ordering
    # we first computed base `calcs` (with additional_area_value=0) above to render cards.
    # After the Additional Areas UI is rendered we will re-run calculations with the
    # real `additional_total` and use those final values for totals (avoids double-counting).

    # Third row - Final metric with highlight card
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #FF6200 0%, #E45528 100%);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(255, 98, 0, 0.25);
        text-align: center;
    ">
        <div style="color: #FFFFFF !important; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">
            ✅ Total Operational Area
        </div>
        <div style="color: #FFFFFF; font-size: 36px; font-weight: 800; font-family: 'DM Sans', sans-serif;">
            {round(total_operational_area + healthcare_area_val + dg_area_val, 0):,.0f} <span style="font-size: 16px; font-weight: 500; color: #FFFFFF !important;">sq.ft</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==================================================
    # ADDITIONAL AREA CALCULATIONS (PREDEFINED DROPDOWN)
    # ==================================================
    # Section header
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
        border-left: 4px solid #4D148C;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1.5rem 0 1rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">🧱 Additional Area Calculations</div>
    </div>
    """, unsafe_allow_html=True)

    # ---------- SESSION STATE INIT ----------
    if "other_areas" not in st.session_state:
        st.session_state.other_areas = []

    # ---------- PREDEFINED AREAS GRID (5 per row) ----------
    # Exclude certain small equipment areas from the Additional Areas grid
    # because they are shown in the Equipment Output section instead.
    items = [(n, a) for n, a in PREDEFINED_AREAS.items() if n not in ("LEO+ MUFASA", "WEIGHING MACHINE")]
    for i in range(0, len(items), 5):
        chunk = items[i:i+5]
        cols = st.columns(5)
        for col_idx, (name, area) in enumerate(chunk):
            col = cols[col_idx]
            # For Forklift, rename to CONFERENCE ROOM and make it manual/editable by default
            display_name = "CONFERENCE ROOM" if name == "FORKLIFT" else name
            display_area = "None" if name == "FORKLIFT" else (f"{area}" if area is not None else "None")
            with col:
                st.markdown(f"""
                <div style="
                    background: #FFFFFF;
                    border-radius: 8px;
                    padding: 12px;
                    margin-bottom: 8px;
                    border: 1px solid #E2E8F0;
                    text-align: center;
                ">
                    <div style="color: #1E293B; font-weight: 700; font-size: 13px; margin-bottom:6px;">{display_name}</div>
                    <div style="color: #FF6200; font-weight: 700; font-size: 16px;">{display_area} sq.ft</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("➕ Add", key=f"add_predef_{i}_{col_idx}", use_container_width=True, help=f"Add {display_name}"):
                    # If this is the Forklift (now CONFERENCE ROOM), always add as editable entry
                    if name == "FORKLIFT":
                        st.session_state.other_areas.append({
                            "Area Type": display_name,
                            "Area Size (sq.ft)": 0,
                            "editable": True
                        })
                    else:
                        # If the predefined area has no preset (None), add as editable with size 0
                        if area is None:
                            st.session_state.other_areas.append({
                                "Area Type": name,
                                "Area Size (sq.ft)": 0,
                                "editable": True
                            })
                        else:
                            st.session_state.other_areas.append({
                                "Area Type": name,
                                "Area Size (sq.ft)": area
                            })
                    st.rerun()
        # Fill remaining columns in the row (if any) with blanks to maintain layout
        if len(chunk) < 5:
            for j in range(len(chunk), 5):
                with cols[j]:
                    st.markdown("<div style='height:78px'></div>", unsafe_allow_html=True)

    # ---------- DISPLAY ADDED AREAS LIST ----------
    if st.session_state.other_areas:
        st.markdown("<h4 style='font-size: 18px; font-weight: 600; color: #334155; margin-top: 15px; margin-bottom: 10px;'>📋 Added Additional Areas</h4>", unsafe_allow_html=True)
        
        # Create a styled container for the areas list - LIGHT THEME
        st.markdown("""
        <style>
        .area-card-compact {
            background: #FFFFFF;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 4px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }
        .area-card-compact:hover {
            border-color: #FF6200;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display each area as a styled row
        for idx, area in enumerate(st.session_state.other_areas):
            col1, col2, col3 = st.columns([5, 3, 1])

            with col1:
                st.markdown(f"""
                <div class="area-card-compact">
                    <span style="color: #1E293B; font-weight: 600; font-size: 14px;">{area['Area Type']}</span>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                # If area size is zero/None or marked editable, allow the user to enter the area
                raw_size = area.get('Area Size (sq.ft)', None)
                current_size = raw_size if raw_size is not None else 0
                editable = area.get('editable', False) or (raw_size is None) or (current_size == 0)

                # Render input directly in col2 for consistent horizontal alignment
                # For CONFERENCE ROOM use a text input with placeholder so there's no visible value until user types
                if area.get('Area Type') == 'CONFERENCE ROOM':
                    # Show editable input only when the row is editable; otherwise show static value or spacer
                    if editable:
                        text_key = f"area_input_text_{idx}"
                        text_val = st.text_input("", value=(str(int(current_size)) if current_size else ""), placeholder="Enter area (sq.ft)", key=text_key)
                        try:
                            if text_val.strip() == "":
                                parsed = 0.0
                            else:
                                parsed = float(text_val)
                        except Exception:
                            parsed = 0.0
                        # Save back into session state
                        st.session_state.other_areas[idx]['Area Size (sq.ft)'] = float(parsed)
                        # Clear editable flag once a non-zero value is entered
                        if parsed > 0 and 'editable' in st.session_state.other_areas[idx]:
                            st.session_state.other_areas[idx].pop('editable', None)
                    else:
                        # If a value exists, render it like other areas; otherwise keep a spacer
                        if float(current_size) > 0:
                            st.markdown(f"<div style='padding-top:8px; font-weight:700; color:#FF6200;'>{current_size:,.0f} sq.ft</div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div style='height:36px'></div>", unsafe_allow_html=True)
                else:
                    if editable:
                        # Use a text input (no spinner controls) and parse to float
                        text_key = f"area_input_text_{idx}"
                        text_val = st.text_input("", value=(str(int(current_size)) if current_size else ""), placeholder="Enter area (sq.ft)", key=text_key)
                        try:
                            if text_val.strip() == "":
                                parsed = 0.0
                            else:
                                parsed = float(text_val)
                        except Exception:
                            parsed = 0.0
                        # Save back into session state
                        st.session_state.other_areas[idx]['Area Size (sq.ft)'] = float(parsed)
                        # Clear editable flag once a non-zero value is entered
                        if float(parsed) > 0:
                            st.session_state.other_areas[idx].pop('editable', None)
                    else:
                        # Render the value in the same compact area to match heights
                        st.markdown(f"<div style='padding-top:8px; font-weight:700; color:#FF6200;'>{current_size:,.0f} sq.ft</div>", unsafe_allow_html=True)

            with col3:
                if st.button("🗑️", key=f"remove_{idx}", help=f"Remove {area['Area Type']}"):
                    st.session_state.other_areas.pop(idx)
                    st.rerun()
        
        # Calculate and display total
        total_other_area = sum(area["Area Size (sq.ft)"] for area in st.session_state.other_areas)
        
        st.markdown("---")
        
        # Styled total card
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #FF6200 0%, #E45528 100%);
            border-radius: 8px;
            padding: 4px 8px;
            margin: 4px 0;
            box-shadow: 0 1px 3px rgba(255,98,0,0.10);
            border: none;
            max-width: 260px;
            display: inline-block;
        ">
            <div style="color: #FFFFFF; font-size: 9px; text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 1px; opacity: 0.92;">
                ✅ Total Additional Area
            </div>
            <div style="color: #ffffff; font-size: 14px; font-weight: 700;">
                {round(total_other_area, 0):,.0f} sq.ft
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        total_other_area = 0
        st.markdown("""
        <div style="
            background: var(--info-bg);
            border-left: 6px solid var(--fc-purple);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: var(--info-text);
        ">
            <div style="font-weight:700;">ℹ️ No additional areas added yet. Select an area from the above options to add.</div>
        </div>
        """, unsafe_allow_html=True)

    # ==================================================
    # FINAL FACILITY AREA SUMMARY
    # ==================================================

    # Section header
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #FAFAFA 0%, #FFFFFF 100%);
        border-left: 4px solid #4D148C;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1.5rem 0 1rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    ">
        <div style="font-weight:700;color:#333333;font-size:16px;">📐 Final Facility Area Summary</div>
    </div>
    """, unsafe_allow_html=True)

    summary_c1, summary_c2 = st.columns(2)

    # Recompute final totals including any additional areas added by the user
    additional_from_other = total_other_area if 'total_other_area' in locals() else 0.0
    # Include healthcare and DG in operational area only if user selected the corresponding checkbox
    healthcare_added = 0.0
    if st.session_state.get(f'add_healthcare_{loc_id}', False):
        healthcare_added = float(st.session_state.get(f'area_healthcare_{loc_id}', 0) or 0.0)
    dg_added = 0.0
    if st.session_state.get(f'add_dg_{loc_id}', False):
        dg_added = float(st.session_state.get(f'area_dg_{loc_id}', 0) or 0.0)
    # Healthcare should be counted as part of Total Operational Area (not Additional Area)
    additional_total = additional_from_other

    # Final recalculation for operational area: exclude non-healthcare additional areas
    # (additional areas should only appear in the 'Total Additional Area' card)
    final_calcs = calculate_area_requirements(
        total_packs=total_packs,
        packs_per_pallet=packs_per_pallet,
        max_volume_percent=max_volume_percent,
        sorting_area_percent=sorting_area_percent,
        cage_percent=cage_percent,
        aisle_percent=aisle_percent,
        additional_area_value=0
    )

    # Add healthcare and DG into the displayed Total Operational Area (but do not treat them as 'Additional Area')
    # Prefer the variables computed earlier in the UI (`healthcare_area_val`, `dg_area_val`) when present
    hc_val_for_total = healthcare_area_val if 'healthcare_area_val' in locals() else healthcare_added
    dg_val_for_total = dg_area_val if 'dg_area_val' in locals() else dg_added
    final_total_operational = final_calcs.get('total_operational_area', 0) + float(hc_val_for_total or 0) + float(dg_val_for_total or 0)
    final_total_equipment = final_calcs.get('equipment_area', 0)

    with summary_c1:
        st.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:8px;padding:10px 14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <div style="color:#565656;font-size:12px;font-weight:700;">🏭 Total Operational Area</div>
            <div style="color:#333333;font-size:20px;font-weight:800;margin-top:6px;">{round(final_total_operational, 0):,.0f} <span style="font-size:12px;font-weight:600;color:#565656;">sq.ft</span></div>
        </div>
        """, unsafe_allow_html=True)

    with summary_c2:
        st.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #E3E3E3;border-radius:8px;padding:10px 14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
            <div style="color:#565656;font-size:12px;font-weight:700;">🧱 Total Additional Area</div>
            <div style="color:#333333;font-size:20px;font-weight:800;margin-top:6px;">{round(additional_total, 0):,.0f} <span style="font-size:12px;font-weight:600;color:#565656;">sq.ft</span></div>
        </div>
        """, unsafe_allow_html=True)

    # Final total with prominent card (styled like FINAL AGENTS card)
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #4D148C 0%, #671CAA 100%);
        border-radius: 12px;
        padding: 0.6rem 0.9rem;
        margin: 0.75rem 0;
        box-shadow: 0 4px 10px rgba(77,20,140,0.16);
        text-align: center;
    ">
        <div style="color: #FFFFFF !important; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">
            Total Station Area
        </div>
        <div style="color: #FF7A18; font-size: 28px; font-weight: 700; font-family: 'DM Sans', sans-serif; text-shadow: 0 1px 4px rgba(0,0,0,0.08);">
            {round(final_total_operational + additional_total, 0):,.0f}
        </div>
        <div style="color: #E6E6FA; font-size: 11px; font-weight: 500; margin-top: 4px;">
            sq.ft
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ========== SYNC ADDITIONAL AREAS TO HEALTH MONITOR ==========
    # Persist station-specific healthcare and combined additional areas so Health Monitor reads the authoritative value

    if loc_id:
        st.session_state[f'area_healthcare_{loc_id}'] = float(healthcare_added)
        st.session_state[f'area_dg_{loc_id}'] = float(dg_added)

    # Persist only the non-healthcare additional area so Health Monitor shows healthcare as part of operational area
    if loc_id:
        st.session_state[f'area_additional_{loc_id}'] = float(additional_total)
        if additional_total > 0:
            st.success(f"✅ Additional area **{additional_total:,.0f} sq.ft** saved for station **{loc_id}**")


