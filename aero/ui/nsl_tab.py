"""
nsl_tab.py — NSL Analytics tab renderer for the Leadership Executive Dashboard.

Call render_nsl_tab() inside a `with tab_svc:` block.
"""
import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from aero.ui.components import (
    render_kpi_card,
    render_info_banner,
    _PURPLE, _ORANGE, _GREEN, _RED, _YELLOW, _GREY,
)

# ── brand palette ─────────────────────────────────────────────────────────────
_COLORS = {
    "purple": "#4D148C", "orange": "#FF6200", "green": "#008A00",
    "red": "#DE002E",    "yellow": "#FFB800", "grey": "#888888",
    "blue": "#1A5276",   "teal": "#0097A7",
}
_SEQ = [_COLORS["purple"], _COLORS["orange"], _COLORS["blue"],
        _COLORS["green"],  _COLORS["red"],    _COLORS["yellow"],
        _COLORS["teal"],   _COLORS["grey"]]

_BUCKET_COLORS = {
    "CLEARANCE":           "#1A5276",
    "DEST":                "#DE002E",
    "EXCLUDE":             "#888888",
    "HUB":                 "#FFB800",
    "ORIGIN":              "#FF6200",
    "TRANSIT-Linehaul":    "#4D148C",
    "TRANSIT-Processing":  "#0097A7",
    "Other":               "#CCCCCC",
}
_MBG_COLORS = {
    "OnTime": "#008A00", "EWDL": "#FFB800",
    "WDL":    "#FF6200", "ERDL": "#DE002E", "RDL": "#8B0000",
}
_PUX_NAMES = {
    3: "PUX03 – Incorrect Address",
    5: "PUX05 – Customer Security Delay",
    8: "PUX08 – Not In/Business Closed",
    15: "PUX15 – Business Closed/Strike",
    16: "PUX16 – Payment Received",
    17: "PUX17 – Future Delivery Requested",
    20: "PUX20 – DG Commodity",
    23: "PUX23 – Received After A/C Departure ⚠️",
    24: "PUX24 – Customer Delay",
    26: "PUX26 – Cartage Agent/Consolidator",
    30: "PUX30 – Attempted After Close Time",
    35: "PUX35 – Third Party – No Package",
    39: "PUX39 – Customer Did Not Wait",
    40: "PUX40 – Multiple Pickups Scheduled",
    42: "PUX42 – Holiday/Business Closed",
    43: "PUX43 – No Package",
    46: "PUX46 – Mass Pickup Scan",
    47: "PUX47 – Mass Routing Scan",
    50: "PUX50 – Missing Regulatory Paperwork",
    78: "PUX78 – Country Not in Service Area",
    79: "PUX79 – Uplift Not Available",
    81: "PUX81 – COMAIL/Convenience",
    84: "PUX84 – Delay Beyond Our Control",
    86: "PUX86 – Pre-Routed Meter Package",
    91: "PUX91 – Exceeds Service Limits",
    92: "PUX92 – Pickup Not Ready",
    93: "PUX93 – Unable to Collect Payment",
    94: "PUX94 – No Credit Approval",
    95: "PUX95 – Package Retrieval",
    96: "PUX96 – Incorrect Pickup Info",
    97: "PUX97 – No Pickup Attempt Made",
    98: "PUX98 – Courier Attempted/Left Behind",
}


def _base_layout(**kwargs):
    kwargs.setdefault("margin", dict(l=16, r=16, t=36, b=16))
    return dict(
        font=dict(family="Inter, sans-serif", size=12, color="#333"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font_size=11),
        **kwargs,
    )


# ── data loader (cached per unique file bytes) ────────────────────────────────
@st.cache_data(show_spinner="Parsing NSL file — may take 30–60 s for large files…")
def _load_nsl(file_bytes: bytes) -> pd.DataFrame:
    chunks = []
    _kw = dict(sep=",", quotechar='"', on_bad_lines="skip", low_memory=False)

    # Pass 1: fast C engine — absorb EOF/parse errors at last row
    try:
        for chunk in pd.read_csv(io.BytesIO(file_bytes), chunksize=400_000, **_kw):
            chunks.append(chunk)
    except Exception:
        pass

    # Pass 2: Python engine fallback
    if not chunks:
        try:
            chunks.append(pd.read_csv(io.BytesIO(file_bytes), engine="python", **_kw))
        except Exception as e:
            raise RuntimeError(f"Cannot parse NSL file: {e}") from e

    df = pd.concat(chunks, ignore_index=True)

    # date columns
    for col in ["month_date", "weekending_dt", "shp_dt", "svc_commit_dt",
                "pckup_scan_dt", "pod_scan_dt"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # numeric vol columns
    for col in ["NSL_OT_VOL", "MBG_OT_VOL", "TOT_VOL", "NSL_F_VOL", "MBG_F_VOL"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "TOT_VOL" in df.columns:
        df["TOT_VOL"] = df["TOT_VOL"].replace(0, 1)  # avoid div/0

    # derived: lane, scan labels
    if "orig_region" in df.columns and "dest_region" in df.columns:
        df["lane"] = df["orig_region"].fillna("?") + " → " + df["dest_region"].fillna("?")
    if "pkg_pckup_scan_typ_cd" in df.columns:
        df["scan_type_num"] = pd.to_numeric(df["pkg_pckup_scan_typ_cd"], errors="coerce")
        df["scan_label"] = df["scan_type_num"].map(
            {8.0: "Standard PUP (Clean)", 29.0: "PUX Exception"}
        ).fillna("No Scan")

    return df


# ── main entry point ──────────────────────────────────────────────────────────
def render_nsl_tab() -> None:
    """Render the full NSL Analytics content inside a tab."""

    render_info_banner(
        "NSL Analytics — India Outbound",
        "Upload the NSL comma-separated data file to explore Network Service Level "
        "performance, failure ownership, scan compliance, and customer-level trends. "
        "Large files (2 M+ rows) are chunked and cached — upload once, filter instantly.",
        accent=_PURPLE,
    )

    uploaded = st.file_uploader(
        "Upload NSL Data File (.txt / .csv)",
        type=["txt", "csv"],
        help="Comma-separated NSL export. Max 2 GB.",
        key="nsl_upload",
    )

    if uploaded is None:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#999;">
            <div style="font-size:48px;margin-bottom:16px;">📂</div>
            <div style="font-size:16px;font-weight:600;">Upload an NSL data file above to begin</div>
            <div style="font-size:13px;margin-top:8px;">
                Supports files up to 2 GB. Charts populate automatically after upload.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    raw_df = _load_nsl(uploaded.read())
    total_rows = len(raw_df)
    st.caption(f"✅ Loaded **{total_rows:,}** records from **{uploaded.name}**")

    # ── filter bar ────────────────────────────────────────────────────────────
    with st.expander("🔽  Filters", expanded=True):
        fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2, 2, 2, 1.5, 1.5, 1.5])

        all_lanes = sorted(raw_df["lane"].dropna().unique()) if "lane" in raw_df.columns else []
        sel_lanes = fc1.multiselect("Lane (orig → dest region)", all_lanes,
                                    placeholder="All lanes", key="nsl_f_lane")

        all_markets = sorted(raw_df["dest_market_cd"].dropna().unique()) \
            if "dest_market_cd" in raw_df.columns else []
        sel_markets = fc2.multiselect("Destination Market", all_markets,
                                      placeholder="All markets", key="nsl_f_market")

        top_custs = (raw_df.groupby("shpr_co_nm")["TOT_VOL"].sum()
                     .nlargest(60).index.tolist()) if "shpr_co_nm" in raw_df.columns else []
        sel_custs = fc3.multiselect("Customer", top_custs,
                                    placeholder="Top 60 by volume", key="nsl_f_cust")

        all_products = sorted(raw_df["Product"].dropna().unique()) \
            if "Product" in raw_df.columns else []
        sel_products = fc4.multiselect("Product", all_products,
                                       placeholder="All", key="nsl_f_prod")

        all_services = sorted(raw_df["Service"].dropna().unique()) \
            if "Service" in raw_df.columns else []
        sel_services = fc5.multiselect("Service", all_services,
                                       placeholder="All", key="nsl_f_svc")

        if "month_date" in raw_df.columns:
            months = sorted(raw_df["month_date"].dropna().dt.to_period("M").unique())
            month_labels = [str(m) for m in months]
            sel_months = fc6.multiselect("Month", month_labels,
                                         placeholder="All months", key="nsl_f_month")
        else:
            sel_months = []

        rc1, _ = st.columns([1, 5])
        if rc1.button("Reset Filters", key="nsl_reset"):
            for k in ["nsl_f_lane","nsl_f_market","nsl_f_cust",
                      "nsl_f_prod","nsl_f_svc","nsl_f_month"]:
                st.session_state.pop(k, None)
            st.rerun()

    # apply filters
    df = raw_df.copy()
    if sel_lanes    and "lane"           in df.columns: df = df[df["lane"].isin(sel_lanes)]
    if sel_markets  and "dest_market_cd" in df.columns: df = df[df["dest_market_cd"].isin(sel_markets)]
    if sel_custs    and "shpr_co_nm"     in df.columns: df = df[df["shpr_co_nm"].isin(sel_custs)]
    if sel_products and "Product"        in df.columns: df = df[df["Product"].isin(sel_products)]
    if sel_services and "Service"        in df.columns: df = df[df["Service"].isin(sel_services)]
    if sel_months and "month_date" in df.columns:
        df = df[df["month_date"].dt.to_period("M").astype(str).isin(sel_months)]

    if len(df) == 0:
        st.warning("No records match the current filters — please broaden your selection.")
        return

    if len(df) < total_rows:
        st.caption(f"📌 Showing **{len(df):,}** of {total_rows:,} records after filters")

    # ── KPI row ───────────────────────────────────────────────────────────────
    tot_vol  = int(df["TOT_VOL"].sum())    if "TOT_VOL"    in df.columns else len(df)
    nsl_vol  = int(df["NSL_OT_VOL"].sum()) if "NSL_OT_VOL" in df.columns else 0
    mbg_vol  = int(df["MBG_OT_VOL"].sum()) if "MBG_OT_VOL" in df.columns else 0
    nsl_pct  = nsl_vol / tot_vol * 100 if tot_vol else 0
    mbg_pct  = mbg_vol / tot_vol * 100 if tot_vol else 0
    scan_comp = ((df["scan_type_num"] == 8.0).sum() / len(df) * 100
                 if "scan_type_num" in df.columns else 0.0)

    nsl_color  = _GREEN if nsl_pct  >= 75 else (_YELLOW if nsl_pct  >= 65 else _RED)
    mbg_color  = _GREEN if mbg_pct  >= 85 else (_YELLOW if mbg_pct  >= 75 else _RED)
    scan_color = _GREEN if scan_comp >= 70 else (_YELLOW if scan_comp >= 50 else _RED)

    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    render_kpi_card(k1, "Total Shipments", f"{tot_vol:,}",     color=_PURPLE, icon="📦")
    render_kpi_card(k2, "NSL On-Time",     f"{nsl_pct:.1f}%",  color=nsl_color,
                    subtitle=f"{nsl_vol:,} of {tot_vol:,}")
    render_kpi_card(k3, "NSL + 24",        "— Pending",        color=_GREY,
                    subtitle="Definition TBD")
    render_kpi_card(k4, "MBG On-Time",     f"{mbg_pct:.1f}%",  color=mbg_color,
                    subtitle=f"{mbg_vol:,} of {tot_vol:,}")
    render_kpi_card(k5, "Scan Compliance", f"{scan_comp:.1f}%", color=scan_color,
                    subtitle="Clean PUP / total shipments")
    st.markdown("<br>", unsafe_allow_html=True)

    # ── analytics tabs ────────────────────────────────────────────────────────
    t_trend, t_geo, t_fail, t_cust, t_scan = st.tabs([
        "📈 Trends", "🌍 Geography", "🔴 Failure Analysis",
        "🏢 Customers", "🔍 Scan Compliance",
    ])

    # ── TRENDS ────────────────────────────────────────────────────────────────
    with t_trend:
        if "weekending_dt" in df.columns and not df["weekending_dt"].isna().all():
            weekly = (df.groupby(["weekending_dt", "Service"])
                      .agg(nsl_ot=("NSL_OT_VOL","sum"), tot=("TOT_VOL","sum"))
                      .reset_index())
            weekly["nsl_pct"] = weekly["nsl_ot"] / weekly["tot"] * 100
            fig = go.Figure()
            for i, svc in enumerate(weekly["Service"].unique()):
                s = weekly[weekly["Service"] == svc].sort_values("weekending_dt")
                fig.add_trace(go.Scatter(
                    x=s["weekending_dt"], y=s["nsl_pct"].round(1),
                    name=svc, mode="lines+markers",
                    line=dict(color=_SEQ[i % len(_SEQ)], width=2.5), marker=dict(size=5),
                    hovertemplate="%{x|%d %b %Y}<br>NSL OT: %{y:.1f}%<extra>" + svc + "</extra>",
                ))
            fig.add_hline(y=100, line_dash="dot", line_color="#CCCCCC", line_width=1)
            fig.update_layout(
                title="NSL On-Time % — Weekly by Service",
                yaxis=dict(title="NSL OT %", range=[0,105], gridcolor="#F0F0F0", ticksuffix="%"),
                xaxis=dict(title="", gridcolor="#F0F0F0"),
                **_base_layout(),
            )
            st.plotly_chart(fig, use_container_width=True)

        if "MBG_Class" in df.columns and "month_date" in df.columns:
            mbg_m = (df.groupby([df["month_date"].dt.to_period("M").astype(str), "MBG_Class"])
                     ["TOT_VOL"].sum().reset_index())
            mbg_m.columns = ["month","mbg_class","vol"]
            fig2 = go.Figure()
            for cls in ["OnTime","EWDL","WDL","ERDL","RDL"]:
                s = mbg_m[mbg_m["mbg_class"] == cls]
                if len(s):
                    fig2.add_trace(go.Bar(
                        x=s["month"], y=s["vol"], name=cls,
                        marker_color=_MBG_COLORS.get(cls,"#CCC"),
                        hovertemplate="%{x}<br>%{y:,} pkgs<extra>" + cls + "</extra>",
                    ))
            fig2.update_layout(barmode="stack", title="Monthly Volume by MBG Class",
                               yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                               xaxis=dict(title=""), **_base_layout())
            st.plotly_chart(fig2, use_container_width=True)

    # ── GEOGRAPHY ─────────────────────────────────────────────────────────────
    with t_geo:
        col_a, col_b = st.columns([1.4, 1])
        with col_a:
            if "dest_region" in df.columns:
                geo = (df.groupby("dest_region")
                       .agg(nsl_ot=("NSL_OT_VOL","sum"), tot=("TOT_VOL","sum"))
                       .reset_index())
                geo["nsl_pct"] = (geo["nsl_ot"] / geo["tot"] * 100).round(1)
                geo = geo.sort_values("nsl_pct")
                bar_colors = [_GREEN if v>=75 else (_YELLOW if v>=65 else _RED)
                              for v in geo["nsl_pct"]]
                fig = go.Figure(go.Bar(
                    x=geo["nsl_pct"], y=geo["dest_region"], orientation="h",
                    marker_color=bar_colors,
                    text=[f"{v:.1f}%  ({r:,})" for v,r in zip(geo["nsl_pct"],geo["tot"])],
                    textposition="outside",
                    hovertemplate="%{y}<br>NSL OT: %{x:.1f}%<extra></extra>",
                ))
                fig.add_vline(x=75, line_dash="dash", line_color=_PURPLE, line_width=1.5,
                              annotation_text="75% target", annotation_position="top right")
                fig.update_layout(
                    title="NSL On-Time % by Destination Region",
                    xaxis=dict(title="NSL OT %", range=[0,115], ticksuffix="%", gridcolor="#F0F0F0"),
                    yaxis=dict(title=""),
                    **_base_layout(margin=dict(l=8,r=80,t=36,b=16)),
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if "dest_market_cd" in df.columns:
                mkts = (df.groupby("dest_market_cd")
                        .agg(nsl_ot=("NSL_OT_VOL","sum"), tot=("TOT_VOL","sum"))
                        .reset_index())
                mkts["nsl_pct"] = (mkts["nsl_ot"] / mkts["tot"] * 100).round(1)
                mkts = mkts.nlargest(15,"tot").sort_values("tot", ascending=False)
                st.markdown('<div style="font-size:13px;font-weight:700;color:#333;'
                            'margin-bottom:8px;">Top 15 Destination Markets</div>',
                            unsafe_allow_html=True)
                disp = mkts[["dest_market_cd","tot","nsl_pct"]].copy()
                disp.columns = ["Market","Volume","NSL OT %"]
                disp["Volume"]   = disp["Volume"].apply(lambda x: f"{int(x):,}")
                disp["NSL OT %"] = disp["NSL OT %"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(disp, use_container_width=True, hide_index=True, height=420)

    # ── FAILURE ANALYSIS ──────────────────────────────────────────────────────
    with t_fail:
        if "Bucket" not in df.columns:
            st.info("'Bucket' column not found.")
        else:
            col_c, col_d = st.columns([1.5, 1])
            with col_c:
                if "month_date" in df.columns:
                    fail_df = df[df["NSL_OT_VOL"] == 0] if "NSL_OT_VOL" in df.columns else df
                    fm = (fail_df.groupby([fail_df["month_date"].dt.to_period("M").astype(str), "Bucket"])
                          ["TOT_VOL"].sum().reset_index())
                    fm.columns = ["month","bucket","vol"]
                    fig = go.Figure()
                    for b in fm.groupby("bucket")["vol"].sum().sort_values(ascending=False).index:
                        s = fm[fm["bucket"] == b]
                        fig.add_trace(go.Bar(x=s["month"], y=s["vol"], name=b,
                                             marker_color=_BUCKET_COLORS.get(b,"#CCC"),
                                             hovertemplate="%{x}<br>%{y:,}<extra>"+b+"</extra>"))
                    fig.update_layout(barmode="stack", title="NSL Failure Volume by Bucket (Monthly)",
                                      yaxis=dict(title="Failed Shipments", gridcolor="#F0F0F0"),
                                      xaxis=dict(title=""), **_base_layout())
                    st.plotly_chart(fig, use_container_width=True)

            with col_d:
                bs = (df[df["NSL_OT_VOL"]==0].groupby("Bucket")["TOT_VOL"].sum()
                      if "NSL_OT_VOL" in df.columns
                      else df.groupby("Bucket")["TOT_VOL"].sum())
                bs = bs.reset_index().sort_values("TOT_VOL", ascending=False)
                bs.columns = ["bucket","vol"]
                fig = go.Figure(go.Pie(
                    labels=bs["bucket"], values=bs["vol"], hole=0.55,
                    marker_colors=[_BUCKET_COLORS.get(b,"#CCC") for b in bs["bucket"]],
                    textinfo="label+percent", textfont_size=11,
                    hovertemplate="%{label}<br>%{value:,}<br>%{percent}<extra></extra>",
                ))
                fig.update_layout(title="Failure Ownership Share", showlegend=False,
                                  **_base_layout(margin=dict(l=8,r=8,t=36,b=8)))
                st.plotly_chart(fig, use_container_width=True)

            if "pof_cause" in df.columns and "NSL_OT_VOL" in df.columns:
                st.markdown('<div style="font-size:13px;font-weight:700;color:#333;'
                            'margin-top:16px;margin-bottom:8px;">Top POF Causes</div>',
                            unsafe_allow_html=True)
                pof = (df[df["NSL_OT_VOL"]==0].groupby("pof_cause")["TOT_VOL"].sum()
                       .reset_index().nlargest(15,"TOT_VOL"))
                pof.columns = ["POF Cause","Failed Shipments"]
                pof["Failed Shipments"] = pof["Failed Shipments"].apply(lambda x: f"{int(x):,}")
                st.dataframe(pof, use_container_width=True, hide_index=True)

    # ── CUSTOMERS ─────────────────────────────────────────────────────────────
    with t_cust:
        if "shpr_co_nm" not in df.columns:
            st.info("Customer column not available.")
        else:
            nc1, _ = st.columns([1, 4])
            top_n = nc1.slider("Show top N customers", 5, 50, 20, step=5, key="nsl_cust_n")
            cg = df.groupby("shpr_co_nm").agg(
                vol=("TOT_VOL","sum"), nsl_ot=("NSL_OT_VOL","sum"), mbg_ot=("MBG_OT_VOL","sum")
            ).reset_index()
            cg["NSL OT %"] = (cg["nsl_ot"] / cg["vol"] * 100).round(1)
            cg["MBG OT %"] = (cg["mbg_ot"] / cg["vol"] * 100).round(1)
            ct = cg.nlargest(top_n,"vol").sort_values("vol", ascending=False)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ct["shpr_co_nm"], y=ct["NSL OT %"], name="NSL OT %",
                                 marker_color=_PURPLE,
                                 hovertemplate="%{x}<br>NSL OT: %{y:.1f}%<extra></extra>"))
            fig.add_trace(go.Bar(x=ct["shpr_co_nm"], y=ct["MBG OT %"], name="MBG OT %",
                                 marker_color=_ORANGE,
                                 hovertemplate="%{x}<br>MBG OT: %{y:.1f}%<extra></extra>"))
            fig.add_hline(y=75, line_dash="dash", line_color=_PURPLE, line_width=1.5,
                          annotation_text="NSL 75% target")
            fig.update_layout(barmode="group",
                              title=f"Top {top_n} Customers — NSL & MBG On-Time %",
                              xaxis=dict(title="", tickangle=-35),
                              yaxis=dict(title="On-Time %", range=[0,110],
                                         ticksuffix="%", gridcolor="#F0F0F0"),
                              **_base_layout())
            st.plotly_chart(fig, use_container_width=True)

            disp = ct[["shpr_co_nm","vol","NSL OT %","MBG OT %"]].copy()
            disp.columns = ["Customer","Volume","NSL OT %","MBG OT %"]
            disp["Volume"]   = disp["Volume"].apply(lambda x: f"{int(x):,}")
            disp["NSL OT %"] = disp["NSL OT %"].apply(lambda x: f"{x:.1f}%")
            disp["MBG OT %"] = disp["MBG OT %"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(disp, use_container_width=True, hide_index=True)

            buf = io.StringIO()
            cg.to_csv(buf, index=False)
            st.download_button("⬇️  Download Full Customer Table (CSV)",
                               buf.getvalue().encode(), "nsl_customers.csv", "text/csv")

    # ── SCAN COMPLIANCE ───────────────────────────────────────────────────────
    with t_scan:
        if "scan_label" not in df.columns:
            st.info("Pickup scan columns not available.")
        else:
            sc1, sc2 = st.columns(2)
            with sc1:
                sd = df["scan_label"].value_counts().reset_index()
                sd.columns = ["scan_type","count"]
                cmap = {"Standard PUP (Clean)": _GREEN, "PUX Exception": _ORANGE, "No Scan": _RED}
                fig = go.Figure(go.Bar(
                    x=sd["scan_type"], y=sd["count"],
                    marker_color=[cmap.get(s,_GREY) for s in sd["scan_type"]],
                    text=[f"{v:,} ({v/len(df)*100:.1f}%)" for v in sd["count"]],
                    textposition="outside",
                    hovertemplate="%{x}<br>%{y:,}<extra></extra>",
                ))
                fig.update_layout(title="Pickup Scan Type Distribution",
                                  yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                                  xaxis=dict(title=""), **_base_layout())
                st.plotly_chart(fig, use_container_width=True)

            with sc2:
                if "pckup_stop_typ_cd" in df.columns:
                    stop_map = {"R":"Regular","C":"Call-tag","O":"On-call","M":"Mass","T":"Other"}
                    df2 = df.copy()
                    df2["stop_label"] = df2["pckup_stop_typ_cd"].map(stop_map).fillna("Unknown")
                    ss = (df2.groupby("stop_label").apply(lambda g: pd.Series({
                        "Clean (%)":  (g["scan_type_num"]==8.0).sum()/len(g)*100,
                        "PUX (%)":    (g["scan_type_num"]==29.0).sum()/len(g)*100,
                        "No Scan (%)": g["scan_type_num"].isna().sum()/len(g)*100,
                    })).reset_index())
                    fig = go.Figure()
                    for lbl, col in [("Clean (%)","Clean Scan"),("PUX (%)","PUX Exception"),("No Scan (%)","No Scan")]:
                        color = {"Clean (%)":_GREEN,"PUX (%)":_ORANGE,"No Scan (%)":_RED}[lbl]
                        fig.add_trace(go.Bar(x=ss["stop_label"], y=ss[lbl].round(1),
                                             name=col, marker_color=color,
                                             hovertemplate="%{x}<br>%{y:.1f}%<extra>"+col+"</extra>"))
                    fig.update_layout(barmode="stack", title="Scan Type % by Stop Type",
                                      yaxis=dict(title="%",ticksuffix="%",range=[0,105],gridcolor="#F0F0F0"),
                                      xaxis=dict(title="Stop Type"), **_base_layout())
                    st.plotly_chart(fig, use_container_width=True)

            # PUX breakdown
            if "pkg_pckup_excp_typ_cd" in df.columns:
                pux = df[df["scan_type_num"] == 29.0].copy()
                if len(pux):
                    st.markdown('<div style="font-size:13px;font-weight:700;color:#333;'
                                'margin-top:8px;margin-bottom:8px;">PUX Exception Code Breakdown</div>',
                                unsafe_allow_html=True)
                    pc = pux["pkg_pckup_excp_typ_cd"].value_counts().reset_index()
                    pc.columns = ["code","count"]
                    pc["code_num"] = pd.to_numeric(pc["code"], errors="coerce")
                    pc["label"] = pc["code_num"].map(
                        lambda x: _PUX_NAMES.get(int(x), f"PUX{int(x):02d}") if pd.notna(x) else "Unknown"
                    )
                    pc["pct"] = (pc["count"] / len(df) * 100).round(2)
                    fig = go.Figure(go.Bar(
                        x=pc["label"], y=pc["count"], marker_color=_ORANGE,
                        text=[f"{v:,}" for v in pc["count"]], textposition="outside",
                        customdata=pc["pct"],
                        hovertemplate="%{x}<br>%{y:,} (%{customdata:.2f}%)<extra></extra>",
                    ))
                    fig.update_layout(title="PUX Exception Volume by Code",
                                      xaxis=dict(title="", tickangle=-30),
                                      yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                                      **_base_layout(margin=dict(l=16,r=16,t=36,b=80)))
                    st.plotly_chart(fig, use_container_width=True)

            # Weekly compliance trend
            if "weekending_dt" in df.columns and not df["weekending_dt"].isna().all():
                ws = (df.groupby("weekending_dt").apply(lambda g: pd.Series({
                    "clean_pct":  (g["scan_type_num"]==8.0).sum()/len(g)*100,
                    "pux_pct":    (g["scan_type_num"]==29.0).sum()/len(g)*100,
                    "noscan_pct": g["scan_type_num"].isna().sum()/len(g)*100,
                })).reset_index().sort_values("weekending_dt"))
                fig = go.Figure()
                for col, color, lbl in [("clean_pct",_GREEN,"Clean Scan"),
                                         ("pux_pct",_ORANGE,"PUX Exception"),
                                         ("noscan_pct",_RED,"No Scan")]:
                    fig.add_trace(go.Scatter(
                        x=ws["weekending_dt"], y=ws[col].round(1),
                        name=lbl, mode="lines+markers",
                        line=dict(color=color, width=2.5), marker=dict(size=5),
                        hovertemplate="%{x|%d %b %Y}<br>%{y:.1f}%<extra>"+lbl+"</extra>",
                    ))
                fig.update_layout(
                    title="Weekly Scan Compliance Trend",
                    yaxis=dict(title="%",ticksuffix="%",range=[0,105],gridcolor="#F0F0F0"),
                    xaxis=dict(title="", gridcolor="#F0F0F0"),
                    **_base_layout(),
                )
                st.plotly_chart(fig, use_container_width=True)

