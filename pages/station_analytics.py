# ============================================================
# AERO — Station Analytics
# Region-level KPI overview → Station drill-down with
# historical Area / Resource / Courier health trends.
# ============================================================
import logging
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.ui.components import render_info_banner, render_kpi_card, _PURPLE, _ORANGE, _GREEN, _RED
from aero.config.settings import load_config, load_area_config
from aero.core.area_calculator import calculate_area_requirements, calculate_area_status
from aero.core.resource_calculator import (
    calculate_resource_requirements, calculate_resource_health_status,
)
from aero.core.courier_calculator import (
    calculate_courier_requirements, calculate_courier_health_status,
)

logger = logging.getLogger(__name__)

# ── Brand palette ─────────────────────────────────────────────────────────────
_STATUS_COLORS = {
    "HEALTHY":      "#008A00",
    "REVIEW_NEEDED": "#FFB800",
    "CRITICAL":     "#DE002E",
    "UNKNOWN":      "#888888",
    "NO DATA":      "#CCCCCC",
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
    """Return FAMIS data: session state → cache → empty."""
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


# ── Health computation helpers ────────────────────────────────────────────────
def _compute_status_row(row: pd.Series, master_row: pd.Series,
                         cfg: dict, area_cfg: dict) -> dict:
    """Return area/resource/courier status for a single FAMIS row."""
    vol     = int(row.get("pk_gross_tot", 0) or 0)
    ib      = int(row.get("pk_gross_inb", 0) or 0)
    ob      = int(row.get("pk_gross_outb", 0) or 0)
    roc_raw = int(row.get("pk_roc", 0) or 0)
    roc     = int(roc_raw * 0.25)
    asp     = roc_raw - roc

    # master defaults
    ops_area   = float(master_row.get("ops_area", 0) or 0) if not master_row.empty else 0.0
    m_agents   = float(master_row.get("current_total_agents",
                        master_row.get("current_total_osa", 0)) or 0) if not master_row.empty else 0.0
    m_couriers = int(master_row.get("current_total_couriers",
                      master_row.get("couriers_available", 0)) or 0) if not master_row.empty else 0

    result = {"loc_id": row["loc_id"], "date": row["date"],
              "pk_gross_tot": vol,
              "area_status": "UNKNOWN", "resource_status": "UNKNOWN", "courier_status": "UNKNOWN",
              "calc_area": 0.0, "calc_agents": 0.0, "calc_couriers": 0.0,
              "master_ops_area": ops_area, "master_agents": m_agents, "master_couriers": m_couriers}

    if vol == 0:
        return result

    # Area
    try:
        ac = calculate_area_requirements(
            total_packs=vol,
            packs_per_pallet=area_cfg.get("PACKS_PER_PALLET", 15),
            max_volume_percent=area_cfg.get("MAX_VOLUME_PERCENT", 55.0),
            sorting_area_percent=area_cfg.get("SORTING_AREA_PERCENT", 60.0),
            cage_percent=area_cfg.get("CAGE_PERCENT", 10.0),
            aisle_percent=area_cfg.get("AISLE_PERCENT", 15.0),
        )
        calc_area = ac.get("total_operational_area", 0)
        result["calc_area"] = calc_area
        if ops_area > 0:
            ast_ = calculate_area_status(
                calculated_total_area=calc_area, master_facility_area=ops_area
            )
            result["area_status"] = ast_.get("status", "UNKNOWN")
    except Exception:
        pass

    # Resource
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
        rs = calculate_resource_health_status(calc_agents, m_agents)
        result["resource_status"] = rs.get("status", "UNKNOWN")
    except Exception:
        pass

    # Courier
    try:
        courier_cfg = cfg.get("COURIER", {})
        cr = calculate_courier_requirements(
            total_packages=vol,
            pk_st_or=float(courier_cfg.get("PK_ST_OR", 1.5)),
            st_hr_or=float(courier_cfg.get("ST_HR_OR", 8.0)),
            productivity_hrs=float(courier_cfg.get("PRODUCTIVITY_HRS", 7.0)),
            couriers_available=m_couriers,
            absenteeism_pct=float(courier_cfg.get("ABSENTEEISM_PCT", 16.0)),
            training_pct=float(courier_cfg.get("TRAINING_PCT", 11.0)),
            working_days=int(courier_cfg.get("WORKING_DAYS", 5)),
        )
        calc_couriers = cr.get("total_required_with_training", 0)
        result["calc_couriers"] = calc_couriers
        cs = calculate_courier_health_status(calc_couriers, m_couriers)
        result["courier_status"] = cs.get("status", "UNKNOWN")
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
        if master is not None and not master.empty and "loc_id" in master.columns:
            mrow = master[master["loc_id"] == loc]
            mrow = mrow.iloc[0] if not mrow.empty else pd.Series()
        else:
            mrow = pd.Series()
        rows.append(_compute_status_row(row, mrow, cfg, area_cfg))

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get(status, "#888")
    label = {"HEALTHY": "✅ Healthy", "REVIEW_NEEDED": "⚠️ Review",
             "CRITICAL": "🔴 Critical", "UNKNOWN": "— Unknown"}.get(status, status)
    return (f'<span style="background:{color};color:#fff;border-radius:4px;'
            f'padding:2px 8px;font-size:11px;font-weight:700;">{label}</span>')


# ════════════════════════════════════════════════════════════════════════════
# PAGE RENDER
# ════════════════════════════════════════════════════════════════════════════
render_header(
    "STATION ANALYTICS",
    "Regional Health Overview & Station-Level Drill-Down",
    logo_height=80,
    badge="ANALYTICS",
)

# Load data
famis_df = _get_famis()
master_df = _get_master()

if famis_df is None or famis_df.empty:
    render_info_banner(
        "No Data Available",
        "No FAMIS data has been uploaded yet. Go to <b>Data Upload Centre</b> and upload "
        "a FAMIS volume file to populate the analytics.",
        accent=_ORANGE,
    )
    render_footer("ANALYTICS")
    st.stop()

# Ensure date column is datetime
famis_df = famis_df.copy()
famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
famis_df = famis_df[famis_df["date"].notna()]

# ── Global filters ────────────────────────────────────────────────────────────
st.markdown("### Filters")
fc1, fc2, fc3 = st.columns([2, 2, 1])
with fc1:
    all_dates = sorted(famis_df["date"].dt.date.unique(), reverse=True)
    sel_date  = st.selectbox("Analysis Date", all_dates, key="analytics_date")
with fc2:
    all_stations = sorted(famis_df["loc_id"].dropna().unique())
    status_filter = st.multiselect("Status Filter", ["HEALTHY","REVIEW_NEEDED","CRITICAL","UNKNOWN"],
                                    default=["HEALTHY","REVIEW_NEEDED","CRITICAL","UNKNOWN"],
                                    key="analytics_status_filter")
with fc3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        _load_famis_cached.clear()
        _build_health_table.clear()
        st.rerun()

# Compute health for selected date
_hash = hash(str(famis_df.shape) + str(famis_df["date"].max()))
health_df = _build_health_table(_hash)

if health_df.empty:
    st.warning("Could not compute health status. Upload Facility Master data for accurate results.")
    render_footer("ANALYTICS")
    st.stop()

health_df["date"] = pd.to_datetime(health_df["date"], errors="coerce")
day_health = health_df[health_df["date"].dt.date == sel_date].copy()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Regional KPI Cards
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Regional Overview
</div>""", unsafe_allow_html=True)

def _count_status(col, status):
    return int((day_health[col] == status).sum()) if col in day_health.columns else 0

total_st = len(day_health)
area_healthy   = _count_status("area_status",     "HEALTHY")
area_review    = _count_status("area_status",     "REVIEW_NEEDED")
area_critical  = _count_status("area_status",     "CRITICAL")
res_healthy    = _count_status("resource_status", "HEALTHY")
res_review     = _count_status("resource_status", "REVIEW_NEEDED")
res_critical   = _count_status("resource_status", "CRITICAL")
cour_healthy   = _count_status("courier_status",  "HEALTHY")
cour_review    = _count_status("courier_status",  "REVIEW_NEEDED")
cour_critical  = _count_status("courier_status",  "CRITICAL")

r1c1, r1c2, r1c3, r1c4 = st.columns(4)
with r1c1:
    render_kpi_card("Stations", str(total_st), f"as of {sel_date}", color=_PURPLE)
with r1c2:
    total_vol = int(day_health["pk_gross_tot"].sum()) if "pk_gross_tot" in day_health.columns else 0
    render_kpi_card("Total Volume", f"{total_vol:,}", "packages", color=_PURPLE)
with r1c3:
    healthy_pct = round(area_healthy / total_st * 100) if total_st else 0
    render_kpi_card("Area Healthy", f"{healthy_pct}%", f"{area_healthy}/{total_st} stations", color=_GREEN if healthy_pct > 70 else _ORANGE)
with r1c4:
    critical_total = area_critical + res_critical + cour_critical
    render_kpi_card("Critical Alerts", str(critical_total), "across all categories", color=_RED if critical_total > 0 else _GREEN)

st.markdown("<br>", unsafe_allow_html=True)

# Status summary bar charts
bar_cols = st.columns(3)
for idx, (domain, h, r, c, label) in enumerate([
    ("area_status",     area_healthy, area_review, area_critical, "Area"),
    ("resource_status", res_healthy,  res_review,  res_critical,  "Resource"),
    ("courier_status",  cour_healthy, cour_review, cour_critical, "Courier"),
]):
    with bar_cols[idx]:
        fig = go.Figure(go.Bar(
            x=["Healthy", "Review", "Critical"],
            y=[h, r, c],
            marker_color=[_STATUS_COLORS["HEALTHY"], _STATUS_COLORS["REVIEW_NEEDED"], _STATUS_COLORS["CRITICAL"]],
            text=[h, r, c], textposition="outside",
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
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Station Status — {dt}
</div>""".format(dt=str(sel_date)), unsafe_allow_html=True)

# Filter by status
filtered = day_health[
    day_health["area_status"].isin(status_filter) |
    day_health["resource_status"].isin(status_filter) |
    day_health["courier_status"].isin(status_filter)
].sort_values("loc_id")

if filtered.empty:
    st.info("No stations match the selected status filters.")
else:
    # Render station cards in rows of 4
    cols_per_row = 4
    stations_list = filtered.to_dict("records")
    for row_start in range(0, len(stations_list), cols_per_row):
        row_stations = stations_list[row_start:row_start + cols_per_row]
        grid_cols = st.columns(cols_per_row)
        for ci, srow in enumerate(row_stations):
            loc   = srow.get("loc_id", "—")
            vol   = int(srow.get("pk_gross_tot", 0))
            a_st  = srow.get("area_status",     "UNKNOWN")
            r_st  = srow.get("resource_status", "UNKNOWN")
            c_st  = srow.get("courier_status",  "UNKNOWN")
            worst = "CRITICAL" if "CRITICAL" in (a_st, r_st, c_st) else \
                    "REVIEW_NEEDED" if "REVIEW_NEEDED" in (a_st, r_st, c_st) else \
                    "HEALTHY" if all(s == "HEALTHY" for s in (a_st, r_st, c_st)) else "UNKNOWN"
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
# SECTION 3 — Station Drill-Down
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Station Drill-Down
</div>""", unsafe_allow_html=True)

drill_station = st.selectbox(
    "Select a station for detailed historical analysis",
    ["— Select Station —"] + all_stations,
    key="drill_station",
)

if drill_station and drill_station != "— Select Station —":
    st_history = health_df[health_df["loc_id"] == drill_station].sort_values("date")

    if st_history.empty:
        st.info(f"No historical data available for **{drill_station}**.")
    else:
        st.markdown(f"#### {drill_station} — Historical Performance")

        # Latest status
        latest_row = st_history.iloc[-1]
        dc1, dc2, dc3, dc4 = st.columns(4)
        with dc1:
            render_kpi_card("Latest Volume", f"{int(latest_row.get('pk_gross_tot',0)):,}",
                            str(latest_row["date"].date()), color=_PURPLE)
        with dc2:
            render_kpi_card("Area Status", latest_row.get("area_status","—"),
                            f"Calc: {latest_row.get('calc_area',0):.0f} m²", color=_STATUS_COLORS.get(latest_row.get("area_status","UNKNOWN")))
        with dc3:
            render_kpi_card("Resource Status", latest_row.get("resource_status","—"),
                            f"Agents: {latest_row.get('calc_agents',0):.1f}", color=_STATUS_COLORS.get(latest_row.get("resource_status","UNKNOWN")))
        with dc4:
            render_kpi_card("Courier Status", latest_row.get("courier_status","—"),
                            f"Req: {latest_row.get('calc_couriers',0):.1f}", color=_STATUS_COLORS.get(latest_row.get("courier_status","UNKNOWN")))

        st.markdown("<br>", unsafe_allow_html=True)
        drill_tab1, drill_tab2, drill_tab3 = st.tabs(["📦 Volume Trend", "📐 Area", "👥 Resource & Courier"])

        with drill_tab1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=st_history["date"], y=st_history["pk_gross_tot"],
                name="Total Volume", marker_color=_PURPLE, opacity=0.8,
            ))
            fig.update_layout(
                title="Daily Volume Trend", height=320,
                xaxis_title="Date", yaxis_title="Packages",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=40, r=20, t=40, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

        with drill_tab2:
            fig2 = go.Figure()
            if "calc_area" in st_history.columns and st_history["calc_area"].sum() > 0:
                fig2.add_trace(go.Scatter(
                    x=st_history["date"], y=st_history["calc_area"],
                    name="Calculated Area", line=dict(color=_PURPLE, width=2), mode="lines+markers",
                ))
                if latest_row.get("master_ops_area", 0) > 0:
                    fig2.add_hline(y=latest_row["master_ops_area"],
                                   line_dash="dash", line_color=_ORANGE,
                                   annotation_text=f"Capacity: {latest_row['master_ops_area']:.0f} m²")
            # Status timeline
            status_map = {"HEALTHY": 1, "REVIEW_NEEDED": 2, "CRITICAL": 3, "UNKNOWN": 0}
            st_history["area_num"] = st_history["area_status"].map(status_map).fillna(0)
            fig2.add_trace(go.Bar(
                x=st_history["date"], y=st_history["area_num"],
                name="Status Level",
                marker_color=[_STATUS_COLORS.get(s, "#888") for s in st_history["area_status"]],
                opacity=0.4, yaxis="y2",
            ))
            fig2.update_layout(
                title="Area Utilisation Trend", height=320,
                xaxis_title="Date", yaxis_title="Area (m²)",
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            tickvals=[1,2,3], ticktext=["Healthy","Review","Critical"],
                            visible=True),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=40, r=60, t=40, b=40), legend=dict(x=0, y=1.1, orientation="h"),
            )
            st.plotly_chart(fig2, use_container_width=True)

        with drill_tab3:
            tc1, tc2 = st.columns(2)
            with tc1:
                fig3 = go.Figure()
                if "calc_agents" in st_history.columns:
                    fig3.add_trace(go.Scatter(
                        x=st_history["date"], y=st_history["calc_agents"],
                        name="Required Agents", line=dict(color=_PURPLE, width=2), mode="lines+markers",
                    ))
                    if latest_row.get("master_agents", 0) > 0:
                        fig3.add_hline(y=latest_row["master_agents"],
                                       line_dash="dash", line_color=_ORANGE,
                                       annotation_text=f"Master: {latest_row['master_agents']:.0f}")
                fig3.update_layout(title="Agent Requirement", height=280,
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   margin=dict(l=40, r=20, t=40, b=40))
                st.plotly_chart(fig3, use_container_width=True)
            with tc2:
                fig4 = go.Figure()
                if "calc_couriers" in st_history.columns:
                    fig4.add_trace(go.Scatter(
                        x=st_history["date"], y=st_history["calc_couriers"],
                        name="Required Couriers", line=dict(color="#1A5276", width=2), mode="lines+markers",
                    ))
                    if latest_row.get("master_couriers", 0) > 0:
                        fig4.add_hline(y=latest_row["master_couriers"],
                                       line_dash="dash", line_color=_ORANGE,
                                       annotation_text=f"Master: {latest_row['master_couriers']:.0f}")
                fig4.update_layout(title="Courier Requirement", height=280,
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   margin=dict(l=40, r=20, t=40, b=40))
                st.plotly_chart(fig4, use_container_width=True)

            # Status summary table
            if not st_history.empty:
                st.markdown("**Status History**")
                tbl = st_history[["date","pk_gross_tot","area_status","resource_status","courier_status"]].copy()
                tbl["date"] = tbl["date"].dt.strftime("%d %b %Y")
                tbl = tbl.rename(columns={
                    "date":"Date","pk_gross_tot":"Volume",
                    "area_status":"Area","resource_status":"Resource","courier_status":"Courier"
                })
                st.dataframe(tbl, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Volume Trend across all stations (last 30 days)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Network Volume Trend
</div>""", unsafe_allow_html=True)

cutoff = famis_df["date"].max() - timedelta(days=30)
trend_df = (
    famis_df[famis_df["date"] >= cutoff]
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
        name="Network Volume",
    ))
    fig5.update_layout(
        title="Total Network Volume — Last 30 Days", height=300,
        xaxis_title="Date", yaxis_title="Total Packages",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    st.plotly_chart(fig5, use_container_width=True)

render_footer("ANALYTICS")
