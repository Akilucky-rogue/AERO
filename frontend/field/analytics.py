# ============================================================
# AERO — Station Analytics  [frontend/field/analytics.py]
#
# Leadership view: Region → Station health intelligence.
#
# END-TO-END FLOW UNDERSTOOD:
#   1. Field uploads FAMIS volume file  →  Data Upload Centre
#      persists to DB / Excel; session_state["famis_data"] set
#   2. Field uploads Facility Master    →  Data Upload Centre
#      persists to FAMIS_META.xlsx;     session_state["master_data"] set
#   3. Station Planning (Area / Resource / Courier planners)
#      read famis_data + master_data → compute requirements → per-station view
#   4. THIS PAGE computes health for EVERY station:
#         Calculated requirement (from FAMIS volume via calculators)
#         vs Master capacity / headcount (from Facility Master upload)
#      → HEALTHY / REVIEW_NEEDED / CRITICAL / PROJECTED
#
# Health status map:
#   HEALTHY       → calc ≤ available capacity
#   REVIEW_NEEDED → within 10-20 % shortfall
#   CRITICAL      → > 20 % shortfall
#   PROJECTED     → calculation ran but NO master data to compare yet
#   UNKNOWN       → volume = 0 or calculation error
#
# Page layout (single scroll, leadership-grade):
#   [A] Network Summary KPIs
#   [B] Region Cards  (South / West / North)
#   [C] Domain Health Charts  (Area | Resource | Courier)
#   [D] Station Health Grid   (grouped by region, cards)
#   [E] Volume Trend Chart    (last 30 days, by region)
#   [F] Station Deep-Dive     (per-station historical)
#   [G] System Configuration  (TACT & area constants)
# ============================================================
from __future__ import annotations

import os, sys, logging
from datetime import timedelta

_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aero.ui.header    import render_header, render_footer
from aero.ui.components import render_info_banner, render_kpi_card, _PURPLE, _ORANGE, _GREEN, _RED
from aero.config.settings import load_config, save_config, load_area_config, save_area_config
from aero.core.area_calculator     import calculate_area_requirements, calculate_area_status
from aero.core.resource_calculator import calculate_resource_requirements, calculate_resource_health_status
from aero.core.courier_calculator  import calculate_courier_requirements, calculate_courier_health_status
from aero.region.mapper            import classify_dataframe, region_order, region_color

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
_YELLOW = "#FFB800"
_GREY   = "#888888"
_BLUE   = "#0055A5"   # PROJECTED

_SC = {                           # status colours
    "HEALTHY":       "#008A00",
    "REVIEW_NEEDED": "#FFB800",
    "CRITICAL":      "#DE002E",
    "PROJECTED":     "#0055A5",
    "UNKNOWN":       "#888888",
}
_SL = {                           # status labels
    "HEALTHY":       "✅ Healthy",
    "REVIEW_NEEDED": "⚠️ Review",
    "CRITICAL":      "🚨 Critical",
    "PROJECTED":     "🔵 Projected",
    "UNKNOWN":       "—",
}


# ════════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def _load_famis_cached() -> pd.DataFrame:
    try:
        from aero.data.famis_store import db_available, load_famis_from_db, famis_row_count
        if db_available() and famis_row_count() > 0:
            df = load_famis_from_db()
            if df is not None and not df.empty:
                return df
    except Exception:
        pass
    try:
        from aero.data.excel_store import read_famis_uploads
        df = read_famis_uploads()
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    return pd.DataFrame()


def _get_famis() -> pd.DataFrame:
    """Session state (live upload) → cached DB (persisted history)."""
    for key in ("famis_data", "famis_df"):
        df = st.session_state.get(key)
        if df is not None and not df.empty:
            return df
    df = _load_famis_cached()
    if df is not None and not df.empty:
        st.session_state["famis_data"] = df
        st.session_state["famis_df"]   = df
    return df if df is not None else pd.DataFrame()


def _get_master() -> pd.DataFrame:
    """Session state → persisted FAMIS_META.xlsx (fixes cross-session gap)."""
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


# ════════════════════════════════════════════════════════════════════════════
# HEALTH COMPUTATION  (pure functions — no session state reads)
# ════════════════════════════════════════════════════════════════════════════

def _safe(v, default=0):
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f  # NaN guard
    except (TypeError, ValueError):
        return default


def _compute_row(row: pd.Series, mrow: pd.Series, cfg: dict, area_cfg: dict) -> dict:
    """Compute all health fields for one FAMIS row."""
    vol = int(_safe(row.get("pk_gross_tot")))
    ib  = int(_safe(row.get("pk_gross_inb")))    # used internally by resource calc
    ob  = int(_safe(row.get("pk_gross_outb")))   # used internally by resource calc
    roc_raw = int(_safe(row.get("pk_roc")))
    roc = int(roc_raw * 0.25)
    asp = roc_raw - roc

    has_master = mrow is not None and not mrow.empty
    ops_area   = float(_safe(mrow.get("ops_area")) if has_master else 0)

    if has_master:
        m_agents          = float(_safe(mrow.get("current_total_agents", mrow.get("current_total_osa", 0))))
        m_couriers        = int(_safe(mrow.get("current_total_couriers", mrow.get("couriers_available", 0))))
        famis_derived_res = False
        famis_derived_cou = False
    else:
        # Use FAMIS operational data as proxy when no Facility Master uploaded
        m_agents  = float(_safe(row.get("fte_tot", 0)))       # actual FTEs recorded in FAMIS
        pk_cr     = _safe(row.get("pk_cr_or", 0))
        pk_roc_v  = _safe(row.get("pk_roc", 0))
        m_couriers = int(round(pk_roc_v / pk_cr)) if pk_cr > 0 else 0
        famis_derived_res = m_agents > 0
        famis_derived_cou = m_couriers > 0

    out = dict(
        loc_id=row.get("loc_id", ""), date=row.get("date"),
        pk_gross_tot=vol,
        area_status="UNKNOWN", resource_status="UNKNOWN", courier_status="UNKNOWN",
        calc_area=0.0, calc_agents=0.0, calc_couriers=0.0,
        master_ops_area=ops_area, master_agents=m_agents, master_couriers=m_couriers,
        area_util_pct=0.0, courier_eff=0.0,
        osa_agents=0.0, lasa_agents=0.0, dispatcher_agents=0.0, trace_agents=0.0,
        famis_derived_res=famis_derived_res, famis_derived_cou=famis_derived_cou,
    )
    if vol == 0:
        return out

    # ── Area ─────────────────────────────────────────────────────────────────
    try:
        ac_cfg = area_cfg.get("AREA_CONSTANTS", area_cfg)
        ac = calculate_area_requirements(
            total_packs=vol,
            packs_per_pallet=ac_cfg.get("PACKS_PER_PALLET", 15),
            max_volume_percent=ac_cfg.get("MAX_VOLUME_PERCENT", 55.0),
            sorting_area_percent=ac_cfg.get("SORTING_AREA_PERCENT", 60.0),
            cage_percent=ac_cfg.get("CAGE_PERCENT", 10.0),
            aisle_percent=ac_cfg.get("AISLE_PERCENT", 15.0),
        )
        ca = float(_safe(ac.get("total_operational_area")))
        out["calc_area"] = ca
        if ops_area > 0 and ca > 0:
            st_ = calculate_area_status(ca, ops_area)
            out["area_status"]   = st_.get("status", "UNKNOWN")
            out["area_util_pct"] = round(ca / ops_area * 100, 1)
        elif ca > 0:
            out["area_status"] = "PROJECTED"
    except Exception:
        pass

    # ── Resource ─────────────────────────────────────────────────────────────
    try:
        c_cfg = cfg.get("COURIER", {})
        rr = calculate_resource_requirements(
            total_volume=vol, ib_volume=ib, ob_volume=ob,
            roc_volume=roc, asp_volume=asp,
            shift_hours=float(_safe(c_cfg.get("SHIFT_HOURS"), 9.0)),
            absenteeism_pct=0.15, training_pct=0.0, roster_buffer_pct=0.11,
            on_call_pickup=80, dex_pct=0.05, csbiv_pct=0.80, rod_pct=0.30,
        )
        ca2 = float(_safe(rr.get("total_agents")))
        out["calc_agents"]       = ca2
        out["osa_agents"]        = float(_safe(rr.get("osa_agents_with_sharp")))
        out["lasa_agents"]       = float(_safe(rr.get("lasa_agents_with_sharp")))
        out["dispatcher_agents"] = float(_safe(rr.get("dispatcher_agents_with_sharp")))
        out["trace_agents"]      = float(_safe(rr.get("trace_agents_with_sharp")))
        if m_agents > 0 and ca2 > 0:
            rs = calculate_resource_health_status(ca2, m_agents)
            out["resource_status"] = rs.get("status", "UNKNOWN")
        elif ca2 > 0:
            out["resource_status"] = "PROJECTED"
    except Exception:
        pass

    # ── Courier ───────────────────────────────────────────────────────────────
    try:
        c_cfg = cfg.get("COURIER", {})
        cr = calculate_courier_requirements(
            total_packages=vol,
            pk_st_or=float(_safe(c_cfg.get("PK_ST_OR"), 2.5)),
            st_hr_or=float(_safe(c_cfg.get("ST_HR_OR"), 4.0)),
            productivity_hrs=float(_safe(c_cfg.get("PRODUCTIVITY_HRS"), 7.0)),
            couriers_available=m_couriers if m_couriers > 0 else None,
            absenteeism_pct=float(_safe(c_cfg.get("ABSENTEEISM_PCT"), 16.0)),
            training_pct=float(_safe(c_cfg.get("TRAINING_PCT"), 11.0)),
            working_days=int(_safe(c_cfg.get("WORKING_DAYS"), 5)),
        )
        cc = float(_safe(cr.get("total_required_with_training")))
        out["calc_couriers"] = cc
        if m_couriers > 0 and cc > 0:
            cs = calculate_courier_health_status(cc, m_couriers)
            out["courier_status"] = cs.get("status", "UNKNOWN")
            out["courier_eff"]    = round(min(m_couriers / cc * 100, 200.0), 1)
        elif cc > 0:
            out["courier_status"] = "PROJECTED"
    except Exception:
        pass

    return out


@st.cache_data(ttl=120, show_spinner=False)
def _build_health_table(famis_df: pd.DataFrame, master_df: pd.DataFrame) -> pd.DataFrame:
    """Compute health for every FAMIS row. DFs passed directly — correct cache."""
    if famis_df is None or famis_df.empty:
        return pd.DataFrame()
    try:
        cfg      = load_config()
        area_cfg = load_area_config()
    except Exception:
        cfg = {}; area_cfg = {}

    # Index master by loc_id for O(1) lookup
    master_idx: dict = {}
    if master_df is not None and not master_df.empty and "loc_id" in master_df.columns:
        for _, mr in master_df.iterrows():
            lid = str(mr.get("loc_id", "") or "").strip()
            if lid:
                master_idx[lid] = mr

    rows = []
    for _, row in famis_df.iterrows():
        loc = str(row.get("loc_id", "") or "").strip()
        if not loc:
            continue
        rows.append(_compute_row(row, master_idx.get(loc, pd.Series(dtype=object)), cfg, area_cfg))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _badge(status: str) -> str:
    c = _SC.get(status, _GREY)
    l = _SL.get(status, status)
    return (f'<span style="background:{c};color:#fff;border-radius:4px;'
            f'padding:2px 7px;font-size:10px;font-weight:700;">{l}</span>')


def _worst(a: str, r: str, c: str) -> str:
    ss = {a, r, c}
    for s in ("CRITICAL", "REVIEW_NEEDED", "PROJECTED", "HEALTHY"):
        if s in ss:
            return s
    return "UNKNOWN"


def _cnt(df: pd.DataFrame, col: str, status: str) -> int:
    if df.empty or col not in df.columns:
        return 0
    return int((df[col] == status).sum())


def _sec(title: str, color: str = _PURPLE) -> None:
    st.markdown(
        f'<div style="font-weight:700;color:{color};font-size:13px;'
        f'text-transform:uppercase;letter-spacing:0.8px;'
        f'border-bottom:2px solid {color};padding-bottom:5px;margin:18px 0 12px 0;">'
        f'{title}</div>', unsafe_allow_html=True
    )


# ════════════════════════════════════════════════════════════════════════════
# PAGE BOOTSTRAP
# ════════════════════════════════════════════════════════════════════════════
render_header(
    "STATION ANALYTICS",
    "Leadership Health Intelligence · Region → Station View",
    logo_height=80, badge="ANALYTICS",
)

famis_df  = _get_famis()
master_df = _get_master()

if famis_df is None or famis_df.empty:
    render_info_banner(
        "No FAMIS Data",
        "Upload a FAMIS volume file via <b>Data Upload Centre</b> to enable analytics.",
        accent=_ORANGE,
    )
    render_footer("ANALYTICS")
    st.stop()

famis_df = famis_df.copy()
famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
famis_df = famis_df[famis_df["date"].notna()].copy()
famis_df = classify_dataframe(famis_df, "loc_id")

has_master = master_df is not None and not master_df.empty

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
with f1:
    all_dates = sorted(famis_df["date"].dt.date.unique(), reverse=True)
    sel_date  = st.selectbox("📅 Analysis Date", all_dates, key="an_date")
with f2:
    regions   = [r for r in region_order() if r != "Unknown" and r in famis_df["region"].unique()]
    sel_reg   = st.selectbox("🗺️ Region", ["All Regions"] + regions, key="an_region")
with f3:
    all_st_opts = ["All Statuses", "HEALTHY", "REVIEW_NEEDED", "CRITICAL", "PROJECTED"]
    sel_status  = st.selectbox("🔍 Status Filter", all_st_opts, key="an_status")
with f4:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", use_container_width=True):
        _load_famis_cached.clear()
        _build_health_table.clear()
        st.rerun()

# Master-absent notice
if not has_master:
    st.info(
        "ℹ️ **Facility Master not yet uploaded.** Resource & Courier health is computed using "
        "FAMIS operational data (`fte_tot`, `pk_roc / pk_cr_or`) as the comparison baseline. "
        "Area health shows 🔵 Projected (ops_area only available in Facility Master). "
        "Upload a Facility Master in Data Upload Centre for full capacity-based comparisons.",
    )

# ── Compute health table ──────────────────────────────────────────────────────
with st.spinner("Computing station health…"):
    health_df = _build_health_table(famis_df, master_df)

if health_df is None or health_df.empty:
    st.warning("Could not compute health data. Check your FAMIS upload.")
    render_footer("ANALYTICS")
    st.stop()

health_df["date"] = pd.to_datetime(health_df["date"], errors="coerce")
health_df = classify_dataframe(health_df, "loc_id")

# Day slice
day_h = health_df[health_df["date"].dt.date == sel_date].copy()

# Region filter
if sel_reg != "All Regions":
    day_h = day_h[day_h["region"] == sel_reg].copy()

# Status filter
if sel_status != "All Statuses":
    day_h = day_h[
        (day_h["area_status"]     == sel_status) |
        (day_h["resource_status"] == sel_status) |
        (day_h["courier_status"]  == sel_status)
    ].copy()

all_stn_ids = sorted(famis_df["loc_id"].dropna().unique())

# Pre-aggregate
tot_st    = len(day_h)
tot_vol   = int(day_h["pk_gross_tot"].sum()) if "pk_gross_tot" in day_h.columns else 0
crit_ct   = sum(_cnt(day_h, c, "CRITICAL") for c in ["area_status","resource_status","courier_status"])
proj_ct   = sum(_cnt(day_h, c, "PROJECTED") for c in ["area_status","resource_status","courier_status"])
hlthy_ct  = sum(
    1 for _, r in day_h.iterrows()
    if _worst(r.get("area_status","UNKNOWN"), r.get("resource_status","UNKNOWN"), r.get("courier_status","UNKNOWN")) == "HEALTHY"
) if tot_st else 0
net_pct   = round(hlthy_ct / tot_st * 100) if tot_st else 0
tot_calc_agents   = round(day_h["calc_agents"].sum(), 1)   if "calc_agents"   in day_h.columns else 0.0
tot_calc_couriers = round(day_h["calc_couriers"].sum(), 1) if "calc_couriers" in day_h.columns else 0.0


# ════════════════════════════════════════════════════════════════════════════
# [A] NETWORK SUMMARY KPIs
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_sec("📊 Network Summary")

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    render_kpi_card("Stations", str(tot_st), f"as of {sel_date}", color=_PURPLE)
with k2:
    render_kpi_card("Total Volume", f"{tot_vol:,}", "packages", color=_PURPLE)
with k3:
    render_kpi_card(
        "Network Health",
        f"{net_pct}%",
        f"{hlthy_ct}/{tot_st} fully healthy",
        color=_GREEN if net_pct >= 70 else (_ORANGE if net_pct >= 40 else _RED),
    )
with k4:
    render_kpi_card(
        "Critical Alerts",
        str(crit_ct),
        "across Area · Resource · Courier",
        color=_RED if crit_ct > 0 else _GREEN,
    )
with k5:
    render_kpi_card(
        "Projected Stations",
        str(proj_ct),
        "awaiting Facility Master",
        color=_BLUE if proj_ct > 0 else _GREEN,
    )


# ════════════════════════════════════════════════════════════════════════════
# [B] REGION CARDS
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_sec("🗺️ Regional Overview")

reg_list  = [r for r in region_order() if r != "Unknown"]
reg_cols  = st.columns(len(reg_list))

for i, reg in enumerate(reg_list):
    day_reg = health_df[
        (health_df["date"].dt.date == sel_date) &
        (health_df["region"] == reg)
    ]
    n_s   = len(day_reg)
    vol_r = int(day_reg["pk_gross_tot"].sum()) if n_s else 0
    n_crit = sum(
        1 for _, r in day_reg.iterrows()
        if _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U")) == "CRITICAL"
    ) if n_s else 0
    n_rev  = sum(
        1 for _, r in day_reg.iterrows()
        if _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U")) == "REVIEW_NEEDED"
    ) if n_s else 0
    n_proj = sum(
        1 for _, r in day_reg.iterrows()
        if _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U")) == "PROJECTED"
    ) if n_s else 0
    n_hlth = sum(
        1 for _, r in day_reg.iterrows()
        if _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U")) == "HEALTHY"
    ) if n_s else 0

    rc = region_color(reg)
    if n_crit:
        alert = f'<div style="color:#DE002E;font-weight:700;font-size:11px;margin-top:6px;">🚨 {n_crit} critical</div>'
    elif n_rev:
        alert = f'<div style="color:#FFB800;font-weight:700;font-size:11px;margin-top:6px;">⚠️ {n_rev} review needed</div>'
    elif n_proj:
        alert = f'<div style="color:#0055A5;font-weight:700;font-size:11px;margin-top:6px;">🔵 {n_proj} projected</div>'
    else:
        alert = '<div style="color:#008A00;font-weight:700;font-size:11px;margin-top:6px;">✅ All stations healthy</div>'

    with reg_cols[i]:
        st.markdown(f"""
<div style="border:2px solid {rc};border-radius:12px;padding:16px 18px;
    background:linear-gradient(135deg,{rc}15 0%,#fff 100%);
    box-shadow:0 2px 8px {rc}22;">
    <div style="font-weight:800;font-size:15px;color:{rc};">{reg.upper()}</div>
    <div style="font-size:28px;font-weight:700;color:#222;margin:4px 0;">{n_s}</div>
    <div style="font-size:11px;color:#666;">stations &nbsp;·&nbsp; {vol_r:,} pkgs</div>
    <div style="font-size:10px;color:#888;margin-top:4px;">
        ✅ {n_hlth} &nbsp;⚠️ {n_rev} &nbsp;🚨 {n_crit} &nbsp;🔵 {n_proj}
    </div>
    {alert}
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# [C] DOMAIN HEALTH CHARTS
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_sec("📐👥🚚 Domain Health — Area · Resource · Courier")

if not day_h.empty:
    dc1, dc2, dc3 = st.columns(3)

    for col_idx, (dom_col, dom_label, dom_icon) in enumerate([
        ("area_status",     "Area",     "📐"),
        ("resource_status", "Resource", "👥"),
        ("courier_status",  "Courier",  "🚚"),
    ]):
        counts = {s: _cnt(day_h, dom_col, s)
                  for s in ["HEALTHY", "REVIEW_NEEDED", "CRITICAL", "PROJECTED"]}
        fig = go.Figure(go.Bar(
            x=["Healthy", "Review", "Critical", "Projected"],
            y=[counts["HEALTHY"], counts["REVIEW_NEEDED"], counts["CRITICAL"], counts["PROJECTED"]],
            marker_color=[_SC["HEALTHY"], _SC["REVIEW_NEEDED"], _SC["CRITICAL"], _SC["PROJECTED"]],
            text=[counts["HEALTHY"], counts["REVIEW_NEEDED"], counts["CRITICAL"], counts["PROJECTED"]],
            textposition="outside",
            textfont=dict(size=12, color="#333"),
        ))
        fig.update_layout(
            title=dict(text=f"{dom_icon} {dom_label} Health", font=dict(size=13, color="#333")),
            height=230,
            margin=dict(l=10, r=10, t=44, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            yaxis=dict(visible=False),
            xaxis=dict(tickfont=dict(size=10)),
        )
        with [dc1, dc2, dc3][col_idx]:
            st.plotly_chart(fig, use_container_width=True)

    # Volume by Region bar chart
    st.markdown("<br>", unsafe_allow_html=True)
    reg_vol_data = []
    for reg in reg_list:
        rv = health_df[(health_df["date"].dt.date == sel_date) & (health_df["region"] == reg)]
        reg_vol_data.append({
            "region": reg,
            "volume": int(rv["pk_gross_tot"].sum()) if not rv.empty else 0,
            "color": region_color(reg),
        })

    fig_rv = go.Figure(go.Bar(
        x=[d["region"] for d in reg_vol_data],
        y=[d["volume"] for d in reg_vol_data],
        marker_color=[d["color"] for d in reg_vol_data],
        text=[f"{d['volume']:,}" for d in reg_vol_data],
        textposition="outside",
        textfont=dict(size=12),
    ))
    fig_rv.update_layout(
        title=dict(text=f"📦 Volume by Region — {sel_date}", font=dict(size=13, color="#333")),
        height=240,
        margin=dict(l=40, r=20, t=44, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Packages",
        showlegend=False,
    )
    st.plotly_chart(fig_rv, use_container_width=True)

else:
    st.info("No data for the selected date / region. Adjust the filters above.")


# ════════════════════════════════════════════════════════════════════════════
# [D] STATION HEALTH — PER-REGION COMPARISON VIEW
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
label_suffix = f" · {sel_date}" + (f" · {sel_reg}" if sel_reg != "All Regions" else "")
_sec(f"🏢 Station Health — Region Comparison{label_suffix}")

# Status background tints for cards
_BG = {
    "CRITICAL":     "linear-gradient(135deg,#fff5f5 0%,#fff 100%)",
    "REVIEW_NEEDED":"linear-gradient(135deg,#fffbf0 0%,#fff 100%)",
    "HEALTHY":      "linear-gradient(135deg,#f0fff4 0%,#fff 100%)",
    "PROJECTED":    "linear-gradient(135deg,#f0f4ff 0%,#fff 100%)",
    "UNKNOWN":      "linear-gradient(135deg,#fafafa 0%,#fff 100%)",
}

def _cmp_row(icon, label, req_val, act_val, act_label, status, no_baseline_msg="—"):
    """Build one domain comparison row as HTML."""
    st_color = _SC.get(status, _GREY)
    st_text  = _SL.get(status, status)
    badge    = (f'<span style="background:{st_color};color:#fff;border-radius:3px;'
                f'padding:2px 7px;font-size:9px;font-weight:700;white-space:nowrap;">'
                f'{st_text}</span>')
    if act_val:
        detail = (
            f'<span style="color:#555;">Req</span> <b>{req_val}</b> &nbsp;'
            f'<span style="color:#aaa;font-size:10px;">vs</span>&nbsp; '
            f'<span style="color:#555;">Actual</span> <b>{act_val}</b> '
            f'<span style="color:#aaa;font-size:10px;">({act_label})</span>'
        )
    else:
        detail = (
            f'<span style="color:#555;">Req</span> <b>{req_val}</b> &nbsp;'
            f'<span style="color:#aaa;font-size:10px;">· {no_baseline_msg}</span>'
        )
    return (
        f'<tr style="border-bottom:1px solid #f0f0f0;">'
        f'<td style="padding:7px 8px;font-size:13px;width:26px;">{icon}</td>'
        f'<td style="padding:7px 4px;font-size:11px;color:#333;width:80px;">{label}</td>'
        f'<td style="padding:7px 6px;font-size:11px;">{detail}</td>'
        f'<td style="padding:7px 8px;text-align:right;width:90px;">{badge}</td>'
        f'</tr>'
    )

if day_h.empty:
    st.info("No stations match the current filters.")
else:
    show_regions = [sel_reg] if sel_reg != "All Regions" else [r for r in reg_list]
    for reg in show_regions:
        reg_rows = day_h[day_h["region"] == reg] if "region" in day_h.columns else day_h
        if reg_rows.empty:
            continue
        rc = region_color(reg)
        slist = reg_rows.sort_values("pk_gross_tot", ascending=False).to_dict("records")
        n_tot   = len(slist)
        n_hlth_ = sum(1 for s in slist
                      if _worst(s.get("area_status","UNKNOWN"),
                                s.get("resource_status","UNKNOWN"),
                                s.get("courier_status","UNKNOWN")) == "HEALTHY")
        n_rev_  = sum(1 for s in slist
                      if _worst(s.get("area_status","UNKNOWN"),
                                s.get("resource_status","UNKNOWN"),
                                s.get("courier_status","UNKNOWN")) == "REVIEW_NEEDED")
        n_crit_ = sum(1 for s in slist
                      if _worst(s.get("area_status","UNKNOWN"),
                                s.get("resource_status","UNKNOWN"),
                                s.get("courier_status","UNKNOWN")) == "CRITICAL")

        # Region header bar
        st.markdown(f"""
<div style="background:linear-gradient(90deg,{rc}22 0%,transparent 100%);
    border-left:5px solid {rc};border-radius:6px;
    padding:10px 16px;margin:14px 0 10px 0;display:flex;
    justify-content:space-between;align-items:center;">
  <span style="font-weight:800;font-size:14px;color:{rc};text-transform:uppercase;letter-spacing:0.8px;">
    {reg} Region &nbsp;·&nbsp; {n_tot} Stations
  </span>
  <span style="font-size:12px;color:#555;">
    ✅ {n_hlth_} Healthy &nbsp; ⚠️ {n_rev_} Review &nbsp; 🚨 {n_crit_} Critical
  </span>
</div>""", unsafe_allow_html=True)

        # 2-per-row station cards
        for rs in range(0, len(slist), 2):
            chunk = slist[rs:rs + 2]
            gcols = st.columns(2)
            for ci, s in enumerate(chunk):
                loc   = s.get("loc_id", "—")
                vol   = int(s.get("pk_gross_tot", 0))
                a_st  = s.get("area_status",     "UNKNOWN")
                r_st  = s.get("resource_status", "UNKNOWN")
                c_st  = s.get("courier_status",  "UNKNOWN")
                worst = _worst(a_st, r_st, c_st)
                bdr   = _SC.get(worst, _GREY)
                bg    = _BG.get(worst, _BG["UNKNOWN"])

                ca    = s.get("calc_area",    0)
                cr_   = s.get("calc_agents",  0)
                cc    = s.get("calc_couriers",0)
                util  = s.get("area_util_pct",0)
                eff   = s.get("courier_eff",  0)
                moa   = s.get("master_ops_area", 0)
                mag   = s.get("master_agents",   0)
                mcr   = s.get("master_couriers", 0)
                fd_r  = s.get("famis_derived_res", False)
                fd_c  = s.get("famis_derived_cou", False)

                # Area: always show Required; show Actual/Capacity if available
                if moa > 0:
                    a_row = _cmp_row("📐", "Area",
                                     f"{ca:,.0f} m²", f"{moa:,.0f} m²",
                                     f"{util:.0f}% utilized", a_st)
                else:
                    a_row = _cmp_row("📐", "Area",
                                     f"{ca:,.0f} m²", None, "",
                                     a_st, "upload Facility Master for capacity")

                # Resource
                r_lbl = "FAMIS FTE" if fd_r else "Facility Master"
                if mag > 0:
                    r_row = _cmp_row("👥", "Resource",
                                     f"{cr_:.0f} agents", f"{mag:.0f}",
                                     r_lbl, r_st)
                else:
                    r_row = _cmp_row("👥", "Resource",
                                     f"{cr_:.0f} agents", None, "",
                                     r_st, "no baseline available")

                # Courier
                c_lbl = "FAMIS derived" if fd_c else "Facility Master"
                if mcr > 0:
                    c_row = _cmp_row("🚚", "Courier",
                                     f"{cc:.0f} couriers", f"{mcr}",
                                     c_lbl, c_st)
                else:
                    c_row = _cmp_row("🚚", "Courier",
                                     f"{cc:.0f} couriers", None, "",
                                     c_st, "no baseline available")

                worst_badge = (
                    f'<span style="background:{bdr};color:#fff;border-radius:4px;'
                    f'padding:3px 10px;font-size:10px;font-weight:700;">'
                    f'{_SL.get(worst, worst)}</span>'
                )

                with gcols[ci]:
                    st.markdown(f"""
<div style="border-left:5px solid {bdr};border-radius:8px;
    background:{bg};
    box-shadow:0 2px 10px rgba(0,0,0,0.07);
    margin-bottom:14px;overflow:hidden;">
  <!-- Card header -->
  <div style="padding:12px 16px 8px 16px;border-bottom:1px solid #eee;
      display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-weight:800;font-size:16px;color:#1a1a1a;">{loc}</div>
      <div style="font-size:11px;color:#888;margin-top:2px;">
        {vol:,} packages &nbsp;·&nbsp; {reg}
      </div>
    </div>
    <div style="margin-top:2px;">{worst_badge}</div>
  </div>
  <!-- Comparison table -->
  <div style="padding:4px 8px 10px 8px;">
    <table style="width:100%;border-collapse:collapse;">
      {a_row}{r_row}{c_row}
    </table>
  </div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# [E] VOLUME TREND  (last 30 days)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_sec("📈 Volume Trend — Last 30 Days")

cutoff     = famis_df["date"].max() - timedelta(days=30)
trend_src  = famis_df if sel_reg == "All Regions" else famis_df[famis_df["region"] == sel_reg]
trend_df   = (
    trend_src[trend_src["date"] >= cutoff]
    .groupby("date", as_index=False)["pk_gross_tot"].sum()
    .sort_values("date")
)

if not trend_df.empty:
    # Per-region daily lines
    fig_tr = go.Figure()
    for reg in reg_list:
        reg_trend = (
            famis_df[(famis_df["region"] == reg) & (famis_df["date"] >= cutoff)]
            .groupby("date", as_index=False)["pk_gross_tot"].sum()
            .sort_values("date")
        )
        if reg_trend.empty:
            continue
        fig_tr.add_trace(go.Scatter(
            x=reg_trend["date"], y=reg_trend["pk_gross_tot"],
            name=reg, mode="lines+markers",
            line=dict(color=region_color(reg), width=2),
            marker=dict(size=4),
        ))

    # Network total area
    fig_tr.add_trace(go.Scatter(
        x=trend_df["date"], y=trend_df["pk_gross_tot"],
        name="Network Total", mode="lines",
        line=dict(color=_PURPLE, width=3, dash="dot"),
        fill="tozeroy", fillcolor="rgba(77,20,140,0.07)",
    ))
    fig_tr.update_layout(
        height=320,
        margin=dict(l=50, r=20, t=30, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Packages",
        xaxis_title="Date",
        legend=dict(orientation="h", x=0, y=1.1),
    )
    st.plotly_chart(fig_tr, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# [F] DEEP-DIVE — Region then Station
# ════════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
_sec("🔍 Deep-Dive Analysis — Region · Station")

# ── F1: Region-level breakdown ────────────────────────────────────────────
st.markdown("##### 🗺️ Region Health Breakdown")
for reg in reg_list:
    reg_day = day_h[day_h["region"] == reg] if "region" in day_h.columns else pd.DataFrame()
    if reg_day.empty:
        continue
    rc_ = region_color(reg)
    n_tot  = len(reg_day)
    n_hlth_ = sum(1 for _, r in reg_day.iterrows()
                  if _worst(r.get("area_status","UNKNOWN"), r.get("resource_status","UNKNOWN"),
                            r.get("courier_status","UNKNOWN")) == "HEALTHY")
    n_rev_  = sum(1 for _, r in reg_day.iterrows()
                  if _worst(r.get("area_status","UNKNOWN"), r.get("resource_status","UNKNOWN"),
                            r.get("courier_status","UNKNOWN")) == "REVIEW_NEEDED")
    n_crit_ = sum(1 for _, r in reg_day.iterrows()
                  if _worst(r.get("area_status","UNKNOWN"), r.get("resource_status","UNKNOWN"),
                            r.get("courier_status","UNKNOWN")) == "CRITICAL")
    n_proj_ = n_tot - n_hlth_ - n_rev_ - n_crit_
    reg_vol = int(reg_day["pk_gross_tot"].sum())
    reg_ag  = round(reg_day["calc_agents"].sum(), 0) if "calc_agents" in reg_day.columns else 0
    reg_cr  = round(reg_day["calc_couriers"].sum(), 0) if "calc_couriers" in reg_day.columns else 0

    with st.expander(
        f"**{reg} Region** — {n_tot} stations · {reg_vol:,} pkgs · "
        f"✅{n_hlth_} ⚠️{n_rev_} 🚨{n_crit_} 🔵{n_proj_}",
        expanded=True,
    ):
        rc1, rc2, rc3, rc4, rc5 = st.columns(5)
        with rc1:
            render_kpi_card("Stations", str(n_tot), reg, color=rc_)
        with rc2:
            render_kpi_card("Volume", f"{reg_vol:,}", "packages", color=rc_)
        with rc3:
            render_kpi_card("Healthy", str(n_hlth_), f"{round(n_hlth_/n_tot*100) if n_tot else 0}% stations", color=_GREEN)
        with rc4:
            render_kpi_card("Req Agents", f"{int(reg_ag):,}", "calculated", color=rc_)
        with rc5:
            render_kpi_card("Req Couriers", f"{int(reg_cr):,}", "calculated", color=rc_)

        # Domain status bar per region
        dom_cols_ = st.columns(3)
        for dc_i, (dcol, dlbl) in enumerate([
            ("area_status","Area"), ("resource_status","Resource"), ("courier_status","Courier")
        ]):
            cnt_ = {s: _cnt(reg_day, dcol, s) for s in ["HEALTHY","REVIEW_NEEDED","CRITICAL","PROJECTED"]}
            fig_r = go.Figure(go.Bar(
                x=["Healthy","Review","Critical","Projected"],
                y=[cnt_["HEALTHY"],cnt_["REVIEW_NEEDED"],cnt_["CRITICAL"],cnt_["PROJECTED"]],
                marker_color=[_SC["HEALTHY"],_SC["REVIEW_NEEDED"],_SC["CRITICAL"],_SC["PROJECTED"]],
                text=[cnt_["HEALTHY"],cnt_["REVIEW_NEEDED"],cnt_["CRITICAL"],cnt_["PROJECTED"]],
                textposition="outside", textfont=dict(size=11),
            ))
            fig_r.update_layout(
                title=dict(text=dlbl, font=dict(size=11, color="#555")),
                height=180, margin=dict(l=5,r=5,t=28,b=5),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False, yaxis=dict(visible=False),
                xaxis=dict(tickfont=dict(size=9)),
            )
            with dom_cols_[dc_i]:
                st.plotly_chart(fig_r, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("##### 📌 Station-Level Historical Deep-Dive")

drill_st = st.selectbox(
    "Select a station to view full historical breakdown",
    ["— select —"] + all_stn_ids,
    key="an_drill",
)

if drill_st and drill_st != "— select —":
    st_hist = health_df[health_df["loc_id"] == drill_st].sort_values("date")
    if st_hist.empty:
        st.info(f"No historical data for **{drill_st}**.")
    else:
        latest = st_hist.iloc[-1]
        reg_l  = latest.get("region", "—") if "region" in st_hist.columns else "—"
        st.markdown(f"#### {drill_st} &nbsp;·&nbsp; Region: **{reg_l}**")

        # Summary KPIs
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            render_kpi_card("Latest Volume", f"{int(latest.get('pk_gross_tot',0)):,}",
                            str(latest["date"].date()), color=_PURPLE)
        with d2:
            a_s = latest.get("area_status","UNKNOWN")
            render_kpi_card("Area", _SL.get(a_s, a_s),
                            f"Calc: {latest.get('calc_area',0):.0f} m²",
                            color=_SC.get(a_s, _GREY))
        with d3:
            r_s = latest.get("resource_status","UNKNOWN")
            render_kpi_card("Resource", _SL.get(r_s, r_s),
                            f"Req: {latest.get('calc_agents',0):.1f} agents",
                            color=_SC.get(r_s, _GREY))
        with d4:
            c_s = latest.get("courier_status","UNKNOWN")
            render_kpi_card("Courier", _SL.get(c_s, c_s),
                            f"Req: {latest.get('calc_couriers',0):.0f}",
                            color=_SC.get(c_s, _GREY))

        # Charts
        tab_v, tab_ar, tab_rc = st.tabs(["📦 Volume", "📐 Area", "👥🚚 Resource & Courier"])

        with tab_v:
            fv = go.Figure()
            fv.add_trace(go.Bar(x=st_hist["date"], y=st_hist["pk_gross_tot"],
                                name="Volume", marker_color=_PURPLE, opacity=0.85))
            if len(st_hist) >= 3:
                roll = st_hist["pk_gross_tot"].rolling(7, min_periods=1).mean()
                fv.add_trace(go.Scatter(x=st_hist["date"], y=roll,
                                        name="7-day avg", mode="lines",
                                        line=dict(color=_ORANGE, width=2, dash="dot")))
            fv.update_layout(height=300, margin=dict(l=40,r=20,t=30,b=40),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              yaxis_title="Packages", legend=dict(orientation="h",x=0,y=1.1))
            st.plotly_chart(fv, use_container_width=True)

        with tab_ar:
            fa = go.Figure()
            if "calc_area" in st_hist.columns and st_hist["calc_area"].sum() > 0:
                fa.add_trace(go.Scatter(x=st_hist["date"], y=st_hist["calc_area"],
                                        name="Required (m²)", mode="lines+markers",
                                        line=dict(color=_PURPLE, width=2)))
            moa = float(latest.get("master_ops_area", 0))
            if moa > 0:
                fa.add_hline(y=moa, line_dash="dash", line_color=_ORANGE,
                             annotation_text=f"Facility: {moa:.0f} m²")
            fa.update_layout(height=300, margin=dict(l=40,r=40,t=30,b=40),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              yaxis_title="Area (m²)", legend=dict(orientation="h",x=0,y=1.1))
            st.plotly_chart(fa, use_container_width=True)

        with tab_rc:
            tc1, tc2 = st.columns(2)
            with tc1:
                fr = go.Figure()
                if "calc_agents" in st_hist.columns:
                    fr.add_trace(go.Scatter(x=st_hist["date"], y=st_hist["calc_agents"],
                                            name="Required Agents", mode="lines+markers",
                                            line=dict(color=_PURPLE, width=2)))
                    mag = float(latest.get("master_agents", 0))
                    if mag > 0:
                        fr.add_hline(y=mag, line_dash="dash", line_color=_ORANGE,
                                     annotation_text=f"Master: {mag:.0f}")
                fr.update_layout(height=280, margin=dict(l=40,r=20,t=30,b=40),
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  yaxis_title="Agents", title="Agent Requirement")
                st.plotly_chart(fr, use_container_width=True)
            with tc2:
                fc_ = go.Figure()
                if "calc_couriers" in st_hist.columns:
                    fc_.add_trace(go.Scatter(x=st_hist["date"], y=st_hist["calc_couriers"],
                                             name="Required Couriers", mode="lines+markers",
                                             line=dict(color="#0055A5", width=2)))
                    mcr = int(latest.get("master_couriers", 0))
                    if mcr > 0:
                        fc_.add_hline(y=mcr, line_dash="dash", line_color=_ORANGE,
                                      annotation_text=f"Master: {mcr}")
                fc_.update_layout(height=280, margin=dict(l=40,r=20,t=30,b=40),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   yaxis_title="Couriers", title="Courier Requirement")
                st.plotly_chart(fc_, use_container_width=True)

        # Status history table
        st.markdown("**Status History**")
        hist_tbl = st_hist[[c for c in [
            "date","pk_gross_tot","area_status","resource_status","courier_status",
            "calc_area","calc_agents","calc_couriers","area_util_pct","courier_eff",
        ] if c in st_hist.columns]].copy()
        if "date" in hist_tbl.columns:
            hist_tbl["date"] = hist_tbl["date"].dt.strftime("%d %b %Y")
        if "pk_gross_tot" in hist_tbl.columns:
            hist_tbl["pk_gross_tot"] = hist_tbl["pk_gross_tot"].map(lambda x: f"{int(x):,}")
        hist_tbl = hist_tbl.rename(columns={
            "date":"Date","pk_gross_tot":"Volume",
            "area_status":"Area","resource_status":"Resource","courier_status":"Courier",
            "calc_area":"Calc Area (m²)","calc_agents":"Req Agents","calc_couriers":"Req Couriers",
            "area_util_pct":"Area Util%","courier_eff":"Cour Eff%",
        })
        st.dataframe(hist_tbl, hide_index=True, use_container_width=True)

else:
    st.info("👆 Select a station above to view its full historical breakdown.")


# ════════════════════════════════════════════════════════════════════════════
# [G] SYSTEM CONFIGURATION  (for field engineers — collapsed by default)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("---")
with st.expander("⚙️ System Configuration — TACT & Area Constants", expanded=False):
    st.caption(
        "These parameters control all AERO planning calculations. "
        "Changes are saved immediately and reflected across all planning tools."
    )
    cfg      = load_config()
    area_cfg = load_area_config()

    osa    = cfg.setdefault("OSA", {})
    c_cfg_ = cfg.setdefault("COURIER", {})
    ac_    = area_cfg.setdefault("AREA_CONSTANTS", {})

    st.markdown("**📐 Area Constants**")
    ca1, ca2 = st.columns(2)
    with ca1:
        ac_["PALLET_AREA"] = st.number_input(
            "Pallet Area (sq.ft)", value=float(ac_.get("PALLET_AREA",16)), step=1.0, key="g_pa")
        ac_["AISLE_PERCENT"] = st.number_input(
            "Aisle Percent", value=float(ac_.get("AISLE_PERCENT",0.15)),
            step=0.01, min_value=0.0, max_value=0.5, key="g_ap")
    with ca2:
        ac_["CAGE_PALLET_AREA"] = st.number_input(
            "Cage Pallet Area (sq.ft)", value=float(ac_.get("CAGE_PALLET_AREA",25)), step=1.0, key="g_cpa")
        ac_["STACKING_PER_PALLET"] = st.number_input(
            "Stacking Factor", value=int(ac_.get("STACKING_PER_PALLET",20)), step=1, key="g_spd")

    st.markdown("**🚚 Courier Constants**")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        c_cfg_["PK_ST_OR"] = st.number_input(
            "PK_ST_OR", value=float(c_cfg_.get("PK_ST_OR",2.5)), step=0.1, min_value=0.1, key="g_pks")
        c_cfg_["ST_HR_OR"] = st.number_input(
            "ST_HR_OR", value=float(c_cfg_.get("ST_HR_OR",4.0)), step=0.1, min_value=0.1, key="g_sth")
    with cc2:
        c_cfg_["PRODUCTIVITY_HRS"] = st.number_input(
            "Productivity Hrs", value=float(c_cfg_.get("PRODUCTIVITY_HRS",7.0)), step=0.5, key="g_ph")
        c_cfg_["SHIFT_HOURS"] = st.number_input(
            "Shift Hours", value=float(c_cfg_.get("SHIFT_HOURS",9.0)), step=0.5, key="g_sh")
    with cc3:
        c_cfg_["ABSENTEEISM_PCT"] = st.number_input(
            "Absenteeism %", value=float(c_cfg_.get("ABSENTEEISM_PCT",16.0)),
            step=1.0, min_value=0.0, max_value=100.0, key="g_abs")
        c_cfg_["TRAINING_PCT"] = st.number_input(
            "Training %", value=float(c_cfg_.get("TRAINING_PCT",11.0)),
            step=1.0, min_value=0.0, max_value=100.0, key="g_tr")

    s1, s2 = st.columns([6,1])
    with s2:
        if st.button("💾 Save", use_container_width=True, type="primary"):
            try:
                save_config(cfg)
                save_area_config(area_cfg)
                _build_health_table.clear()
                st.success("✅ Saved.")
            except Exception as ex:
                st.error(f"Save failed: {ex}")

render_footer("ANALYTICS")
