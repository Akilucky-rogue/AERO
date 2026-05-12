"""
nsl_tab.py — NSL Analytics tab renderer for the Leadership Executive Dashboard.

Call render_nsl_tab() inside a `with tab_svc:` block.
"""
import io
import os
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
    "red":    "#DE002E", "yellow": "#FFB800", "grey":  "#888888",
    "blue":   "#1A5276", "teal":   "#0097A7",
}
_SEQ = [_COLORS["purple"], _COLORS["orange"], _COLORS["blue"],
        _COLORS["green"],  _COLORS["red"],    _COLORS["yellow"],
        _COLORS["teal"],   _COLORS["grey"]]

_BUCKET_COLORS = {
    "CLEARANCE":          "#1A5276",
    "DEST":               "#DE002E",
    "EXCLUDE":            "#888888",
    "HUB":                "#FFB800",
    "ORIGIN":             "#FF6200",
    "TRANSIT-Linehaul":   "#4D148C",
    "TRANSIT-Processing": "#0097A7",
    "Maintenance":        "#9B59B6",
    "UNASSIGNED":         "#BDC3C7",
    "Other":              "#CCCCCC",
}
_BUCKET_LABELS = {
    "CLEARANCE":          "Clearance — Package held at customs/clearance",
    "DEST":               "Destination — Delivery failure at recipient",
    "EXCLUDE":            "Excluded — Service disruption / force majeure",
    "HUB":                "Hub — Sortation facility delay",
    "ORIGIN":             "Origin — Pickup or origin station failure",
    "TRANSIT-Linehaul":   "Transit-Linehaul — Linehaul departure/arrival delay",
    "TRANSIT-Processing": "Transit-Processing — In-transit sort or processing delay",
    "Maintenance":        "Maintenance — Aircraft or equipment maintenance",
    "UNASSIGNED":         "Unassigned — Root cause not yet coded",
    "Other":              "Other",
}
_POF_CAUSE_LABELS = {
    # Common POF cause codes → human-readable labels
    "A": "Adverse Weather",
    "B": "Bulk Out / Capacity",
    "C": "Customs / Clearance Hold",
    "D": "Damaged Package",
    "E": "Exceeds Service Limits",
    "F": "Flight / Aircraft Delay",
    "G": "Government / Regulatory Hold",
    "H": "Holiday / Closed",
    "I": "Incorrect Address",
    "J": "Mechanical Breakdown",
    "K": "Missed Pickup",
    "L": "Linehaul Delay",
    "M": "Missed Sort",
    "N": "No Attempt Made",
    "O": "On-Hold by Shipper",
    "P": "Payment / Credit Issue",
    "Q": "Queue / Sortation Delay",
    "R": "Refused by Recipient",
    "S": "Security Delay",
    "T": "Traffic / Congestion",
    "U": "Undeliverable",
    "V": "Volume Surge",
    "W": "Weather Delay",
    "X": "Exceptional Circumstances",
    "Y": "System / IT Failure",
    "Z": "Other / Unknown",
}
_PUX_NAMES = {
    3:  "PUX03 — Incorrect Address",
    5:  "PUX05 — Customer Security Delay",
    8:  "PUX08 — Not In / Business Closed",
    15: "PUX15 — Business Closed / Strike",
    16: "PUX16 — Payment Received",
    17: "PUX17 — Future Delivery Requested",
    20: "PUX20 — DG Commodity",
    23: "PUX23 — Received After A/C Departure ⚠️",
    24: "PUX24 — Customer Delay",
    26: "PUX26 — Cartage Agent / Consolidator",
    30: "PUX30 — Attempted After Close Time",
    35: "PUX35 — Third Party — No Package",
    39: "PUX39 — Customer Did Not Wait",
    40: "PUX40 — Multiple Pickups Scheduled",
    42: "PUX42 — Holiday / Business Closed",
    43: "PUX43 — No Package",
    46: "PUX46 — Mass Pickup Scan",
    47: "PUX47 — Mass Routing Scan",
    50: "PUX50 — Missing Regulatory Paperwork",
    78: "PUX78 — Country Not in Service Area",
    79: "PUX79 — Uplift Not Available",
    81: "PUX81 — COMAIL / Convenience",
    84: "PUX84 — Delay Beyond Our Control",
    86: "PUX86 — Pre-Routed Meter Package",
    91: "PUX91 — Exceeds Service Limits",
    92: "PUX92 — Pickup Not Ready",
    93: "PUX93 — Unable to Collect Payment",
    94: "PUX94 — No Credit Approval",
    95: "PUX95 — Package Retrieval",
    96: "PUX96 — Incorrect Pickup Info",
    97: "PUX97 — No Pickup Attempt Made",
    98: "PUX98 — Courier Attempted / Left Behind",
}


def _base_layout(**kwargs):
    kwargs.setdefault("margin", dict(l=16, r=16, t=40, b=16))
    return dict(
        font=dict(family="Inter, sans-serif", size=12, color="#333"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font_size=11),
        **kwargs,
    )


def _pof_label(code) -> str:
    """Return a human-readable label for a POF cause code."""
    if pd.isna(code) or code is None:
        return "Unknown"
    s = str(code).strip().upper()
    if s in _POF_CAUSE_LABELS:
        return f"{s} — {_POF_CAUSE_LABELS[s].split('—')[-1].strip()}"
    return s


def _load_india_loc_ids() -> dict:
    """Load India LOC ID → City mapping from CSV."""
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "india_loc_ids.csv"
    )
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df["Alpha"].astype(str),
                        df["City"].fillna("").astype(str) + " (" + df["Facility"].fillna("").astype(str) + ")"))
    except Exception:
        return {}


# ── data loader (cached per unique file bytes) ────────────────────────────────
@st.cache_data(show_spinner="Parsing NSL file — may take 30–60 s for large files…")
def _load_nsl(file_bytes: bytes) -> pd.DataFrame:
    chunks = []
    _kw = dict(sep=",", quotechar='"', on_bad_lines="skip", low_memory=False)

    try:
        for chunk in pd.read_csv(io.BytesIO(file_bytes), chunksize=400_000, **_kw):
            chunks.append(chunk)
    except Exception:
        pass

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
        df["TOT_VOL"] = df["TOT_VOL"].replace(0, 1)

    # derived: direction (OB / IB)
    if "orig_market_cd" in df.columns and "dest_market_cd" in df.columns:
        df["direction"] = "Other"
        df.loc[df["orig_market_cd"] == "IN", "direction"] = "OB"
        df.loc[(df["direction"] == "Other") & (df["dest_market_cd"] == "IN"), "direction"] = "IB"
    elif "orig_market_cd" in df.columns:
        df["direction"] = df["orig_market_cd"].apply(lambda x: "OB" if x == "IN" else "Other")

    # derived: lane
    if "orig_region" in df.columns and "dest_region" in df.columns:
        df["lane"] = df["orig_region"].fillna("?") + " → " + df["dest_region"].fillna("?")

    # derived: scan labels
    if "pkg_pckup_scan_typ_cd" in df.columns:
        df["scan_type_num"] = pd.to_numeric(df["pkg_pckup_scan_typ_cd"], errors="coerce")
        df["scan_label"] = df["scan_type_num"].map(
            {8.0: "Standard PUP (Clean)", 29.0: "PUX Exception"}
        ).fillna("No Scan")

    # POF cause full label
    if "pof_cause" in df.columns:
        df["pof_cause_label"] = df["pof_cause"].apply(_pof_label)

    return df


# ── main entry point ──────────────────────────────────────────────────────────
def render_nsl_tab() -> None:
    """Render the full NSL Analytics content inside a tab."""

    render_info_banner(
        "NSL Analytics — India",
        "Upload an NSL data file (Outbound or Inbound). Each upload <b>upserts</b> "
        "records by tracking number — new shipments are added, existing ones are updated. "
        "Data persists permanently across sessions, restarts, and tab switches.",
        accent=_PURPLE,
    )

    # ── DB availability check (once per session) ──────────────────────────────
    try:
        from aero.data.nsl_store import (  # type: ignore
            db_available, ensure_nsl_tables, upsert_nsl_data,
            load_nsl_from_db, get_nsl_upload_log, nsl_row_count,
        )
        _use_db = db_available()
        if _use_db and not st.session_state.get("nsl_tables_ensured"):
            ensure_nsl_tables()
            st.session_state["nsl_tables_ensured"] = True
    except Exception:
        _use_db = False

    # ── upload + status row ───────────────────────────────────────────────────
    up_col, status_col = st.columns([4, 2])
    uploaded = up_col.file_uploader(
        "Upload NSL Data File (.txt / .csv)",
        type=["txt", "csv"],
        help="Comma-separated NSL export. Saved to database on upload.",
        key="nsl_upload",
    )

    # ── DB status badge ───────────────────────────────────────────────────────
    if _use_db:
        try:
            db_rows = nsl_row_count()
            log     = get_nsl_upload_log(1)
            last_up = log[0]["uploaded_at"].strftime("%d %b %Y %H:%M") if log else "—"
            last_fn = log[0]["filename"] if log else "—"
            status_col.markdown(f"""
            <div style="background:#ECFDF5;border:1px solid #BBF7D0;border-radius:8px;
                padding:10px 14px;font-size:12px;margin-top:24px;">
                <div style="font-weight:700;color:#065f46;margin-bottom:4px;">
                    🗄️ Database Connected</div>
                <div style="color:#047857;"><b>{db_rows:,}</b> shipments stored</div>
                <div style="color:#6B7280;margin-top:2px;">Last upload: {last_up}</div>
                <div style="color:#6B7280;font-size:11px;">{last_fn}</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            status_col.markdown("""
            <div style="background:#FEF3C7;border:1px solid #FDE68A;border-radius:8px;
                padding:10px 14px;font-size:12px;margin-top:24px;">
                <div style="font-weight:700;color:#92400E;">⚠️ DB Unreachable</div>
                <div style="color:#78350F;">Data loaded from session cache</div>
            </div>""", unsafe_allow_html=True)
            _use_db = False
    # No badge at all when DB is not configured — avoids confusing "Session Mode" message

    # ── process new upload ────────────────────────────────────────────────────
    if uploaded is not None:
        file_id = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.get("nsl_file_id") != file_id:
            file_bytes = uploaded.read()
            with st.spinner("Parsing file…"):
                df_new = _load_nsl(file_bytes)
            st.success(f"Parsed **{len(df_new):,}** rows from {uploaded.name}")

            if _use_db:
                try:
                    with st.spinner(f"Saving {len(df_new):,} rows to database…"):
                        meta = upsert_nsl_data(df_new, uploaded.name)
                    st.success(
                        f"✅ Saved — **{meta['rows_upserted']:,}** rows upserted. "
                        f"Total in DB: **{meta['total_rows_db']:,}**"
                    )
                    with st.spinner("Loading full dataset from database…"):
                        df_new = load_nsl_from_db()
                    st.info(f"📊 Showing **{len(df_new):,}** total records from database")
                except Exception as e:
                    st.warning(f"DB save failed ({e}) — using parsed file data for this session.")

            st.session_state["nsl_df"]       = df_new
            st.session_state["nsl_filename"] = uploaded.name
            st.session_state["nsl_file_id"]  = file_id
            st.rerun()

    # ── auto-load from DB if session empty ────────────────────────────────────
    if st.session_state.get("nsl_df") is None and _use_db:
        try:
            db_rows = nsl_row_count()
            if db_rows > 0:
                with st.spinner(f"Loading {db_rows:,} records from database…"):
                    df_db = load_nsl_from_db()
                st.session_state["nsl_df"]       = df_db
                st.session_state["nsl_filename"] = "Database"
                st.session_state["nsl_file_id"]  = "db"
                st.rerun()
        except Exception:
            pass

    if st.session_state.get("nsl_df") is None:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#999;">
            <div style="font-size:48px;margin-bottom:16px;">📂</div>
            <div style="font-size:16px;font-weight:600;">Upload an NSL data file above to begin</div>
            <div style="font-size:13px;margin-top:8px;">
                Supports India Outbound (OB) and Inbound (IB) data.<br>
                Data is saved permanently and accumulated across uploads.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    raw_df     = st.session_state["nsl_df"]
    total_rows = len(raw_df)
    src_label  = st.session_state.get("nsl_filename", "database")
    st.caption(f"✅ **{total_rows:,}** records — source: **{src_label}**")

    # ── FILTERS ───────────────────────────────────────────────────────────────
    india_loc_map = _load_india_loc_ids()  # Alpha → "City (FacilityType)"

    with st.expander("🔽  Filters", expanded=True):
        # Row 1: Direction
        dir_col, _, _, _ = st.columns([2, 2, 2, 2])
        direction_opts = ["All", "OB — Outbound from India", "IB — Inbound to India"]
        sel_dir_label = dir_col.selectbox(
            "Direction", direction_opts,
            index=1 if "direction" in raw_df.columns else 0,
            key="nsl_f_dir",
        )
        sel_dir = "OB" if "OB" in sel_dir_label else ("IB" if "IB" in sel_dir_label else None)

        # Apply direction first so downstream filters reflect correct subset
        df_dir = raw_df.copy()
        if sel_dir and "direction" in df_dir.columns:
            df_dir = df_dir[df_dir["direction"] == sel_dir]

        # Row 2: Lane | Origin Market | Destination Market | LOC ID
        fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])

        all_lanes = sorted(df_dir["lane"].dropna().unique()) if "lane" in df_dir.columns else []
        sel_lanes = fc1.multiselect("Lane (orig → dest region)", all_lanes,
                                    placeholder="All lanes", key="nsl_f_lane")

        all_orig_mkts = sorted(df_dir["orig_market_cd"].dropna().unique()) \
            if "orig_market_cd" in df_dir.columns else []
        default_orig = ["IN"] if ("IN" in all_orig_mkts and sel_dir == "OB") else []
        sel_orig_mkts = fc2.multiselect("Origin Market", all_orig_mkts,
                                        default=default_orig,
                                        placeholder="All origins", key="nsl_f_orig_mkt")

        all_dest_mkts = sorted(df_dir["dest_market_cd"].dropna().unique()) \
            if "dest_market_cd" in df_dir.columns else []
        default_dest = ["IN"] if ("IN" in all_dest_mkts and sel_dir == "IB") else []
        sel_dest_mkts = fc3.multiselect("Destination Market", all_dest_mkts,
                                        default=default_dest,
                                        placeholder="All destinations", key="nsl_f_dest_mkt")

        # LOC ID filter — use orig_loc_cd for OB, dest_loc_cd for IB, combined for All
        if sel_dir == "OB":
            loc_col_use = "orig_loc_cd"
        elif sel_dir == "IB":
            loc_col_use = "dest_loc_cd"
        else:
            loc_col_use = "orig_loc_cd"

        if loc_col_use in df_dir.columns:
            loc_vals = sorted(df_dir[loc_col_use].dropna().astype(str).unique())
            # Filter to India LOC IDs only (if origin=IN selected or OB mode)
            if sel_dir in ("OB", None) and india_loc_map:
                india_locs_in_data = [l for l in loc_vals if l in india_loc_map]
                loc_display = india_locs_in_data if india_locs_in_data else loc_vals
            else:
                loc_display = loc_vals
            loc_labels = {l: f"{l} — {india_loc_map.get(l, l)}" for l in loc_display}
            sel_loc_ids = fc4.multiselect(
                "LOC ID",
                options=list(loc_labels.keys()),
                format_func=lambda x: loc_labels.get(x, x),
                placeholder="All locations", key="nsl_f_loc",
            )
        else:
            sel_loc_ids = []

        # Row 3: Service | Service Detail | Product | Month | Customer
        sc1, sc2, sc3, sc4, sc5 = st.columns([2, 2, 1.5, 1.5, 2])

        all_svcs = sorted(df_dir["Service"].dropna().unique()) \
            if "Service" in df_dir.columns else []
        sel_svcs = sc1.multiselect("Service Type", all_svcs,
                                   placeholder="All services", key="nsl_f_svc")

        all_svc_det = sorted(df_dir["Service_Detail"].dropna().unique()) \
            if "Service_Detail" in df_dir.columns else []
        sel_svc_det = sc2.multiselect("Service Detail", all_svc_det,
                                      placeholder="All", key="nsl_f_svc_det")

        all_products = sorted(df_dir["Product"].dropna().unique()) \
            if "Product" in df_dir.columns else []
        sel_products = sc3.multiselect("Product Type", all_products,
                                       placeholder="All", key="nsl_f_prod")

        if "month_date" in df_dir.columns:
            months = sorted(df_dir["month_date"].dropna().dt.to_period("M").unique())
            month_labels = [str(m) for m in months]
            sel_months = sc4.multiselect("Month", month_labels,
                                         placeholder="All months", key="nsl_f_month")
        else:
            sel_months = []

        top_custs = (df_dir.groupby("shpr_co_nm")["TOT_VOL"].sum()
                     .nlargest(60).index.tolist()) if "shpr_co_nm" in df_dir.columns else []
        sel_custs = sc5.multiselect("Customer", top_custs,
                                    placeholder="Top 60 by volume", key="nsl_f_cust")

        rc1, _ = st.columns([1, 7])
        if rc1.button("Reset Filters", key="nsl_reset"):
            for k in ["nsl_f_dir", "nsl_f_lane", "nsl_f_orig_mkt", "nsl_f_dest_mkt",
                      "nsl_f_loc", "nsl_f_svc", "nsl_f_svc_det", "nsl_f_prod",
                      "nsl_f_month", "nsl_f_cust"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── apply all filters ─────────────────────────────────────────────────────
    df = df_dir.copy()
    if sel_lanes    and "lane"           in df.columns: df = df[df["lane"].isin(sel_lanes)]
    if sel_orig_mkts and "orig_market_cd" in df.columns: df = df[df["orig_market_cd"].isin(sel_orig_mkts)]
    if sel_dest_mkts and "dest_market_cd" in df.columns: df = df[df["dest_market_cd"].isin(sel_dest_mkts)]
    if sel_loc_ids  and loc_col_use      in df.columns: df = df[df[loc_col_use].astype(str).isin(sel_loc_ids)]
    if sel_svcs     and "Service"        in df.columns: df = df[df["Service"].isin(sel_svcs)]
    if sel_svc_det  and "Service_Detail" in df.columns: df = df[df["Service_Detail"].isin(sel_svc_det)]
    if sel_products and "Product"        in df.columns: df = df[df["Product"].isin(sel_products)]
    if sel_custs    and "shpr_co_nm"     in df.columns: df = df[df["shpr_co_nm"].isin(sel_custs)]
    if sel_months and "month_date" in df.columns:
        df = df[df["month_date"].dt.to_period("M").astype(str).isin(sel_months)]

    if len(df) == 0:
        st.warning("No records match the current filters — please broaden your selection.")
        return

    if len(df) < total_rows:
        st.caption(f"📌 Showing **{len(df):,}** of {total_rows:,} records after filters")

    # ── KPI row ───────────────────────────────────────────────────────────────
    tot_vol   = int(df["TOT_VOL"].sum())    if "TOT_VOL"    in df.columns else len(df)
    nsl_vol   = int(df["NSL_OT_VOL"].sum()) if "NSL_OT_VOL" in df.columns else 0
    nsl_pct   = nsl_vol / tot_vol * 100 if tot_vol else 0
    scan_comp = ((df["scan_type_num"] == 8.0).sum() / len(df) * 100
                 if "scan_type_num" in df.columns else 0.0)

    nsl_color  = _GREEN if nsl_pct  >= 75 else (_YELLOW if nsl_pct  >= 65 else _RED)
    scan_color = _GREEN if scan_comp >= 70 else (_YELLOW if scan_comp >= 50 else _RED)

    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    render_kpi_card(k1, "Total Shipments", f"{tot_vol:,}",      color=_PURPLE, icon="📦")
    render_kpi_card(k2, "NSL On-Time",     f"{nsl_pct:.1f}%",   color=nsl_color,
                    subtitle=f"{nsl_vol:,} of {tot_vol:,}")
    render_kpi_card(k3, "NSL + 24",        "— Pending",         color=_GREY,
                    subtitle="Definition TBD")
    render_kpi_card(k4, "Scan Compliance", f"{scan_comp:.1f}%", color=scan_color,
                    subtitle="Clean PUP / total shipments")
    render_kpi_card(k5, "ESP Metrics",     "— Pending",         color=_GREY,
                    subtitle="Clearance stats — coming soon")
    render_kpi_card(k6, "Damaged Goods",   "— Pending",         color=_GREY,
                    subtitle="Damage data — coming soon")
    st.markdown("<br>", unsafe_allow_html=True)

    # ── analytics tabs ────────────────────────────────────────────────────────
    t_trend, t_geo, t_fail, t_cust, t_scan = st.tabs([
        "📈 Trends", "🌍 Geography", "🔴 Failure Analysis",
        "🏢 Customers", "🔍 Scan Compliance",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TRENDS
    # ══════════════════════════════════════════════════════════════════════════
    with t_trend:
        # ── Weekly NSL% by Service ─────────────────────────────────────────
        if "weekending_dt" in df.columns and not df["weekending_dt"].isna().all():
            weekly = (df.groupby(["weekending_dt", "Service"])
                      .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                      .reset_index())
            weekly["nsl_pct"] = weekly["nsl_ot"] / weekly["tot"] * 100
            fig = go.Figure()
            for i, svc in enumerate(weekly["Service"].dropna().unique()):
                s = weekly[weekly["Service"] == svc].sort_values("weekending_dt")
                fig.add_trace(go.Scatter(
                    x=s["weekending_dt"], y=s["nsl_pct"].round(1),
                    name=svc, mode="lines+markers",
                    line=dict(color=_SEQ[i % len(_SEQ)], width=2.5),
                    marker=dict(size=5),
                    hovertemplate="%{x|%d %b %Y}<br>NSL OT: %{y:.1f}%<extra>" + str(svc) + "</extra>",
                ))
            fig.add_hline(y=100, line_dash="dot", line_color="#CCCCCC", line_width=1)
            fig.update_layout(
                title="NSL On-Time % — Weekly by Service",
                yaxis=dict(title="NSL OT %", range=[0, 105],
                           gridcolor="#F0F0F0", ticksuffix="%"),
                xaxis=dict(title="", gridcolor="#F0F0F0"),
                **_base_layout(),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Daily India OB NSL trend (bar=volume, line=NSL%) ──────────────
        _date_col = "shp_dt" if "shp_dt" in df.columns else (
                    "weekending_dt" if "weekending_dt" in df.columns else None)

        if _date_col:
            for _dir, _title in [("OB", "India Outbound NSL Trend (Daily)"),
                                  ("IB", "India Inbound NSL Trend (Daily)")]:
                if "direction" not in df.columns:
                    break
                df_d = df[df["direction"] == _dir]
                if df_d.empty:
                    continue
                daily = (df_d.groupby(_date_col)
                         .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                         .reset_index().sort_values(_date_col))
                daily["nsl_pct"] = (daily["nsl_ot"] / daily["tot"] * 100).round(1)

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=daily[_date_col], y=daily["tot"],
                    name="Total pks",
                    marker_color=_PURPLE,
                    opacity=0.75,
                    hovertemplate="%{x|%d %b %Y}<br>%{y:,} pkgs<extra>Volume</extra>",
                    yaxis="y",
                ))
                fig.add_trace(go.Scatter(
                    x=daily[_date_col], y=daily["nsl_pct"],
                    name="NSL%",
                    mode="lines+markers+text",
                    line=dict(color=_ORANGE, width=2.5),
                    marker=dict(size=4),
                    text=daily["nsl_pct"].apply(lambda v: f"{v:.0f}%"),
                    textposition="top center",
                    textfont=dict(size=9, color=_ORANGE),
                    hovertemplate="%{x|%d %b %Y}<br>NSL: %{y:.1f}%<extra>NSL%</extra>",
                    yaxis="y2",
                ))
                fig.update_layout(
                    title=_title,
                    yaxis=dict(title="Total Packages", gridcolor="#F0F0F0", showgrid=True),
                    yaxis2=dict(title="NSL %", overlaying="y", side="right",
                                ticksuffix="%", range=[0, 110], showgrid=False),
                    xaxis=dict(title="", gridcolor="#F0F0F0"),
                    barmode="overlay",
                    **_base_layout(margin=dict(l=16, r=60, t=40, b=16)),
                )
                st.plotly_chart(fig, use_container_width=True)

        # NOTE: Monthly Volume by MBG Class removed per request

    # ══════════════════════════════════════════════════════════════════════════
    # GEOGRAPHY
    # ══════════════════════════════════════════════════════════════════════════
    with t_geo:
        col_a, col_b = st.columns([1.4, 1])
        with col_a:
            if "dest_region" in df.columns:
                geo = (df.groupby("dest_region")
                       .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                       .reset_index())
                geo["nsl_pct"] = (geo["nsl_ot"] / geo["tot"] * 100).round(1)
                geo = geo.sort_values("nsl_pct")
                bar_colors = [_GREEN if v >= 75 else (_YELLOW if v >= 65 else _RED)
                              for v in geo["nsl_pct"]]
                fig = go.Figure(go.Bar(
                    x=geo["nsl_pct"], y=geo["dest_region"], orientation="h",
                    marker_color=bar_colors,
                    text=[f"{v:.1f}%  ({r:,})" for v, r in zip(geo["nsl_pct"], geo["tot"])],
                    textposition="outside",
                    hovertemplate="%{y}<br>NSL OT: %{x:.1f}%<extra></extra>",
                ))
                fig.add_vline(x=75, line_dash="dash", line_color=_PURPLE, line_width=1.5,
                              annotation_text="75% target",
                              annotation_position="top right")
                fig.update_layout(
                    title="NSL On-Time % by Destination Region",
                    xaxis=dict(title="NSL OT %", range=[0, 115],
                               ticksuffix="%", gridcolor="#F0F0F0"),
                    yaxis=dict(title=""),
                    **_base_layout(margin=dict(l=8, r=100, t=40, b=16)),
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if "dest_market_cd" in df.columns:
                mkts = (df.groupby("dest_market_cd")
                        .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                        .reset_index())
                mkts["nsl_pct"] = (mkts["nsl_ot"] / mkts["tot"] * 100).round(1)
                mkts = mkts.nlargest(15, "tot").sort_values("tot", ascending=False)
                st.markdown('<div style="font-size:13px;font-weight:700;color:#333;'
                            'margin-bottom:8px;">Top 15 Destination Markets</div>',
                            unsafe_allow_html=True)
                disp = mkts[["dest_market_cd", "tot", "nsl_pct"]].copy()
                disp.columns = ["Market", "Volume", "NSL OT %"]
                disp["Volume"]   = disp["Volume"].apply(lambda x: f"{int(x):,}")
                disp["NSL OT %"] = disp["NSL OT %"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(disp, use_container_width=True, hide_index=True, height=420)

    # ══════════════════════════════════════════════════════════════════════════
    # FAILURE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    with t_fail:
        if "Bucket" not in df.columns:
            st.info("'Bucket' column not found in this dataset.")
        else:
            fail_df = (df[df["NSL_OT_VOL"] == 0]
                       if "NSL_OT_VOL" in df.columns else df)

            col_c, col_d = st.columns([1.5, 1])

            # ── Stacked bar: Failure volume by bucket / month ──────────────
            with col_c:
                if "month_date" in df.columns:
                    fm = (fail_df
                          .groupby([fail_df["month_date"].dt.to_period("M").astype(str), "Bucket"])
                          ["TOT_VOL"].sum().reset_index())
                    fm.columns = ["month", "bucket", "vol"]
                    ordered_buckets = (fm.groupby("bucket")["vol"]
                                       .sum().sort_values(ascending=False).index.tolist())
                    fig = go.Figure()
                    for b in ordered_buckets:
                        s = fm[fm["bucket"] == b]
                        total_for_label = s["vol"].sum()
                        fig.add_trace(go.Bar(
                            x=s["month"],
                            y=s["vol"],
                            name=_BUCKET_LABELS.get(b, b),
                            marker_color=_BUCKET_COLORS.get(b, "#CCC"),
                            text=[f"{int(v):,}" if v > 500 else "" for v in s["vol"]],
                            textposition="inside",
                            textfont=dict(size=9, color="white"),
                            hovertemplate="%{x}<br><b>" + _BUCKET_LABELS.get(b, b) + "</b><br>"
                                          "%{y:,} failed pkgs<extra></extra>",
                        ))
                    fig.update_layout(
                        barmode="stack",
                        title="NSL Failure Volume by Bucket (Monthly)",
                        yaxis=dict(title="Failed Shipments", gridcolor="#F0F0F0"),
                        xaxis=dict(title="", tickangle=0),
                        bargap=0.25,
                        **_base_layout(margin=dict(l=16, r=16, t=40, b=40)),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # ── Donut: Failure ownership share ────────────────────────────
            with col_d:
                bs = (fail_df.groupby("Bucket")["TOT_VOL"].sum()
                      .reset_index().sort_values("TOT_VOL", ascending=False))
                bs.columns = ["bucket", "vol"]
                bs["label"] = bs["bucket"].apply(lambda b: _BUCKET_LABELS.get(b, b))

                fig = go.Figure(go.Pie(
                    labels=bs["label"],
                    values=bs["vol"],
                    hole=0.55,
                    marker_colors=[_BUCKET_COLORS.get(b, "#CCC") for b in bs["bucket"]],
                    textinfo="label+percent",
                    textfont_size=10,
                    hovertemplate="%{label}<br>%{value:,} pkgs<br>%{percent}<extra></extra>",
                ))
                fig.update_layout(
                    title="Failure Ownership Share",
                    showlegend=False,
                    **_base_layout(margin=dict(l=8, r=8, t=40, b=8)),
                )
                st.plotly_chart(fig, use_container_width=True)

            # ── Drill-down: select a bucket to see AWB