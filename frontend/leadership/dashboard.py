# ============================================================
# AERO — Executive Dashboard (Leadership)
# 3 independent tabs: Station/Hub | Gateway | Services
# No emojis — professional enterprise format
# ============================================================
import streamlit as st
import pandas as pd
from aero.ui.header import render_header, render_footer
from aero.data.excel_store import read_report_sheet
from aero.data.hub_store import read_hub_report_sheet


render_header(
    "EXECUTIVE DASHBOARD",
    "Leadership analytics overview across all operational divisions",
    logo_height=80,
    badge="LEADERSHIP",
)


# ── Shared helpers ──────────────────────────────────────────────────────────
def _status_counts(df: pd.DataFrame) -> dict:
    if df.empty or "STATUS" not in df.columns:
        return {"Healthy": 0, "Review": 0, "Critical": 0, "total": 0}
    h, r, c = 0, 0, 0
    for val in df["STATUS"].astype(str):
        val_upper = val.upper()
        if "HEALTH" in val_upper or "✅" in val or "GREEN" in val_upper:
            h += 1
        elif "CRIT" in val_upper or "🚨" in val or "RED" in val_upper:
            c += 1
        else:
            r += 1
    return {"Healthy": h, "Review": r, "Critical": c, "total": h + r + c}


def _health_pct(sc: dict) -> float:
    return round(sc["Healthy"] / sc["total"] * 100, 1) if sc["total"] else 0.0


def _kpi_card(label: str, value: str, sublabel: str = "", color: str = "#4D148C"):
    sub_html = f'<div style="font-size:10px;color:#888;margin-top:2px;">{sublabel}</div>' if sublabel else ""
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#FFFFFF 0%,#F7F3FF 100%);
        border-left:5px solid {color};border-radius:10px;padding:14px 12px;
        box-shadow:0 2px 8px rgba(0,0,0,0.07);text-align:center;min-height:88px;
        display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:24px;font-weight:800;color:{color};letter-spacing:-0.5px;
            font-family:var(--font-head);">{value}</div>
        <div style="font-size:9px;color:#555;font-weight:700;letter-spacing:1px;
            text-transform:uppercase;margin-top:4px;">{label}</div>
        {sub_html}
    </div>""", unsafe_allow_html=True)


def _calculate_kpis(area_df: pd.DataFrame, res_df: pd.DataFrame, cour_df: pd.DataFrame) -> dict:
    if area_df.empty:
        return {
            "latest_date": None, "stations": 0, "volume": 0,
            "health_pct": 0, "healthy_count": 0, "critical": 0,
            "courier_dev": 0.0, "area_dev": 0.0
        }
    
    latest_date = area_df["DATE"].max()
    area_latest = area_df[area_df["DATE"] == latest_date]
    res_latest = res_df[res_df["DATE"] == latest_date] if not res_df.empty else pd.DataFrame()
    cour_latest = cour_df[cour_df["DATE"] == latest_date] if not cour_df.empty else pd.DataFrame()
    
    # 1. Total Volume
    total_vol = 0
    if not area_latest.empty:
        total_vol = pd.to_numeric(
            area_latest['VOLUME'].astype(str).str.replace(',', '', regex=False),
            errors='coerce'
        ).fillna(0).sum()
        
    # 2. Health & Alerts
    healthy_total = 0
    critical_total = 0
    locs = area_latest["LOC ID"].unique()
    for loc in locs:
        a_status = area_latest[area_latest["LOC ID"] == loc]["STATUS"].values[0] if loc in area_latest["LOC ID"].values else ""
        r_status = res_latest[res_latest["LOC ID"] == loc]["STATUS"].values[0] if not res_latest.empty and loc in res_latest["LOC ID"].values else ""
        c_status = cour_latest[cour_latest["LOC ID"] == loc]["STATUS"].values[0] if not cour_latest.empty and loc in cour_latest["LOC ID"].values else ""
        
        is_a_crit = "CRIT" in str(a_status).upper() or "🚨" in str(a_status)
        is_r_crit = "CRIT" in str(r_status).upper() or "🚨" in str(r_status)
        is_c_crit = "CRIT" in str(c_status).upper() or "🚨" in str(c_status)
        
        if is_a_crit: critical_total += 1
        if is_r_crit: critical_total += 1
        if is_c_crit: critical_total += 1
        
        is_a_h = "HEALTH" in str(a_status).upper() or "✅" in str(a_status)
        is_r_h = "HEALTH" in str(r_status).upper() or "✅" in str(r_status) or r_status == ""
        is_c_h = "HEALTH" in str(c_status).upper() or "✅" in str(c_status) or c_status == ""
        
        if is_a_h and is_r_h and is_c_h:
            healthy_total += 1
            
    n_stations = len(locs)
    health_pct = round(healthy_total / n_stations * 100) if n_stations else 0
    
    # 3. Deviations
    import re
    def _avg_dev(df_latest):
        if df_latest.empty or "STATUS" not in df_latest.columns:
            return 0.0
        deviations = []
        for s in df_latest["STATUS"].astype(str):
            m = re.search(r'([+-]?\d+\.?\d*)%', s)
            if m:
                deviations.append(float(m.group(1)))
        return round(sum(deviations) / len(deviations), 1) if deviations else 0.0
        
    area_dev = _avg_dev(area_latest)
    cour_dev = _avg_dev(cour_latest)
    
    return {
        "latest_date": latest_date,
        "stations": n_stations,
        "volume": total_vol,
        "health_pct": health_pct,
        "healthy_count": healthy_total,
        "critical": critical_total,
        "courier_dev": cour_dev,
        "area_dev": area_dev
    }


def _section_header(title: str, subtitle: str = "", color: str = "#4D148C"):
    sub_html = f'<div style="font-size:12px;color:#777;margin-top:3px;">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#FFFFFF 0%,#F3E8FF 100%);
        border-left:6px solid {color};border-radius:8px;padding:12px 18px;
        margin:18px 0 10px 0;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
        <div style="font-weight:800;color:#1A1A1A;font-size:15px;text-transform:uppercase;
            letter-spacing:0.4px;">{title}</div>
        {sub_html}
    </div>""", unsafe_allow_html=True)


def _status_bar(label: str, sc: dict, color: str):
    t = sc["total"]
    h_p = sc["Healthy"] / t * 100 if t else 0
    r_p = sc["Review"]  / t * 100 if t else 0
    c_p = sc["Critical"]/ t * 100 if t else 0
    st.markdown(f"""
    <div style="background:#FAFAFA;border-radius:8px;padding:10px 14px;margin:5px 0;
        border-left:4px solid {color};">
        <div style="font-size:11px;font-weight:700;color:#444;text-transform:uppercase;
            letter-spacing:0.5px;margin-bottom:6px;">{label}</div>
        <div style="display:flex;gap:16px;font-size:11px;font-weight:600;">
            <span style="color:#008A00;">&#9679; Healthy &nbsp;{sc['Healthy']} ({h_p:.0f}%)</span>
            <span style="color:#FF6200;">&#9679; Review &nbsp;{sc['Review']} ({r_p:.0f}%)</span>
            <span style="color:#DE002E;">&#9679; Critical &nbsp;{sc['Critical']} ({c_p:.0f}%)</span>
        </div>
    </div>""", unsafe_allow_html=True)


def _phase_card(metric_label: str, color: str):
    st.markdown(f"""
    <div style="background:#FAFAFA;border:1px solid #E3E3E3;border-radius:8px;
        padding:16px 12px;text-align:center;min-height:76px;">
        <div style="font-size:11px;font-weight:700;color:#555;text-transform:uppercase;
            letter-spacing:0.5px;margin-bottom:4px;">{metric_label}</div>
        <div style="font-size:24px;font-weight:800;color:{color};">—</div>
        <div style="font-size:10px;color:#AAA;margin-top:2px;">Pending Phase 2</div>
    </div>""", unsafe_allow_html=True)


def _phase_scope(title: str, items: list, bg: str, color: str):
    li = "".join(f"<li>{i}</li>" for i in items)
    st.markdown(f"""
    <div style="background:{bg};border-radius:8px;padding:1.4rem 1.6rem;
        line-height:1.75;color:#333;font-size:13px;">
        <div style="font-weight:700;color:{color};margin-bottom:8px;text-transform:uppercase;
            letter-spacing:0.5px;">{title}</div>
        <ul style="margin:0;padding-left:20px;color:#555;">{li}</ul>
    </div>""", unsafe_allow_html=True)


# ── Live fallback engines ───────────────────────────────────────────────────
from aero.data.excel_store import read_famis_uploads, read_master_data
from aero.data.hub_store import read_hub_uploads
from aero.core.area_calculator import calculate_area_requirements, calculate_area_status
from aero.core.resource_calculator import calculate_resource_requirements, calculate_resource_health_status
from aero.core.courier_calculator import calculate_courier_requirements, calculate_courier_health_status
from aero.config.settings import load_config, load_area_config

def _build_live_station_reports(famis_df: pd.DataFrame, master_df: pd.DataFrame):
    """Build live fallback DataFrames for Area, Resource, Courier, and Total reports."""
    if famis_df is None or famis_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    try:
        cfg = load_config()
        area_cfg = load_area_config()
    except Exception:
        cfg = {}
        area_cfg = {}

    area_rows = []
    res_rows = []
    cour_rows = []
    total_rows = []

    # Ensure Date column is normalized
    famis_df = famis_df.copy()
    famis_df["date"] = pd.to_datetime(famis_df["date"]).dt.normalize()

    # Pre-load config values
    area_constants = area_cfg.get("AREA_CONSTANTS", {})
    area_ppp = area_constants.get("PACKS_PER_PALLET", 15)
    area_mv = area_constants.get("MAX_VOLUME_PERCENT", 55.0)
    area_sp = area_constants.get("SORTING_AREA_PERCENT", 60.0)
    area_cp = area_constants.get("CAGE_PERCENT", 10.0)
    area_ap = area_constants.get("AISLE_PERCENT", 15.0)

    courier_cfg = cfg.get("COURIER", {})
    res_shift = float(courier_cfg.get("SHIFT_HOURS", 9.0))
    res_absent = 0.15
    res_roster = 0.11
    res_oncall = 80
    res_dex = 0.05
    res_csbiv = 0.80
    res_rod = 0.30

    cour_pk_st = float(courier_cfg.get("PK_ST_OR", 2.5))
    cour_st_hr = float(courier_cfg.get("ST_HR_OR", 4.0))
    cour_prod = float(courier_cfg.get("PRODUCTIVITY_HRS", 7.0))
    cour_absent = float(courier_cfg.get("ABSENTEEISM_PCT", 16.0))
    cour_train = float(courier_cfg.get("TRAINING_PCT", 11.0))
    cour_wdays = int(courier_cfg.get("WORKING_DAYS", 5))

    for _, row in famis_df.iterrows():
        loc = row.get("loc_id", "")
        if not loc:
            continue
        dt_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
        vol = int(row.get("pk_gross_tot", 0) or 0)
        ib = int(row.get("pk_gross_inb", 0) or 0)
        ob = int(row.get("pk_gross_outb", 0) or 0)
        roc_raw = int(row.get("pk_roc", 0) or 0)
        roc = int(roc_raw * 0.25)
        asp = roc_raw - roc

        # Find master row
        if master_df is not None and not master_df.empty and "loc_id" in master_df.columns:
            mrows = master_df[master_df["loc_id"] == loc]
            mrow = mrows.iloc[0] if not mrows.empty else pd.Series()
        else:
            mrow = pd.Series()

        # Resolve Region
        region = str(mrow.get("region", "")) if not mrow.empty and "region" in mrow.index else ""
        if not region or region.lower() in ("nan", "none", ""):
            loc_upper = loc.upper()
            if loc_upper.startswith("AMD") or loc_upper.startswith("BOM"):
                region = "Western Region"
            elif loc_upper.startswith("DEL"):
                region = "Northern Region"
            elif loc_upper.startswith("MAA") or loc_upper.startswith("BLR"):
                region = "Southern Region"
            elif loc_upper.startswith("CCU"):
                region = "Eastern Region"
            else:
                prefix = loc.split("-")[0] if "-" in loc else loc[:3]
                region = f"Operational Region {prefix}"

        ops_area = float(mrow.get("ops_area", 0) or 0) if not mrow.empty else 0.0
        m_agents = float(mrow.get("current_total_agents", mrow.get("current_total_osa", 0)) or 0) if not mrow.empty else 0.0
        m_couriers = int(mrow.get("current_total_couriers", mrow.get("couriers_available", 0)) or 0) if not mrow.empty else 0

        # Area Calcs
        calc_area = 0.0
        area_status = "UNKNOWN"
        area_dev = 0.0
        if vol > 0:
            try:
                ac = calculate_area_requirements(
                    total_packs=vol,
                    packs_per_pallet=area_ppp,
                    max_volume_percent=area_mv,
                    sorting_area_percent=area_sp,
                    cage_percent=area_cp,
                    aisle_percent=area_ap,
                )
                calc_area = ac.get("total_operational_area", 0)
                if ops_area > 0:
                    ast_ = calculate_area_status(calc_area, ops_area)
                    area_status = ast_.get("status", "UNKNOWN")
                    area_dev = ast_.get("deviation_percent", 0.0)
            except Exception:
                pass

        # Resource Calcs
        calc_agents = 0.0
        res_status = "UNKNOWN"
        res_dev = 0.0
        if vol > 0:
            try:
                rr = calculate_resource_requirements(
                    total_volume=vol, ib_volume=ib, ob_volume=ob,
                    roc_volume=roc, asp_volume=asp,
                    shift_hours=res_shift,
                    absenteeism_pct=res_absent, training_pct=0.0, roster_buffer_pct=res_roster,
                    on_call_pickup=res_oncall, dex_pct=res_dex, csbiv_pct=res_csbiv, rod_pct=res_rod,
                )
                calc_agents = rr.get("total_agents", 0)
                if m_agents > 0:
                    rs = calculate_resource_health_status(calc_agents, m_agents)
                    res_status = rs.get("status", "UNKNOWN")
                    res_dev = rs.get("deviation_percent", 0.0)
            except Exception:
                pass

        # Courier Calcs
        calc_couriers = 0.0
        cour_status = "UNKNOWN"
        cour_dev = 0.0
        if vol > 0:
            try:
                cr = calculate_courier_requirements(
                    total_packages=vol,
                    pk_st_or=cour_pk_st,
                    st_hr_or=cour_st_hr,
                    productivity_hrs=cour_prod,
                    couriers_available=m_couriers,
                    absenteeism_pct=cour_absent,
                    training_pct=cour_train,
                    working_days=cour_wdays,
                )
                calc_couriers = cr.get("total_required_with_training", 0)
                if m_couriers > 0:
                    cs = calculate_courier_health_status(calc_couriers, m_couriers)
                    cour_status = cs.get("status", "UNKNOWN")
                    cour_dev = cs.get("deviation_percent", 0.0)
            except Exception:
                pass

        a_lbl = "Healthy" if area_status == "HEALTHY" else ("Critical" if area_status == "CRITICAL" else "Review")
        r_lbl = "Healthy" if res_status == "HEALTHY" else ("Critical" if res_status == "CRITICAL" else "Review")
        c_lbl = "Healthy" if cour_status == "HEALTHY" else ("Critical" if cour_status == "CRITICAL" else "Review")
        
        area_emoji = "✅" if area_status == "HEALTHY" else ("🚨" if area_status == "CRITICAL" else ("⚠️" if area_status == "REVIEW_NEEDED" else "⚪"))
        res_emoji = "✅" if res_status == "HEALTHY" else ("🚨" if res_status == "CRITICAL" else ("⚠️" if res_status == "REVIEW_NEEDED" else "⚪"))
        cour_emoji = "✅" if cour_status == "HEALTHY" else ("🚨" if cour_status == "CRITICAL" else ("⚠️" if cour_status == "REVIEW_NEEDED" else "⚪"))

        area_rows.append({
            "DATE": dt_str,
            "LOC ID": loc,
            "REGION": region,
            "VOLUME": vol,
            "STATUS": f"{area_emoji} {a_lbl} {area_dev:+.1f}%"
        })
        res_rows.append({
            "DATE": dt_str,
            "LOC ID": loc,
            "REGION": region,
            "VOLUME": vol,
            "STATUS": f"{res_emoji} {r_lbl} {res_dev:+.1f}%"
        })
        cour_rows.append({
            "DATE": dt_str,
            "LOC ID": loc,
            "REGION": region,
            "VOLUME": vol,
            "STATUS": f"{cour_emoji} {c_lbl} {cour_dev:+.1f}%"
        })
        total_rows.append({
            "DATE": dt_str,
            "LOC ID": loc,
            "REGION": region,
            "VOLUME": vol,
            "AREA STATUS": f"{area_emoji} {a_lbl} {area_dev:+.1f}%",
            "RESOURCE STATUS": f"{res_emoji} {r_lbl} {res_dev:+.1f}%",
            "COURIER STATUS": f"{cour_emoji} {c_lbl} {cour_dev:+.1f}%",
        })

    return pd.DataFrame(area_rows), pd.DataFrame(res_rows), pd.DataFrame(cour_rows), pd.DataFrame(total_rows)

def _build_live_hub_reports(hub_famis_df: pd.DataFrame, hub_master_df: pd.DataFrame):
    """Build live fallback DataFrames for Hub Area, Resource, Courier, and Total reports."""
    if hub_famis_df is None or hub_famis_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    area_rows = []
    res_rows = []
    cour_rows = []
    total_rows = []

    # Ensure Date column is normalized
    hub_famis_df = hub_famis_df.copy()
    hub_famis_df["date"] = pd.to_datetime(hub_famis_df["date"]).dt.normalize()

    # Pre-load Hub config parameters / defaults
    area_packs_per_pallet = 15
    area_max_volume = 55.0
    area_sorting_percent = 60.0
    area_aisle_percent = 15.0
    area_cage_percent = 10.0

    SHIFT_HOURS = 9.0
    ABSENTEEISM_PCT = 11.0 / 100.0
    ROSTER_BUFFER_PCT = 11.0 / 100.0
    ON_CALL_PICKUP = 80

    pk_st_or = 1.5
    st_hr_or = 8.0
    productivity_hrs = 7.0
    absenteeism_pct = 16.0
    training_pct = 11.0
    working_days = 5

    for _, row in hub_famis_df.iterrows():
        loc_id = row.get("loc_id", "")
        if not loc_id:
            continue
        dt_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
        total_packs = int(row.get("pk_gross_tot", 0) or 0)
        ib_vol = int(row.get("pk_gross_inb", 0) or 0)
        ob_vol = int(row.get("pk_gross_outb", 0) or 0)
        roc_f = int(row.get("pk_roc", 0) or 0)
        roc_vol = int(roc_f * 0.25)
        asp_vol = roc_f - roc_vol

        # Find master row
        if hub_master_df is not None and not hub_master_df.empty and "loc_id" in hub_master_df.columns:
            mrows = hub_master_df[hub_master_df["loc_id"] == loc_id]
            mrow = mrows.iloc[0] if not mrows.empty else pd.Series()
        else:
            mrow = pd.Series()

        # Extract ops_area safely
        ops_area = 0.0
        if not mrow.empty and 'ops_area' in mrow.columns:
            try:
                ops_area = float(mrow['ops_area'])
            except Exception:
                pass

        # Extract master_agents safely
        master_agents = 0.0
        if not mrow.empty:
            for _col in ['current_total_agents', 'current_total_osa']:
                if _col in mrow.columns:
                    try:
                        master_agents = float(mrow[_col])
                        break
                    except Exception:
                        pass

        # Extract couriers_available safely
        couriers_available = 0
        if not mrow.empty:
            for col in ['current_total_couriers', 'couriers_available', 'existing_couriers']:
                if col in mrow.columns:
                    try:
                        couriers_available = int(mrow[col])
                        break
                    except Exception:
                        pass

        # Hub Area Calcs
        calc_area = 0.0
        area_status = "UNKNOWN"
        area_dev = 0.0
        if total_packs > 0:
            try:
                calcs = calculate_area_requirements(
                    total_packs=total_packs,
                    packs_per_pallet=area_packs_per_pallet,
                    max_volume_percent=area_max_volume,
                    sorting_area_percent=area_sorting_percent,
                    cage_percent=area_cage_percent,
                    aisle_percent=area_aisle_percent,
                )
                calc_area = calcs.get("total_operational_area", 0.0)
                if ops_area > 0:
                    ast_ = calculate_area_status(calc_area, ops_area)
                    area_status = ast_.get("status", "UNKNOWN")
                    area_dev = ast_.get("deviation_percent", 0.0)
            except Exception:
                pass

        # Hub Resource Calcs
        calc_agents = 0.0
        res_status = "UNKNOWN"
        res_dev = 0.0
        if total_packs > 0:
            try:
                reqs = calculate_resource_requirements(
                    total_volume=total_packs, ib_volume=ib_vol, ob_volume=ob_vol,
                    roc_volume=roc_vol, asp_volume=asp_vol,
                    shift_hours=SHIFT_HOURS, absenteeism_pct=ABSENTEEISM_PCT,
                    training_pct=0.0, roster_buffer_pct=ROSTER_BUFFER_PCT,
                    on_call_pickup=ON_CALL_PICKUP, dex_pct=0.05, csbiv_pct=0.80, rod_pct=0.30
                )
                calc_agents = reqs.get('total_agents', 0.0)
                if master_agents > 0:
                    rs = calculate_resource_health_status(calc_agents, master_agents)
                    res_status = rs.get("status", "UNKNOWN")
                    res_dev = rs.get("deviation_percent", 0.0)
            except Exception:
                pass

        # Hub Courier Calcs
        calc_couriers = 0.0
        cour_status = "UNKNOWN"
        cour_dev = 0.0
        if total_packs > 0:
            try:
                cour_reqs = calculate_courier_requirements(
                    total_packages=total_packs,
                    pk_st_or=pk_st_or,
                    st_hr_or=st_hr_or,
                    productivity_hrs=productivity_hrs,
                    couriers_available=couriers_available,
                    absenteeism_pct=absenteeism_pct,
                    training_pct=training_pct,
                    working_days=working_days,
                )
                calc_couriers = cour_reqs.get('total_required_with_training', 0.0)
                if couriers_available > 0:
                    cs = calculate_courier_health_status(calc_couriers, couriers_available)
                    cour_status = cs.get("status", "UNKNOWN")
                    cour_dev = cs.get("deviation_percent", 0.0)
            except Exception:
                pass

        a_lbl = "Healthy" if area_status == "HEALTHY" else ("Critical" if area_status == "CRITICAL" else "Review")
        r_lbl = "Healthy" if res_status == "HEALTHY" else ("Critical" if res_status == "CRITICAL" else "Review")
        c_lbl = "Healthy" if cour_status == "HEALTHY" else ("Critical" if cour_status == "CRITICAL" else "Review")
        
        area_emoji = "✅" if area_status == "HEALTHY" else ("🚨" if area_status == "CRITICAL" else ("⚠️" if area_status == "REVIEW_NEEDED" else "⚪"))
        res_emoji = "✅" if res_status == "HEALTHY" else ("🚨" if res_status == "CRITICAL" else ("⚠️" if res_status == "REVIEW_NEEDED" else "⚪"))
        cour_emoji = "✅" if cour_status == "HEALTHY" else ("🚨" if cour_status == "CRITICAL" else ("⚠️" if cour_status == "REVIEW_NEEDED" else "⚪"))

        area_rows.append({
            "DATE": dt_str,
            "LOC ID": loc_id,
            "VOLUME": total_packs,
            "STATUS": f"{area_emoji} {a_lbl} {area_dev:+.1f}%"
        })
        res_rows.append({
            "DATE": dt_str,
            "LOC ID": loc_id,
            "VOLUME": total_packs,
            "STATUS": f"{res_emoji} {r_lbl} {res_dev:+.1f}%"
        })
        cour_rows.append({
            "DATE": dt_str,
            "LOC ID": loc_id,
            "VOLUME": total_packs,
            "STATUS": f"{cour_emoji} {c_lbl} {cour_dev:+.1f}%"
        })
        total_rows.append({
            "DATE": dt_str,
            "LOC ID": loc_id,
            "VOLUME": total_packs,
            "AREA STATUS": f"{area_emoji} {a_lbl} {area_dev:+.1f}%",
            "RESOURCE STATUS": f"{res_emoji} {r_lbl} {res_dev:+.1f}%",
            "COURIER STATUS": f"{cour_emoji} {c_lbl} {cour_dev:+.1f}%",
        })

    return pd.DataFrame(area_rows), pd.DataFrame(res_rows), pd.DataFrame(cour_rows), pd.DataFrame(total_rows)

def _ensure_region_column(df: pd.DataFrame, master_df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the DataFrame has a REGION column by looking up or mapping location IDs."""
    if df.empty:
        return df
    df = df.copy()
    if "REGION" in df.columns:
        return df

    regions = []
    for loc in df["LOC ID"].astype(str):
        region = ""
        if master_df is not None and not master_df.empty and "loc_id" in master_df.columns:
            mrows = master_df[master_df["loc_id"] == loc]
            if not mrows.empty:
                mrow = mrows.iloc[0]
                region = str(mrow.get("region", "")) if "region" in mrow.index else ""

        if not region or region.lower() in ("nan", "none", ""):
            loc_upper = loc.upper()
            if loc_upper.startswith("AMD") or loc_upper.startswith("BOM"):
                region = "Western Region"
            elif loc_upper.startswith("DEL"):
                region = "Northern Region"
            elif loc_upper.startswith("MAA") or loc_upper.startswith("BLR"):
                region = "Southern Region"
            elif loc_upper.startswith("CCU"):
                region = "Eastern Region"
            else:
                prefix = loc.split("-")[0] if "-" in loc else loc[:3]
                region = f"Operational Region {prefix}"
        regions.append(region)

    df["REGION"] = regions
    return df

def _render_region_analysis(area_df: pd.DataFrame, res_df: pd.DataFrame, cour_df: pd.DataFrame):
    """Render a premium region-wise analysis and operational rollup for Station division."""
    if area_df.empty:
        st.info("No data available for Region-Wise Analysis.")
        return

    # Filter to latest date
    latest_date = area_df["DATE"].max()
    area_latest = area_df[area_df["DATE"] == latest_date]
    res_latest = res_df[res_df["DATE"] == latest_date] if not res_df.empty else pd.DataFrame()
    cour_latest = cour_df[cour_df["DATE"] == latest_date] if not cour_df.empty else pd.DataFrame()

    region_records = []

    # Group by region
    import re
    regions = sorted(area_latest["REGION"].unique())

    for reg in regions:
        reg_area = area_latest[area_latest["REGION"] == reg]
        reg_res = res_latest[res_latest["LOC ID"].isin(reg_area["LOC ID"])] if not res_latest.empty else pd.DataFrame()
        reg_cour = cour_latest[cour_latest["LOC ID"].isin(reg_area["LOC ID"])] if not cour_latest.empty else pd.DataFrame()

        total_vol = 0
        healthy_count = 0
        critical_alerts = 0
        courier_devs = []
        area_devs = []

        for loc in reg_area["LOC ID"].unique():
            # Volume
            vol_val = reg_area[reg_area["LOC ID"] == loc]["VOLUME"].values[0]
            try:
                vol_num = int(str(vol_val).replace(",", ""))
            except Exception:
                vol_num = 0
            total_vol += vol_num

            # Statuses
            a_status = reg_area[reg_area["LOC ID"] == loc]["STATUS"].values[0] if loc in reg_area["LOC ID"].values else ""
            r_status = reg_res[reg_res["LOC ID"] == loc]["STATUS"].values[0] if not reg_res.empty and loc in reg_res["LOC ID"].values else ""
            c_status = reg_cour[reg_cour["LOC ID"] == loc]["STATUS"].values[0] if not reg_cour.empty and loc in reg_cour["LOC ID"].values else ""

            is_a_crit = "CRIT" in str(a_status).upper() or "🚨" in str(a_status)
            is_r_crit = "CRIT" in str(r_status).upper() or "🚨" in str(r_status)
            is_c_crit = "CRIT" in str(c_status).upper() or "🚨" in str(c_status)

            if is_a_crit: critical_alerts += 1
            if is_r_crit: critical_alerts += 1
            if is_c_crit: critical_alerts += 1

            is_a_h = "HEALTH" in str(a_status).upper() or "✅" in str(a_status)
            is_r_h = "HEALTH" in str(r_status).upper() or "✅" in str(r_status) or r_status == ""
            is_c_h = "HEALTH" in str(c_status).upper() or "✅" in str(c_status) or c_status == ""

            if is_a_h and is_r_h and is_c_h:
                healthy_count += 1

            # Deviations
            def _get_dev(s):
                m = re.search(r'([+-]?\d+\.?\d*)%', str(s))
                return float(m.group(1)) if m else None

            a_dev_val = _get_dev(a_status)
            if a_dev_val is not None:
                area_devs.append(a_dev_val)

            c_dev_val = _get_dev(c_status)
            if c_dev_val is not None:
                courier_devs.append(c_dev_val)

        n_stations = len(reg_area["LOC ID"].unique())
        health_pct = round(healthy_count / n_stations * 100) if n_stations else 0
        avg_area_dev = round(sum(area_devs) / len(area_devs), 1) if area_devs else 0.0
        avg_cour_dev = round(sum(courier_devs) / len(courier_devs), 1) if courier_devs else 0.0

        region_records.append({
            "Region": reg,
            "Active Stations": n_stations,
            "Total Volume": total_vol,
            "Network Health": health_pct,
            "Avg Courier Dev": avg_cour_dev,
            "Avg Area Dev": avg_area_dev,
            "Critical Alerts": critical_alerts,
        })

    reg_df = pd.DataFrame(region_records)
    
    st.dataframe(
        reg_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Region": st.column_config.TextColumn("Operational Region", width="medium", help="Active logistics regions"),
            "Active Stations": st.column_config.NumberColumn("Stations", help="Count of active station facilities"),
            "Total Volume": st.column_config.NumberColumn("Total Volume", format="%d", help="Total outbound & inbound packages"),
            "Network Health": st.column_config.ProgressColumn("Network Health %", min_value=0, max_value=100, format="%d%%", help="Fully healthy stations percentage"),
            "Avg Courier Dev": st.column_config.NumberColumn("Avg Courier Dev %", format="%+1.1f%%", help="Calculated courier efficiency deviation"),
            "Avg Area Dev": st.column_config.NumberColumn("Avg Area Dev %", format="%+1.1f%%", help="Calculated facility area utilization deviation"),
            "Critical Alerts": st.column_config.NumberColumn("Alerts 🚨", help="Active high-priority critical alerts across all domains")
        }
    )

# ── Load all report data ─────────────────────────────────────────────────────
st_area  = read_report_sheet("AREA HEALTH SUMMARY")
st_res   = read_report_sheet("RESOURCE HEALTH SUMMARY")
st_cour  = read_report_sheet("COURIER HEALTH SUMMARY")
st_total = read_report_sheet("TOTAL SUMMARY")
hub_area  = read_hub_report_sheet("AREA HEALTH SUMMARY")
hub_res   = read_hub_report_sheet("RESOURCE HEALTH SUMMARY")
hub_cour  = read_hub_report_sheet("COURIER HEALTH SUMMARY")
hub_total = read_hub_report_sheet("TOTAL SUMMARY")

# Dynamically fall back to live FAMIS uploads and Master Data if published reports are empty
if st_area.empty or st_res.empty or st_cour.empty:
    _famis_df = read_famis_uploads()
    _master_df = read_master_data()
    if not _famis_df.empty:
        st_area, st_res, st_cour, st_total = _build_live_station_reports(_famis_df, _master_df)

# Dynamically fall back to live Hub uploads if published reports are empty
if hub_area.empty or hub_res.empty or hub_cour.empty:
    _hub_famis = read_hub_uploads()
    _hub_master = st.session_state.get("hub_master_data") or st.session_state.get("hub_health_master_data")
    if not _hub_famis.empty:
        hub_area, hub_res, hub_cour, hub_total = _build_live_hub_reports(_hub_famis, _hub_master)

# ── Split Station and Hub Tabs ───────────────────────────────────────────────
tab_st, tab_hub = st.tabs([
    "   STATION   ",
    "   HUB   ",
])

# ============================================================
# TAB 1 — STATION
# ============================================================
with tab_st:
    st_area_sc  = _status_counts(st_area)
    st_res_sc   = _status_counts(st_res)
    st_cour_sc  = _status_counts(st_cour)

    # Calculate KPIs for Station
    st_kpis = _calculate_kpis(st_area, st_res, st_cour)
    if st_kpis["latest_date"]:
        # Banner or subheader
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#4D148C 0%,#3a0f6e 100%);
            border-radius:10px;padding:12px 18px;margin-bottom:16px;
            box-shadow:0 3px 10px rgba(77,20,140,0.15);">
            <div style="color:rgba(255,255,255,0.75);font-size:10px;font-weight:700;
                text-transform:uppercase;letter-spacing:1px;">
                FedEx Station Operations Summary
            </div>
            <div style="color:#FFFFFF;font-size:16px;font-weight:800;margin-top:2px;">
                Network Health Intelligence — Station Division
            </div>
        </div>""", unsafe_allow_html=True)

        # 6 KPI cards
        kc = st.columns(6)
        with kc[0]:
            _kpi_card("Stations", str(st_kpis["stations"]), "Active stations", color="#4D148C")
        with kc[1]:
            _kpi_card("Total Volume", f"{st_kpis['volume']:,}", f"As of {st_kpis['latest_date']}", color="#4D148C")
        with kc[2]:
            net_pct = st_kpis["health_pct"]
            _kpi_card("Network Health", f"{net_pct}%", f"{st_kpis['healthy_count']}/{st_kpis['stations']} healthy", color="#008A00" if net_pct >= 70 else ("#FFB800" if net_pct >= 40 else "#DE002E"))
        with kc[3]:
            crit = st_kpis["critical"]
            _kpi_card("Critical Alerts", str(crit), "across all domains", color="#DE002E" if crit > 0 else "#008A00")
        with kc[4]:
            _kpi_card("Avg Courier Dev.", f"{st_kpis['courier_dev']:+.1f}%", "required vs actual", color="#008A00" if st_kpis['courier_dev'] >= 0 else "#DE002E")
        with kc[5]:
            _kpi_card("Avg Area Dev.", f"{st_kpis['area_dev']:+.1f}%", "calculated vs actual", color="#008A00" if st_kpis['area_dev'] >= 0 else "#DE002E")
            
        st.markdown("<br>", unsafe_allow_html=True)

    if st_area.empty and st_res.empty and st_cour.empty:
        st.info(
            "No published Station health reports found. Facility teams must publish "
            "reports from their respective Health Monitor tabs before data appears here."
        )
    else:
        # Critical Station Locations
        if not st_area.empty and "STATUS" in st_area.columns and "LOC ID" in st_area.columns:
            crit = st_area[st_area["STATUS"] == "Critical"]
            if not crit.empty:
                st.markdown("---")
                with st.expander(
                    "CRITICAL STATION LOCATIONS — Immediate Attention Required",
                    expanded=True,
                ):
                    show = ["LOC ID", "DATE", "STATUS"] + [
                        c for c in crit.columns if c not in ("LOC ID", "DATE", "STATUS")
                    ]
                    st.dataframe(crit[show[:8]].reset_index(drop=True), use_container_width=True)

# ============================================================
# TAB 2 — HUB
# ============================================================
with tab_hub:
    hub_area_sc = _status_counts(hub_area)
    hub_res_sc  = _status_counts(hub_res)
    hub_cour_sc = _status_counts(hub_cour)

    # Calculate KPIs for Hub
    hub_kpis = _calculate_kpis(hub_area, hub_res, hub_cour)
    if hub_kpis["latest_date"]:
        # Banner or subheader
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#FF6200 0%,#d35400 100%);
            border-radius:10px;padding:12px 18px;margin-bottom:16px;
            box-shadow:0 3px 10px rgba(255,98,0,0.15);">
            <div style="color:rgba(255,255,255,0.75);font-size:10px;font-weight:700;
                text-transform:uppercase;letter-spacing:1px;">
                FedEx Hub Operations Summary
            </div>
            <div style="color:#FFFFFF;font-size:16px;font-weight:800;margin-top:2px;">
                Network Health Intelligence — Hub Division
            </div>
        </div>""", unsafe_allow_html=True)

        # 6 KPI cards
        kc = st.columns(6)
        with kc[0]:
            _kpi_card("Hubs", str(hub_kpis["stations"]), "Active hubs", color="#FF6200")
        with kc[1]:
            _kpi_card("Total Volume", f"{hub_kpis['volume']:,}", f"As of {hub_kpis['latest_date']}", color="#FF6200")
        with kc[2]:
            net_pct = hub_kpis["health_pct"]
            _kpi_card("Network Health", f"{net_pct}%", f"{hub_kpis['healthy_count']}/{hub_kpis['stations']} healthy", color="#008A00" if net_pct >= 70 else ("#FFB800" if net_pct >= 40 else "#DE002E"))
        with kc[3]:
            crit = hub_kpis["critical"]
            _kpi_card("Critical Alerts", str(crit), "across all domains", color="#DE002E" if crit > 0 else "#008A00")
        with kc[4]:
            _kpi_card("Avg Courier Dev.", f"{hub_kpis['courier_dev']:+.1f}%", "required vs actual", color="#008A00" if hub_kpis['courier_dev'] >= 0 else "#DE002E")
        with kc[5]:
            _kpi_card("Avg Area Dev.", f"{hub_kpis['area_dev']:+.1f}%", "calculated vs actual", color="#008A00" if hub_kpis['area_dev'] >= 0 else "#DE002E")
            
        st.markdown("<br>", unsafe_allow_html=True)

    _section_header("Health Status Distribution — Hub", "Breakdown by monitoring category — Area, Resource, Courier")
    if hub_area.empty and hub_res.empty and hub_cour.empty:
        st.info(
            "No published Hub health reports found. Hub teams must publish "
            "reports from their respective Hub Health Monitor tabs before data appears here."
        )
    else:
        _status_bar("Area Health", hub_area_sc, "#4D148C")
        _status_bar("Resource Health", hub_res_sc, "#FF6200")
        _status_bar("Courier Health", hub_cour_sc, "#DE002E")

        # Volume Trend
        if not hub_total.empty and "DATE" in hub_total.columns:
            vol_col = next(
                (c for c in hub_total.columns
                 if any(k in c.lower() for k in ("volume", "gross", "packs"))), None
            )
            if vol_col:
                st.markdown("---")
                _section_header("Volume Trend — Hub", "Hub package volume over time")
                trend = hub_total.groupby("DATE")[vol_col].sum().reset_index()
                trend.sort_values("DATE", inplace=True)
                st.line_chart(trend.set_index("DATE")[vol_col])

        # Critical Hub Locations
        if not hub_area.empty and "STATUS" in hub_area.columns and "LOC ID" in hub_area.columns:
            crit = hub_area[hub_area["STATUS"] == "Critical"]
            if not crit.empty:
                st.markdown("---")
                with st.expander(
                    "CRITICAL HUB LOCATIONS — Immediate Attention Required",
                    expanded=True,
                ):
                    show = ["LOC ID", "DATE", "STATUS"] + [
                        c for c in crit.columns if c not in ("LOC ID", "DATE", "STATUS")
                    ]
                    st.dataframe(crit[show[:8]].reset_index(drop=True), use_container_width=True)








render_footer("LEADERSHIP")

