# ============================================================
# AERO — Station Analytics  [frontend/field/analytics.py]
# Region-level (South / West / North) health overview,
# station status grid, historical drill-down, and inline
# System Configuration for Field Engineers.
# ============================================================
from __future__ import annotations

import os
import sys
import logging
from datetime import timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.ui.components import render_info_banner, render_kpi_card, _PURPLE, _ORANGE, _GREEN, _RED
from aero.config.settings import load_config, save_config, load_area_config, save_area_config
from aero.core.area_calculator import calculate_area_requirements, calculate_area_status
from aero.core.resource_calculator import (
    calculate_resource_requirements, calculate_resource_health_status,
)
from aero.core.courier_calculator import (
    calculate_courier_requirements, calculate_courier_health_status,
)
from aero.region.mapper import classify_dataframe, region_order, region_color

logger = logging.getLogger(__name__)

# ── Brand / status palette ────────────────────────────────────────────────────
_STATUS_COLORS = {
    "HEALTHY":       "#008A00",
    "REVIEW_NEEDED": "#FFB800",
    "CRITICAL":      "#DE002E",
    "UNKNOWN":       "#888888",
    "NO DATA":       "#CCCCCC",
}


# ── Data loaders ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _load_famis_cached() -> pd.DataFrame:
    """Load FAMIS from DB first, then Excel store."""
    try:
        from aero.data.famis_store import db_available, load_famis_from_db, famis_row_count  # type: ignore
        if db_available() and famis_row_count() > 0:
            return load_famis_from_db()
    except Exception:
        pass
    try:
        from aero.data.excel_store import read_famis_uploads
        return read_famis_uploads()
    except Exception:
        return pd.DataFrame()


def _get_famis() -> pd.DataFrame:
    df = st.session_state.get("famis_data")
    if df is not None and not df.empty:
        return df
    df = _load_famis_cached()
    if not df.empty:
        st.session_state["famis_data"] = df
        st.session_state["famis_df"]   = df
    return df


def _get_master() -> pd.DataFrame:
    return st.session_state.get("master_data", pd.DataFrame())


# ── Per-row health computation ────────────────────────────────────────────────
def _compute_status_row(row: pd.Series, master_row: pd.Series,
                         cfg: dict, area_cfg: dict) -> dict:
    vol     = int(row.get("pk_gross_tot", 0) or 0)
    ib      = int(row.get("pk_gross_inb",  0) or 0)
    ob      = int(row.get("pk_gross_outb", 0) or 0)
    roc_raw = int(row.get("pk_roc", 0) or 0)
    roc     = int(roc_raw * 0.25)
    asp     = roc_raw - roc

    mr_empty = master_row is None or (hasattr(master_row, "empty") and master_row.empty)
    ops_area   = float(master_row.get("ops_area", 0) or 0)  if not mr_empty else 0.0
    m_agents   = float(master_row.get("current_total_agents",
                        master_row.get("current_total_osa", 0)) or 0) if not mr_empty else 0.0
    m_couriers = int(master_row.get("current_total_couriers",
                      master_row.get("couriers_available", 0)) or 0) if not mr_empty else 0

    result = {
        "loc_id": row["loc_id"], "date": row["date"], "pk_gross_tot": vol,
        "area_status": "UNKNOWN", "resource_status": "UNKNOWN", "courier_status": "UNKNOWN",
        "calc_area": 0.0, "calc_agents": 0.0, "calc_couriers": 0.0,
        "master_ops_area": ops_area, "master_agents": m_agents, "master_couriers": m_couriers,
    }
    if vol == 0:
        return result

    area_constants = area_cfg.get("AREA_CONSTANTS", area_cfg)
    try:
        ac = calculate_area_requirements(
            total_packs=vol,
            packs_per_pallet=area_constants.get("PACKS_PER_PALLET", 15),
            max_volume_percent=area_constants.get("MAX_VOLUME_PERCENT", 55.0),
            sorting_area_percent=area_constants.get("SORTING_AREA_PERCENT", 60.0),
            cage_percent=area_constants.get("CAGE_PERCENT", 10.0),
            aisle_percent=area_constants.get("AISLE_PERCENT", 15.0),
        )
        calc_area = ac.get("total_operational_area", 0)
        result["calc_area"] = calc_area
        if ops_area > 0:
            result["area_status"] = calculate_area_status(calc_area, ops_area).get("status", "UNKNOWN")
    except Exception:
        pass

    try:
        rr = calculate_resource_requirements(
            total_volume=vol, ib_volume=ib, ob_volume=ob,
            roc_volume=roc, asp_volume=asp,
            shift_hours=cfg.get("COURIER", {}).get("SHIFT_HOURS", 9.0),
            absenteeism_pct=0.15, training_pct=0.0, roster_buffer_pct=0.11,
            on_call_pickup=80, dex_pct=0.05, csbiv_pct=0.80, rod_pct=0.30,
        )
        calc_agents = rr.get("total_agents", 0)
        result["calc_agents"] = calc_agents
        result["resource_status"] = calculate_resource_health_status(calc_agents, m_agents).get("status", "UNKNOWN")
    except Exception:
        pass

    try:
        ccfg = cfg.get("COURIER", {})
        cr = calculate_courier_requirements(
            total_packages=vol,
            pk_st_or=float(ccfg.get("PK_ST_OR", 1.5)),
            st_hr_or=float(ccfg.get("ST_HR_OR", 8.0)),
            productivity_hrs=float(ccfg.get("PRODUCTIVITY_HRS", 7.0)),
            couriers_available=m_couriers,
            absenteeism_pct=float(ccfg.get("ABSENTEEISM_PCT", 16.0)),
            training_pct=float(ccfg.get("TRAINING_PCT", 11.0)),
            working_days=int(ccfg.get("WORKING_DAYS", 5)),
        )
        calc_couriers = cr.get("total_required_with_training", 0)
        result["calc_couriers"] = calc_couriers
        result["courier_status"] = calculate_courier_health_status(calc_couriers, m_couriers).get("status", "UNKNOWN")
    except Exception:
        pass

    return result


@st.cache_data(ttl=120, show_spinner=False)
def _build_health_table(famis_hash: int) -> pd.DataFrame:
    """Compute full health status for all FAMIS rows (cached by data hash)."""
    famis  = st.session_state.get("famis_data", pd.DataFrame())
    master = st.session_state.get("master_data", pd.DataFrame())
    if famis is None or famis.empty:
        return pd.DataFrame()
    try:
        cfg      = load_config()
        area_cfg = load_area_config()
    except Exception:
        cfg = {}; area_cfg = {}

    rows = []
    for _, row in famis.iterrows():
        loc = row.get("loc_id", "")
        if not loc:
            continue
        mrow = pd.Series()
        if master is not None and not master.empty and "loc_id" in master.columns:
            m = master[master["loc_id"] == loc]
            if not m.empty:
                mrow = m.iloc[0]
        rows.append(_compute_status_row(row, mrow, cfg, area_cfg))

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get(status, "#888")
    label = {"HEALTHY": "✅ Healthy", "REVIEW_NEEDED": "⚠️ Review",
             "CRITICAL": "🔴 Critical", "UNKNOWN": "— Unknown"}.get(status, status)
    return (f'<span style="background:{color};color:#fff;border-radius:4px;'
            f'padding:2px 8px;font-size:11px;font-weight:700;">{label}</span>')


def _section_header(title: str) -> None:
    st.markdown(f"""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    {title}
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE RENDER
# ════════════════════════════════════════════════════════════════════════════
render_header(
    "STATION ANALYTICS",
    "Regional Health Overview · Station Drill-Down · System Configuration",
    logo_height=80,
    badge="ANALYTICS",
)

famis_df  = _get_famis()
master_df = _get_master()

if famis_df is None or famis_df.empty:
    render_info_banner(
        "No FAMIS Data",
        "No FAMIS data is loaded. Go to <b>Data Upload Centre</b> and upload a FAMIS volume "
        "file to enable analytics.",
        accent=_ORANGE,
    )
    render_footer("ANALYTICS")
    st.stop()

# Ensure date is datetime
famis_df = famis_df.copy()
famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
famis_df = famis_df[famis_df["date"].notna()]

# Attach region classification
famis_df = classify_dataframe(famis_df, "loc_id")

# ── Global filters ────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1])
with fc1:
    all_dates = sorted(famis_df["date"].dt.date.unique(), reverse=True)
    sel_date  = st.selectbox("Analysis Date", all_dates, key="analytics_date")
with fc2:
    region_options = ["All Regions"] + [r for r in region_order() if r in famis_df["region"].unique()]
    sel_region = st.selectbox("Region", region_options, key="analytics_region")
with fc3:
    status_filter = st.multiselect(
        "Status Filter",
        ["HEALTHY", "REVIEW_NEEDED", "CRITICAL", "UNKNOWN"],
        default=["HEALTHY", "REVIEW_NEEDED", "CRITICAL", "UNKNOWN"],
        key="analytics_status_filter",
    )
with fc4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", use_container_width=True):
        _load_famis_cached.clear()
        _build_health_table.clear()
        st.rerun()

# Apply region filter to display data
display_famis = famis_df if sel_region == "All Regions" else famis_df[famis_df["region"] == sel_region]

# Build health table
_hash = hash(str(famis_df.shape) + str(famis_df["date"].max()))
health_df = _build_health_table(_hash)

if not health_df.empty:
    health_df["date"] = pd.to_datetime(health_df["date"], errors="coerce")
    health_df = classify_dataframe(health_df, "loc_id")

# Day-level slice
day_health = pd.DataFrame()
if not health_df.empty:
    day_health = health_df[health_df["date"].dt.date == sel_date].copy()
    if sel_region != "All Regions":
        day_health = day_health[day_health["region"] == sel_region]

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Regional KPI Cards (South / West / North)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_section_header("Regional Overview")

# Build per-region summary from day_health
regions_present = [r for r in region_order() if r != "Unknown"]
reg_cards = st.columns(len(regions_present) + 1)

for i, reg in enumerate(regions_present):
    reg_slice = health_df[health_df["date"].dt.date == sel_date]
    reg_slice = reg_slice[reg_slice["region"] == reg] if not reg_slice.empty else pd.DataFrame()
    n_st  = len(reg_slice)
    vol   = int(reg_slice["pk_gross_tot"].sum()) if not reg_slice.empty and "pk_gross_tot" in reg_slice.columns else 0
    n_crit = int(((reg_slice.get("area_status","") == "CRITICAL") |
                  (reg_slice.get("resource_status","") == "CRITICAL") |
                  (reg_slice.get("courier_status","") == "CRITICAL")).sum()) if n_st else 0
    with reg_cards[i]:
        rc = region_color(reg)
        st.markdown(f"""
<div style="border:2px solid {rc};border-radius:10px;padding:14px 16px;
    background:linear-gradient(135deg,{rc}18 0%,#fff 100%);margin-bottom:10px;">
    <div style="font-weight:800;font-size:15px;color:{rc};letter-spacing:0.5px;">{reg.upper()}</div>
    <div style="font-size:22px;font-weight:700;color:#222;margin:4px 0;">{n_st}</div>
    <div style="font-size:11px;color:#555;">stations · {vol:,} pkgs</div>
    {'<div style="margin-top:6px;font-size:11px;font-weight:700;color:#DE002E;">⚠️ ' + str(n_crit) + ' critical alert(s)</div>' if n_crit else '<div style="margin-top:6px;font-size:11px;color:#008A00;font-weight:700;">✅ No critical alerts</div>'}
</div>""", unsafe_allow_html=True)

with reg_cards[len(regions_present)]:
    total_vol = int(day_health["pk_gross_tot"].sum()) if not day_health.empty and "pk_gross_tot" in day_health.columns else 0
    total_crit = 0
    if not day_health.empty:
        for col in ("area_status","resource_status","courier_status"):
            if col in day_health.columns:
                total_crit += int((day_health[col] == "CRITICAL").sum())
    st.markdown(f"""
<div style="border:2px solid #4D148C;border-radius:10px;padding:14px 16px;
    background:linear-gradient(135deg,#4D148C18 0%,#fff 100%);margin-bottom:10px;">
    <div style="font-weight:800;font-size:15px;color:#4D148C;letter-spacing:0.5px;">NETWORK</div>
    <div style="font-size:22px;font-weight:700;color:#222;margin:4px 0;">{len(day_health)}</div>
    <div style="font-size:11px;color:#555;">total stations · {total_vol:,} pkgs</div>
    {'<div style="margin-top:6px;font-size:11px;font-weight:700;color:#DE002E;">⚠️ ' + str(total_crit) + ' critical alerts</div>' if total_crit else '<div style="margin-top:6px;font-size:11px;color:#008A00;font-weight:700;">✅ All clear</div>'}
</div>""", unsafe_allow_html=True)

# Status bar charts — Area / Resource / Courier
if not day_health.empty:
    st.markdown("<br>", unsafe_allow_html=True)
    bar_cols = st.columns(3)
    for idx, (col, label) in enumerate([
        ("area_status", "Area"),
        ("resource_status", "Resource"),
        ("courier_status", "Courier"),
    ]):
        with bar_cols[idx]:
            if col in day_health.columns:
                counts = {s: int((day_health[col] == s).sum()) for s in ["HEALTHY","REVIEW_NEEDED","CRITICAL"]}
                fig = go.Figure(go.Bar(
                    x=["Healthy", "Review", "Critical"],
                    y=[counts["HEALTHY"], counts["REVIEW_NEEDED"], counts["CRITICAL"]],
                    marker_color=[_STATUS_COLORS["HEALTHY"], _STATUS_COLORS["REVIEW_NEEDED"], _STATUS_COLORS["CRITICAL"]],
                    text=[counts["HEALTHY"], counts["REVIEW_NEEDED"], counts["CRITICAL"]],
                    textposition="outside",
                ))
                fig.update_layout(
                    title=dict(text=f"{label} Status", font=dict(size=13, color="#333")),
                    height=220, margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False, yaxis=dict(visible=False),
                    xaxis=dict(tickfont=dict(size=11)),
                )
                st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Station Status Grid
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_section_header(f"Station Status — {sel_date}" + (f" · {sel_region}" if sel_region != "All Regions" else ""))

all_stations = sorted(famis_df["loc_id"].dropna().unique())

if day_health.empty:
    st.warning("No health data for the selected date. Try a different date or upload more FAMIS data.")
else:
    filtered = day_health[
        day_health["area_status"].isin(status_filter) |
        day_health["resource_status"].isin(status_filter) |
        day_health["courier_status"].isin(status_filter)
    ].sort_values(["region", "loc_id"] if "region" in day_health.columns else ["loc_id"])

    if filtered.empty:
        st.info("No stations match the selected filters.")
    else:
        # Group by region
        for reg in (region_order() if sel_region == "All Regions" else [sel_region]):
            reg_rows = filtered[filtered["region"] == reg] if "region" in filtered.columns else filtered
            if reg_rows.empty:
                continue
            rc = region_color(reg)
            st.markdown(f"""<div style="font-size:12px;font-weight:700;color:{rc};
                text-transform:uppercase;letter-spacing:0.6px;margin:10px 0 6px 0;">
                {reg} Region — {len(reg_rows)} station(s)</div>""", unsafe_allow_html=True)

            cols_per_row = 4
            stations_list = reg_rows.to_dict("records")
            for row_start in range(0, len(stations_list), cols_per_row):
                chunk = stations_list[row_start:row_start + cols_per_row]
                grid_cols = st.columns(cols_per_row)
                for ci, srow in enumerate(chunk):
                    loc  = srow.get("loc_id", "—")
                    vol  = int(srow.get("pk_gross_tot", 0))
                    a_st = srow.get("area_status",     "UNKNOWN")
                    r_st = srow.get("resource_status", "UNKNOWN")
                    c_st = srow.get("courier_status",  "UNKNOWN")
                    worst = ("CRITICAL" if "CRITICAL" in (a_st, r_st, c_st) else
                             "REVIEW_NEEDED" if "REVIEW_NEEDED" in (a_st, r_st, c_st) else
                             "HEALTHY" if all(s == "HEALTHY" for s in (a_st, r_st, c_st)) else "UNKNOWN")
                    border_color = _STATUS_COLORS[worst]
                    with grid_cols[ci]:
                        st.markdown(f"""
<div style="border:2px solid {border_color};border-radius:10px;padding:12px 14px;
    background:#fff;box-shadow:0 2px 6px rgba(0,0,0,0.06);margin-bottom:8px;">
    <div style="font-weight:700;font-size:15px;color:#333;">{loc}</div>
    <div style="font-size:11px;color:#666;margin:4px 0;">{vol:,} packages</div>
    <div style="margin-top:6px;font-size:11px;">
        <span style="display:block;margin-bottom:2px;">📐 Area: {_status_badge(a_st)}</span>
        <span style="display:block;margin-bottom:2px;">👥 Resource: {_status_badge(r_st)}</span>
        <span style="display:block;">🚚 Courier: {_status_badge(c_st)}</span>
    </div>
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Station Drill-Down (historical)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_section_header("Station Drill-Down — Historical Trends")

drill_station = st.selectbox(
    "Select station for detailed analysis",
    ["— Select —"] + all_stations,
    key="drill_station",
)

if drill_station and drill_station != "— Select —":
    if health_df.empty:
        st.info("Health data not yet computed.")
    else:
        st_hist = health_df[health_df["loc_id"] == drill_station].sort_values("date")
        if st_hist.empty:
            st.info(f"No historical data for **{drill_station}**.")
        else:
            latest = st_hist.iloc[-1]
            reg    = latest.get("region", "—") if "region" in st_hist.columns else "—"
            st.markdown(f"#### {drill_station}  ·  Region: **{reg}**")

            dc1, dc2, dc3, dc4 = st.columns(4)
            with dc1:
                render_kpi_card("Latest Volume", f"{int(latest.get('pk_gross_tot',0)):,}",
                                str(latest["date"].date()), color=_PURPLE)
            with dc2:
                a = latest.get("area_status", "UNKNOWN")
                render_kpi_card("Area Status", a, f"Calc: {latest.get('calc_area',0):.0f} m²",
                                color=_STATUS_COLORS.get(a, "#888"))
            with dc3:
                r = latest.get("resource_status", "UNKNOWN")
                render_kpi_card("Resource Status", r, f"Agents: {latest.get('calc_agents',0):.1f}",
                                color=_STATUS_COLORS.get(r, "#888"))
            with dc4:
                c = latest.get("courier_status", "UNKNOWN")
                render_kpi_card("Courier Status", c, f"Req: {latest.get('calc_couriers',0):.1f}",
                                color=_STATUS_COLORS.get(c, "#888"))

            st.markdown("<br>", unsafe_allow_html=True)
            dt1, dt2, dt3 = st.tabs(["📦 Volume Trend", "📐 Area", "👥 Resource & Courier"])

            with dt1:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=st_hist["date"], y=st_hist["pk_gross_tot"],
                    name="Total Volume", marker_color=_PURPLE, opacity=0.8,
                ))
                fig.update_layout(title="Daily Volume Trend", height=300,
                                  xaxis_title="Date", yaxis_title="Packages",
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  margin=dict(l=40, r=20, t=40, b=40))
                st.plotly_chart(fig, use_container_width=True)

            with dt2:
                fig2 = go.Figure()
                if "calc_area" in st_hist.columns and st_hist["calc_area"].sum() > 0:
                    fig2.add_trace(go.Scatter(
                        x=st_hist["date"], y=st_hist["calc_area"],
                        name="Calculated Area", line=dict(color=_PURPLE, width=2),
                        mode="lines+markers",
                    ))
                    if latest.get("master_ops_area", 0) > 0:
                        fig2.add_hline(y=latest["master_ops_area"], line_dash="dash",
                                       line_color=_ORANGE,
                                       annotation_text=f"Capacity: {latest['master_ops_area']:.0f} m²")
                fig2.update_layout(title="Area Utilisation Trend", height=300,
                                   xaxis_title="Date", yaxis_title="Area (m²)",
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   margin=dict(l=40, r=40, t=40, b=40),
                                   legend=dict(x=0, y=1.1, orientation="h"))
                st.plotly_chart(fig2, use_container_width=True)

            with dt3:
                tc1, tc2 = st.columns(2)
                with tc1:
                    fig3 = go.Figure()
                    if "calc_agents" in st_hist.columns:
                        fig3.add_trace(go.Scatter(
                            x=st_hist["date"], y=st_hist["calc_agents"],
                            name="Required Agents", line=dict(color=_PURPLE, width=2),
                            mode="lines+markers",
                        ))
                        if latest.get("master_agents", 0) > 0:
                            fig3.add_hline(y=latest["master_agents"], line_dash="dash",
                                           line_color=_ORANGE,
                                           annotation_text=f"Master: {latest['master_agents']:.0f}")
                    fig3.update_layout(title="Agent Requirement", height=280,
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                       margin=dict(l=40, r=20, t=40, b=40))
                    st.plotly_chart(fig3, use_container_width=True)
                with tc2:
                    fig4 = go.Figure()
                    if "calc_couriers" in st_hist.columns:
                        fig4.add_trace(go.Scatter(
                            x=st_hist["date"], y=st_hist["calc_couriers"],
                            name="Required Couriers", line=dict(color="#1A5276", width=2),
                            mode="lines+markers",
                        ))
                        if latest.get("master_couriers", 0) > 0:
                            fig4.add_hline(y=latest["master_couriers"], line_dash="dash",
                                           line_color=_ORANGE,
                                           annotation_text=f"Master: {latest['master_couriers']:.0f}")
                    fig4.update_layout(title="Courier Requirement", height=280,
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                       margin=dict(l=40, r=20, t=40, b=40))
                    st.plotly_chart(fig4, use_container_width=True)

                st.markdown("**Status History**")
                tbl = st_hist[["date","pk_gross_tot","area_status","resource_status","courier_status"]].copy()
                tbl["date"] = tbl["date"].dt.strftime("%d %b %Y")
                tbl = tbl.rename(columns={
                    "date":"Date","pk_gross_tot":"Volume",
                    "area_status":"Area","resource_status":"Resource","courier_status":"Courier",
                })
                st.dataframe(tbl, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Network Volume Trend (last 30 days)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_section_header("Network Volume Trend — Last 30 Days")

cutoff = famis_df["date"].max() - timedelta(days=30)
trend_src = display_famis if sel_region != "All Regions" else famis_df
trend_df = (
    trend_src[trend_src["date"] >= cutoff]
    .groupby("date", as_index=False)["pk_gross_tot"].sum()
    .sort_values("date")
)
if not trend_df.empty:
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(
        x=trend_df["date"], y=trend_df["pk_gross_tot"],
        fill="tozeroy", mode="lines+markers",
        line=dict(color=_PURPLE, width=2),
        fillcolor="rgba(77,20,140,0.12)",
        name="Volume",
    ))
    label = sel_region if sel_region != "All Regions" else "Network"
    fig5.update_layout(
        title=f"{label} Total Volume — Last 30 Days", height=300,
        xaxis_title="Date", yaxis_title="Total Packages",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    st.plotly_chart(fig5, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — System Configuration (INLINE)
# Field engineers can adjust TACT values and area constants here.
# Changes take effect immediately in all planning calculations.
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_section_header("⚙️  System Configuration")

st.caption(
    "These parameters control how AERO calculates agent requirements, area utilisation, "
    "and courier needs. Changes are saved immediately and reflected in all planning tools."
)

cfg      = load_config()
area_cfg = load_area_config()

osa          = cfg.setdefault("OSA", {})
lasa         = cfg.setdefault("LASA", {})
dispatcher   = cfg.setdefault("DISPATCHER", {})
trace_agent  = cfg.setdefault("TRACE_AGENT", {})
area_const   = area_cfg.setdefault("AREA_CONSTANTS", {})

_changed = False

with st.expander("📐 Area Constants", expanded=False):
    st.caption("Floor-plan assumptions used by the Area Planner.")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        area_const["PALLET_AREA"] = st.number_input(
            "Pallet Area (sq.ft per pallet)",
            value=float(area_const.get("PALLET_AREA", 16)), step=1.0,
            key="cfg_area_pallet",
        )
        area_const["AISLE_PERCENT"] = st.number_input(
            "Aisle Percentage",
            value=float(area_const.get("AISLE_PERCENT", 0.15)), step=0.01,
            min_value=0.0, max_value=0.5, key="cfg_area_aisle",
        )
    with col_a2:
        area_const["CAGE_PALLET_AREA"] = st.number_input(
            "Cage Pallet Area (sq.ft)",
            value=float(area_const.get("CAGE_PALLET_AREA", 25)), step=1.0,
            key="cfg_area_cage",
        )
        area_const["STACKING_PER_PALLET"] = st.number_input(
            "Vertical Stacking Factor (pallets)",
            value=int(area_const.get("STACKING_PER_PALLET", 20)), step=1,
            key="cfg_area_stack",
        )

with st.expander("👥 OSA TACT Values", expanded=False):
    st.caption("Time-and-motion constants for OSA (Operational Support Agent) tasks.")
    col_o1, col_o2 = st.columns(2)
    with col_o1:
        osa["IB_OB_SCAN_TACT"] = st.number_input("IB / OB Scan TACT (mins)",
            value=float(osa.get("IB_OB_SCAN_TACT", 0.12)), step=0.01, key="cfg_osa_scan")
        osa["DAMAGE_SCAN_TACT"] = st.number_input("Damage Scan TACT",
            value=float(osa.get("DAMAGE_SCAN_TACT", 3)), step=0.5, key="cfg_osa_dmg")
        osa["ROD_BOE_TACT"] = st.number_input("ROD & BOE TACT",
            value=float(osa.get("ROD_BOE_TACT", 1)), step=0.5, key="cfg_osa_rod")
        osa["EMAIL_QUERY_TACT"] = st.number_input("Queries Handling TACT",
            value=float(osa.get("EMAIL_QUERY_TACT", 1.5)), step=0.5, key="cfg_osa_email")
        osa["FAMIS_TACT"] = st.number_input("FAMIS Report TACT",
            value=float(osa.get("FAMIS_TACT", 30)), step=1.0, key="cfg_osa_famis")
    with col_o2:
        osa["CAGE_MONITORING_TACT"] = st.number_input("Cage Monitoring TACT",
            value=float(osa.get("CAGE_MONITORING_TACT", 2)), step=0.5, key="cfg_osa_cage")
        osa["ROC_TACT"] = st.number_input("ROC Activities TACT",
            value=float(osa.get("ROC_TACT", 5)), step=1.0, key="cfg_osa_roc")
        osa["OB_SCAN_LOAD_TACT"] = st.number_input("OB Scan & Load TACT",
            value=float(osa.get("OB_SCAN_LOAD_TACT", 0.1)), step=0.01, key="cfg_osa_ob")
        osa["ASP_HANDLING_TACT"] = st.number_input("ASP Handling TACT",
            value=float(osa.get("ASP_HANDLING_TACT", 0.5)), step=0.1, key="cfg_osa_asp")
        osa["STATION_OPEN_CLOSE_TACT"] = st.number_input("Station Open/Close TACT",
            value=float(osa.get("STATION_OPEN_CLOSE_TACT", 10)), step=1.0, key="cfg_osa_oc")

with st.expander("🚚 Courier Constants", expanded=False):
    st.caption("Courier capacity and productivity parameters.")
    col_c1, col_c2 = st.columns(2)
    courier_cfg = cfg.setdefault("COURIER", {})
    with col_c1:
        courier_cfg["COURIER_CAPACITY"] = st.number_input(
            "Courier Capacity (pkgs per courier)",
            value=int(courier_cfg.get("COURIER_CAPACITY", 250)), min_value=1, step=1,
            key="cfg_cour_cap",
        )
        courier_cfg["SHIFT_HOURS"] = st.number_input(
            "Shift Hours",
            value=float(courier_cfg.get("SHIFT_HOURS", 9.0)), step=0.5,
            key="cfg_cour_shift",
        )
    with col_c2:
        courier_cfg["ABSENTEEISM_PCT"] = st.number_input(
            "Absenteeism %",
            value=float(courier_cfg.get("ABSENTEEISM_PCT", 16.0)), step=1.0,
            min_value=0.0, max_value=100.0, key="cfg_cour_abs",
        )
        courier_cfg["TRAINING_PCT"] = st.number_input(
            "Training Buffer %",
            value=float(courier_cfg.get("TRAINING_PCT", 11.0)), step=1.0,
            min_value=0.0, max_value=100.0, key="cfg_cour_train",
        )

# Save button
sc1, sc2 = st.columns([6, 1])
with sc2:
    if st.button("💾 Save Config", use_container_width=True, type="primary"):
        try:
            save_config(cfg)
            save_area_config(area_cfg)
            _build_health_table.clear()
            st.success("✅ Configuration saved.")
        except Exception as exc:
            st.error(f"Save failed: {exc}")

render_footer("ANALYTICS")
