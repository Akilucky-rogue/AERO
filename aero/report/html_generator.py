"""
aero/report/html_generator.py
──────────────────────────────────────────────────────────────────────────────
Generates a self-contained, interactive HTML analytics report from FAMIS data.

Entry point
───────────
    from aero.report.html_generator import generate_famis_report
    html_bytes = generate_famis_report(famis_df, master_df, nsl_df)

The returned bytes represent a single HTML file containing:
  • Plotly charts loaded via CDN (plotly-2.26.0.min.js)
  • JavaScript-powered tab navigation (no React/Vue dependency)
  • FedEx brand styling (purple #4D148C, orange #FF6200)
  • Four tabs: Executive Summary · Volume & Health · Station Deep-Dive · NSL Performance
  • Fully offline-capable once the Plotly CDN has been loaded once
"""

from __future__ import annotations

import html as _html
import json
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_PURPLE = "#4D148C"
_ORANGE = "#FF6200"
_GREEN  = "#008A00"
_RED    = "#DE002E"
_YELLOW = "#F7B118"
_BLUE   = "#007AB7"
_GREY   = "#888888"

_NSL_TARGET = 97.0


# ────────────────────────────────────────────────────────────────────
# Chart builder helpers
# ────────────────────────────────────────────────────────────────────

def _fig_div(fig, div_id: str) -> str:
    """Return a standalone HTML div + script block for the given Plotly figure."""
    try:
        import plotly.io as pio
        return pio.to_html(fig, full_html=False, include_plotlyjs=False, div_id=div_id)
    except Exception as exc:
        logger.warning("Could not render chart %s: %s", div_id, exc)
        return f'<div id="{div_id}" style="padding:20px;color:#888;">Chart unavailable</div>'


def _sdiv(a, b, default: float = 0.0) -> float:
    try:
        return float(a) / float(b) if float(b) > 0 else default
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def _safe(v, default=0):
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def _status_color(status: str) -> str:
    return {
        "HEALTHY":       _GREEN,
        "REVIEW_NEEDED": _YELLOW,
        "CRITICAL":      _RED,
        "PROJECTED":     _BLUE,
    }.get(status, _GREY)


def _status_label(status: str) -> str:
    return {
        "HEALTHY":       "Healthy",
        "REVIEW_NEEDED": "Review",
        "CRITICAL":      "Critical",
        "PROJECTED":     "Projected",
    }.get(status, status or "—")


def _worst(a: str, r: str, c: str) -> str:
    for s in ("CRITICAL", "REVIEW_NEEDED", "PROJECTED", "HEALTHY"):
        if s in (a, r, c):
            return s
    return "UNKNOWN"


# ────────────────────────────────────────────────────────────────────
# Health computation (mirrors analytics.py — no Streamlit dependency)
# ────────────────────────────────────────────────────────────────────

def _compute_health_all(famis_df: pd.DataFrame, master_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Compute area / resource / courier health for every FAMIS row."""
    if famis_df is None or famis_df.empty:
        return pd.DataFrame()
    try:
        from aero.config.settings import load_config, load_area_config
        from aero.core.area_calculator import calculate_area_requirements, calculate_area_status
        from aero.core.resource_calculator import calculate_resource_requirements, calculate_resource_health_status
        from aero.core.courier_calculator import calculate_courier_requirements, calculate_courier_health_status
        cfg      = load_config()
        area_cfg = load_area_config()
    except Exception as exc:
        logger.warning("Could not load config for health computation: %s", exc)
        return pd.DataFrame()

    master_idx: dict = {}
    if master_df is not None and not master_df.empty and "loc_id" in master_df.columns:
        for _, mr in master_df.iterrows():
            lid = str(mr.get("loc_id", "") or "").strip()
            if lid:
                master_idx[lid] = mr

    rows: list[dict] = []
    for _, row in famis_df.iterrows():
        loc = str(row.get("loc_id", "") or "").strip()
        if not loc:
            continue
        mrow = master_idx.get(loc, pd.Series(dtype=object))
        has_master = not mrow.empty

        vol = int(_safe(row.get("pk_gross_tot")))
        ib  = int(_safe(row.get("pk_gross_inb")))
        ob  = int(_safe(row.get("pk_gross_outb")))
        roc_raw = int(_safe(row.get("pk_roc")))
        roc = int(roc_raw * 0.25)
        asp = roc_raw - roc

        ops_area = float(_safe(mrow.get("ops_area")) if has_master else 0)
        m_agents  = float(_safe(mrow.get("current_total_agents", 0) if has_master else row.get("fte_tot", 0)))
        pk_cr = _safe(row.get("pk_cr_or", 0))
        m_couriers = (
            int(_safe(mrow.get("current_total_couriers", mrow.get("couriers_available", 0))))
            if has_master
            else (int(round(_safe(row.get("pk_roc", 0)) / pk_cr)) if pk_cr > 0 else 0)
        )

        out = dict(
            loc_id=loc,
            date=row.get("date"),
            region=row.get("region", "Unknown"),
            pk_gross_tot=vol,
            area_status="UNKNOWN", resource_status="UNKNOWN", courier_status="UNKNOWN",
            calc_area=0.0, calc_agents=0.0, calc_couriers=0.0,
            master_ops_area=ops_area, master_agents=m_agents, master_couriers=m_couriers,
            area_util_pct=0.0, courier_eff=0.0,
        )

        if vol == 0:
            rows.append(out)
            continue

        # Area
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

        # Resource
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
            out["calc_agents"] = ca2
            if m_agents > 0 and ca2 > 0:
                rs = calculate_resource_health_status(ca2, m_agents)
                out["resource_status"] = rs.get("status", "UNKNOWN")
            elif ca2 > 0:
                out["resource_status"] = "PROJECTED"
        except Exception:
            pass

        # Courier
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

        rows.append(out)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ────────────────────────────────────────────────────────────────────
# Tab builders — each returns an HTML string
# ────────────────────────────────────────────────────────────────────

def _tab_summary(health_df: pd.DataFrame, famis_df: pd.DataFrame, report_date: str) -> str:
    """Executive Summary tab."""
    if health_df.empty:
        return "<p style='color:#888;padding:20px'>No health data available.</p>"

    try:
        import plotly.graph_objects as go

        # ── KPI values ────────────────────────────────────────────────
        tot_st  = len(health_df["loc_id"].unique()) if "loc_id" in health_df.columns else len(health_df)
        tot_vol = int(health_df["pk_gross_tot"].sum()) if "pk_gross_tot" in health_df.columns else 0

        def worst_status(r):
            return _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U"))

        hlth_ct  = sum(1 for _, r in health_df.iterrows() if worst_status(r) == "HEALTHY")
        rev_ct   = sum(1 for _, r in health_df.iterrows() if worst_status(r) == "REVIEW_NEEDED")
        crit_ct  = sum(1 for _, r in health_df.iterrows() if worst_status(r) == "CRITICAL")
        proj_ct  = sum(1 for _, r in health_df.iterrows() if worst_status(r) == "PROJECTED")
        net_pct  = round(hlth_ct / max(tot_st, 1) * 100)

        net_color = _GREEN if net_pct >= 70 else (_YELLOW if net_pct >= 40 else _RED)

        kpi_cards = f"""
        <div class="kpi-row">
          <div class="kpi-card" style="border-top:3px solid {_PURPLE}">
            <div class="kpi-label">Total Stations</div>
            <div class="kpi-value">{tot_st}</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {_PURPLE}">
            <div class="kpi-label">Total Volume</div>
            <div class="kpi-value">{tot_vol:,}</div>
            <div class="kpi-sub">packages</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {net_color}">
            <div class="kpi-label">Network Health</div>
            <div class="kpi-value" style="color:{net_color}">{net_pct}%</div>
            <div class="kpi-sub">{hlth_ct}/{tot_st} fully healthy</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {_RED if crit_ct > 0 else _GREEN}">
            <div class="kpi-label">Critical Alerts</div>
            <div class="kpi-value" style="color:{_RED if crit_ct > 0 else _GREEN}">{crit_ct}</div>
            <div class="kpi-sub">Area · Resource · Courier</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {_BLUE if proj_ct > 0 else _GREEN}">
            <div class="kpi-label">Projected</div>
            <div class="kpi-value" style="color:{_BLUE}">{proj_ct}</div>
            <div class="kpi-sub">awaiting Facility Master</div>
          </div>
        </div>"""

        # ── Health donut chart ─────────────────────────────────────────
        donut = go.Figure(go.Pie(
            labels=["Healthy", "Review", "Critical", "Projected"],
            values=[hlth_ct, rev_ct, crit_ct, proj_ct],
            marker_colors=[_GREEN, _YELLOW, _RED, _BLUE],
            hole=0.55,
            textinfo="label+value",
            hovertemplate="<b>%{label}</b><br>%{value} stations<extra></extra>",
        ))
        donut.update_layout(
            height=340, margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.1),
        )
        donut_div = _fig_div(donut, "chart_donut")

        # ── Region summary table ───────────────────────────────────────
        reg_rows = ""
        if "region" in health_df.columns:
            for reg in sorted(health_df["region"].unique()):
                rdf = health_df[health_df["region"] == reg]
                r_hlth  = sum(1 for _, r in rdf.iterrows() if worst_status(r) == "HEALTHY")
                r_rev   = sum(1 for _, r in rdf.iterrows() if worst_status(r) == "REVIEW_NEEDED")
                r_crit  = sum(1 for _, r in rdf.iterrows() if worst_status(r) == "CRITICAL")
                r_proj  = sum(1 for _, r in rdf.iterrows() if worst_status(r) == "PROJECTED")
                r_vol   = int(rdf["pk_gross_tot"].sum()) if "pk_gross_tot" in rdf.columns else 0
                r_pct   = round(r_hlth / max(len(rdf), 1) * 100)
                reg_rows += f"""
                <tr>
                  <td style="font-weight:700">{_html.escape(str(reg))}</td>
                  <td style="text-align:center">{len(rdf)}</td>
                  <td style="text-align:right">{r_vol:,}</td>
                  <td style="text-align:center;color:{_GREEN}">{r_hlth}</td>
                  <td style="text-align:center;color:{_YELLOW}">{r_rev}</td>
                  <td style="text-align:center;color:{_RED}">{r_crit}</td>
                  <td style="text-align:center;color:{_BLUE}">{r_proj}</td>
                  <td style="text-align:center"><b style="color:{_GREEN if r_pct>=70 else (_YELLOW if r_pct>=40 else _RED)}">{r_pct}%</b></td>
                </tr>"""

        reg_table = f"""
        <div class="section-title">Regional Overview</div>
        <table class="data-table">
          <thead><tr>
            <th>Region</th><th>Stations</th><th>Volume</th>
            <th>Healthy</th><th>Review</th><th>Critical</th><th>Projected</th><th>Health %</th>
          </tr></thead>
          <tbody>{reg_rows}</tbody>
        </table>""" if reg_rows else ""

        return f"""
        <div class="section-title">Key Performance Indicators · {_html.escape(report_date)}</div>
        {kpi_cards}
        <div style="display:flex;gap:24px;margin-top:20px;flex-wrap:wrap;">
          <div style="flex:0 0 360px">{donut_div}</div>
          <div style="flex:1;min-width:280px">{reg_table}</div>
        </div>"""

    except Exception as exc:
        logger.warning("Summary tab build error: %s", exc)
        return f"<p style='color:#888'>Summary unavailable: {_html.escape(str(exc))}</p>"


def _tab_volume(famis_df: pd.DataFrame, health_df: pd.DataFrame) -> str:
    """Volume & Health tab."""
    if famis_df is None or famis_df.empty:
        return "<p style='color:#888;padding:20px'>No FAMIS data available.</p>"
    try:
        import plotly.graph_objects as go

        famis_df = famis_df.copy()
        famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
        famis_df = famis_df[famis_df["date"].notna()].copy()

        out_parts = []

        # ── Volume trend ───────────────────────────────────────────────
        daily = (famis_df.groupby("date", as_index=False)["pk_gross_tot"]
                 .sum().sort_values("date"))
        if not daily.empty:
            fig_trend = go.Figure()
            if "region" in famis_df.columns:
                for reg in sorted(famis_df["region"].dropna().unique()):
                    rdf = famis_df[famis_df["region"] == reg]
                    rdaily = rdf.groupby("date", as_index=False)["pk_gross_tot"].sum().sort_values("date")
                    fig_trend.add_trace(go.Scatter(
                        x=rdaily["date"], y=rdaily["pk_gross_tot"],
                        name=str(reg), mode="lines+markers",
                        marker=dict(size=4),
                    ))
            fig_trend.add_trace(go.Scatter(
                x=daily["date"], y=daily["pk_gross_tot"],
                name="Network Total", mode="lines",
                line=dict(color=_PURPLE, width=3, dash="dot"),
                fill="tozeroy", fillcolor="rgba(77,20,140,0.07)",
            ))
            fig_trend.update_layout(
                title=dict(text="Network Volume Trend", font=dict(size=14)),
                height=320, yaxis_title="Packages",
                margin=dict(l=50, r=20, t=44, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", x=0, y=1.12),
            )
            out_parts.append(f'<div class="section-title">Volume Trend</div>{_fig_div(fig_trend, "chart_trend")}')

        # ── Top 20 stations by volume on latest date ───────────────────
        latest = famis_df["date"].max()
        day_df = famis_df[famis_df["date"] == latest].copy()
        if not day_df.empty:
            top20 = (day_df.groupby("loc_id", as_index=False)["pk_gross_tot"]
                     .sum().nlargest(20, "pk_gross_tot"))
            fig_top = go.Figure(go.Bar(
                y=top20["loc_id"].astype(str),
                x=top20["pk_gross_tot"],
                orientation="h",
                marker_color=_PURPLE,
                text=top20["pk_gross_tot"].apply(lambda v: f"{v:,}"),
                textposition="outside",
            ))
            fig_top.update_layout(
                title=dict(text=f"Top 20 Stations by Volume ({latest.date()})", font=dict(size=14)),
                height=max(300, len(top20) * 28 + 80),
                xaxis_title="Packages",
                yaxis=dict(autorange="reversed"),
                margin=dict(l=80, r=80, t=44, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            )
            out_parts.append(f'<div class="section-title">Top Stations by Volume</div>{_fig_div(fig_top, "chart_top20")}')

        # ── Health distribution bar ────────────────────────────────────
        if not health_df.empty:
            def worst_status(r):
                return _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U"))
            health_df = health_df.copy()
            health_df["_worst"] = health_df.apply(worst_status, axis=1)
            status_counts = health_df["_worst"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            status_counts["color"] = status_counts["status"].map(_status_color)

            fig_health = go.Figure(go.Bar(
                x=status_counts["status"].map(_status_label),
                y=status_counts["count"],
                marker_color=status_counts["color"],
                text=status_counts["count"],
                textposition="outside",
            ))
            fig_health.update_layout(
                title=dict(text="Station Health Distribution", font=dict(size=14)),
                height=280, yaxis_title="Stations",
                margin=dict(l=40, r=20, t=44, b=40),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            )
            out_parts.append(f'<div class="section-title">Health Distribution</div>{_fig_div(fig_health, "chart_health")}')

        return "\n".join(out_parts) if out_parts else "<p style='color:#888'>No chart data available.</p>"
    except Exception as exc:
        logger.warning("Volume tab error: %s", exc)
        return f"<p style='color:#888'>Volume charts unavailable: {_html.escape(str(exc))}</p>"


def _tab_stations(health_df: pd.DataFrame) -> str:
    """Station Deep-Dive tab — sortable table."""
    if health_df is None or health_df.empty:
        return "<p style='color:#888;padding:20px'>No station health data available.</p>"
    try:
        import plotly.graph_objects as go

        def worst_status(r):
            return _worst(r.get("area_status","U"), r.get("resource_status","U"), r.get("courier_status","U"))

        df = health_df.copy()
        df["_worst"] = df.apply(worst_status, axis=1)
        df = df.sort_values(["_worst", "loc_id"])

        # ── Area utilisation scatter ────────────────────────────────────
        area_df = df[(df["calc_area"] > 0) & (df["master_ops_area"] > 0)].copy()
        scatter_html = ""
        if not area_df.empty:
            fig_sc = go.Figure()
            for st, col in [("HEALTHY", _GREEN), ("REVIEW_NEEDED", _YELLOW), ("CRITICAL", _RED), ("PROJECTED", _BLUE)]:
                sdf = area_df[area_df["area_status"] == st]
                if sdf.empty:
                    continue
                fig_sc.add_trace(go.Scatter(
                    x=sdf["master_ops_area"], y=sdf["calc_area"],
                    mode="markers",
                    name=_status_label(st),
                    marker=dict(color=col, size=8, opacity=0.8),
                    customdata=sdf[["loc_id", "pk_gross_tot"]].values,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>Vol: %{customdata[1]:,}<br>"
                        "Req: %{y:,.0f} m²<br>Avail: %{x:,.0f} m²<extra></extra>"
                    ),
                ))
            max_v = max(area_df["master_ops_area"].max(), area_df["calc_area"].max()) * 1.05
            fig_sc.add_trace(go.Scatter(
                x=[0, max_v], y=[0, max_v],
                mode="lines", name="Breakeven",
                line=dict(color="#ccc", dash="dash"),
            ))
            fig_sc.update_layout(
                title=dict(text="Area Required vs Available Capacity", font=dict(size=14)),
                height=340,
                xaxis_title="Available Ops Area (m²)",
                yaxis_title="Required Area (m²)",
                margin=dict(l=60, r=20, t=44, b=44),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=1.12),
            )
            scatter_html = f'<div class="section-title">Area Capacity Analysis</div>{_fig_div(fig_sc, "chart_scatter")}'

        # ── Station table ──────────────────────────────────────────────
        rows = ""
        for _, r in df.iterrows():
            ws = r.get("_worst", "UNKNOWN")
            sc = _status_color(ws)
            sl = _status_label(ws)
            a_sc = _status_color(r.get("area_status","U"))
            res_sc = _status_color(r.get("resource_status","U"))
            cou_sc = _status_color(r.get("courier_status","U"))
            vol = int(r.get("pk_gross_tot", 0))
            ca = r.get("calc_area", 0)
            ra = r.get("calc_agents", 0)
            cc = r.get("calc_couriers", 0)
            rows += f"""
            <tr>
              <td style="font-weight:700">{_html.escape(str(r.get("loc_id","—")))}</td>
              <td>{_html.escape(str(r.get("region","—")))}</td>
              <td style="text-align:right">{vol:,}</td>
              <td style="text-align:center"><span class="badge" style="background:{a_sc}">{_status_label(r.get("area_status","U"))}</span></td>
              <td style="text-align:center"><span class="badge" style="background:{res_sc}">{_status_label(r.get("resource_status","U"))}</span></td>
              <td style="text-align:center"><span class="badge" style="background:{cou_sc}">{_status_label(r.get("courier_status","U"))}</span></td>
              <td style="text-align:center"><span class="badge" style="background:{sc}">{sl}</span></td>
              <td style="text-align:right">{ca:,.0f}</td>
              <td style="text-align:right">{ra:.0f}</td>
              <td style="text-align:right">{cc:.0f}</td>
            </tr>"""

        table_html = f"""
        <div class="section-title">All Stations — Health Detail</div>
        <div class="table-wrap">
        <table class="data-table sortable" id="stn_table">
          <thead><tr>
            <th>Station</th><th>Region</th><th>Volume</th>
            <th>Area</th><th>Resource</th><th>Courier</th><th>Overall</th>
            <th>Calc Area (m²)</th><th>Calc Agents</th><th>Calc Couriers</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        </div>"""

        return scatter_html + table_html

    except Exception as exc:
        logger.warning("Station tab error: %s", exc)
        return f"<p style='color:#888'>Station deep-dive unavailable: {_html.escape(str(exc))}</p>"


def _tab_nsl(nsl_df: Optional[pd.DataFrame]) -> str:
    """NSL Performance tab."""
    if nsl_df is None or nsl_df.empty:
        return """<div style="padding:32px;text-align:center;color:#888;">
            <div style="font-size:28px;margin-bottom:12px">📊</div>
            <b>No NSL data uploaded.</b><br>
            Upload a Station-Level NSL file in the Data Upload Centre to see NSL analytics here.
        </div>"""
    try:
        import plotly.graph_objects as go

        df = nsl_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        for c in ["tot_vol", "nsl_ot_vol", "nsl_f_vol", "mbg_ot_vol", "mbg_f_vol"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        date_col = next((c for c in ["month_date", "weekending_dt"] if c in df.columns and df[c].notna().any()), None)
        stn_col  = "orig_loc_cd" if "orig_loc_cd" in df.columns else None
        svc_col  = "service"     if "service"     in df.columns else None

        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        # KPIs
        tot_vol   = int(df["tot_vol"].sum()) if "tot_vol" in df.columns else 0
        nsl_ot    = int(df["nsl_ot_vol"].sum()) if "nsl_ot_vol" in df.columns else 0
        nsl_f     = int(df["nsl_f_vol"].sum())  if "nsl_f_vol"  in df.columns else 0
        mbg_f     = int(df["mbg_f_vol"].sum())  if "mbg_f_vol"  in df.columns else 0
        has_mbg   = (df["mbg_ot_vol"].sum() > 0 or mbg_f > 0) if "mbg_ot_vol" in df.columns else False

        nsl_pct  = _sdiv(nsl_ot, tot_vol) * 100
        nsl24_pct = _sdiv(tot_vol - mbg_f, tot_vol) * 100 if has_mbg else _sdiv(nsl_ot + nsl_f * 0.25, tot_vol) * 100

        nsl_color  = _GREEN if nsl_pct >= _NSL_TARGET else (_YELLOW if nsl_pct >= _NSL_TARGET - 3 else _RED)
        nsl24_color = _GREEN if nsl24_pct >= 99.0 else (_YELLOW if nsl24_pct >= 96.0 else _RED)

        kpi_row = f"""
        <div class="kpi-row">
          <div class="kpi-card" style="border-top:3px solid {nsl_color}">
            <div class="kpi-label">Network NSL %</div>
            <div class="kpi-value" style="color:{nsl_color}">{nsl_pct:.1f}%</div>
            <div class="kpi-sub">Target ≥ {_NSL_TARGET:.0f}%</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {nsl24_color}">
            <div class="kpi-label">NSL+24 %</div>
            <div class="kpi-value" style="color:{nsl24_color}">{nsl24_pct:.1f}%</div>
            <div class="kpi-sub">{"MBG-based" if has_mbg else "Estimated"} · Target ≥ 99%</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {_PURPLE}">
            <div class="kpi-label">Total Shipments</div>
            <div class="kpi-value">{tot_vol:,}</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {_GREEN}">
            <div class="kpi-label">On-Time Volume</div>
            <div class="kpi-value" style="color:{_GREEN}">{nsl_ot:,}</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid {_RED if nsl_f>0 else _GREEN}">
            <div class="kpi-label">Failures</div>
            <div class="kpi-value" style="color:{_RED if nsl_f>0 else _GREEN}">{nsl_f:,}</div>
          </div>
        </div>"""

        out_parts = [kpi_row]

        # NSL trend chart
        if date_col and "nsl_ot_vol" in df.columns:
            ts = df.groupby(date_col, as_index=False).agg(
                tot_vol=("tot_vol","sum"), nsl_ot_vol=("nsl_ot_vol","sum"),
                **{c: (c,"sum") for c in ["mbg_f_vol"] if c in df.columns}
            ).sort_values(date_col)
            ts = ts[ts["tot_vol"] > 0].copy()
            ts["nsl_pct"] = (ts["nsl_ot_vol"] / ts["tot_vol"] * 100).round(2)
            fig_ts = go.Figure()
            fig_ts.add_trace(go.Scatter(
                x=ts[date_col], y=ts["nsl_pct"],
                name="NSL %", mode="lines+markers",
                line=dict(color=_PURPLE, width=2.5), marker=dict(size=6),
            ))
            if has_mbg and "mbg_f_vol" in ts.columns:
                ts["nsl24_pct"] = ((ts["tot_vol"] - ts["mbg_f_vol"]) / ts["tot_vol"] * 100).round(2)
                fig_ts.add_trace(go.Scatter(
                    x=ts[date_col], y=ts["nsl24_pct"],
                    name="NSL+24 % (MBG)", mode="lines+markers",
                    line=dict(color=_ORANGE, width=2.5, dash="dot"), marker=dict(size=5),
                ))
            fig_ts.add_hline(y=_NSL_TARGET, line_dash="dash", line_color=_GREEN,
                             annotation_text=f"Target {_NSL_TARGET:.0f}%", annotation_position="bottom right")
            fig_ts.update_layout(
                title=dict(text="NSL Performance Trend", font=dict(size=14)),
                height=300, yaxis_title="NSL %",
                margin=dict(l=50, r=20, t=44, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=1.12),
            )
            out_parts.append(f'<div class="section-title">NSL Trend Over Time</div>{_fig_div(fig_ts, "chart_nsl_ts")}')

        # Worst stations bar
        if stn_col and "nsl_ot_vol" in df.columns:
            sdf = df.groupby(stn_col, as_index=False).agg(
                tot_vol=("tot_vol","sum"), nsl_ot_vol=("nsl_ot_vol","sum"),
            )
            sdf = sdf[sdf["tot_vol"] > 0].copy()
            sdf["nsl_pct"] = (sdf["nsl_ot_vol"] / sdf["tot_vol"] * 100).round(1)
            worst20 = sdf.nsmallest(20, "nsl_pct")
            if not worst20.empty:
                fig_w = go.Figure(go.Bar(
                    y=worst20[stn_col].astype(str),
                    x=worst20["nsl_pct"],
                    orientation="h",
                    marker_color=[_GREEN if p>=_NSL_TARGET else (_YELLOW if p>=_NSL_TARGET-3 else _RED) for p in worst20["nsl_pct"]],
                    text=worst20["nsl_pct"].apply(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                ))
                fig_w.add_vline(x=_NSL_TARGET, line_dash="dash", line_color=_GREEN,
                                annotation_text=f"Target {_NSL_TARGET:.0f}%", annotation_position="top right")
                fig_w.update_layout(
                    title=dict(text="Worst 20 Stations — NSL %", font=dict(size=14)),
                    height=max(300, len(worst20) * 28 + 80),
                    xaxis=dict(title="NSL %", range=[0, 107]),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=80, r=80, t=44, b=30),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                out_parts.append(f'<div class="section-title">Worst-Performing Stations</div>{_fig_div(fig_w, "chart_nsl_worst")}')

        # Service breakdown
        if svc_col and "nsl_ot_vol" in df.columns:
            svc = df.groupby(svc_col, as_index=False).agg(tot_vol=("tot_vol","sum"), nsl_ot_vol=("nsl_ot_vol","sum"))
            svc = svc[svc["tot_vol"] > 0].copy()
            svc["nsl_pct"] = (svc["nsl_ot_vol"] / svc["tot_vol"] * 100).round(1)
            fig_svc = go.Figure(go.Bar(
                x=svc[svc_col],
                y=svc["nsl_pct"],
                marker_color=[_GREEN if p>=_NSL_TARGET else (_YELLOW if p>=_NSL_TARGET-3 else _RED) for p in svc["nsl_pct"]],
                text=svc["nsl_pct"].apply(lambda v: f"{v:.1f}%"),
                textposition="outside",
            ))
            fig_svc.add_hline(y=_NSL_TARGET, line_dash="dash", line_color=_GREEN)
            fig_svc.update_layout(
                title=dict(text="NSL % by Service Type", font=dict(size=14)),
                height=280, yaxis=dict(title="NSL %", range=[0, 108]),
                margin=dict(l=40, r=20, t=44, b=50),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            )
            out_parts.append(f'<div class="section-title">Service-Level NSL Breakdown</div>{_fig_div(fig_svc, "chart_nsl_svc")}')

        return "\n".join(out_parts)

    except Exception as exc:
        logger.warning("NSL tab error: %s", exc)
        return f"<p style='color:#888'>NSL charts unavailable: {_html.escape(str(exc))}</p>"


# ────────────────────────────────────────────────────────────────────
# HTML assembly
# ────────────────────────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
  font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
  background: #F4F5F8; color: #333; margin: 0; padding: 0;
  -webkit-font-smoothing: antialiased;
}
a { color: #4D148C; }

/* ── HEADER ── */
.report-header {
  background: linear-gradient(90deg, #4D148C 0%, #671CAA 60%, #3C1080 100%);
  padding: 18px 32px; display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 3px 14px rgba(0,0,0,0.2);
}
.report-header-left { display: flex; align-items: center; gap: 20px; }
.header-logo-fedex { color: #fff; font-size: 28px; font-weight: 900; letter-spacing: -1px; }
.header-logo-fedex span { color: #FF6200; }
.header-sep { width: 1px; height: 42px; background: rgba(255,255,255,0.25); }
.header-aero { display: flex; flex-direction: column; border-left: 3px solid #FF6200; padding-left: 14px; gap: 1px; }
.header-aero-name { font-size: 20px; font-weight: 900; color: #fff; letter-spacing: 2.5px; line-height: 1; }
.header-aero-tag  { font-size: 8px; color: rgba(255,255,255,0.55); text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; line-height: 1.4; }
.header-title { color: rgba(255,255,255,0.80); font-size: 13px; text-align: right; }
.header-title strong { color: #fff; display: block; font-size: 15px; }

/* ── TABS ── */
.tab-bar {
  background: #fff; border-bottom: 3px solid #4D148C;
  display: flex; gap: 0; padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); position: sticky; top: 0; z-index: 100;
}
.tab-btn {
  padding: 14px 22px; border: none; background: transparent; cursor: pointer;
  font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
  color: #888; border-bottom: 3px solid transparent; margin-bottom: -3px;
  transition: color .18s, border-color .18s;
}
.tab-btn:hover { color: #4D148C; }
.tab-btn.active { color: #4D148C; border-bottom-color: #FF6200; }

/* ── CONTENT ── */
.tab-panel { display: none; padding: 28px 32px; max-width: 1600px; margin: 0 auto; }
.tab-panel.active { display: block; }

/* ── KPI CARDS ── */
.kpi-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 8px; }
.kpi-card {
  background: #fff; border: 1px solid #E3E3E3; border-radius: 10px;
  padding: 14px 18px; min-width: 140px; flex: 1;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.kpi-label { font-size: 10px; font-weight: 700; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.kpi-value { font-size: 28px; font-weight: 800; color: #1A1A1A; line-height: 1.1; }
.kpi-sub   { font-size: 11px; color: #999; margin-top: 2px; }

/* ── SECTION TITLES ── */
.section-title {
  font-size: 13px; font-weight: 800; color: #4D148C;
  text-transform: uppercase; letter-spacing: 0.8px;
  border-bottom: 2px solid #4D148C; padding-bottom: 5px;
  margin: 24px 0 14px 0;
}

/* ── TABLES ── */
.table-wrap { overflow-x: auto; }
.data-table {
  width: 100%; border-collapse: collapse;
  background: #fff; border-radius: 10px; overflow: hidden;
  box-shadow: 0 1px 6px rgba(0,0,0,0.07);
  font-size: 13px;
}
.data-table thead th {
  background: #4D148C; color: #fff; font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.8px;
  padding: 10px 12px; text-align: left; border-bottom: 3px solid #FF6200;
  cursor: pointer; white-space: nowrap;
}
.data-table thead th:hover { background: #671CAA; }
.data-table tbody td { padding: 9px 12px; border-bottom: 1px solid #F0F0F0; }
.data-table tbody tr:last-child td { border-bottom: 3px solid #FF6200; }
.data-table tbody tr:hover td { background: rgba(77,20,140,0.03); }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  color: #fff; font-size: 10px; font-weight: 700; white-space: nowrap;
}

/* ── FOOTER ── */
.report-footer {
  margin-top: 40px; padding: 20px 32px; border-top: 1px solid #E3E3E3;
  text-align: center; font-size: 11px; color: #999; background: #fff;
}
.report-footer strong { color: #4D148C; }
"""

_JS = """
function showTab(id) {
  document.querySelectorAll('.tab-panel').forEach(function(p){ p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
  document.getElementById(id).classList.add('active');
  event.currentTarget.classList.add('active');
}

// Simple client-side table sort
(function(){
  function sortTable(table, col, asc){
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort(function(a,b){
      var av = a.cells[col] ? a.cells[col].innerText.replace(/[,%]/g,'') : '';
      var bv = b.cells[col] ? b.cells[col].innerText.replace(/[,%]/g,'') : '';
      var an = parseFloat(av), bn = parseFloat(bv);
      if(!isNaN(an) && !isNaN(bn)) return asc ? an-bn : bn-an;
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
    rows.forEach(function(r){ tbody.appendChild(r); });
  }
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('table.sortable thead th').forEach(function(th, idx){
      th._asc = false;
      th.addEventListener('click', function(){
        th._asc = !th._asc;
        sortTable(th.closest('table'), idx, th._asc);
      });
    });
  });
})();
"""


def _build_full_html(
    summary_html: str,
    volume_html: str,
    station_html: str,
    nsl_html: str,
    report_title: str,
    report_date: str,
    generated_by: str,
    has_nsl: bool,
) -> str:
    nsl_tab_btn = (
        '<button class="tab-btn" onclick="showTab(\'tab_nsl\')">NSL Performance</button>'
        if has_nsl else ""
    )
    nsl_tab_panel = (
        f'<div id="tab_nsl" class="tab-panel">{nsl_html}</div>'
        if has_nsl else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_html.escape(report_title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.26.0.min.js" charset="utf-8"></script>
  <style>{_CSS}</style>
</head>
<body>

<!-- HEADER -->
<header class="report-header">
  <div class="report-header-left">
    <div class="header-logo-fedex">Fed<span>Ex</span></div>
    <div class="header-sep"></div>
    <div class="header-aero">
      <div class="header-aero-name">AERO</div>
      <div class="header-aero-tag">Automated Evaluation of Resource Occupancy</div>
    </div>
  </div>
  <div class="header-title">
    <strong>{_html.escape(report_title)}</strong>
    Generated {_html.escape(report_date)} &nbsp;&bull;&nbsp; {_html.escape(generated_by)}
  </div>
</header>

<!-- TAB BAR -->
<nav class="tab-bar">
  <button class="tab-btn active" onclick="showTab('tab_summary')">Executive Summary</button>
  <button class="tab-btn" onclick="showTab('tab_volume')">Volume &amp; Health</button>
  <button class="tab-btn" onclick="showTab('tab_stations')">Station Deep-Dive</button>
  {nsl_tab_btn}
</nav>

<!-- TAB PANELS -->
<div id="tab_summary"  class="tab-panel active">{summary_html}</div>
<div id="tab_volume"   class="tab-panel">{volume_html}</div>
<div id="tab_stations" class="tab-panel">{station_html}</div>
{nsl_tab_panel}

<!-- FOOTER -->
<footer class="report-footer">
  <strong>AERO Platform</strong> &nbsp;&bull;&nbsp; Automated Evaluation of Resource Occupancy &nbsp;&bull;&nbsp;
  FedEx Planning &amp; Engineering &nbsp;&bull;&nbsp; Report Date: {_html.escape(report_date)} &nbsp;&bull;&nbsp;
  &copy; 2026 FedEx. Confidential &amp; Proprietary.
</footer>

<script>{_JS}</script>
</body>
</html>"""


# ────────────────────────────────────────────────────────────────────
# Public entry point
# ────────────────────────────────────────────────────────────────────

def generate_famis_report(
    famis_df: pd.DataFrame,
    master_df: Optional[pd.DataFrame] = None,
    nsl_df: Optional[pd.DataFrame] = None,
    report_title: str = "AERO Analytics Report",
    generated_by: str = "AERO Platform",
) -> bytes:
    """Generate a self-contained interactive HTML analytics report.

    Parameters
    ----------
    famis_df : FAMIS volume DataFrame (required)
    master_df : Facility Master DataFrame (optional — enriches health scoring)
    nsl_df : Station NSL DataFrame (optional — enables NSL tab)
    report_title : Title shown in the HTML header and browser tab
    generated_by : User/system attribution shown in the footer

    Returns
    -------
    bytes : UTF-8 encoded HTML
    """
    if famis_df is None or famis_df.empty:
        raise ValueError("famis_df must not be empty")

    report_date = datetime.now().strftime("%d %b %Y %H:%M")

    # Add region classification if available
    try:
        from aero.region.mapper import classify_dataframe
        famis_df = classify_dataframe(famis_df.copy(), "loc_id")
    except Exception:
        pass

    # Compute health table
    health_df = _compute_health_all(famis_df, master_df)

    # Add region to health_df from famis_df if missing
    if not health_df.empty and "region" not in health_df.columns and "region" in famis_df.columns:
        reg_map = famis_df.drop_duplicates("loc_id").set_index("loc_id")["region"].to_dict()
        health_df["region"] = health_df["loc_id"].map(reg_map).fillna("Unknown")

    # Use latest-date slice for summary/station analysis
    famis_df["date"] = pd.to_datetime(famis_df["date"], errors="coerce")
    latest = famis_df["date"].max()
    latest_health = health_df[pd.to_datetime(health_df["date"], errors="coerce") == latest] if not health_df.empty else health_df

    summary_html = _tab_summary(latest_health if not latest_health.empty else health_df, famis_df, report_date)
    volume_html  = _tab_volume(famis_df, latest_health if not latest_health.empty else health_df)
    station_html = _tab_stations(latest_health if not latest_health.empty else health_df)
    nsl_html     = _tab_nsl(nsl_df)

    has_nsl = nsl_df is not None and not nsl_df.empty

    full_html = _build_full_html(
        summary_html=summary_html,
        volume_html=volume_html,
        station_html=station_html,
        nsl_html=nsl_html,
        report_title=report_title,
        report_date=report_date,
        generated_by=generated_by,
        has_nsl=has_nsl,
    )

    return full_html.encode("utf-8")
