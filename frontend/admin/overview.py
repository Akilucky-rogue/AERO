# ============================================================
# AERO — Admin Overview  [frontend/admin/overview.py]
# Read-only operations dashboard for the Operations role.
# Provides aggregated visibility across Field, Gateway,
# Services and System — ZERO input fields or calculators.
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
import plotly.express as px
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.ui.components import render_info_banner, render_kpi_card, _PURPLE, _ORANGE, _GREEN, _RED
from aero.region.mapper import classify_dataframe, region_order, region_color
from aero.auth.service import list_users, get_current_user

logger = logging.getLogger(__name__)

_STATUS_COLORS = {
    "HEALTHY":       "#008A00",
    "REVIEW_NEEDED": "#FFB800",
    "CRITICAL":      "#DE002E",
    "UNKNOWN":       "#888888",
}


# ── Data loaders ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def _load_famis() -> pd.DataFrame:
    try:
        from aero.data.famis_store import db_available, load_famis_from_db, famis_row_count  # type: ignore
        if db_available() and famis_row_count() > 0:
            df = load_famis_from_db()
            if df is not None and not df.empty:
                return df
    except Exception:
        pass
    try:
        from aero.data.excel_store import read_famis_uploads
        return read_famis_uploads()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def _db_status() -> dict:
    try:
        from aero.data.famis_store import db_available, famis_row_count  # type: ignore
        ok = db_available()
        rows = famis_row_count() if ok else 0
        return {"connected": ok, "rows": rows}
    except Exception:
        return {"connected": False, "rows": 0}


# ── Page ──────────────────────────────────────────────────────────────────────
render_header(
    "OPERATIONS OVERVIEW",
    "Enterprise-Wide Visibility — Field · Gateway · Services · System",
    logo_height=80,
    badge="ADMIN",
)

user = get_current_user()
st.caption(f"Signed in as **{user.get('display_name', user.get('user_id',''))}** · Role: **{user.get('role','')}** · Read-only view")

# ── System status bar ─────────────────────────────────────────────────────────
db_stat = _db_status()
if db_stat["connected"]:
    render_info_banner(
        "PostgreSQL Connected",
        f"Database is live · <b>{db_stat['rows']:,}</b> FAMIS records stored · All systems operational.",
        accent=_GREEN,
    )
else:
    render_info_banner(
        "PostgreSQL Offline",
        "Database not connected — analytics sourced from local Excel store. "
        "Configure PostgreSQL for real-time data.",
        accent=_ORANGE,
    )

if st.button("🔄 Refresh All Data"):
    _load_famis.clear()
    _db_status.clear()
    st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Load FAMIS
famis_raw = _load_famis()
famis_df  = pd.DataFrame()
if famis_raw is not None and not famis_raw.empty:
    famis_df = famis_raw.copy()
    famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
    famis_df = famis_df[famis_df["date"].notna()]
    famis_df = classify_dataframe(famis_df, "loc_id")

# ════════════════════════════════════════════════════════════════════════════
# TOP KPI ROW
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Key Metrics — Network Snapshot
</div>""", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    n_records = len(famis_df) if not famis_df.empty else 0
    render_kpi_card("FAMIS Records", f"{n_records:,}", "total rows loaded", color=_PURPLE)
with k2:
    n_stations = famis_df["loc_id"].nunique() if not famis_df.empty and "loc_id" in famis_df.columns else 0
    render_kpi_card("Stations", str(n_stations), "unique locations", color=_PURPLE)
with k3:
    if not famis_df.empty and "date" in famis_df.columns:
        latest_date = famis_df["date"].max().strftime("%d %b %Y")
        render_kpi_card("Latest Date", latest_date, "most recent FAMIS row", color=_GREEN)
    else:
        render_kpi_card("Latest Date", "—", "no data", color="#888")
with k4:
    if not famis_df.empty and "pk_gross_tot" in famis_df.columns:
        latest_day = famis_df[famis_df["date"] == famis_df["date"].max()]
        total_vol = int(latest_day["pk_gross_tot"].sum())
        render_kpi_card("Latest Day Volume", f"{total_vol:,}", "packages", color=_ORANGE)
    else:
        render_kpi_card("Latest Day Volume", "—", "no data", color="#888")
with k5:
    try:
        users_df = list_users()
        n_users = len(users_df) if not users_df.empty else 0
    except Exception:
        n_users = "—"
    render_kpi_card("Active Users", str(n_users), "registered accounts", color=_PURPLE)

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# REGION-LEVEL VOLUME BREAKDOWN
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Region-Level Field Operations
</div>""", unsafe_allow_html=True)

if famis_df.empty:
    st.info("No FAMIS data available. A Field Engineer needs to upload data via the Data Upload Centre.")
else:
    # Region summary (latest date)
    latest = famis_df[famis_df["date"] == famis_df["date"].max()]
    reg_cols = st.columns(3)
    for i, reg in enumerate(["South", "West", "North"]):
        r_slice = latest[latest["region"] == reg]
        n = len(r_slice)
        vol = int(r_slice["pk_gross_tot"].sum()) if "pk_gross_tot" in r_slice.columns else 0
        n_st = r_slice["loc_id"].nunique() if "loc_id" in r_slice.columns else 0
        rc = region_color(reg)
        with reg_cols[i]:
            st.markdown(f"""
<div style="border:2px solid {rc};border-radius:10px;padding:14px 18px;
    background:linear-gradient(135deg,{rc}18 0%,#fff 100%);margin-bottom:12px;">
    <div style="font-size:13px;font-weight:800;color:{rc};letter-spacing:0.5px;">{reg.upper()} REGION</div>
    <div style="font-size:26px;font-weight:700;color:#222;margin:4px 0;">{vol:,}</div>
    <div style="font-size:11px;color:#555;">packages across {n_st} station(s)</div>
</div>""", unsafe_allow_html=True)

    # Volume by region (last 30 days)
    cutoff = famis_df["date"].max() - timedelta(days=30)
    trend = (
        famis_df[famis_df["date"] >= cutoff]
        .groupby(["date", "region"], as_index=False)["pk_gross_tot"].sum()
        .sort_values("date")
    )
    if not trend.empty:
        region_palette = {r: region_color(r) for r in region_order()}
        fig = px.line(
            trend, x="date", y="pk_gross_tot", color="region",
            color_discrete_map=region_palette,
            labels={"pk_gross_tot": "Packages", "date": "Date", "region": "Region"},
            title="Volume Trend by Region — Last 30 Days",
        )
        fig.update_layout(
            height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=50, b=40),
            legend=dict(orientation="h", x=0, y=1.15),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Station volume table (latest date, read-only)
    st.markdown("**Station Volume Summary — Latest Date**")
    tbl_cols = ["loc_id", "region", "pk_gross_tot", "pk_gross_inb", "pk_gross_outb", "fte_tot"]
    tbl_cols = [c for c in tbl_cols if c in latest.columns]
    tbl = latest[tbl_cols].sort_values(["region", "loc_id"]).copy()
    tbl = tbl.rename(columns={
        "loc_id": "Station", "region": "Region", "pk_gross_tot": "Total Vol",
        "pk_gross_inb": "Inbound", "pk_gross_outb": "Outbound", "fte_tot": "FTE",
    })
    st.dataframe(tbl, use_container_width=True, hide_index=True)

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# GATEWAY & SERVICES STATUS
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    Gateway & Services
</div>""", unsafe_allow_html=True)

gs1, gs2 = st.columns(2)
with gs1:
    st.markdown("""
<div style="border:2px solid #1A5276;border-radius:10px;padding:14px 18px;background:#f0f4f8;">
    <div style="font-size:13px;font-weight:800;color:#1A5276;">✈️  GATEWAY OPERATIONS</div>
    <div style="margin-top:8px;font-size:12px;color:#555;">
        Cross-dock throughput monitoring, hub connectivity analytics, and sort-plan
        adherence tracking. <br><br>
        <span style="background:#FFB800;color:#fff;border-radius:4px;padding:2px 8px;
        font-size:11px;font-weight:700;">Phase 2 — Upcoming</span>
    </div>
</div>""", unsafe_allow_html=True)
with gs2:
    st.markdown("""
<div style="border:2px solid #145A32;border-radius:10px;padding:14px 18px;background:#f0f8f4;">
    <div style="font-size:13px;font-weight:800;color:#145A32;">🛎️  SERVICES OPERATIONS</div>
    <div style="margin-top:8px;font-size:12px;color:#555;">
        Operational analytics and workflows for the Services team including
        predictive insights and purpose-built dashboards. <br><br>
        <span style="background:#FFB800;color:#fff;border-radius:4px;padding:2px 8px;
        font-size:11px;font-weight:700;">New Use Case — In Development</span>
    </div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT (read-only view) + DB status
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    User Accounts
</div>""", unsafe_allow_html=True)

try:
    users_df = list_users()
    if users_df.empty:
        st.info("No users found.")
    else:
        st.dataframe(users_df, use_container_width=True, hide_index=True)
except Exception as e:
    st.info(f"User data unavailable: {e}")

st.markdown("<br>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# DATABASE STATUS PANEL (read-only)
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="font-weight:700;color:#4D148C;font-size:14px;text-transform:uppercase;
    letter-spacing:0.8px;border-bottom:2px solid #4D148C;padding-bottom:6px;margin-bottom:14px;">
    System Status
</div>""", unsafe_allow_html=True)

sys_c1, sys_c2, sys_c3 = st.columns(3)
with sys_c1:
    status_label = "🟢 Connected" if db_stat["connected"] else "🔴 Offline"
    render_kpi_card("PostgreSQL", status_label, f"{db_stat['rows']:,} FAMIS rows", color=_GREEN if db_stat["connected"] else _RED)
with sys_c2:
    try:
        from aero.config.settings import CONFIG_FILE
        cfg_exists = os.path.exists(CONFIG_FILE)
        render_kpi_card("TACT Config", "✅ Present" if cfg_exists else "⚠️ Missing",
                        CONFIG_FILE, color=_GREEN if cfg_exists else _ORANGE)
    except Exception:
        render_kpi_card("TACT Config", "—", "unavailable", color="#888")
with sys_c3:
    import importlib
    mods = []
    for mod in ["psycopg2", "plotly", "pandas", "streamlit"]:
        try:
            importlib.import_module(mod)
            mods.append(f"✅ {mod}")
        except ImportError:
            mods.append(f"❌ {mod}")
    render_kpi_card("Core Packages", f"{sum(1 for m in mods if '✅' in m)}/{len(mods)}", "installed", color=_GREEN)

render_footer("ADMIN")
