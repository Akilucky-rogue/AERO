# ============================================================
# AERO — NSL Analytics Dashboard (Leadership)
# ============================================================
import io
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from aero.ui.header import render_header, render_footer
from aero.auth.service import get_current_user
from aero.ui.components import (
    render_kpi_card,
    render_info_banner,
    _PURPLE, _ORANGE, _GREEN, _RED, _YELLOW,
)

# ── brand colours for Plotly ─────────────────────────────────
_COLORS = {
    "purple": "#4D148C",
    "orange": "#FF6200",
    "green":  "#008A00",
    "red":    "#DE002E",
    "yellow": "#FFB800",
    "grey":   "#888888",
    "blue":   "#1A5276",
    "teal":   "#0097A7",
}
_SEQ = [_COLORS["purple"], _COLORS["orange"], _COLORS["blue"],
        _COLORS["green"], _COLORS["red"], _COLORS["yellow"],
        _COLORS["teal"], _COLORS["grey"]]

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
    "OnTime": "#008A00",
    "EWDL":   "#FFB800",
    "WDL":    "#FF6200",
    "ERDL":   "#DE002E",
    "RDL":    "#8B0000",
}

_user = get_current_user()

render_header(
    "NSL ANALYTICS",
    "Network Service Level | India Outbound | FedEx Planning & Engineering",
    logo_height=80,
    badge="LEADERSHIP",
)

# ── Plotly layout defaults ───────────────────────────────────
def _base_layout(**kwargs):
    return dict(
        font=dict(family="Inter, sans-serif", size=12, color="#333"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=16, r=16, t=36, b=16),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font_size=11),
        **kwargs,
    )


# ════════════════════════════════════════════════════════════
# DATA LOADING — cached on file content hash
# ════════════════════════════════════════════════════════════
@st.cache_data(show_spinner="Parsing NSL file — this may take 30–60 s for large files…")
def load_nsl(file_bytes: bytes) -> pd.DataFrame:
    """Load the full NSL file into a DataFrame (cached per unique file).

    Strategy:
    1. Try fast C-engine in chunks; break gracefully on EOF/parse errors (last row often
       has an unclosed quoted string in large exports).
    2. If zero chunks loaded, fall back to the Python engine which handles malformed
       EOF rows without crashing.
    """
    chunks = []
    chunk_size = 400_000
    _common_kwargs = dict(
        sep=",",
        quotechar='"',
        on_bad_lines="skip",
        low_memory=False,
    )

    # ── Pass 1: C engine (fast) — tolerate EOF parse error on last chunk
    try:
        reader = pd.read_csv(
            io.BytesIO(file_bytes),
            chunksize=chunk_size,
            **_common_kwargs,
        )
        for chunk in reader:
            chunks.append(chunk)
    except Exception:
        # EOF/parse error hit — keep whatever chunks we have so far
        pass

    # ── Pass 2: Python engine fallback if C engine got nothing at all
    if not chunks:
        try:
            df_fallback = pd.read_csv(
                io.BytesIO(file_bytes),
                engine="python",
                **_common_kwargs,
            )
            chunks.append(df_fallback)
        except Exception as e2:
            raise RuntimeError(
                f"Could not parse the NSL file with either parser. Error: {e2}"
            ) from e2

    df = pd.concat(chunks, ignore_index=True)

    # ── date parsing
    for col in ["month_date", "weekending_dt", "shp_dt", "svc_commit_dt",
                "pckup_scan_dt", "pod_scan_dt"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # ── derived columns
    if "NSL_OT_VOL" in df.columns and "TOT_VOL" in df.columns:
        df["NSL_OT_VOL"] = pd.to_numeric(df["NSL_OT_VOL"], errors="coerce").fillna(0)
        df["MBG_OT_VOL"] = pd.to_numeric(df.get("MBG_OT_VOL", 0), errors="coerce").fillna(0)
        df["TOT_VOL"]    = pd.to_numeric(df["TOT_VOL"],    errors="coerce").fillna(1)

    # Lane = orig_region → dest_region
    if "orig_region" in df.columns and "dest_region" in df.columns:
        df["lane"] = df["orig_region"].fillna("?") + " → " + df["dest_region"].fillna("?")

    # Scan compliance label
    if "pkg_pckup_scan_typ_cd" in df.columns:
        df["scan_type_num"] = pd.to_numeric(df["pkg_pckup_scan_typ_cd"], errors="coerce")
        df["scan_label"] = df["scan_type_num"].map(
            {8.0: "Standard PUP (Clean)", 29.0: "PUX Exception"}
        ).fillna("No Scan")

    return df


# ════════════════════════════════════════════════════════════
# UPLOAD SECTION
# ════════════════════════════════════════════════════════════
render_info_banner(
    "NSL Analytics — India Outbound",
    "Upload the NSL tab/comma-separated data file to explore Network Service Level "
    "performance, failure ownership, scan compliance, and customer-level trends. "
    "Large files (2M+ rows) are chunked automatically and cached for fast re-filtering.",
    accent=_PURPLE,
)

uploaded = st.file_uploader(
    "Upload NSL Data File",
    type=["txt", "csv"],
    help="Tab-separated or comma-separated NSL export. Accepts .txt or .csv.",
    key="nsl_upload",
)

if uploaded is None:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;color:#999;">
        <div style="font-size:48px;margin-bottom:16px;">📂</div>
        <div style="font-size:16px;font-weight:600;">Upload an NSL data file above to get started</div>
        <div style="font-size:13px;margin-top:8px;">
            Supports files up to 2M+ rows. Charts appear automatically after upload.
        </div>
    </div>""", unsafe_allow_html=True)
    render_footer("LEADERSHIP")
    st.stop()

# ── Load data ────────────────────────────────────────────────
with st.spinner("Loading…"):
    raw_df = load_nsl(uploaded.read())

total_rows = len(raw_df)
st.caption(f"✅ Loaded {total_rows:,} shipment records from **{uploaded.name}**")


# ════════════════════════════════════════════════════════════
# FILTER BAR
# ════════════════════════════════════════════════════════════
with st.expander("🔽  Filters", expanded=True):
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2, 2, 2, 1.5, 1.5, 1.5])

    # Lane
    all_lanes = sorted(raw_df["lane"].dropna().unique()) if "lane" in raw_df.columns else []
    sel_lanes = fc1.multiselect("Lane (orig → dest region)", all_lanes,
                                placeholder="All lanes", key="f_lane")

    # Market
    all_markets = sorted(raw_df["dest_market_cd"].dropna().unique()) \
        if "dest_market_cd" in raw_df.columns else []
    sel_markets = fc2.multiselect("Destination Market", all_markets,
                                  placeholder="All markets", key="f_market")

    # Customer
    if "shpr_co_nm" in raw_df.columns:
        top_custs = (raw_df.groupby("shpr_co_nm")["TOT_VOL"]
                     .sum().nlargest(60).index.tolist())
        sel_custs = fc3.multiselect("Customer", top_custs,
                                    placeholder="Top 60 by volume", key="f_cust")
    else:
        sel_custs = []

    # Product
    all_products = sorted(raw_df["Product"].dropna().unique()) \
        if "Product" in raw_df.columns else []
    sel_products = fc4.multiselect("Product", all_products,
                                   placeholder="All", key="f_prod")

    # Service
    all_services = sorted(raw_df["Service"].dropna().unique()) \
        if "Service" in raw_df.columns else []
    sel_services = fc5.multiselect("Service", all_services,
                                   placeholder="All", key="f_svc")

    # Month
    if "month_date" in raw_df.columns:
        months = sorted(raw_df["month_date"].dropna().dt.to_period("M").unique())
        month_labels = [str(m) for m in months]
        sel_months = fc6.multiselect("Month", month_labels,
                                     placeholder="All months", key="f_month")
    else:
        sel_months = []

    rc1, rc2 = st.columns([1, 5])
    if rc1.button("Reset Filters", key="reset_filters"):
        for k in ["f_lane", "f_market", "f_cust", "f_prod", "f_svc", "f_month"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── Apply filters ────────────────────────────────────────────
df = raw_df.copy()
if sel_lanes:
    df = df[df["lane"].isin(sel_lanes)]
if sel_markets:
    df = df[df["dest_market_cd"].isin(sel_markets)]
if sel_custs:
    df = df[df["shpr_co_nm"].isin(sel_custs)]
if sel_products:
    df = df[df["Product"].isin(sel_products)]
if sel_services:
    df = df[df["Service"].isin(sel_services)]
if sel_months and "month_date" in df.columns:
    df = df[df["month_date"].dt.to_period("M").astype(str).isin(sel_months)]

if len(df) == 0:
    st.warning("No records match the current filters. Please broaden your selection.")
    render_footer("LEADERSHIP")
    st.stop()

filtered_rows = len(df)
if filtered_rows < total_rows:
    st.caption(f"📌 Showing **{filtered_rows:,}** of {total_rows:,} records after filters")


# ════════════════════════════════════════════════════════════
# KPI CARDS
# ════════════════════════════════════════════════════════════
tot_vol     = int(df["TOT_VOL"].sum()) if "TOT_VOL" in df.columns else filtered_rows
nsl_vol     = int(df["NSL_OT_VOL"].sum()) if "NSL_OT_VOL" in df.columns else 0
mbg_vol     = int(df["MBG_OT_VOL"].sum()) if "MBG_OT_VOL" in df.columns else 0
nsl_pct     = nsl_vol / tot_vol * 100 if tot_vol else 0
mbg_pct     = mbg_vol / tot_vol * 100 if tot_vol else 0

# Scan compliance: standard clean pickup (scan type 8) among scanned shipments
if "scan_type_num" in df.columns:
    scanned_df  = df[df["scan_type_num"].notna()]
    clean_scans = int((df["scan_type_num"] == 8.0).sum())
    scan_comp   = clean_scans / len(df) * 100 if len(df) else 0
else:
    scan_comp = 0.0

nsl_color  = _GREEN if nsl_pct >= 75 else (_YELLOW if nsl_pct >= 65 else _RED)
mbg_color  = _GREEN if mbg_pct >= 85 else (_YELLOW if mbg_pct >= 75 else _RED)
scan_color = _GREEN if scan_comp >= 70 else (_YELLOW if scan_comp >= 50 else _RED)

st.markdown("<br>", unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)
render_kpi_card(k1, "Total Shipments",  f"{tot_vol:,}",     color=_PURPLE, icon="📦")
render_kpi_card(k2, "NSL On-Time",      f"{nsl_pct:.1f}%",  color=nsl_color,
                subtitle=f"{nsl_vol:,} of {tot_vol:,} on-time")
render_kpi_card(k3, "NSL + 24",         "— Pending",        color=_GREY,
                subtitle="Definition TBD")
render_kpi_card(k4, "MBG On-Time",      f"{mbg_pct:.1f}%",  color=mbg_color,
                subtitle=f"{mbg_vol:,} of {tot_vol:,} on-time")
render_kpi_card(k5, "Scan Compliance",  f"{scan_comp:.1f}%", color=scan_color,
                subtitle="Clean PUP scans / total shipments")

st.markdown("<br>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════
tab_trend, tab_geo, tab_fail, tab_cust, tab_scan = st.tabs([
    "📈 Trends", "🌍 Geography", "🔴 Failure Analysis",
    "🏢 Customers", "🔍 Scan Compliance"
])


# ────────────────────────────────────────────────────────────
# TAB 1 — TRENDS
# ────────────────────────────────────────────────────────────
with tab_trend:
    if "weekending_dt" not in df.columns or df["weekending_dt"].isna().all():
        st.info("weekending_dt column not available for trend analysis.")
    else:
        weekly = (
            df.groupby(["weekending_dt", "Service"])
            .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
            .reset_index()
        )
        weekly["nsl_pct"] = weekly["nsl_ot"] / weekly["tot"] * 100

        fig_line = go.Figure()
        for i, svc in enumerate(weekly["Service"].unique()):
            s = weekly[weekly["Service"] == svc].sort_values("weekending_dt")
            fig_line.add_trace(go.Scatter(
                x=s["weekending_dt"], y=s["nsl_pct"].round(1),
                name=svc, mode="lines+markers",
                line=dict(color=_SEQ[i % len(_SEQ)], width=2.5),
                marker=dict(size=5),
                hovertemplate="%{x|%d %b %Y}<br>NSL OT: %{y:.1f}%<extra>" + svc + "</extra>",
            ))
        fig_line.add_hline(y=100, line_dash="dot", line_color="#CCCCCC", line_width=1)
        fig_line.update_layout(
            title="NSL On-Time % — Weekly by Service",
            yaxis=dict(title="NSL OT %", range=[0, 105],
                       gridcolor="#F0F0F0", ticksuffix="%"),
            xaxis=dict(title="", gridcolor="#F0F0F0"),
            **_base_layout(),
        )
        st.plotly_chart(fig_line, width="stretch")

        st.markdown("<br>", unsafe_allow_html=True)

        # Monthly volume stacked by MBG_Class
        if "MBG_Class" in df.columns and "month_date" in df.columns:
            mbg_month = (
                df.groupby([df["month_date"].dt.to_period("M").astype(str), "MBG_Class"])["TOT_VOL"]
                .sum().reset_index()
            )
            mbg_month.columns = ["month", "mbg_class", "vol"]
            fig_mbg = go.Figure()
            for cls in ["OnTime", "EWDL", "WDL", "ERDL", "RDL"]:
                s = mbg_month[mbg_month["mbg_class"] == cls]
                if len(s):
                    fig_mbg.add_trace(go.Bar(
                        x=s["month"], y=s["vol"],
                        name=cls,
                        marker_color=_MBG_COLORS.get(cls, "#CCC"),
                        hovertemplate="%{x}<br>%{y:,} packages<extra>" + cls + "</extra>",
                    ))
            fig_mbg.update_layout(
                barmode="stack",
                title="Monthly Volume by MBG Class",
                yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                xaxis=dict(title=""),
                **_base_layout(),
            )
            st.plotly_chart(fig_mbg, width="stretch")


# ────────────────────────────────────────────────────────────
# TAB 2 — GEOGRAPHY
# ────────────────────────────────────────────────────────────
with tab_geo:
    col_a, col_b = st.columns([1.4, 1])

    with col_a:
        if "dest_region" in df.columns:
            geo_reg = (
                df.groupby("dest_region")
                .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                .reset_index()
            )
            geo_reg["nsl_pct"] = (geo_reg["nsl_ot"] / geo_reg["tot"] * 100).round(1)
            geo_reg["vol_pct"] = (geo_reg["tot"] / geo_reg["tot"].sum() * 100).round(1)
            geo_reg = geo_reg.sort_values("nsl_pct")
            bar_colors = [
                _GREEN if v >= 75 else (_YELLOW if v >= 65 else _RED)
                for v in geo_reg["nsl_pct"]
            ]
            fig_reg = go.Figure(go.Bar(
                x=geo_reg["nsl_pct"], y=geo_reg["dest_region"],
                orientation="h",
                marker_color=bar_colors,
                text=[f"{v:.1f}% ({r:,} pkgs)" for v, r in
                      zip(geo_reg["nsl_pct"], geo_reg["tot"])],
                textposition="outside",
                hovertemplate="%{y}<br>NSL OT: %{x:.1f}%<extra></extra>",
            ))
            fig_reg.add_vline(x=75, line_dash="dash",
                              line_color=_PURPLE, line_width=1.5,
                              annotation_text="75% target",
                              annotation_position="top right")
            fig_reg.update_layout(
                title="NSL On-Time % by Destination Region",
                xaxis=dict(title="NSL OT %", range=[0, 110], ticksuffix="%",
                           gridcolor="#F0F0F0"),
                yaxis=dict(title=""),
                **_base_layout(margin=dict(l=8, r=80, t=36, b=16)),
            )
            st.plotly_chart(fig_reg, width="stretch")

    with col_b:
        if "dest_market_cd" in df.columns:
            top_mkts = (
                df.groupby("dest_market_cd")
                .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                .reset_index()
            )
            top_mkts["nsl_pct"] = (top_mkts["nsl_ot"] / top_mkts["tot"] * 100).round(1)
            top_mkts["mbg_pct"] = (
                df.groupby("dest_market_cd")["MBG_OT_VOL"].sum().reset_index()["MBG_OT_VOL"]
                / top_mkts["tot"] * 100
            ).round(1) if "MBG_OT_VOL" in df.columns else 0
            top_mkts = top_mkts.nlargest(15, "tot").sort_values("tot", ascending=False)

            st.markdown(
                '<div style="font-size:13px;font-weight:700;color:#333;'
                'margin-bottom:8px;">Top 15 Destination Markets</div>',
                unsafe_allow_html=True,
            )
            display_df = top_mkts[["dest_market_cd", "tot", "nsl_pct"]].copy()
            display_df.columns = ["Market", "Volume", "NSL OT %"]
            display_df["Volume"] = display_df["Volume"].apply(lambda x: f"{int(x):,}")
            display_df["NSL OT %"] = display_df["NSL OT %"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(display_df, width="stretch", hide_index=True,
                         height=420)


# ────────────────────────────────────────────────────────────
# TAB 3 — FAILURE ANALYSIS
# ────────────────────────────────────────────────────────────
with tab_fail:
    if "Bucket" not in df.columns:
        st.info("'Bucket' column not found in this dataset.")
    else:
        col_c, col_d = st.columns([1.5, 1])

        with col_c:
            # Stacked bar: failure volume by bucket by month
            if "month_date" in df.columns:
                fail_df = df[df["NSL_OT_VOL"] == 0].copy() if "NSL_OT_VOL" in df.columns else df
                fail_month = (
                    fail_df.groupby([fail_df["month_date"].dt.to_period("M").astype(str), "Bucket"])
                    ["TOT_VOL"].sum().reset_index()
                )
                fail_month.columns = ["month", "bucket", "vol"]

                fig_fail = go.Figure()
                buckets_sorted = (
                    fail_month.groupby("bucket")["vol"].sum()
                    .sort_values(ascending=False).index.tolist()
                )
                for b in buckets_sorted:
                    s = fail_month[fail_month["bucket"] == b]
                    fig_fail.add_trace(go.Bar(
                        x=s["month"], y=s["vol"],
                        name=b,
                        marker_color=_BUCKET_COLORS.get(b, "#CCC"),
                        hovertemplate="%{x}<br>%{y:,} failures<extra>" + b + "</extra>",
                    ))
                fig_fail.update_layout(
                    barmode="stack",
                    title="NSL Failure Volume by Bucket (Monthly)",
                    yaxis=dict(title="Failed Shipments", gridcolor="#F0F0F0"),
                    xaxis=dict(title=""),
                    **_base_layout(),
                )
                st.plotly_chart(fig_fail, width="stretch")

        with col_d:
            # Donut: bucket share over full period
            bucket_share = (
                df[df["NSL_OT_VOL"] == 0].groupby("Bucket")["TOT_VOL"].sum()
                .reset_index() if "NSL_OT_VOL" in df.columns
                else df.groupby("Bucket")["TOT_VOL"].sum().reset_index()
            )
            bucket_share.columns = ["bucket", "vol"]
            bucket_share = bucket_share.sort_values("vol", ascending=False)

            fig_donut = go.Figure(go.Pie(
                labels=bucket_share["bucket"],
                values=bucket_share["vol"],
                hole=0.55,
                marker_colors=[_BUCKET_COLORS.get(b, "#CCC")
                               for b in bucket_share["bucket"]],
                textinfo="label+percent",
                textfont_size=11,
                hovertemplate="%{label}<br>%{value:,} shipments<br>%{percent}<extra></extra>",
            ))
            fig_donut.update_layout(
                title="Failure Ownership Share",
                showlegend=False,
                **_base_layout(margin=dict(l=8, r=8, t=36, b=8)),
            )
            st.plotly_chart(fig_donut, width="stretch")

        # POF cause breakdown table
        if "pof_cause" in df.columns:
            st.markdown(
                '<div style="font-size:13px;font-weight:700;color:#333;'
                'margin-top:16px;margin-bottom:8px;">Top POF Causes</div>',
                unsafe_allow_html=True,
            )
            pof_tbl = (
                df[df["NSL_OT_VOL"] == 0].groupby("pof_cause")["TOT_VOL"].sum()
                .reset_index().nlargest(15, "TOT_VOL")
            ) if "NSL_OT_VOL" in df.columns else pd.DataFrame()
            if len(pof_tbl):
                pof_tbl.columns = ["POF Cause", "Failed Shipments"]
                pof_tbl["Failed Shipments"] = pof_tbl["Failed Shipments"].apply(lambda x: f"{int(x):,}")
                st.dataframe(pof_tbl, width="stretch", hide_index=True)


# ────────────────────────────────────────────────────────────
# TAB 4 — CUSTOMERS
# ────────────────────────────────────────────────────────────
with tab_cust:
    if "shpr_co_nm" not in df.columns:
        st.info("Customer (shpr_co_nm) column not available.")
    else:
        nc1, nc2 = st.columns([1, 4])
        top_n = nc1.slider("Show top N customers", 5, 50, 20, step=5, key="cust_n")

        cust_grp = (
            df.groupby("shpr_co_nm").agg(
                vol      =("TOT_VOL",    "sum"),
                nsl_ot   =("NSL_OT_VOL", "sum"),
                mbg_ot   =("MBG_OT_VOL", "sum"),
            ).reset_index()
        )
        cust_grp["NSL OT %"] = (cust_grp["nsl_ot"] / cust_grp["vol"] * 100).round(1)
        cust_grp["MBG OT %"] = (cust_grp["mbg_ot"] / cust_grp["vol"] * 100).round(1)
        cust_top = cust_grp.nlargest(top_n, "vol").sort_values("vol", ascending=False)

        # Bar chart
        fig_cust = go.Figure()
        fig_cust.add_trace(go.Bar(
            x=cust_top["shpr_co_nm"], y=cust_top["NSL OT %"],
            name="NSL OT %", marker_color=_COLORS["purple"],
            hovertemplate="%{x}<br>NSL OT: %{y:.1f}%<extra></extra>",
        ))
        fig_cust.add_trace(go.Bar(
            x=cust_top["shpr_co_nm"], y=cust_top["MBG OT %"],
            name="MBG OT %", marker_color=_COLORS["orange"],
            hovertemplate="%{x}<br>MBG OT: %{y:.1f}%<extra></extra>",
        ))
        fig_cust.add_hline(y=75, line_dash="dash", line_color=_COLORS["purple"],
                           line_width=1.5, annotation_text="NSL 75% target")
        fig_cust.update_layout(
            barmode="group",
            title=f"Top {top_n} Customers — NSL & MBG On-Time %",
            xaxis=dict(title="", tickangle=-35),
            yaxis=dict(title="On-Time %", range=[0, 110], ticksuffix="%",
                       gridcolor="#F0F0F0"),
            **_base_layout(),
        )
        st.plotly_chart(fig_cust, width="stretch")

        # Table
        display_cust = cust_top[["shpr_co_nm", "vol", "NSL OT %", "MBG OT %"]].copy()
        display_cust.columns = ["Customer", "Volume", "NSL OT %", "MBG OT %"]
        display_cust["Volume"] = display_cust["Volume"].apply(lambda x: f"{int(x):,}")
        display_cust["NSL OT %"] = display_cust["NSL OT %"].apply(lambda x: f"{x:.1f}%")
        display_cust["MBG OT %"] = display_cust["MBG OT %"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_cust, width="stretch", hide_index=True)

        # Download
        csv_buf = io.StringIO()
        cust_grp.to_csv(csv_buf, index=False)
        st.download_button(
            "⬇️  Download Full Customer Table (CSV)",
            csv_buf.getvalue().encode(),
            "nsl_customer_breakdown.csv",
            "text/csv",
        )


# ────────────────────────────────────────────────────────────
# TAB 5 — SCAN COMPLIANCE
# ────────────────────────────────────────────────────────────
with tab_scan:
    if "scan_label" not in df.columns:
        st.info("Pickup scan columns not available in this dataset.")
    else:
        sc1, sc2 = st.columns(2)

        with sc1:
            # Scan type distribution
            scan_dist = df["scan_label"].value_counts().reset_index()
            scan_dist.columns = ["scan_type", "count"]
            scan_colors_map = {
                "Standard PUP (Clean)": _GREEN,
                "PUX Exception":        _ORANGE,
                "No Scan":              _RED,
            }
            fig_scan = go.Figure(go.Bar(
                x=scan_dist["scan_type"],
                y=scan_dist["count"],
                marker_color=[scan_colors_map.get(s, _GREY) for s in scan_dist["scan_type"]],
                text=[f"{v:,}\n({v/len(df)*100:.1f}%)" for v in scan_dist["count"]],
                textposition="outside",
                hovertemplate="%{x}<br>%{y:,} shipments<extra></extra>",
            ))
            fig_scan.update_layout(
                title="Pickup Scan Type Distribution",
                yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                xaxis=dict(title=""),
                **_base_layout(margin=dict(l=16, r=16, t=36, b=16)),
            )
            st.plotly_chart(fig_scan, width="stretch")

        with sc2:
            # Scan compliance by stop type
            if "pckup_stop_typ_cd" in df.columns:
                stop_map = {"R": "Regular", "C": "Call-tag", "O": "On-call",
                            "M": "Mass", "T": "Other"}
                df["stop_label"] = df["pckup_stop_typ_cd"].map(stop_map).fillna("Unknown")
                stop_scan = (
                    df.groupby("stop_label")
                    .apply(lambda g: pd.Series({
                        "Clean Scan (%)": (g["scan_type_num"] == 8.0).sum() / len(g) * 100,
                        "PUX Exception (%)": (g["scan_type_num"] == 29.0).sum() / len(g) * 100,
                        "No Scan (%)": g["scan_type_num"].isna().sum() / len(g) * 100,
                        "Total": len(g),
                    }))
                    .reset_index()
                )
                fig_stop = go.Figure()
                for col_name, color in [("Clean Scan (%)", _GREEN),
                                         ("PUX Exception (%)", _ORANGE),
                                         ("No Scan (%)", _RED)]:
                    fig_stop.add_trace(go.Bar(
                        x=stop_scan["stop_label"],
                        y=stop_scan[col_name].round(1),
                        name=col_name.replace(" (%)", ""),
                        marker_color=color,
                        hovertemplate="%{x}<br>%{y:.1f}%<extra>" + col_name + "</extra>",
                    ))
                fig_stop.update_layout(
                    barmode="stack",
                    title="Scan Type % by Stop Type",
                    yaxis=dict(title="%", ticksuffix="%", range=[0, 105],
                               gridcolor="#F0F0F0"),
                    xaxis=dict(title="Stop Type"),
                    **_base_layout(),
                )
                st.plotly_chart(fig_stop, width="stretch")

        # PUX exception code breakdown
        if "pkg_pckup_excp_typ_cd" in df.columns:
            pux_df = df[df["scan_type_num"] == 29.0].copy()
            if len(pux_df):
                st.markdown(
                    '<div style="font-size:13px;font-weight:700;color:#333;'
                    'margin-top:8px;margin-bottom:8px;">PUX Exception Code Breakdown</div>',
                    unsafe_allow_html=True,
                )

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

                pux_counts = pux_df["pkg_pckup_excp_typ_cd"].value_counts().reset_index()
                pux_counts.columns = ["code", "count"]
                pux_counts["code_num"] = pd.to_numeric(pux_counts["code"], errors="coerce")
                pux_counts["label"] = pux_counts["code_num"].map(
                    lambda x: _PUX_NAMES.get(int(x), f"PUX{int(x):02d}") if pd.notna(x) else "Unknown"
                )
                pux_counts["pct"] = (pux_counts["count"] / len(df) * 100).round(2)
                pux_counts = pux_counts.sort_values("count", ascending=False)

                fig_pux = go.Figure(go.Bar(
                    x=pux_counts["label"],
                    y=pux_counts["count"],
                    marker_color=_COLORS["orange"],
                    text=[f"{v:,}" for v in pux_counts["count"]],
                    textposition="outside",
                    hovertemplate="%{x}<br>%{y:,} shipments (%{customdata:.2f}%)<extra></extra>",
                    customdata=pux_counts["pct"],
                ))
                fig_pux.update_layout(
                    title="PUX Exception Volume by Code",
                    xaxis=dict(title="", tickangle=-30),
                    yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                    **_base_layout(margin=dict(l=16, r=16, t=36, b=80)),
                )
                st.plotly_chart(fig_pux, width="stretch")

        # Weekly scan compliance trend
        if "weekending_dt" in df.columns and not df["weekending_dt"].isna().all():
            st.markdown(
                '<div style="font-size:13px;font-weight:700;color:#333;'
                'margin-top:8px;margin-bottom:4px;">Scan Compliance Trend (Weekly)</div>',
                unsafe_allow_html=True,
            )
            weekly_scan = (
                df.groupby("weekending_dt").apply(lambda g: pd.Series({
                    "clean_pct":   (g["scan_type_num"] == 8.0).sum() / len(g) * 100,
                    "pux_pct":     (g["scan_type_num"] == 29.0).sum() / len(g) * 100,
                    "noscan_pct":  g["scan_type_num"].isna().sum() / len(g) * 100,
                    "total":       len(g),
                })).reset_index()
            )
            weekly_scan = weekly_scan.sort_values("weekending_dt")

            fig_trend = go.Figure()
            for col_name, color, label in [
                ("clean_pct",  _GREEN,  "Clean Scan"),
                ("pux_pct",    _ORANGE, "PUX Exception"),
                ("noscan_pct", _RED,    "No Scan"),
            ]:
                fig_trend.add_trace(go.Scatter(
                    x=weekly_scan["weekending_dt"],
                    y=weekly_scan[col_name].round(1),
                    name=label, mode="lines+markers",
                    line=dict(color=color, width=2.5),
                    marker=dict(size=5),
                    hovertemplate="%{x|%d %b %Y}<br>%{y:.1f}%<extra>" + label + "</extra>",
                ))
            fig_trend.update_layout(
                yaxis=dict(title="%", ticksuffix="%", range=[0, 105],
                           gridcolor="#F0F0F0"),
                xaxis=dict(title="", gridcolor="#F0F0F0"),
                **_base_layout(),
            )
            st.plotly_chart(fig_trend, width="stretch")

render_footer("LEADERSHIP")
