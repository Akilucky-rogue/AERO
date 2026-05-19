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
from aero.ui.nsl_tab import render_nsl_tab

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
    vc = df["STATUS"].value_counts()
    h, r, c = int(vc.get("Healthy", 0)), int(vc.get("Review", 0)), int(vc.get("Critical", 0))
    return {"Healthy": h, "Review": r, "Critical": c, "total": h + r + c}


def _health_pct(sc: dict) -> float:
    return round(sc["Healthy"] / sc["total"] * 100, 1) if sc["total"] else 0.0


def _kpi_card(label: str, value: str, color: str = "#4D148C"):
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#FFFFFF 0%,#F7F3FF 100%);
        border-left:5px solid {color};border-radius:10px;padding:18px 16px;
        box-shadow:0 2px 8px rgba(0,0,0,0.07);text-align:center;min-height:88px;
        display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:26px;font-weight:800;color:{color};letter-spacing:-0.5px;
            font-family:var(--font-head);">{value}</div>
        <div style="font-size:10px;color:#777;font-weight:700;letter-spacing:1px;
            text-transform:uppercase;margin-top:5px;">{label}</div>
    </div>""", unsafe_allow_html=True)


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


# ── Load all report data ─────────────────────────────────────────────────────
st_area  = read_report_sheet("AREA HEALTH SUMMARY")
st_res   = read_report_sheet("RESOURCE HEALTH SUMMARY")
st_cour  = read_report_sheet("COURIER HEALTH SUMMARY")
st_total = read_report_sheet("TOTAL SUMMARY")
hub_area  = read_hub_report_sheet("AREA HEALTH SUMMARY")
hub_res   = read_hub_report_sheet("RESOURCE HEALTH SUMMARY")
hub_cour  = read_hub_report_sheet("COURIER HEALTH SUMMARY")
hub_total = read_hub_report_sheet("TOTAL SUMMARY")

# ── 3 independent tabs ───────────────────────────────────────────────────────
tab_sh, tab_gw, tab_svc = st.tabs([
    "   STATION / HUB   ",
    "   GATEWAY   ",
    "   SERVICES   ",
])

# ============================================================
# TAB 1 — STATION / HUB
# ============================================================
with tab_sh:
    st_area_sc  = _status_counts(st_area)
    st_res_sc   = _status_counts(st_res)
    st_cour_sc  = _status_counts(st_cour)
    hub_area_sc = _status_counts(hub_area)
    hub_res_sc  = _status_counts(hub_res)
    hub_cour_sc = _status_counts(hub_cour)

    total_st  = max(st_area_sc["total"], st_res_sc["total"], st_cour_sc["total"])
    total_hub = max(hub_area_sc["total"], hub_res_sc["total"], hub_cour_sc["total"])

    all_h = (st_area_sc["Healthy"] + st_res_sc["Healthy"] + st_cour_sc["Healthy"]
           + hub_area_sc["Healthy"] + hub_res_sc["Healthy"] + hub_cour_sc["Healthy"])
    all_t = (st_area_sc["total"] + st_res_sc["total"] + st_cour_sc["total"]
           + hub_area_sc["total"] + hub_res_sc["total"] + hub_cour_sc["total"])
    all_c = (st_area_sc["Critical"] + st_res_sc["Critical"] + st_cour_sc["Critical"]
           + hub_area_sc["Critical"] + hub_res_sc["Critical"] + hub_cour_sc["Critical"])
    overall_pct = round(all_h / all_t * 100, 1) if all_t else 0.0

    # Enterprise Overview KPI banner removed per request

    # ── Status distribution ──────────────────────────────────────────────────
    _section_header("Health Status Distribution", "Breakdown by monitoring category — Area, Resource, Courier")
    no_data = (st_area.empty and st_res.empty and st_cour.empty
               and hub_area.empty and hub_res.empty and hub_cour.empty)
    if no_data:
        st.info(
            "No published health reports found. Facility and Hub teams must publish "
            "reports from their respective Health Monitor tabs before data appears here."
        )
    else:
        c_st, c_hub = st.columns(2)
        with c_st:
            st.markdown("""<div style="font-size:12px;font-weight:700;color:#4D148C;
                text-transform:uppercase;letter-spacing:0.6px;margin-bottom:8px;
                padding-bottom:5px;border-bottom:2px solid #4D148C;">Station</div>""",
                unsafe_allow_html=True)
            _status_bar("Area Health", st_area_sc, "#4D148C")
            _status_bar("Resource Health", st_res_sc, "#FF6200")
            _status_bar("Courier Health", st_cour_sc, "#DE002E")
        with c_hub:
            st.markdown("""<div style="font-size:12px;font-weight:700;color:#FF6200;
                text-transform:uppercase;letter-spacing:0.6px;margin-bottom:8px;
                padding-bottom:5px;border-bottom:2px solid #FF6200;">Hub</div>""",
                unsafe_allow_html=True)
            _status_bar("Area Health", hub_area_sc, "#4D148C")
            _status_bar("Resource Health", hub_res_sc, "#FF6200")
            _status_bar("Courier Health", hub_cour_sc, "#DE002E")

        # ── Volume trend ─────────────────────────────────────────────────────
        combined = pd.DataFrame()
        for _df, _lbl in [(st_total, "Station"), (hub_total, "Hub")]:
            if not _df.empty and "DATE" in _df.columns:
                tmp = _df.copy()
                tmp["Division"] = _lbl
                combined = pd.concat([combined, tmp], ignore_index=True)
        if not combined.empty:
            vol_col = next(
                (c for c in combined.columns
                 if any(k in c.lower() for k in ("volume", "gross", "packs"))), None
            )
            if vol_col:
                st.markdown("---")
                _section_header("Volume Trend", "Combined station and hub pack volume over time")
                trend = combined.groupby(["DATE", "Division"])[vol_col].sum().reset_index()
                trend.sort_values("DATE", inplace=True)
                st.line_chart(trend.pivot(index="DATE", columns="Division", values=vol_col))

        # ── Critical location tables ──────────────────────────────────────────
        for _lbl, _df in [("Station", st_area), ("Hub", hub_area)]:
            if not _df.empty and "STATUS" in _df.columns and "LOC ID" in _df.columns:
                crit = _df[_df["STATUS"] == "Critical"]
                if not crit.empty:
                    st.markdown("---")
                    with st.expander(
                        f"CRITICAL {_lbl.upper()} LOCATIONS — Immediate Attention Required",
                        expanded=True,
                    ):
                        show = ["LOC ID", "DATE", "STATUS"] + [
                            c for c in crit.columns if c not in ("LOC ID", "DATE", "STATUS")
                        ]
                        st.dataframe(crit[show[:8]].reset_index(drop=True), use_container_width=True)


# ============================================================
# TAB 2 — GATEWAY
# ============================================================
with tab_gw:
    _section_header("Gateway Analytics", "Inter-hub linehaul and air gateway performance metrics", "#1A5276")

    st.markdown("""
    <div style="background:#EBF5FB;border-left:5px solid #1A5276;border-radius:8px;
        padding:14px 18px;margin-bottom:16px;">
        <div style="font-weight:700;color:#1A5276;font-size:13px;text-transform:uppercase;
            letter-spacing:0.5px;">Gateway Analytics — Phase 2 Integration</div>
        <div style="color:#555;font-size:12px;margin-top:4px;">Live gateway data feeds are scheduled for integration in Phase 2.
        Placeholder metrics below indicate the KPIs that will be tracked.</div>
    </div>""", unsafe_allow_html=True)

    gw1, gw2, gw3 = st.columns(3)
    with gw1: _phase_card("On-Time Departure Rate", "#1A5276")
    with gw2: _phase_card("Linehaul Utilization", "#1A5276")
    with gw3: _phase_card("Gateway Volume", "#1A5276")

    st.markdown("---")
    _section_header("Report Coverage — Phase 2", "What the Gateway tab will report on activation", "#1A5276")
    _phase_scope(
        "Gateway Scope",
        [
            "Linehaul on-time departure and arrival tracking by route",
            "Gateway volume and capacity utilization reporting",
            "Air gateway manifest compliance and cut-off adherence",
            "Cross-dock efficiency and dwell-time analytics",
            "Route-level performance vs. planned benchmarks",
            "Trailer utilization and payload efficiency metrics",
        ],
        "#EBF5FB",
        "#1A5276",
    )


# ============================================================
# TAB 3 — SERVICES
# ============================================================
with tab_svc:
    render_nsl_tab()

render_footer("LEADERSHIP")

