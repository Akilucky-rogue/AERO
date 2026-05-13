"""
nsl_tab.py — NSL Analytics tab renderer for the Leadership Executive Dashboard.

Call render_nsl_tab() inside a `with tab_svc:` block.
"""
import io
import os
import pickle
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
    # Numeric sub-cause codes (derived from cat_cause_cd analysis)
    "3":  "Unspecified / Catch-all",
    "8":  "Consignee Not Available / No Delivery Attempt",
    "21": "Late Tender — Package Not Ready at Pickup Time",
    "22": "Missort / Incorrect Routing at Origin",
    "32": "Transit Delay — En-Route Hold",
    "33": "Missed Linehaul Connection",
    "50": "Volume Surge / Capacity Exceeded",
    "52": "Clearance Processing Error",
    "55": "Regulatory / Documentation Issue",
    "73": "Customs — Incomplete or Incorrect Documentation",
    "80": "Regulatory / Compliance Hold at Clearance",
    "84": "Hub Equipment or Facility Failure",
    # Alpha sub-cause codes
    "AT": "Air Transit Miss — Aircraft Not Available",
    "CD": "Connection Delay — Missed Onward Flight",
    "EH": "Exception Hold — Package Flagged in Transit",
    "HH": "Held at Hub — Awaiting Onward Dispatch",
    "HI": "Hub Infrastructure / Sort System Issue",
    "IC": "In-Clearance — Regulatory Processing (Customs)",
    "LD": "Late Delivery — Final Mile Delay",
    "OE": "Origin Exception — Station-Level Failure",
    "SN": "No Scan Recorded — Gateway Visibility Gap",
    "TD": "Transit Delay — Gateway Hold",
    "TH": "Transit Hold — Awaiting Clearance or Docs",
    # Legacy single-letter fallbacks
    "A": "Addressing / AWB Issue",
    "B": "Bulk Handling Delay",
    "C": "Clearance Hold",
    "D": "Delivery Failure",
    "F": "Flight / Aircraft Delay",
    "G": "Gateway Issue",
    "H": "Hub Delay",
    "I": "Interline / Connecting Carrier Delay",
    "O": "Origin Station Failure",
    "P": "Processing / Sort Delay",
    "R": "Regulatory / Recipient Issue",
    "S": "Shipper-Caused Delay",
    "T": "Transit Delay",
    "W": "Weather / Natural Disaster",
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
    s = str(code).strip()
    key = s.upper()
    # Try exact match first (handles both numeric "21" and alpha "EH")
    if key in _POF_CAUSE_LABELS:
        return f"{s} — {_POF_CAUSE_LABELS[key]}"
    # Try without leading zeros for numeric codes
    try:
        num_key = str(int(float(s)))
        if num_key in _POF_CAUSE_LABELS:
            return f"{s} — {_POF_CAUSE_LABELS[num_key]}"
    except (ValueError, TypeError):
        pass
    return s


def _cache_path() -> str:
    """Return path to the local pickle cache file (lives next to this module)."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "_nsl_cache.pkl"
    )


def _save_cache(df: pd.DataFrame, filename: str) -> None:
    """Persist DataFrame to disk so data survives app restarts."""
    try:
        payload = {"df": df, "filename": filename}
        with open(_cache_path(), "wb") as f:
            pickle.dump(payload, f, protocol=4)
    except Exception:
        pass  # non-fatal


def _load_cache() -> tuple:
    """Load (df, filename) from disk cache. Returns (None, None) if absent."""
    try:
        path = _cache_path()
        if not os.path.exists(path):
            return None, None
        with open(path, "rb") as f:
            payload = pickle.load(f)
        return payload.get("df"), payload.get("filename", "cache")
    except Exception:
        return None, None


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
        help="Comma-separated NSL export. Saved permanently on submit.",
        key="nsl_upload",
    )
    submit_upload = up_col.button(
        "✅  Submit & Process File",
        key="nsl_submit",
        disabled=(uploaded is None),
        use_container_width=False,
    )

    # ── DB / cache status badge ───────────────────────────────────────────────
    if _use_db:
        try:
            db_rows = nsl_row_count()
            log     = get_nsl_upload_log(1)
            last_up = log[0]["uploaded_at"].strftime("%d %b %Y %H:%M") if log else "—"
            last_fn = log[0]["filename"] if log else "—"
            status_col.markdown(f"""
            <div style="background:#ECFDF5;border:1px solid #BBF7D0;border-radius:8px;
                padding:10px 14px;font-size:12px;margin-top:8px;">
                <div style="font-weight:700;color:#065f46;margin-bottom:4px;">
                    🗄️ Database Connected</div>
                <div style="color:#047857;"><b>{db_rows:,}</b> shipments stored</div>
                <div style="color:#6B7280;margin-top:2px;">Last upload: {last_up}</div>
                <div style="color:#6B7280;font-size:11px;">{last_fn}</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            status_col.markdown("""
            <div style="background:#FEF3C7;border:1px solid #FDE68A;border-radius:8px;
                padding:10px 14px;font-size:12px;margin-top:8px;">
                <div style="font-weight:700;color:#92400E;">⚠️ DB Unreachable</div>
                <div style="color:#78350F;">Using local file cache</div>
            </div>""", unsafe_allow_html=True)
            _use_db = False
    else:
        # Show local cache status
        cache_df, cache_fn = _load_cache() if st.session_state.get("nsl_df") is None else (None, None)
        cache_exists = os.path.exists(_cache_path())
        if cache_exists:
            try:
                cache_size = os.path.getsize(_cache_path()) // (1024 * 1024)
                status_col.markdown(f"""
                <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;
                    padding:10px 14px;font-size:12px;margin-top:8px;">
                    <div style="font-weight:700;color:#1e40af;margin-bottom:4px;">
                        💾 Local Cache Active</div>
                    <div style="color:#1d4ed8;">Data saved on disk ({cache_size} MB)</div>
                    <div style="color:#6B7280;font-size:11px;margin-top:2px;">
                        Persists across restarts</div>
                </div>""", unsafe_allow_html=True)
            except Exception:
                pass

    # ── process new upload (only on submit) ──────────────────────────────────
    if uploaded is not None and submit_upload:
        file_id = f"{uploaded.name}_{uploaded.size}"
        file_bytes = uploaded.read()

        with st.spinner("Parsing file…"):
            df_new = _load_nsl(file_bytes)
        st.success(f"Parsed **{len(df_new):,}** rows from {uploaded.name}")

        if _use_db:
            try:
                with st.spinner(f"Saving {len(df_new):,} rows to database…"):
                    meta = upsert_nsl_data(df_new, uploaded.name)
                st.success(
                    f"✅ Saved to DB — **{meta['rows_upserted']:,}** rows upserted. "
                    f"Total in DB: **{meta['total_rows_db']:,}**"
                )
                with st.spinner("Loading full dataset from database…"):
                    df_new = load_nsl_from_db()
                st.info(f"📊 Showing **{len(df_new):,}** total records from database")
            except Exception as e:
                st.warning(f"DB save failed ({e}) — saving to local cache instead.")

        # Always save to local disk cache as well (belt-and-suspenders)
        with st.spinner("Saving to local cache…"):
            _save_cache(df_new, uploaded.name)

        st.session_state["nsl_df"]       = df_new
        st.session_state["nsl_filename"] = uploaded.name
        st.session_state["nsl_file_id"]  = file_id
        st.rerun()

    # ── auto-load on session start: DB first, then local cache ───────────────
    if st.session_state.get("nsl_df") is None:
        loaded = False
        if _use_db:
            try:
                db_rows = nsl_row_count()
                if db_rows > 0:
                    with st.spinner(f"Loading {db_rows:,} records from database…"):
                        df_db = load_nsl_from_db()
                    st.session_state["nsl_df"]       = df_db
                    st.session_state["nsl_filename"] = "Database"
                    st.session_state["nsl_file_id"]  = "db"
                    loaded = True
                    st.rerun()
            except Exception:
                pass

        if not loaded:
            cache_df, cache_fn = _load_cache()
            if cache_df is not None and len(cache_df) > 0:
                with st.spinner("Restoring data from local cache…"):
                    pass  # already loaded
                st.session_state["nsl_df"]       = cache_df
                st.session_state["nsl_filename"] = f"{cache_fn} (cached)"
                st.session_state["nsl_file_id"]  = "cache"
                st.rerun()

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
        _date_col = "shp_dt" if "shp_dt" in df.columns else (
                    "weekending_dt" if "weekending_dt" in df.columns else None)

        # ── Daily OB / IB bar+line (volume + NSL%) ────────────────────────
        if _date_col and "direction" in df.columns:
            for _dir, _color, _title in [
                ("OB", _PURPLE, "India Outbound — Daily Volume & NSL%"),
                ("IB", _COLORS["blue"], "India Inbound — Daily Volume & NSL%"),
            ]:
                df_d = df[df["direction"] == _dir]
                if df_d.empty:
                    continue
                daily = (df_d.groupby(_date_col)
                         .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                         .reset_index().sort_values(_date_col))
                daily["nsl_pct"] = (daily["nsl_ot"] / daily["tot"] * 100).round(1)
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=daily[_date_col], y=daily["tot"], name="Total Pkgs",
                    marker_color=_color, opacity=0.7, yaxis="y",
                    hovertemplate="%{x|%d %b %Y}<br>%{y:,} pkgs<extra>Volume</extra>",
                ))
                fig.add_trace(go.Scatter(
                    x=daily[_date_col], y=daily["nsl_pct"], name="NSL%",
                    mode="lines+markers", line=dict(color=_ORANGE, width=2.5),
                    marker=dict(size=4), yaxis="y2",
                    text=daily["nsl_pct"].apply(lambda v: f"{v:.0f}%"),
                    textposition="top center", textfont=dict(size=8, color=_ORANGE),
                    hovertemplate="%{x|%d %b %Y}<br>NSL: %{y:.1f}%<extra>NSL%</extra>",
                ))
                fig.update_layout(
                    title=_title,
                    yaxis=dict(title="Total Packages", gridcolor="#F0F0F0"),
                    yaxis2=dict(title="NSL %", overlaying="y", side="right",
                                ticksuffix="%", range=[0, 115], showgrid=False),
                    xaxis=dict(title="", gridcolor="#F0F0F0"),
                    **_base_layout(margin=dict(l=16, r=60, t=40, b=16)),
                )
                st.plotly_chart(fig, use_container_width=True)

        # ── Weekly NSL% by Service — multi-line ───────────────────────────
        if "weekending_dt" in df.columns and not df["weekending_dt"].isna().all():
            weekly = (df.groupby(["weekending_dt", "Service"])
                      .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                      .reset_index())
            weekly["nsl_pct"] = (weekly["nsl_ot"] / weekly["tot"] * 100).round(1)
            fig = go.Figure()
            for i, svc in enumerate(sorted(weekly["Service"].dropna().unique())):
                s = weekly[weekly["Service"] == svc].sort_values("weekending_dt")
                fig.add_trace(go.Scatter(
                    x=s["weekending_dt"], y=s["nsl_pct"], name=svc,
                    mode="lines+markers",
                    line=dict(color=_SEQ[i % len(_SEQ)], width=2.5),
                    marker=dict(size=6),
                    hovertemplate="%{x|%d %b %Y}<br>NSL: %{y:.1f}%<extra>" + str(svc) + "</extra>",
                ))
            fig.add_hline(y=75, line_dash="dash", line_color=_RED, line_width=1.5,
                          annotation_text="75% target", annotation_position="bottom right")
            fig.update_layout(
                title="Weekly NSL On-Time % by Service Type",
                yaxis=dict(title="NSL OT %", range=[0, 105],
                           gridcolor="#F0F0F0", ticksuffix="%"),
                xaxis=dict(title="", gridcolor="#F0F0F0"),
                **_base_layout(),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Heatmap: Week × Destination Region NSL% ───────────────────────
        if "weekending_dt" in df.columns and "dest_region" in df.columns:
            hm = (df.groupby(["weekending_dt", "dest_region"])
                  .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                  .reset_index())
            hm["nsl_pct"] = (hm["nsl_ot"] / hm["tot"] * 100).round(1)
            hm["week_str"] = hm["weekending_dt"].dt.strftime("%d %b")
            pivot = hm.pivot_table(index="dest_region", columns="week_str",
                                   values="nsl_pct", aggfunc="mean")
            # Sort weeks chronologically
            week_order = (hm[["weekending_dt", "week_str"]]
                          .drop_duplicates().sort_values("weekending_dt")["week_str"].tolist())
            pivot = pivot.reindex(columns=[w for w in week_order if w in pivot.columns])
            fig = go.Figure(go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=[[0, "#DE002E"], [0.4, "#FFB800"], [0.7, "#AAFFAA"], [1, "#008A00"]],
                zmin=0, zmax=100,
                text=[[f"{v:.0f}%" if not np.isnan(v) else "" for v in row]
                      for row in pivot.values],
                texttemplate="%{text}",
                textfont=dict(size=10),
                hovertemplate="Region: %{y}<br>Week: %{x}<br>NSL: %{z:.1f}%<extra></extra>",
                colorbar=dict(title="NSL%", ticksuffix="%"),
            ))
            fig.update_layout(
                title="NSL% Heatmap — Destination Region × Week",
                xaxis=dict(title="Week Ending", tickangle=-30),
                yaxis=dict(title=""),
                **_base_layout(margin=dict(l=120, r=16, t=40, b=80)),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # GEOGRAPHY
    # ══════════════════════════════════════════════════════════════════════════
    with t_geo:
        # ── Row 1: Region bar + Top markets table ─────────────────────────
        col_a, col_b = st.columns([1.4, 1])
        with col_a:
            if "dest_region" in df.columns:
                geo = (df.groupby("dest_region")
                       .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                       .reset_index())
                geo["nsl_pct"] = (geo["nsl_ot"] / geo["tot"] * 100).round(1)
                geo = geo.sort_values("nsl_pct")
                fig = go.Figure(go.Bar(
                    x=geo["nsl_pct"], y=geo["dest_region"], orientation="h",
                    marker_color=[_GREEN if v >= 75 else (_YELLOW if v >= 65 else _RED)
                                  for v in geo["nsl_pct"]],
                    text=[f"{v:.1f}%  ({r:,})" for v, r in zip(geo["nsl_pct"], geo["tot"])],
                    textposition="outside",
                    hovertemplate="%{y}<br>NSL OT: %{x:.1f}%<extra></extra>",
                ))
                fig.add_vline(x=75, line_dash="dash", line_color=_PURPLE, line_width=1.5,
                              annotation_text="75% target", annotation_position="top right")
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
                mkts = mkts.nlargest(15, "tot").sort_values("nsl_pct")
                disp = mkts[["dest_market_cd", "tot", "nsl_pct"]].copy()
                disp.columns = ["Market", "Volume", "NSL OT %"]
                disp["Volume"]   = disp["Volume"].apply(lambda x: f"{int(x):,}")
                disp["NSL OT %"] = disp["NSL OT %"].apply(lambda x: f"{x:.1f}%")
                st.markdown('<div style="font-size:13px;font-weight:700;color:#333;'
                            'margin-bottom:8px;">Top 15 Dest Markets by Volume</div>',
                            unsafe_allow_html=True)
                st.dataframe(disp, use_container_width=True, hide_index=True, height=420)

        # ── Heatmap: Origin Region × Destination Region NSL% ─────────────
        if "orig_region" in df.columns and "dest_region" in df.columns:
            lane_hm = (df.groupby(["orig_region", "dest_region"])
                       .agg(nsl_ot=("NSL_OT_VOL", "sum"), tot=("TOT_VOL", "sum"))
                       .reset_index())
            lane_hm["nsl_pct"] = (lane_hm["nsl_ot"] / lane_hm["tot"] * 100).round(1)
            pivot_lane = lane_hm.pivot_table(index="orig_region", columns="dest_region",
                                             values="nsl_pct", aggfunc="mean")
            fig = go.Figure(go.Heatmap(
                z=pivot_lane.values,
                x=pivot_lane.columns.tolist(),
                y=pivot_lane.index.tolist(),
                colorscale=[[0, "#DE002E"], [0.4, "#FFB800"], [0.75, "#AAFFAA"], [1, "#008A00"]],
                zmin=0, zmax=100,
                text=[[f"{v:.0f}%" if not np.isnan(v) else "—" for v in row]
                      for row in pivot_lane.values],
                texttemplate="%{text}",
                textfont=dict(size=10),
                hovertemplate="From: %{y}<br>To: %{x}<br>NSL: %{z:.1f}%<extra></extra>",
                colorbar=dict(title="NSL%", ticksuffix="%"),
            ))
            fig.update_layout(
                title="Lane NSL% Heatmap — Origin Region × Destination Region",
                xaxis=dict(title="Destination Region", tickangle=-30),
                yaxis=dict(title="Origin Region"),
                **_base_layout(margin=dict(l=120, r=16, t=40, b=100)),
            )
            st.plotly_chart(fig, use_container_width=True)

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

            # ── Stacked bar: Failure by bucket / month ────────────────────
            with col_c:
                if "month_date" in df.columns:
                    fm = (fail_df
                          .groupby([fail_df["month_date"].dt.to_period("M").astype(str), "Bucket"])
                          ["TOT_VOL"].sum().reset_index())
                    fm.columns = ["month", "bucket", "vol"]
                    ordered = (fm.groupby("bucket")["vol"]
                               .sum().sort_values(ascending=False).index.tolist())
                    fig = go.Figure()
                    for b in ordered:
                        s = fm[fm["bucket"] == b]
                        fig.add_trace(go.Bar(
                            x=s["month"], y=s["vol"], name=b,
                            marker_color=_BUCKET_COLORS.get(b, "#CCC"),
                            text=[f"{int(v):,}" if v > 500 else "" for v in s["vol"]],
                            textposition="inside",
                            textfont=dict(size=9, color="white"),
                            hovertemplate="%{x}<br><b>" + _BUCKET_LABELS.get(b, b) +
                                          "</b><br>%{y:,} failed<extra></extra>",
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

            # ── Donut: Failure ownership ──────────────────────────────────
            with col_d:
                bs = (fail_df.groupby("Bucket")["TOT_VOL"].sum()
                      .reset_index().sort_values("TOT_VOL", ascending=False))
                bs.columns = ["bucket", "vol"]
                fig = go.Figure(go.Pie(
                    labels=bs["bucket"], values=bs["vol"], hole=0.55,
                    marker_colors=[_BUCKET_COLORS.get(b, "#CCC") for b in bs["bucket"]],
                    textinfo="label+percent", textfont_size=11,
                    customdata=[_BUCKET_LABELS.get(b, b) for b in bs["bucket"]],
                    hovertemplate="<b>%{customdata}</b><br>%{value:,} pkgs<br>%{percent}<extra></extra>",
                ))
                fig.update_layout(title="Failure Ownership Share", showlegend=False,
                                  **_base_layout(margin=dict(l=8, r=8, t=40, b=8)))
                st.plotly_chart(fig, use_container_width=True)

            # ── Heatmap: Bucket × Week failure volume ─────────────────────
            if "weekending_dt" in df.columns:
                fh = (fail_df.groupby(["weekending_dt", "Bucket"])["TOT_VOL"]
                      .sum().reset_index())
                fh["week_str"] = fh["weekending_dt"].dt.strftime("%d %b")
                week_ord = (fh[["weekending_dt", "week_str"]]
                            .drop_duplicates().sort_values("weekending_dt")["week_str"].tolist())
                pivot_fh = fh.pivot_table(index="Bucket", columns="week_str",
                                          values="TOT_VOL", aggfunc="sum", fill_value=0)
                pivot_fh = pivot_fh.reindex(columns=[w for w in week_ord if w in pivot_fh.columns])
                fig = go.Figure(go.Heatmap(
                    z=pivot_fh.values,
                    x=pivot_fh.columns.tolist(),
                    y=pivot_fh.index.tolist(),
                    colorscale=[[0, "#F0F4FF"], [0.5, "#FF6200"], [1, "#DE002E"]],
                    text=[[f"{int(v):,}" if v > 0 else "" for v in row]
                          for row in pivot_fh.values],
                    texttemplate="%{text}",
                    textfont=dict(size=9),
                    hovertemplate="Bucket: %{y}<br>Week: %{x}<br>%{z:,} failed<extra></extra>",
                    colorbar=dict(title="Failed Pkgs"),
                ))
                fig.update_layout(
                    title="Failure Volume Heatmap — Bucket × Week",
                    xaxis=dict(title="Week Ending", tickangle=-30),
                    yaxis=dict(title=""),
                    **_base_layout(margin=dict(l=160, r=16, t=40, b=80)),
                )
                st.plotly_chart(fig, use_container_width=True)

            # ── Drill-down: select bucket → view AWBs ─────────────────────
            st.markdown("---")
            st.markdown('<div style="font-size:13px;font-weight:700;color:#4D148C;'
                        'margin-bottom:8px;">🔍 Drill Down by Failure Bucket</div>',
                        unsafe_allow_html=True)
            bucket_opts = ["— Select a bucket —"] + bs["bucket"].tolist()
            sel_bucket = st.selectbox(
                "bucket", bucket_opts,
                format_func=lambda x: _BUCKET_LABELS.get(x, x),
                key="nsl_bucket_drill", label_visibility="collapsed",
            )
            if sel_bucket != "— Select a bucket —":
                drill = fail_df[fail_df["Bucket"] == sel_bucket].copy()
                drill_cols = ["shp_trk_nbr", "shp_dt", "shpr_co_nm", "orig_market_cd",
                              "dest_market_cd", "Service", "Service_Detail",
                              "pof_cause", "pof_cause_label", "NSL_F_VOL"]
                drill_cols = [c for c in drill_cols if c in drill.columns]
                st.markdown(f'<div style="font-size:12px;color:#555;margin-bottom:6px;">'
                            f'<b>{len(drill):,}</b> failed AWBs in '
                            f'<b>{_BUCKET_LABELS.get(sel_bucket, sel_bucket)}</b></div>',
                            unsafe_allow_html=True)
                st.dataframe(drill[drill_cols].reset_index(drop=True),
                             use_container_width=True, height=320)
                buf = io.StringIO()
                drill[drill_cols].to_csv(buf, index=False)
                st.download_button(f"⬇️  Download {sel_bucket} AWBs (CSV)",
                                   buf.getvalue().encode(),
                                   f"nsl_failed_{sel_bucket.lower().replace(' ','_')}.csv",
                                   "text/csv", key="nsl_bucket_dl")

            # ── Top POF Causes table (full labels) ────────────────────────
            if "pof_cause" in df.columns and "NSL_OT_VOL" in df.columns:
                st.markdown("---")
                st.markdown('<div style="font-size:13px;font-weight:700;color:#333;'
                            'margin-bottom:8px;">Top POF Causes</div>',
                            unsafe_allow_html=True)
                pof = (df[df["NSL_OT_VOL"] == 0]
                       .groupby("pof_cause")["TOT_VOL"].sum()
                       .reset_index().nlargest(15, "TOT_VOL"))
                pof.columns = ["code", "Failed Shipments"]
                pof_total = pof["Failed Shipments"].sum()
                pof["POF Cause"] = pof["code"].apply(_pof_label)
                pof["% of Failures"] = (pof["Failed Shipments"] / pof_total * 100
                                        ).round(1).astype(str) + "%"
                pof["Failed Shipments"] = pof["Failed Shipments"].apply(lambda x: f"{int(x):,}")
                st.dataframe(pof[["POF Cause", "Failed Shipments", "% of Failures"]],
                             use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # CUSTOMERS
    # ══════════════════════════════════════════════════════════════════════════
    with t_cust:
        if "shpr_co_nm" not in df.columns:
            st.info("Customer column not available.")
        else:
            nc1, _ = st.columns([1, 4])
            top_n = nc1.slider("Show top N customers", 5, 50, 20, step=5, key="nsl_cust_n")
            cg = df.groupby("shpr_co_nm").agg(
                vol=("TOT_VOL", "sum"), nsl_ot=("NSL_OT_VOL", "sum"),
            ).reset_index()
            cg["NSL OT %"] = (cg["nsl_ot"] / cg["vol"] * 100).round(1)
            ct = cg.nlargest(top_n, "vol").sort_values("vol", ascending=False)

            # ── Bubble chart: Volume vs NSL% ─────────────────────────────
            fig = go.Figure(go.Scatter(
                x=ct["vol"], y=ct["NSL OT %"],
                mode="markers+text",
                marker=dict(
                    size=ct["vol"] / ct["vol"].max() * 50 + 8,
                    color=ct["NSL OT %"],
                    colorscale=[[0, "#DE002E"], [0.5, "#FFB800"], [1, "#008A00"]],
                    cmin=0, cmax=100,
                    showscale=True,
                    colorbar=dict(title="NSL%", ticksuffix="%"),
                    line=dict(width=1, color="white"),
                ),
                text=ct["shpr_co_nm"].apply(lambda x: x[:18] if len(x) > 18 else x),
                textposition="top center",
                textfont=dict(size=9),
                hovertemplate="<b>%{text}</b><br>Volume: %{x:,}<br>NSL OT: %{y:.1f}%<extra></extra>",
            ))
            fig.add_hline(y=75, line_dash="dash", line_color=_RED, line_width=1.5,
                          annotation_text="75% target")
            fig.update_layout(
                title=f"Top {top_n} Customers — Volume vs NSL% (bubble size = volume)",
                xaxis=dict(title="Total Shipments", gridcolor="#F0F0F0"),
                yaxis=dict(title="NSL OT %", ticksuffix="%",
                           range=[0, 110], gridcolor="#F0F0F0"),
                **_base_layout(margin=dict(l=16, r=80, t=40, b=16)),
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── Bar chart: top customers by NSL% ─────────────────────────
            ct_sorted = ct.sort_values("NSL OT %")
            fig2 = go.Figure(go.Bar(
                x=ct_sorted["NSL OT %"], y=ct_sorted["shpr_co_nm"],
                orientation="h",
                marker_color=[_GREEN if v >= 75 else (_YELLOW if v >= 60 else _RED)
                              for v in ct_sorted["NSL OT %"]],
                text=[f"{v:.1f}%" for v in ct_sorted["NSL OT %"]],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>NSL OT: %{x:.1f}%<extra></extra>",
            ))
            fig2.add_vline(x=75, line_dash="dash", line_color=_PURPLE, line_width=1.5,
                           annotation_text="75% target", annotation_position="top right")
            fig2.update_layout(
                title=f"Top {top_n} Customers — NSL On-Time %",
                xaxis=dict(title="NSL OT %", range=[0, 115],
                           ticksuffix="%", gridcolor="#F0F0F0"),
                yaxis=dict(title=""),
                height=max(300, top_n * 22),
                **_base_layout(margin=dict(l=160, r=80, t=40, b=16)),
            )
            st.plotly_chart(fig2, use_container_width=True)

            disp = ct[["shpr_co_nm", "vol", "NSL OT %"]].copy()
            disp.columns = ["Customer", "Volume", "NSL OT %"]
            disp["Volume"]   = disp["Volume"].apply(lambda x: f"{int(x):,}")
            disp["NSL OT %"] = disp["NSL OT %"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(disp, use_container_width=True, hide_index=True)
            buf = io.StringIO()
            cg.to_csv(buf, index=False)
            st.download_button("⬇️  Download Full Customer Table (CSV)",
                               buf.getvalue().encode(), "nsl_customers.csv", "text/csv",
                               key="nsl_cust_dl")

    # ══════════════════════════════════════════════════════════════════════════
    # SCAN COMPLIANCE
    # ══════════════════════════════════════════════════════════════════════════
    with t_scan:
        scan_cols_present = any(c in df.columns for c in ["scan_label", "pux_event_cd"])
        if not scan_cols_present:
            st.info("Pickup scan columns not available in this dataset.")
        else:
            sc1, sc2 = st.columns(2)

            if "scan_label" in df.columns:
                with sc1:
                    sd = df["scan_label"].value_counts().reset_index()
                    sd.columns = ["scan_type", "count"]
                    cmap = {"Standard PUP (Clean)": _GREEN,
                            "PUX Exception": _ORANGE, "No Scan": _RED}
                    fig = go.Figure(go.Bar(
                        x=sd["scan_type"], y=sd["count"],
                        marker_color=[cmap.get(s, _GREY) for s in sd["scan_type"]],
                        text=[f"{v:,} ({v / max(len(df), 1) * 100:.1f}%)" for v in sd["count"]],
                        textposition="outside",
                        hovertemplate="%{x}<br>%{y:,}<extra></extra>",
                    ))
                    fig.update_layout(
                        title="Scan Type Distribution",
                        yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                        xaxis=dict(title=""),
                        **_base_layout(margin=dict(l=16, r=16, t=40, b=60)),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            if "pux_event_cd" in df.columns:
                with sc2:
                    pux = df["pux_event_cd"].value_counts().head(12).reset_index()
                    pux.columns = ["event", "count"]
                    fig2 = go.Figure(go.Bar(
                        x=pux["count"], y=pux["event"],
                        orientation="h",
                        marker_color=_ORANGE,
                        text=[f"{v:,}" for v in pux["count"]],
                        textposition="outside",
                        hovertemplate="%{y}<br>%{x:,}<extra></extra>",
                    ))
                    fig2.update_layout(
                        title="Top PUX Event Codes",
                        xaxis=dict(title="Count", gridcolor="#F0F0F0"),
                        yaxis=dict(title=""),
                        **_base_layout(margin=dict(l=120, r=60, t=40, b=16)),
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            if "loc_id" in df.columns and "scan_label" in df.columns:
                st.markdown("---")
                loc_scan = df.groupby("loc_id").agg(
                    total=("TOT_VOL", "sum"),
                    clean=("scan_label", lambda x: (x == "Standard PUP (Clean)").sum()),
                ).reset_index()
                loc_scan["Scan Compliance %"] = (
                    loc_scan["clean"] / loc_scan["total"].clip(lower=1) * 100
                ).round(1)
                loc_scan = loc_scan[loc_scan["total"] >= 10].nlargest(25, "Scan Compliance %")

                fig3 = go.Figure(go.Bar(
                    x=loc_scan["Scan Compliance %"],
                    y=loc_scan["loc_id"],
                    orientation="h",
                    marker_color=[_GREEN if v >= 90 else (_YELLOW if v >= 75 else _RED)
                                  for v in loc_scan["Scan Compliance %"]],
                    text=[f"{v:.1f}%" for v in loc_scan["Scan Compliance %"]],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Scan Compliance: %{x:.1f}%<extra></extra>",
                ))
                fig3.add_vline(x=90, line_dash="dash", line_color=_PURPLE, line_width=1.5,
                               annotation_text="90% target")
                fig3.update_layout(
                    title="Top 25 LOC IDs by Scan Compliance % (min 10 shipments)",
                    xaxis=dict(title="Scan Compliance %", range=[0, 115],
                               ticksuffix="%", gridcolor="#F0F0F0"),
                    yaxis=dict(title="LOC ID"),
                    height=600,
                    **_base_layout(margin=dict(l=80, r=80, t=40, b=16)),
                )
                st.plotly_chart(fig3, use_container_width=True)

            if "weekending_dt" in df.columns and "scan_label" in df.columns:
                wk_scan = df.groupby("weekending_dt").agg(
                    total=("TOT_VOL", "sum"),
                    clean=("scan_label", lambda x: (x == "Standard PUP (Clean)").sum()),
                ).reset_index()
                wk_scan["Compliance %"] = (
                    wk_scan["clean"] / wk_scan["total"].clip(lower=1) * 100
                ).round(1)
                wk_scan = wk_scan.sort_values("weekending_dt")

                fig4 = go.Figure()
                fig4.add_trace(go.Bar(
                    x=wk_scan["weekending_dt"], y=wk_scan["total"],
                    name="Total Shipments", marker_color=_GREY,
                    yaxis="y", opacity=0.4,
                    hovertemplate="%{x|%d %b}<br>Total: %{y:,}<extra></extra>",
                ))
                fig4.add_trace(go.Scatter(
                    x=wk_scan["weekending_dt"], y=wk_scan["Compliance %"],
                    name="Scan Compliance %", mode="lines+markers+text",
                    line=dict(color=_PURPLE, width=2.5),
                    marker=dict(size=7, color=_PURPLE),
                    text=[f"{v:.1f}%" for v in wk_scan["Compliance %"]],
                    textposition="top center",
                    textfont=dict(size=9),
                    yaxis="y2",
                    hovertemplate="%{x|%d %b}<br>Compliance: %{y:.1f}%<extra></extra>",
                ))
                fig4.add_hline(y=90, line_dash="dash", line_color=_RED, line_width=1,
                               yref="y2", annotation_text="90% target")
                fig4.update_layout(
                    title="Weekly Scan Compliance Trend",
                    xaxis=dict(title="Week", tickangle=-30, gridcolor="#F0F0F0"),
                    yaxis=dict(title="Shipments", gridcolor="#F0F0F0"),
                    yaxis2=dict(title="Compliance %", overlaying="y", side="right",
                                range=[0, 110], ticksuffix="%"),

                    **_base_layout(margin=dict(l=16, r=80, t=60, b=60)),
                )
                st.plotly_chart(fig4, use_container_width=True)
