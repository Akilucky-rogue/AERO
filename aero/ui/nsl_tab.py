"""
aero/ui/nsl_tab.py — NSL + NSL+24 analytics tab component.

Rendered inside frontend/field/analytics.py section [F].

NSL metric definitions
──────────────────────
  NSL %     = nsl_ot_vol / tot_vol × 100
              (percentage of shipments delivered on/before commitment time)

  NSL+24 %  = (tot_vol − mbg_f_vol) / tot_vol × 100   [when MBG cols present]
              MBG_F_VOL = shipments that exceeded MBG window (commitment + ~24h),
              so (tot − mbg_f) = all shipments within commitment + 24 h.
              Fallback when no MBG data: (nsl_ot + nsl_f × 0.25) / tot_vol × 100
              (conservative estimate: ~25% of missed-NSL parcels arrive within +24h)
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_PURPLE = "#4D148C"
_ORANGE = "#FF6200"
_GREEN  = "#008A00"
_RED    = "#DE002E"
_BLUE   = "#007AB7"

_NSL_TARGET   = 97.0   # standard FedEx NSL target %
_NSL24_TARGET = 99.0   # NSL+24 target %


# ────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────

def _sdiv(a, b, default: float = 0.0) -> float:
    try:
        return float(a) / float(b) if float(b) > 0 else default
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def _nsl_color(pct: float, target: float = _NSL_TARGET) -> str:
    if pct >= target:
        return _GREEN
    if pct >= target - 3.0:
        return _ORANGE
    return _RED


def _summary(df: pd.DataFrame) -> dict:
    """Network-level NSL summary aggregated from the supplied DataFrame."""
    out = dict(
        tot_vol=0, nsl_ot_vol=0, nsl_f_vol=0,
        mbg_ot_vol=0, mbg_f_vol=0,
        nsl_pct=0.0, nsl24_pct=0.0, has_mbg=False,
    )
    if df is None or df.empty:
        return out
    for c in ["tot_vol", "nsl_ot_vol", "nsl_f_vol", "mbg_ot_vol", "mbg_f_vol"]:
        if c in df.columns:
            out[c] = int(pd.to_numeric(df[c], errors="coerce").fillna(0).sum())

    out["nsl_pct"] = _sdiv(out["nsl_ot_vol"], out["tot_vol"]) * 100
    has_mbg = out["mbg_ot_vol"] > 0 or out["mbg_f_vol"] > 0
    out["has_mbg"] = has_mbg
    if has_mbg:
        out["nsl24_pct"] = _sdiv(out["tot_vol"] - out["mbg_f_vol"], out["tot_vol"]) * 100
    else:
        within_24 = out["nsl_f_vol"] * 0.25
        out["nsl24_pct"] = _sdiv(out["nsl_ot_vol"] + within_24, out["tot_vol"]) * 100
    return out


# ────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────

def render_nsl_tab(nsl_df: Optional[pd.DataFrame] = None) -> None:
    """Render the full NSL + NSL+24 analytics section.

    If *nsl_df* is None the function reads ``st.session_state["station_nsl_data"]``.
    """
    from aero.ui.components import render_kpi_card, render_info_banner

    if nsl_df is None:
        nsl_df = st.session_state.get("station_nsl_data")

    if nsl_df is None or nsl_df.empty:
        render_info_banner(
            "No NSL Data Available",
            "Upload a Station-Level NSL file via <b>Data Upload Centre → Station-Level NSL Data</b> "
            "to enable NSL analytics. The file must contain columns: "
            "<code>orig_loc_cd · tot_vol · nsl_ot_vol · nsl_f_vol</code> (plus optional MBG columns).",
            accent=_BLUE,
        )
        return

    df = nsl_df.copy()
    df.columns = df.columns.astype(str).str.strip().str.lower()

    # ── Normalise numeric columns ──────────────────────────────────────
    num_cols = ["tot_vol", "nsl_ot_vol", "nsl_f_vol", "mbg_ot_vol", "mbg_f_vol"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # ── Identify structural columns ───────────────────────────────────
    date_col    = next((c for c in ["month_date", "weekending_dt"] if c in df.columns and df[c].notna().any()), None)
    stn_col     = "orig_loc_cd"    if "orig_loc_cd"    in df.columns else None
    region_col  = "orig_region"    if "orig_region"    in df.columns else None
    service_col = "service"        if "service"        in df.columns else None

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # ── Filter controls ───────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        if service_col and df[service_col].notna().any():
            svc_opts = ["All Services"] + sorted(df[service_col].dropna().unique().tolist())
            sel_svc = st.selectbox("Service Type", svc_opts, key="nsl_svc_sel")
        else:
            sel_svc = "All Services"
    with fc2:
        if region_col and df[region_col].notna().any():
            reg_opts = ["All Regions"] + sorted(df[region_col].dropna().unique().tolist())
            sel_reg = st.selectbox("Region", reg_opts, key="nsl_reg_sel")
        else:
            sel_reg = "All Regions"
    with fc3:
        if stn_col and df[stn_col].notna().any():
            stn_opts = ["All Stations"] + sorted(df[stn_col].dropna().astype(str).unique().tolist())
            sel_stn = st.selectbox("Station", stn_opts, key="nsl_stn_sel")
        else:
            sel_stn = "All Stations"

    # Apply filters
    filt = df.copy()
    if sel_svc != "All Services" and service_col:
        filt = filt[filt[service_col] == sel_svc]
    if sel_reg != "All Regions" and region_col:
        filt = filt[filt[region_col] == sel_reg]
    if sel_stn != "All Stations" and stn_col:
        filt = filt[filt[stn_col].astype(str) == sel_stn]

    if filt.empty:
        st.warning("No NSL data matches the selected filters.")
        return

    # ── KPI summary ───────────────────────────────────────────────────
    sm = _summary(filt)
    nsl_pct  = sm["nsl_pct"]
    nsl24_pct = sm["nsl24_pct"]
    has_mbg  = sm["has_mbg"]

    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        render_kpi_card(
            "Network NSL %",
            f"{nsl_pct:.1f}%",
            f"Target ≥ {_NSL_TARGET}%",
            color=_nsl_color(nsl_pct),
        )
    with k2:
        src_label = "MBG-based" if has_mbg else "Estimated"
        render_kpi_card(
            "NSL+24 %",
            f"{nsl24_pct:.1f}%",
            f"{src_label} · Target ≥ {_NSL24_TARGET}%",
            color=_nsl_color(nsl24_pct, _NSL24_TARGET),
        )
    with k3:
        render_kpi_card("Total Shipments", f"{sm['tot_vol']:,}", "total volume", color=_PURPLE)
    with k4:
        render_kpi_card("On-Time Volume", f"{sm['nsl_ot_vol']:,}", "delivered on time", color=_GREEN)
    with k5:
        fail_color = _RED if sm["nsl_f_vol"] > 0 else _GREEN
        render_kpi_card("Failures", f"{sm['nsl_f_vol']:,}", "missed commitment", color=fail_color)

    if not has_mbg:
        st.caption(
            "ℹ️  **NSL+24** is estimated (25 % of NSL failures assumed within +24 h window). "
            "Upload NSL data with **mbg_ot_vol** and **mbg_f_vol** columns for an exact calculation."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: worst-stations bar + station summary table ─────────────
    chart_col, tbl_col = st.columns([1.3, 0.7])

    with chart_col:
        _render_worst_stations_chart(filt, stn_col, region_col)

    with tbl_col:
        _render_station_summary_table(filt, stn_col, has_mbg)

    # ── Row 2: trend chart ────────────────────────────────────────────
    if date_col:
        st.markdown("<br>", unsafe_allow_html=True)
        _render_nsl_trend(filt, date_col, has_mbg)

    # ── Row 3: service breakdown ──────────────────────────────────────
    if service_col and sel_svc == "All Services":
        st.markdown("<br>", unsafe_allow_html=True)
        _render_service_breakdown(filt, service_col)

    # ── Row 4: weekly pivot table ─────────────────────────────────────
    if date_col and stn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        _render_pivot_table(filt, date_col, stn_col)


# ────────────────────────────────────────────────────────────────────
# Sub-render helpers
# ────────────────────────────────────────────────────────────────────

def _render_worst_stations_chart(df: pd.DataFrame, stn_col, region_col) -> None:
    if not stn_col or df.empty:
        return
    grp = [stn_col] + ([region_col] if region_col else [])
    agg = {c: "sum" for c in ["tot_vol", "nsl_ot_vol", "nsl_f_vol"] if c in df.columns}
    if not agg:
        return
    sdf = df.groupby(grp, as_index=False).agg(agg)
    sdf = sdf[sdf["tot_vol"] > 0].copy()
    if "nsl_ot_vol" in sdf.columns:
        sdf["_nsl"] = sdf["nsl_ot_vol"] / sdf["tot_vol"] * 100
    else:
        return
    worst = sdf.nsmallest(20, "_nsl")
    if worst.empty:
        return

    colors = [_nsl_color(p) for p in worst["_nsl"]]
    fig = go.Figure(go.Bar(
        y=worst[stn_col].astype(str),
        x=worst["_nsl"].round(1),
        orientation="h",
        marker_color=colors,
        text=worst["_nsl"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        customdata=worst["tot_vol"],
        hovertemplate="<b>%{y}</b><br>NSL: %{x:.1f}%<br>Volume: %{customdata:,}<extra></extra>",
    ))
    fig.add_vline(
        x=_NSL_TARGET, line_dash="dash", line_color=_GREEN,
        annotation_text=f"Target {_NSL_TARGET:.0f}%",
        annotation_position="top right",
    )
    height = max(300, len(worst) * 28 + 80)
    fig.update_layout(
        title=dict(text="Worst 20 Stations — NSL %", font=dict(size=13, color="#333")),
        height=height,
        xaxis=dict(title="NSL %", range=[0, 107]),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=80, r=70, t=44, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_station_summary_table(df: pd.DataFrame, stn_col, has_mbg: bool) -> None:
    if not stn_col or df.empty:
        return
    agg = {c: "sum" for c in ["tot_vol", "nsl_ot_vol", "nsl_f_vol", "mbg_ot_vol", "mbg_f_vol"] if c in df.columns}
    if not agg:
        return
    tbl = df.groupby(stn_col, as_index=False).agg(agg)
    tbl = tbl[tbl["tot_vol"] > 0].copy()
    if "nsl_ot_vol" in tbl.columns:
        tbl["NSL %"] = (tbl["nsl_ot_vol"] / tbl["tot_vol"] * 100).round(1)
    if has_mbg and "mbg_f_vol" in tbl.columns:
        tbl["NSL+24 %"] = ((tbl["tot_vol"] - tbl["mbg_f_vol"]) / tbl["tot_vol"] * 100).round(1)
    elif "nsl_f_vol" in tbl.columns and "nsl_ot_vol" in tbl.columns:
        tbl["NSL+24 %"] = ((tbl["nsl_ot_vol"] + tbl["nsl_f_vol"] * 0.25) / tbl["tot_vol"] * 100).round(1)

    keep = {stn_col: "Station", "tot_vol": "Volume", "NSL %": "NSL %", "NSL+24 %": "NSL+24 %"}
    disp = tbl[[c for c in keep if c in tbl.columns]].rename(columns=keep)
    if "NSL %" in disp.columns:
        disp = disp.sort_values("NSL %")
    st.markdown("**Station NSL Summary**")
    st.dataframe(disp, hide_index=True, use_container_width=True)


def _render_nsl_trend(df: pd.DataFrame, date_col: str, has_mbg: bool) -> None:
    agg = {c: "sum" for c in ["tot_vol", "nsl_ot_vol", "nsl_f_vol", "mbg_f_vol"] if c in df.columns}
    if "tot_vol" not in agg or "nsl_ot_vol" not in agg:
        return
    ts = df.groupby(date_col, as_index=False).agg(agg).sort_values(date_col)
    ts = ts[ts["tot_vol"] > 0].copy()
    if ts.empty:
        return
    ts["nsl_pct"] = (ts["nsl_ot_vol"] / ts["tot_vol"] * 100).round(2)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts[date_col], y=ts["nsl_pct"],
        name="NSL %",
        mode="lines+markers",
        line=dict(color=_PURPLE, width=2.5),
        marker=dict(size=6),
        hovertemplate="<b>%{x}</b><br>NSL: %{y:.1f}%<extra></extra>",
    ))
    if has_mbg and "mbg_f_vol" in ts.columns:
        ts["nsl24_pct"] = ((ts["tot_vol"] - ts["mbg_f_vol"]) / ts["tot_vol"] * 100).round(2)
        fig.add_trace(go.Scatter(
            x=ts[date_col], y=ts["nsl24_pct"],
            name="NSL+24 % (MBG)",
            mode="lines+markers",
            line=dict(color=_ORANGE, width=2.5, dash="dot"),
            marker=dict(size=5),
            hovertemplate="<b>%{x}</b><br>NSL+24: %{y:.1f}%<extra></extra>",
        ))

    fig.add_hline(
        y=_NSL_TARGET, line_dash="dash", line_color=_GREEN,
        annotation_text=f"NSL Target ({_NSL_TARGET}%)",
        annotation_position="bottom right",
    )
    y_min = max(0, ts["nsl_pct"].min() - 5)
    fig.update_layout(
        title=dict(text="NSL Performance Trend Over Time", font=dict(size=13, color="#333")),
        height=300,
        yaxis=dict(title="NSL %", range=[y_min, 102]),
        margin=dict(l=50, r=20, t=44, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", x=0, y=1.12),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_service_breakdown(df: pd.DataFrame, service_col: str) -> None:
    agg = {c: "sum" for c in ["tot_vol", "nsl_ot_vol"] if c in df.columns}
    if "tot_vol" not in agg or "nsl_ot_vol" not in agg:
        return
    svc = df.groupby(service_col, as_index=False).agg(agg)
    svc = svc[svc["tot_vol"] > 0].copy()
    svc["NSL %"] = (svc["nsl_ot_vol"] / svc["tot_vol"] * 100).round(1)
    if svc.empty:
        return

    fig = go.Figure(go.Bar(
        x=svc[service_col],
        y=svc["NSL %"],
        marker_color=[_nsl_color(p) for p in svc["NSL %"]],
        text=svc["NSL %"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>NSL: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=_NSL_TARGET, line_dash="dash", line_color=_GREEN,
                  annotation_text=f"Target {_NSL_TARGET:.0f}%", annotation_position="top right")
    fig.update_layout(
        title=dict(text="NSL % by Service Type", font=dict(size=13, color="#333")),
        height=280,
        yaxis=dict(title="NSL %", range=[0, 108]),
        margin=dict(l=40, r=20, t=44, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_pivot_table(df: pd.DataFrame, date_col: str, stn_col: str) -> None:
    """Station × Date NSL % pivot table."""
    if "tot_vol" not in df.columns or "nsl_ot_vol" not in df.columns:
        return
    piv_src = df.groupby([stn_col, date_col], as_index=False).agg(
        tot_vol=("tot_vol", "sum"),
        nsl_ot_vol=("nsl_ot_vol", "sum"),
    )
    piv_src = piv_src[piv_src["tot_vol"] > 0].copy()
    piv_src["nsl_pct"] = (piv_src["nsl_ot_vol"] / piv_src["tot_vol"] * 100).round(1)

    if piv_src.empty:
        return

    piv = piv_src.pivot_table(
        index=stn_col,
        columns=date_col,
        values="nsl_pct",
        aggfunc="mean",
    )
    piv.columns = [str(c.date()) if hasattr(c, "date") else str(c) for c in piv.columns]
    piv["Avg NSL %"] = piv.mean(axis=1).round(1)
    piv = piv.sort_values("Avg NSL %").reset_index()
    piv = piv.rename(columns={stn_col: "Station"})

    st.markdown("**Weekly / Monthly NSL % Pivot** *(station × period, sorted worst-first)*")
    st.dataframe(
        piv.style.format({c: "{:.1f}" for c in piv.columns if c not in ("Station",)}, na_rep="—"),
        hide_index=True,
        use_container_width=True,
    )
