# ============================================================
# AERO — Station Analytics
# Leadership-Grade Regional & Station-Level Health Dashboard
# Covers: Area | Resource | Courier | Network | Export
# ============================================================
import io
import logging
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.ui.components import (
    render_info_banner, render_kpi_card,
    _PURPLE, _ORANGE, _GREEN, _RED,
)
from aero.config.settings import load_config, load_area_config
from aero.core.area_calculator import calculate_area_requirements, calculate_area_status
from aero.core.resource_calculator import (
    calculate_resource_requirements, calculate_resource_health_status,
)
from aero.core.courier_calculator import (
    calculate_courier_requirements, calculate_courier_health_status,
)

logger = logging.getLogger(__name__)

_GREY   = "#888888"
_YELLOW = "#FFB800"

# ── Status helpers ─────────────────────────────────────────────────────────────
_STATUS_COLORS = {
    "HEALTHY":       "#008A00",
    "REVIEW_NEEDED": "#FFB800",
    "CRITICAL":      "#DE002E",
    "PROJECTED":     "#0055A5",
    "UNKNOWN":       "#888888",
    "NO DATA":       "#CCCCCC",
}
_STATUS_LABELS = {
    "HEALTHY":       "✅ Healthy",
    "REVIEW_NEEDED": "⚠️ Review",
    "CRITICAL":      "🚨 Critical",
    "PROJECTED":     "🔵 Projected",
    "UNKNOWN":       "— Unknown",
    "NO DATA":       "○ No Data",
}


# ── Data loaders ───────────────────────────────────────────────────────────────
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
    """Return FAMIS: session state (last upload) → cached DB (all history)."""
    df = st.session_state.get("famis_data")
    if df is not None and not df.empty:
        return df
    df = _load_famis_cached()
    if not df.empty:
        st.session_state["famis_data"] = df
        st.session_state["famis_df"]   = df
    return df


def _get_master() -> pd.DataFrame:
    """Return Facility Master: session state → persisted Excel store fallback."""
    df = st.session_state.get("master_data")
    if df is not None and not df.empty:
        return df
    try:
        from aero.data.excel_store import read_master_data
        df = read_master_data()
        if df is not None and not df.empty:
            st.session_state["master_data"] = df
            return df
    except Exception:
        pass
    return pd.DataFrame()


# ── Health computation ─────────────────────────────────────────────────────────
def _compute_status_row(
    row: pd.Series,
    master_row: pd.Series,
    cfg: dict,
    area_cfg: dict,
) -> dict:
    """Compute Area / Resource / Courier health for a single FAMIS row.

    Returns a flat dict with all calculated fields including:
    region, pk_gross_inb, pk_gross_outb, area_util_pct, courier_eff.
    """
    vol     = int(row.get("pk_gross_tot", 0) or 0)
    ib      = int(row.get("pk_gross_inb", 0) or 0)
    ob      = int(row.get("pk_gross_outb", 0) or 0)
    roc_raw = int(row.get("pk_roc", 0) or 0)
    roc     = int(roc_raw * 0.25)
    asp     = roc_raw - roc
    region  = str(master_row.get("region", "") or "") if not master_row.empty else ""

    ops_area = float(master_row.get("ops_area", 0) or 0) if not master_row.empty else 0.0

    if not master_row.empty:
        m_agents   = float(master_row.get("current_total_agents", master_row.get("current_total_osa", 0)) or 0)
        m_couriers = int(master_row.get("current_total_couriers", master_row.get("couriers_available", 0)) or 0)
        famis_derived_res = False
        famis_derived_cou = False
    else:
        # Use FAMIS operational fields as proxy baseline when no Facility Master uploaded
        m_agents  = float(row.get("fte_tot", 0) or 0)
        pk_cr_val = float(row.get("pk_cr_or", 0) or 0)
        pk_roc_v  = float(row.get("pk_roc",   0) or 0)
        m_couriers = int(round(pk_roc_v / pk_cr_val)) if pk_cr_val > 0 else 0
        famis_derived_res = m_agents   > 0
        famis_derived_cou = m_couriers > 0

    result = {
        "loc_id": row["loc_id"], "date": row["date"], "region": region,
        "pk_gross_tot": vol, "pk_gross_inb": ib, "pk_gross_outb": ob,
        "area_status":     "UNKNOWN",
        "resource_status": "UNKNOWN",
        "courier_status":  "UNKNOWN",
        "calc_area":     0.0,
        "calc_agents":   0.0,
        "calc_couriers": 0.0,
        "master_ops_area": ops_area,
        "master_agents":   m_agents,
        "master_couriers": m_couriers,
        "area_util_pct": 0.0,
        "courier_eff":   0.0,
        "famis_derived_res": famis_derived_res,
        "famis_derived_cou": famis_derived_cou,
    }

    if vol == 0:
        return result

    # ── Area ──────────────────────────────────────────────────────────────────
    try:
        area_constants = area_cfg.get("AREA_CONSTANTS", area_cfg)
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
        if ops_area > 0 and calc_area > 0:
            ast_ = calculate_area_status(
                calculated_total_area=calc_area, master_facility_area=ops_area
            )
            result["area_status"]   = ast_.get("status", "UNKNOWN")
            result["area_util_pct"] = round(calc_area / ops_area * 100, 1)
        elif calc_area > 0:
            result["area_status"] = "PROJECTED"
    except Exception:
        pass

    # ── Resource ──────────────────────────────────────────────────────────────
    try:
        courier_cfg = cfg.get("COURIER", {})
        rr = calculate_resource_requirements(
            total_volume=vol, ib_volume=ib, ob_volume=ob,
            roc_volume=roc, asp_volume=asp,
            shift_hours=float(courier_cfg.get("SHIFT_HOURS", 9.0)),
            absenteeism_pct=0.15, training_pct=0.0, roster_buffer_pct=0.11,
            on_call_pickup=80, dex_pct=0.05, csbiv_pct=0.80, rod_pct=0.30,
        )
        calc_agents = rr.get("total_agents", 0)
        result["calc_agents"] = calc_agents
        if m_agents > 0 and calc_agents > 0:
            rs = calculate_resource_health_status(calc_agents, m_agents)
            result["resource_status"] = rs.get("status", "UNKNOWN")
        elif calc_agents > 0:
            result["resource_status"] = "PROJECTED"
    except Exception:
        pass

    # ── Courier ───────────────────────────────────────────────────────────────
    try:
        courier_cfg = cfg.get("COURIER", {})
        cr = calculate_courier_requirements(
            total_packages=vol,
            pk_st_or=float(courier_cfg.get("PK_ST_OR", 2.5)),    # correct TACT default
            st_hr_or=float(courier_cfg.get("ST_HR_OR", 4.0)),    # correct TACT default
            productivity_hrs=float(courier_cfg.get("PRODUCTIVITY_HRS", 7.0)),
            couriers_available=m_couriers,
            absenteeism_pct=float(courier_cfg.get("ABSENTEEISM_PCT", 16.0)),
            training_pct=float(courier_cfg.get("TRAINING_PCT", 11.0)),
            working_days=int(courier_cfg.get("WORKING_DAYS", 5)),
        )
        calc_couriers = cr.get("total_required_with_training", 0)
        result["calc_couriers"] = calc_couriers
        if m_couriers > 0 and calc_couriers > 0:
            cs = calculate_courier_health_status(calc_couriers, m_couriers)
            result["courier_status"] = cs.get("status", "UNKNOWN")
            result["courier_eff"] = round(min(m_couriers / calc_couriers * 100, 200.0), 1)
        elif calc_couriers > 0:
            result["courier_status"] = "PROJECTED"
    except Exception:
        pass

    return result


@st.cache_data(ttl=120, show_spinner=False)
def _build_health_table(
    famis_df: pd.DataFrame,
    master_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute full health status for every FAMIS row.

    DataFrames are passed directly (not read from session_state) so that
    Streamlit's cache correctly invalidates when data changes.
    """
    if famis_df is None or famis_df.empty:
        return pd.DataFrame()
    try:
        cfg      = load_config()
        area_cfg = load_area_config()
    except Exception:
        cfg = {}
        area_cfg = {}

    rows = []
    for _, row in famis_df.iterrows():
        loc = row.get("loc_id", "")
        if not loc:
            continue
        if master_df is not None and not master_df.empty and "loc_id" in master_df.columns:
            mrows = master_df[master_df["loc_id"] == loc]
            mrow  = mrows.iloc[0] if not mrows.empty else pd.Series()
        else:
            mrow = pd.Series()
        rows.append(_compute_status_row(row, mrow, cfg, area_cfg))

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _count_status(df: pd.DataFrame, col: str, status: str) -> int:
    """Standalone helper — count rows where df[col] == status."""
    return int((df[col] == status).sum()) if not df.empty and col in df.columns else 0


def _overall_worst(a_st: str, r_st: str, c_st: str) -> str:
    """Return the worst status across the three health domains."""
    statuses = {a_st, r_st, c_st}
    if "CRITICAL"      in statuses: return "CRITICAL"
    if "REVIEW_NEEDED" in statuses: return "REVIEW_NEEDED"
    if "PROJECTED"     in statuses: return "PROJECTED"
    if all(s == "HEALTHY" for s in (a_st, r_st, c_st)): return "HEALTHY"
    return "UNKNOWN"


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get(status, "#888")
    label = _STATUS_LABELS.get(status, status)
    return (
        f'<span style="background:{color};color:#fff;border-radius:4px;'
        f'padding:2px 8px;font-size:11px;font-weight:700;">{label}</span>'
    )


# ════════════════════════════════════════════════════════════════════════════
# PAGE RENDER
# ════════════════════════════════════════════════════════════════════════════
render_header(
    "STATION ANALYTICS",
    "Leadership Dashboard · Regional & Station-Level Health Intelligence",
    logo_height=80,
    badge="ANALYTICS",
)

famis_df  = _get_famis()
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

# Normalise date column
famis_df = famis_df.copy()
famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
famis_df = famis_df[famis_df["date"].notna()]

# ── Global filters ─────────────────────────────────────────────────────────────
st.markdown("---")
gf1, gf2, gf3, gf4 = st.columns([2, 2, 2, 1])
with gf1:
    all_dates = sorted(famis_df["date"].dt.date.unique(), reverse=True)
    sel_date  = st.selectbox("📅 Analysis Date", all_dates, key="analytics_date")
with gf2:
    status_filter = st.multiselect(
        "🔍 Status Filter",
        ["HEALTHY", "REVIEW_NEEDED", "CRITICAL", "UNKNOWN"],
        default=["HEALTHY", "REVIEW_NEEDED", "CRITICAL", "UNKNOWN"],
        key="analytics_status_filter",
    )
with gf3:
    search_text = st.text_input(
        "🔎 Station Search", placeholder="Type station ID…", key="analytics_search"
    )
with gf4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", use_container_width=True):
        _load_famis_cached.clear()
        _build_health_table.clear()
        st.rerun()
st.markdown("---")

# Build health table — DataFrames passed directly (correct cache behaviour)
health_df = _build_health_table(famis_df, master_df)

if health_df.empty:
    st.warning(
        "⚠️ Could not compute health status. "
        "Upload Facility Master data for accurate analytics results."
    )
    render_footer("ANALYTICS")
    st.stop()

health_df["date"] = pd.to_datetime(health_df["date"], errors="coerce")
day_health = health_df[health_df["date"].dt.date == sel_date].copy()

# Apply search filter
if search_text:
    day_health = day_health[
        day_health["loc_id"].astype(str).str.contains(search_text, case=False, na=False)
    ]

all_stations = sorted(famis_df["loc_id"].dropna().unique())

# Pre-compute domain counts (used in multiple tabs)
total_st  = len(day_health)
total_vol = int(day_health["pk_gross_tot"].sum()) if "pk_gross_tot" in day_health.columns else 0
total_ib  = int(day_health["pk_gross_inb"].sum())  if "pk_gross_inb"  in day_health.columns else 0
total_ob  = int(day_health["pk_gross_outb"].sum()) if "pk_gross_outb" in day_health.columns else 0

area_h  = _count_status(day_health, "area_status",     "HEALTHY")
area_r  = _count_status(day_health, "area_status",     "REVIEW_NEEDED")
area_c  = _count_status(day_health, "area_status",     "CRITICAL")
res_h   = _count_status(day_health, "resource_status", "HEALTHY")
res_r   = _count_status(day_health, "resource_status", "REVIEW_NEEDED")
res_c   = _count_status(day_health, "resource_status", "CRITICAL")
cour_h  = _count_status(day_health, "courier_status",  "HEALTHY")
cour_r  = _count_status(day_health, "courier_status",  "REVIEW_NEEDED")
cour_c  = _count_status(day_health, "courier_status",  "CRITICAL")

healthy_total   = sum(
    1 for _, r in day_health.iterrows()
    if _overall_worst(
        r.get("area_status", "UNKNOWN"),
        r.get("resource_status", "UNKNOWN"),
        r.get("courier_status", "UNKNOWN"),
    ) == "HEALTHY"
) if total_st else 0
critical_total  = area_c + res_c + cour_c
net_health_pct  = round(healthy_total / total_st * 100) if total_st else 0
avg_cour_eff    = (
    round(day_health["courier_eff"].mean(), 1)
    if "courier_eff" in day_health.columns and day_health["courier_eff"].sum() > 0
    else 0.0
)
avg_area_util   = (
    round(day_health["area_util_pct"].mean(), 1)
    if "area_util_pct" in day_health.columns and day_health["area_util_pct"].sum() > 0
    else 0.0
)


# ════════════════════════════════════════════════════════════════════════════
# 5-TAB LEADERSHIP DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
TAB_OV, TAB_GRID, TAB_DRILL, TAB_TREND, TAB_EXPORT = st.tabs([
    "🏢 Executive Overview",
    "📊 Station Grid",
    "🔍 Station Drill-Down",
    "📈 Network Trends",
    "📥 Export Report",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — EXECUTIVE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
with TAB_OV:
    # Leadership banner
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#4D148C 0%,#3a0f6e 100%);
        border-radius:14px;padding:22px 28px;margin-bottom:20px;
        box-shadow:0 4px 16px rgba(77,20,140,0.25);">
        <div style="color:rgba(255,255,255,0.70);font-size:11px;font-weight:700;
            text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;">
            AERO · STATION ANALYTICS · LEADERSHIP VIEW
        </div>
        <div style="color:#FFFFFF;font-size:22px;font-weight:800;margin-bottom:4px;">
            Network Health Intelligence
        </div>
        <div style="color:rgba(255,255,255,0.80);font-size:13px;">
            Analysis Date: <b style="color:#FF6200;">{sel_date}</b>
            &nbsp;·&nbsp; FedEx Field &amp; Station Operations
        </div>
    </div>""", unsafe_allow_html=True)

    # ── 6 KPI Cards ──────────────────────────────────────────────────────────
    kc = st.columns(6)
    with kc[0]:
        render_kpi_card("Stations", str(total_st), f"as of {sel_date}", color=_PURPLE)
    with kc[1]:
        render_kpi_card(
            "Total Volume", f"{total_vol:,}",
            f"IB {total_ib:,} · OB {total_ob:,}",
            color=_PURPLE,
        )
    with kc[2]:
        render_kpi_card(
            "Network Health", f"{net_health_pct}%",
            f"{healthy_total}/{total_st} fully healthy",
            color=_GREEN if net_health_pct >= 70 else (_ORANGE if net_health_pct >= 40 else _RED),
        )
    with kc[3]:
        render_kpi_card(
            "Critical Alerts", str(critical_total),
            "Area · Resource · Courier",
            color=_RED if critical_total > 0 else _GREEN,
        )
    with kc[4]:
        render_kpi_card(
            "Avg Courier Eff.", f"{avg_cour_eff}%",
            "master vs required",
            color=_GREEN if avg_cour_eff >= 90 else (_ORANGE if avg_cour_eff >= 70 else _RED),
        )
    with kc[5]:
        render_kpi_card(
            "Avg Area Util.", f"{avg_area_util}%",
            "calculated vs capacity",
            color=_GREEN if avg_area_util <= 80 else (_ORANGE if avg_area_util <= 100 else _RED),
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Domain status bar charts ──────────────────────────────────────────────
    bc1, bc2, bc3 = st.columns(3)
    for col_ctx, (h, r, c, label, icon) in zip(
        [bc1, bc2, bc3],
        [
            (area_h,  area_r,  area_c,  "Area",     "📐"),
            (res_h,   res_r,   res_c,   "Resource", "👥"),
            (cour_h,  cour_r,  cour_c,  "Courier",  "🚚"),
        ],
    ):
        with col_ctx:
            fig = go.Figure(go.Bar(
                x=["Healthy", "Review", "Critical"],
                y=[h, r, c],
                marker_color=[
                    _STATUS_COLORS["HEALTHY"],
                    _STATUS_COLORS["REVIEW_NEEDED"],
                    _STATUS_COLORS["CRITICAL"],
                ],
                text=[h, r, c],
                textposition="outside",
                textfont=dict(size=12, color="#333"),
            ))
            fig.update_layout(
                title=dict(text=f"{icon} {label} Domain", font=dict(size=13, color="#333"), x=0),
                height=240,
                margin=dict(l=10, r=10, t=44, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                yaxis=dict(visible=False),
                xaxis=dict(tickfont=dict(size=11)),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top 5 by Volume + Stations Needing Attention ──────────────────────────
    ov_c1, ov_c2 = st.columns(2)

    with ov_c1:
        st.markdown(f"""
        <div style="font-weight:700;color:{_PURPLE};font-size:13px;text-transform:uppercase;
            letter-spacing:0.8px;border-bottom:2px solid {_PURPLE};
            padding-bottom:6px;margin-bottom:12px;">
            🏆 Top 5 Stations by Volume
        </div>""", unsafe_allow_html=True)
        if not day_health.empty and "pk_gross_tot" in day_health.columns:
            top5_cols = [c for c in [
                "loc_id", "pk_gross_tot", "pk_gross_inb", "pk_gross_outb",
                "area_status", "resource_status", "courier_status",
            ] if c in day_health.columns]
            top5 = day_health.nlargest(5, "pk_gross_tot")[top5_cols].copy()
            for col in ["pk_gross_tot", "pk_gross_inb", "pk_gross_outb"]:
                if col in top5.columns:
                    top5[col] = top5[col].map(lambda x: f"{int(x):,}")
            top5.columns = [c.replace("pk_gross_", "").replace("_status", "").replace("_", " ").title()
                            for c in top5.columns]
            st.dataframe(top5, hide_index=True, use_container_width=True)

    with ov_c2:
        st.markdown(f"""
        <div style="font-weight:700;color:{_RED};font-size:13px;text-transform:uppercase;
            letter-spacing:0.8px;border-bottom:2px solid {_RED};
            padding-bottom:6px;margin-bottom:12px;">
            🚨 Stations Needing Attention
        </div>""", unsafe_allow_html=True)
        if not day_health.empty:
            attn = day_health[
                day_health["area_status"].isin(["CRITICAL", "REVIEW_NEEDED"]) |
                day_health["resource_status"].isin(["CRITICAL", "REVIEW_NEEDED"]) |
                day_health["courier_status"].isin(["CRITICAL", "REVIEW_NEEDED"])
            ].sort_values("pk_gross_tot", ascending=False).head(8)
            if attn.empty:
                st.success("✅ All stations are currently healthy!")
            else:
                attn_cols = [c for c in [
                    "loc_id", "pk_gross_tot",
                    "area_status", "resource_status", "courier_status",
                ] if c in attn.columns]
                attn_disp = attn[attn_cols].copy()
                if "pk_gross_tot" in attn_disp.columns:
                    attn_disp["pk_gross_tot"] = attn_disp["pk_gross_tot"].map(lambda x: f"{int(x):,}")
                attn_disp.columns = [c.replace("pk_gross_tot", "Volume").replace("_status", "")
                                      .replace("_", " ").title() for c in attn_disp.columns]
                st.dataframe(attn_disp, hide_index=True, use_container_width=True)

    # ── Region Rollup (if region data available) ──────────────────────────────
    if (
        "region" in day_health.columns
        and day_health["region"].notna().any()
        and day_health["region"].str.strip().str.len().gt(0).any()
    ):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="font-weight:700;color:{_PURPLE};font-size:13px;text-transform:uppercase;
            letter-spacing:0.8px;border-bottom:2px solid {_PURPLE};
            padding-bottom:6px;margin-bottom:12px;">
            🗺️ Region Rollup
        </div>""", unsafe_allow_html=True)

        agg_map = {
            "Stations":          ("loc_id",         "count"),
            "Total Volume":      ("pk_gross_tot",   "sum"),
            "Inbound":           ("pk_gross_inb",   "sum"),
            "Outbound":          ("pk_gross_outb",  "sum"),
            "Area Critical":     ("area_status",    lambda x: (x == "CRITICAL").sum()),
            "Resource Critical": ("resource_status", lambda x: (x == "CRITICAL").sum()),
            "Courier Critical":  ("courier_status",  lambda x: (x == "CRITICAL").sum()),
            "Avg Courier Eff%":  ("courier_eff",     "mean"),
            "Avg Area Util%":    ("area_util_pct",  "mean"),
        }
        # Only include columns that exist
        safe_agg = {
            k: v for k, v in agg_map.items()
            if v[0] in day_health.columns
        }
        reg_grp = day_health.groupby("region").agg(**{
            k: pd.NamedAgg(column=v[0], aggfunc=v[1]) for k, v in safe_agg.items()
        }).reset_index()
        reg_grp = reg_grp.rename(columns={"region": "Region"})
        for col in ["Total Volume", "Inbound", "Outbound"]:
            if col in reg_grp.columns:
                reg_grp[col] = reg_grp[col].map(lambda x: f"{x:,.0f}")
        for col in ["Avg Courier Eff%", "Avg Area Util%"]:
            if col in reg_grp.columns:
                reg_grp[col] = reg_grp[col].map(lambda x: f"{x:.1f}%")
        st.dataframe(reg_grp, hide_index=True, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — STATION GRID
# ════════════════════════════════════════════════════════════════════════════
with TAB_GRID:
    st.markdown(f"""
    <div style="font-weight:700;color:{_PURPLE};font-size:14px;text-transform:uppercase;
        letter-spacing:0.8px;border-bottom:2px solid {_PURPLE};
        padding-bottom:6px;margin-bottom:16px;">
        Station Status Grid — {sel_date}
    </div>""", unsafe_allow_html=True)

    filtered = day_health.copy()
    if status_filter:
        filtered = filtered[
            filtered["area_status"].isin(status_filter) |
            filtered["resource_status"].isin(status_filter) |
            filtered["courier_status"].isin(status_filter)
        ]
    filtered = filtered.sort_values("loc_id")

    if filtered.empty:
        st.info("No stations match the selected status / search filters.")
    else:
        st.markdown(
            f"Showing **{len(filtered)}** of **{total_st}** station(s) for {sel_date}",
        )
        COLS_PER_ROW = 4
        stations_list = filtered.to_dict("records")
        for row_start in range(0, len(stations_list), COLS_PER_ROW):
            row_batch = stations_list[row_start:row_start + COLS_PER_ROW]
            grid_cols = st.columns(COLS_PER_ROW)
            for ci, srow in enumerate(row_batch):
                loc    = srow.get("loc_id", "—")
                vol    = int(srow.get("pk_gross_tot", 0))
                a_st   = srow.get("area_status",     "UNKNOWN")
                r_st   = srow.get("resource_status", "UNKNOWN")
                c_st   = srow.get("courier_status",  "UNKNOWN")
                worst  = _overall_worst(a_st, r_st, c_st)
                border = _STATUS_COLORS.get(worst, "#888888")
                c_eff  = srow.get("courier_eff",   0.0)
                a_util = srow.get("area_util_pct", 0.0)
                calc_a = srow.get("calc_area",     0.0)
                calc_r = srow.get("calc_agents",   0.0)
                calc_c = srow.get("calc_couriers", 0.0)
                a_detail = f"{a_util:.0f}% util" if srow.get("master_ops_area", 0) > 0 else f"{calc_a:,.0f} m² needed"
                r_detail = f"Master:{srow.get('master_agents',0):.0f}" if srow.get("master_agents", 0) > 0 else f"{calc_r:.0f} needed"
                c_detail = f"Eff:{c_eff:.0f}%" if srow.get("master_couriers", 0) > 0 else f"{calc_c:.0f} needed"

                with grid_cols[ci]:
                    st.markdown(f"""
<div style="border:2px solid {border};border-radius:10px;padding:12px 14px;
    background:#fff;box-shadow:0 2px 6px rgba(0,0,0,0.06);
    margin-bottom:8px;min-height:195px;">
    <div style="font-weight:800;font-size:15px;color:#333;margin-bottom:2px;">{loc}</div>
    <div style="font-size:11px;color:#666;margin-bottom:8px;">{vol:,} packages</div>
    <div style="font-size:11px;margin-bottom:3px;">📐 {_status_badge(a_st)}<br>
        <span style="color:#888;font-size:10px;">{a_detail}</span></div>
    <div style="font-size:11px;margin-bottom:3px;">👥 {_status_badge(r_st)}<br>
        <span style="color:#888;font-size:10px;">{r_detail}</span></div>
    <div style="font-size:11px;">🚚 {_status_badge(c_st)}<br>
        <span style="color:#888;font-size:10px;">{c_detail}</span></div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — STATION DRILL-DOWN
# ════════════════════════════════════════════════════════════════════════════
with TAB_DRILL:
    st.markdown(f"""
    <div style="font-weight:700;color:{_PURPLE};font-size:14px;text-transform:uppercase;
        letter-spacing:0.8px;border-bottom:2px solid {_PURPLE};
        padding-bottom:6px;margin-bottom:16px;">
        Station Deep Dive — Historical Analysis
    </div>""", unsafe_allow_html=True)

    drill_station = st.selectbox(
        "Select Station for Detailed Analysis",
        ["— Select Station —"] + all_stations,
        key="drill_station",
    )

    if drill_station and drill_station != "— Select Station —":
        st_hist = health_df[health_df["loc_id"] == drill_station].sort_values("date")

        if st_hist.empty:
            st.info(f"No historical data available for **{drill_station}**.")
        else:
            latest = st_hist.iloc[-1]

            # 4 KPI cards
            dc1, dc2, dc3, dc4 = st.columns(4)
            with dc1:
                render_kpi_card(
                    "Latest Volume",
                    f"{int(latest.get('pk_gross_tot', 0)):,}",
                    f"IB {int(latest.get('pk_gross_inb', 0)):,} · OB {int(latest.get('pk_gross_outb', 0)):,}",
                    color=_PURPLE,
                )
            with dc2:
                a_st = latest.get("area_status", "UNKNOWN")
                render_kpi_card(
                    "Area Status",
                    _STATUS_LABELS.get(a_st, a_st),
                    f"Util: {latest.get('area_util_pct', 0):.1f}% · Calc: {latest.get('calc_area', 0):.0f} m²",
                    color=_STATUS_COLORS.get(a_st, _GREY),
                )
            with dc3:
                r_st = latest.get("resource_status", "UNKNOWN")
                render_kpi_card(
                    "Resource Status",
                    _STATUS_LABELS.get(r_st, r_st),
                    f"Required: {latest.get('calc_agents', 0):.1f} · Master: {latest.get('master_agents', 0):.0f}",
                    color=_STATUS_COLORS.get(r_st, _GREY),
                )
            with dc4:
                c_st = latest.get("courier_status", "UNKNOWN")
                render_kpi_card(
                    "Courier Status",
                    _STATUS_LABELS.get(c_st, c_st),
                    f"Eff: {latest.get('courier_eff', 0):.1f}% · Req: {latest.get('calc_couriers', 0):.1f}",
                    color=_STATUS_COLORS.get(c_st, _GREY),
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # 4 sub-tabs
            dt1, dt2, dt3, dt4 = st.tabs([
                "📦 Volume Trend",
                "📐 Area",
                "👥 Resource & Courier",
                "📋 Status History",
            ])

            # ── Volume Trend ──────────────────────────────────────────────────
            with dt1:
                fig_v = go.Figure()
                if "pk_gross_inb" in st_hist.columns:
                    fig_v.add_trace(go.Bar(
                        x=st_hist["date"], y=st_hist["pk_gross_inb"],
                        name="Inbound", marker_color=_PURPLE, opacity=0.85,
                    ))
                if "pk_gross_outb" in st_hist.columns:
                    fig_v.add_trace(go.Bar(
                        x=st_hist["date"], y=st_hist["pk_gross_outb"],
                        name="Outbound", marker_color=_ORANGE, opacity=0.85,
                    ))
                fig_v.update_layout(
                    barmode="group",
                    title=f"{drill_station} — Daily Volume Trend (IB / OB)",
                    height=340, xaxis_title="Date", yaxis_title="Packages",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=40, r=20, t=44, b=40),
                    legend=dict(orientation="h", x=0, y=1.12),
                )
                st.plotly_chart(fig_v, use_container_width=True)

            # ── Area ──────────────────────────────────────────────────────────
            with dt2:
                fig_a = go.Figure()
                if "calc_area" in st_hist.columns and st_hist["calc_area"].sum() > 0:
                    fig_a.add_trace(go.Scatter(
                        x=st_hist["date"], y=st_hist["calc_area"],
                        name="Calculated Area (m²)",
                        line=dict(color=_PURPLE, width=2),
                        mode="lines+markers",
                    ))
                ops_cap = latest.get("master_ops_area", 0)
                if ops_cap > 0:
                    fig_a.add_hline(
                        y=ops_cap, line_dash="dash", line_color=_ORANGE,
                        annotation_text=f"Facility Capacity: {ops_cap:.0f} m²",
                    )
                if "area_util_pct" in st_hist.columns and st_hist["area_util_pct"].sum() > 0:
                    fig_a.add_trace(go.Bar(
                        x=st_hist["date"], y=st_hist["area_util_pct"],
                        name="Util %", marker_color=_PURPLE, opacity=0.20,
                        yaxis="y2",
                    ))
                fig_a.update_layout(
                    title=f"{drill_station} — Area Utilisation Trend",
                    height=340, xaxis_title="Date", yaxis_title="Area (m²)",
                    yaxis2=dict(overlaying="y", side="right", title="Util %",
                                showgrid=False, range=[0, 150]),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=40, r=60, t=44, b=40),
                    legend=dict(orientation="h", x=0, y=1.12),
                )
                st.plotly_chart(fig_a, use_container_width=True)

            # ── Resource & Courier ────────────────────────────────────────────
            with dt3:
                tc1, tc2 = st.columns(2)

                with tc1:
                    fig_r = go.Figure()
                    if "calc_agents" in st_hist.columns:
                        fig_r.add_trace(go.Scatter(
                            x=st_hist["date"], y=st_hist["calc_agents"],
                            name="Required Agents",
                            line=dict(color=_PURPLE, width=2),
                            mode="lines+markers",
                        ))
                    m_ag = latest.get("master_agents", 0)
                    if m_ag > 0:
                        fig_r.add_hline(
                            y=m_ag, line_dash="dash", line_color=_ORANGE,
                            annotation_text=f"Master: {m_ag:.0f}",
                        )
                    fig_r.update_layout(
                        title="Agent Requirement Trend", height=300,
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=40, r=20, t=44, b=40),
                    )
                    st.plotly_chart(fig_r, use_container_width=True)

                with tc2:
                    fig_c = go.Figure()
                    if "calc_couriers" in st_hist.columns:
                        fig_c.add_trace(go.Scatter(
                            x=st_hist["date"], y=st_hist["calc_couriers"],
                            name="Required Couriers",
                            line=dict(color="#1A5276", width=2),
                            mode="lines+markers",
                        ))
                    m_cr = latest.get("master_couriers", 0)
                    if m_cr > 0:
                        fig_c.add_hline(
                            y=m_cr, line_dash="dash", line_color=_ORANGE,
                            annotation_text=f"Master: {m_cr:.0f}",
                        )
                    if "courier_eff" in st_hist.columns and st_hist["courier_eff"].sum() > 0:
                        fig_c.add_trace(go.Bar(
                            x=st_hist["date"], y=st_hist["courier_eff"],
                            name="Courier Eff %",
                            marker_color=_GREEN, opacity=0.20,
                            yaxis="y2",
                        ))
                    fig_c.update_layout(
                        title="Courier Requirement & Efficiency", height=300,
                        yaxis2=dict(overlaying="y", side="right", title="Eff %",
                                    showgrid=False, range=[0, 200]),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=40, r=60, t=44, b=40),
                        legend=dict(orientation="h", x=0, y=1.12),
                    )
                    st.plotly_chart(fig_c, use_container_width=True)

            # ── Status History ─────────────────────────────────────────────────
            with dt4:
                st.markdown("**Complete Status History**")
                tbl_cols = [c for c in [
                    "date", "pk_gross_tot", "pk_gross_inb", "pk_gross_outb",
                    "area_status", "resource_status", "courier_status",
                    "area_util_pct", "courier_eff",
                    "calc_area", "calc_agents", "calc_couriers",
                ] if c in st_hist.columns]
                tbl = st_hist[tbl_cols].copy()
                if "date" in tbl.columns:
                    tbl["date"] = tbl["date"].dt.strftime("%d %b %Y")
                tbl = tbl.rename(columns={
                    "date": "Date",
                    "pk_gross_tot": "Vol",
                    "pk_gross_inb": "IB",
                    "pk_gross_outb": "OB",
                    "area_status": "Area",
                    "resource_status": "Resource",
                    "courier_status": "Courier",
                    "area_util_pct": "Area Util%",
                    "courier_eff": "Cour Eff%",
                    "calc_area": "Calc Area",
                    "calc_agents": "Req Agents",
                    "calc_couriers": "Req Couriers",
                })
                st.dataframe(tbl, hide_index=True, use_container_width=True)
    else:
        st.info("👆 Select a station above to view its full historical performance breakdown.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — NETWORK TRENDS
# ════════════════════════════════════════════════════════════════════════════
with TAB_TREND:
    st.markdown(f"""
    <div style="font-weight:700;color:{_PURPLE};font-size:14px;text-transform:uppercase;
        letter-spacing:0.8px;border-bottom:2px solid {_PURPLE};
        padding-bottom:6px;margin-bottom:16px;">
        Network Volume &amp; Health Trends
    </div>""", unsafe_allow_html=True)

    max_date   = famis_df["date"].max()
    cutoff_30  = max_date - timedelta(days=30)
    trend_df   = (
        famis_df[famis_df["date"] >= cutoff_30]
        .groupby("date", as_index=False)["pk_gross_tot"].sum()
        .sort_values("date")
    )

    if not trend_df.empty:
        trend_df["rolling_7"] = trend_df["pk_gross_tot"].rolling(7, min_periods=1).mean()

        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["pk_gross_tot"],
            fill="tozeroy", mode="lines",
            line=dict(color=_PURPLE, width=1.5),
            fillcolor="rgba(77,20,140,0.10)",
            name="Daily Volume",
        ))
        fig_t.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["rolling_7"],
            mode="lines",
            line=dict(color=_ORANGE, width=2.5, dash="dot"),
            name="7-Day Rolling Avg",
        ))
        fig_t.update_layout(
            title="Total Network Volume — Last 30 Days",
            height=320, xaxis_title="Date", yaxis_title="Total Packages",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=44, b=40),
            legend=dict(orientation="h", x=0, y=1.12),
        )
        st.plotly_chart(fig_t, use_container_width=True)

        # Week-over-week bar chart
        trend_df["week"] = trend_df["date"].dt.to_period("W").astype(str)
        wow = trend_df.groupby("week", as_index=False)["pk_gross_tot"].sum()
        if len(wow) >= 2:
            fig_w = go.Figure(go.Bar(
                x=wow["week"],
                y=wow["pk_gross_tot"],
                marker_color=_PURPLE,
                text=wow["pk_gross_tot"].map(lambda x: f"{x:,.0f}"),
                textposition="outside",
            ))
            fig_w.update_layout(
                title="Week-over-Week Network Volume",
                height=260, xaxis_title="Week", yaxis_title="Packages",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=40, r=20, t=44, b=40),
            )
            st.plotly_chart(fig_w, use_container_width=True)

    # Network Health % trend across all available dates
    st.markdown("---")
    st.markdown("**Network Health % Trend (all available dates)**")
    all_dates_sorted = sorted(health_df["date"].dropna().dt.date.unique())
    ht_rows = []
    for d in all_dates_sorted:
        dh = health_df[health_df["date"].dt.date == d]
        if dh.empty:
            continue
        n = len(dh)
        h_n = sum(
            1 for _, r in dh.iterrows()
            if _overall_worst(
                r.get("area_status", "UNKNOWN"),
                r.get("resource_status", "UNKNOWN"),
                r.get("courier_status", "UNKNOWN"),
            ) == "HEALTHY"
        )
        ht_rows.append({"date": d, "health_pct": round(h_n / n * 100, 1) if n else 0})

    if ht_rows:
        ht_df = pd.DataFrame(ht_rows)
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(
            x=ht_df["date"], y=ht_df["health_pct"],
            mode="lines+markers",
            line=dict(color=_GREEN, width=2.5),
            name="Network Health %",
            fill="tozeroy", fillcolor="rgba(0,138,0,0.08)",
        ))
        fig_h.add_hline(
            y=70, line_dash="dash", line_color=_ORANGE,
            annotation_text="70% Target", annotation_position="bottom right",
        )
        fig_h.update_layout(
            title="Network Health % Over Time",
            height=280, xaxis_title="Date", yaxis_title="% Fully Healthy Stations",
            yaxis=dict(range=[0, 105]),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=44, b=40),
        )
        st.plotly_chart(fig_h, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — EXPORT REPORT
# ════════════════════════════════════════════════════════════════════════════
with TAB_EXPORT:
    st.markdown(f"""
    <div style="font-weight:700;color:{_PURPLE};font-size:14px;text-transform:uppercase;
        letter-spacing:0.8px;border-bottom:2px solid {_PURPLE};
        padding-bottom:6px;margin-bottom:16px;">
        Export Station Health Report
    </div>""", unsafe_allow_html=True)

    render_info_banner(
        "Export Options",
        "Download the full station health analysis as <b>Excel</b> (two sheets: "
        "Station Health + Network Summary) or <b>CSV</b> for use in BI tools "
        "and leadership presentations.",
        accent=_PURPLE,
    )

    export_df = day_health.copy()
    if "date" in export_df.columns:
        export_df["date"] = export_df["date"].dt.strftime("%d %b %Y")

    ec1, ec2 = st.columns(2)

    with ec1:
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # Sheet 1: Station Health
                sh1_cols = [c for c in [
                    "loc_id", "date", "region",
                    "pk_gross_tot", "pk_gross_inb", "pk_gross_outb",
                    "area_status",    "resource_status",   "courier_status",
                    "calc_area",      "master_ops_area",   "area_util_pct",
                    "calc_agents",    "master_agents",
                    "calc_couriers",  "master_couriers",   "courier_eff",
                ] if c in export_df.columns]
                export_df[sh1_cols].to_excel(writer, sheet_name="Station Health", index=False)

                # Sheet 2: Network Summary (16 metrics)
                summary_data = {
                    "Metric": [
                        "Analysis Date",
                        "Stations Analysed",
                        "Total Volume",
                        "Total Inbound",
                        "Total Outbound",
                        "Area Healthy",
                        "Area Review",
                        "Area Critical",
                        "Resource Healthy",
                        "Resource Review",
                        "Resource Critical",
                        "Courier Healthy",
                        "Courier Review",
                        "Courier Critical",
                        "Network Health %",
                        "Avg Courier Efficiency %",
                    ],
                    "Value": [
                        str(sel_date),
                        total_st,
                        total_vol,
                        total_ib,
                        total_ob,
                        area_h,
                        area_r,
                        area_c,
                        res_h,
                        res_r,
                        res_c,
                        cour_h,
                        cour_r,
                        cour_c,
                        f"{net_health_pct}%",
                        f"{avg_cour_eff}%",
                    ],
                }
                pd.DataFrame(summary_data).to_excel(
                    writer, sheet_name="Network Summary", index=False
                )

            output.seek(0)
            st.download_button(
                label="⬇️ Download Excel Report (.xlsx)",
                data=output,
                file_name=f"AERO_Station_Health_{sel_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Excel export failed: {e}")

    with ec2:
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name=f"AERO_Station_Health_{sel_date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"**Preview — Station Health Data ({sel_date})**")
    preview_cols = [c for c in [
        "loc_id", "date", "pk_gross_tot", "pk_gross_inb", "pk_gross_outb",
        "area_status", "resource_status", "courier_status",
        "area_util_pct", "courier_eff",
        "calc_area", "calc_agents", "calc_couriers",
    ] if c in export_df.columns]
    st.dataframe(
        export_df[preview_cols].head(50),
        hide_index=True,
        use_container_width=True,
    )


render_footer("ANALYTICS")
