# ============================================================
# AERO — Services Operations
# Delay Prediction Engine — powered by NSL historical data
#
# Tab 1 · TRAINING DATA    — upload NSL file, review stats
# Tab 2 · MODEL            — network profile & risk breakdown
# Tab 3 · DAILY PREDICTION — upload AWB file, run predictions
# Tab 4 · HISTORY          — past prediction sessions
# ============================================================
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from aero.ui.header import render_header, render_footer
from aero.ui.components import (
    render_kpi_card,
    render_kpi_row,
    render_info_banner,
    _PURPLE, _ORANGE, _GREEN, _RED, _YELLOW, _GREY,
)
from aero.data.nsl_store import (
    parse_nsl_file,
    parse_awb_file,
    save_model,
    load_model,
    delete_model,
    save_prediction_results,
    load_prediction_history,
)
from aero.core.delay_predictor import build_model, predict_batch, model_summary

# ────────────────────────────────────────────────────────────
render_header(
    "SERVICES OPERATIONS",
    "Delay Prediction Engine — NSL-based Bayesian Risk Scoring",
    logo_height=80,
    badge="SERVICES",
)

# ── Load persisted model once per session ────────────────────
if "svc_model" not in st.session_state:
    _m, _mm = load_model()
    st.session_state["svc_model"]      = _m
    st.session_state["svc_model_meta"] = _mm

tab_train, tab_model, tab_predict, tab_history = st.tabs([
    "📥  TRAINING DATA",
    "🧠  MODEL",
    "🔮  DAILY PREDICTION",
    "📋  HISTORY",
])


# ════════════════════════════════════════════════════════════
# TAB 1 — TRAINING DATA
# ════════════════════════════════════════════════════════════
with tab_train:

    render_info_banner(
        "Upload NSL Historical File",
        "Upload the <b>IN SPAC NSL</b> (or equivalent) file — tab-separated .txt, .csv, or .xlsx. "
        "The engine reads NSL_OT_VOL, MBG_OT_VOL, origin/destination loc codes, service type, "
        "ship date, commit date, and POF cause columns to build the statistical delay model.<br><br>"
        "<b>Required:</b> orig_loc_cd &nbsp;·&nbsp; dest_loc_cd &nbsp;·&nbsp; NSL_OT_VOL "
        "&nbsp;&nbsp;|&nbsp;&nbsp; "
        "<b>Improves accuracy:</b> svc_commit_dt &nbsp;·&nbsp; shp_dt &nbsp;·&nbsp; "
        "dest_market_cd &nbsp;·&nbsp; pof_cause &nbsp;·&nbsp; Service",
    )

    # ── Model status banner ──────────────────────────────────
    _m  = st.session_state.get("svc_model")
    _mm = st.session_state.get("svc_model_meta")
    if _m and not _m.get("empty") and _mm:
        trained_at = str(_mm.get("trained_at", "—"))[:16].replace("T", " ")
        st.success(
            f"✅ Model trained — {_mm.get('total_rows', '?'):,} records  |  "
            f"NSL OT: {_mm.get('nsl_ot_pct', '?')}%  |  Trained: {trained_at} UTC"
        )
    else:
        st.warning("⚠️ No model trained yet. Upload an NSL file and click **Train Model** below.")

    # ── File uploader ────────────────────────────────────────
    uploaded = st.file_uploader(
        "Drop NSL file here",
        type=["txt", "csv", "xlsx", "xls"],
        key="nsl_upload",
        help="Tab-separated .txt (typical NSL export), .csv, or .xlsx",
    )

    if uploaded:
        with st.spinner(f"Parsing {uploaded.name} …"):
            try:
                df_nsl, nsl_meta = parse_nsl_file(uploaded.read(), uploaded.name)
                st.session_state["svc_nsl_df"]  = df_nsl
                st.session_state["svc_nsl_meta"] = nsl_meta
                st.success(f"✅ Parsed {nsl_meta['total_rows']:,} records successfully.")
            except Exception as e:
                st.error(f"❌ Parse error: {e}")
                st.session_state.pop("svc_nsl_df", None)

    df_nsl   = st.session_state.get("svc_nsl_df")
    nsl_meta = st.session_state.get("svc_nsl_meta")

    if df_nsl is not None and nsl_meta:
        st.markdown("---")
        st.markdown("#### File Preview")

        render_kpi_row([
            {"label": "Total Records",  "value": f"{nsl_meta['total_rows']:,}"},
            {"label": "NSL On-Time",    "value": f"{nsl_meta['nsl_ot_pct']}%",  "color": _GREEN},
            {"label": "NSL Failed",     "value": f"{nsl_meta['failed']:,}",      "color": _RED},
            {"label": "Date Range",     "value": f"{nsl_meta['date_min']} → {nsl_meta['date_max']}",
             "color": _ORANGE},
        ])

        st.markdown("<br>", unsafe_allow_html=True)

        disp_cols = [c for c in [
            "awb_number", "orig_loc", "dest_loc", "dest_market", "service_type",
            "ship_date", "commit_date", "nsl_ot", "mbg_ot", "pof_cause", "mbg_class",
        ] if c in df_nsl.columns]
        st.dataframe(df_nsl[disp_cols].head(10), use_container_width=True)
        st.caption(
            f"Detected columns: {', '.join(nsl_meta['columns'][:15])}"
            f"{'…' if len(nsl_meta['columns']) > 15 else ''}"
        )

        st.markdown("---")

        col_train, col_clear = st.columns([3, 1])
        with col_train:
            if st.button("🧠  Train Model on this Dataset", type="primary", use_container_width=True):
                with st.spinner("Building statistical model — scanning all records…"):
                    try:
                        model = build_model(df_nsl)
                        if model.get("empty"):
                            st.error(
                                "❌ Model came back empty — check that orig_loc_cd / "
                                "dest_loc_cd / NSL_OT_VOL are populated."
                            )
                        else:
                            meta_to_save = {
                                "filename":   nsl_meta["filename"],
                                "total_rows": nsl_meta["total_rows"],
                                "nsl_ot_pct": nsl_meta["nsl_ot_pct"],
                                "date_min":   nsl_meta["date_min"],
                                "date_max":   nsl_meta["date_max"],
                            }
                            save_model(model, meta=meta_to_save)
                            trained_at = pd.Timestamp.utcnow().isoformat()
                            st.session_state["svc_model"]      = model
                            st.session_state["svc_model_meta"] = {
                                **meta_to_save, "trained_at": trained_at,
                            }
                            summ = model_summary(model)
                            st.success(
                                f"✅ Model trained on {model['total']:,} records.  "
                                f"NSL fail rate: {model['nsl_fail_rate']}%  |  "
                                f"Lanes: {summ['total_lanes']:,}  |  Hubs: {summ['total_hubs']}"
                            )
                            st.balloons()
                    except Exception as e:
                        st.error(f"❌ Training failed: {e}")

        with col_clear:
            if st.button("🗑️  Clear Model", use_container_width=True):
                delete_model()
                st.session_state["svc_model"]      = None
                st.session_state["svc_model_meta"] = None
                st.rerun()


# ════════════════════════════════════════════════════════════
# TAB 2 — MODEL PROFILE
# ════════════════════════════════════════════════════════════
with tab_model:

    active_model = st.session_state.get("svc_model")

    if not active_model or active_model.get("empty"):
        st.info("No model trained yet — go to **Training Data** tab and upload an NSL file.")
    else:
        summ = model_summary(active_model)
        thrs = summ.get("thresholds", {})
        meta = st.session_state.get("svc_model_meta") or {}

        st.markdown("### Network Profile")

        render_kpi_row([
            {"label": "Total Records",  "value": f"{summ['total_records']:,}"},
            {"label": "NSL Fail Rate",  "value": f"{summ['nsl_fail_rate']}%",  "color": _RED},
            {"label": "MBG Fail Rate",  "value": f"{summ['mbg_fail_rate']}%",  "color": _ORANGE},
            {"label": "Lanes Profiled", "value": f"{summ['total_lanes']:,}"},
            {"label": "Markets",        "value": f"{summ['total_markets']}",   "color": _GREEN},
        ])

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(
            f"Risk thresholds — "
            f"Passing: <{thrs.get('medium','?')}%  ·  "
            f"At Risk: {thrs.get('medium','?')}–{thrs.get('high','?')}%  ·  "
            f"High Risk: {thrs.get('high','?')}–{thrs.get('critical','?')}%  ·  "
            f"Critical: >{thrs.get('critical','?')}%  ·  "
            f"Data: {meta.get('date_min','?')} → {meta.get('date_max','?')}"
        )

        st.markdown("---")
        left, right = st.columns(2)

        # ── Top risky lanes ──────────────────────────────────
        with left:
            st.markdown("#### Top 5 Riskiest Lanes")
            for lane in summ.get("top_risky_lanes", []):
                pct   = lane["fail_rate"]
                color = (_RED if pct > thrs.get("critical", 70)
                         else _ORANGE if pct > thrs.get("high", 51) else _YELLOW)
                st.markdown(f"""
                <div style="background:#FAFAFA;border-left:4px solid {color};border-radius:6px;
                    padding:10px 14px;margin:6px 0;display:flex;justify-content:space-between;
                    align-items:center;">
                    <div style="font-weight:700;color:#1A1A1A;font-size:13px;">{lane['lane']}</div>
                    <div>
                        <span style="background:{color};color:#fff;padding:3px 10px;
                            border-radius:20px;font-size:12px;font-weight:700;">{pct}%</span>
                        <span style="color:#888;font-size:11px;margin-left:8px;">{lane['volume']:,} pkgs</span>
                    </div>
                </div>""", unsafe_allow_html=True)

        # ── Market bar chart ─────────────────────────────────
        with right:
            st.markdown("#### Market Breakdown")
            mkt_data = summ.get("market_breakdown", [])
            if mkt_data:
                bar_colors = [
                    (_RED   if m["fail_rate"] > thrs.get("critical", 70) else
                     _ORANGE if m["fail_rate"] > thrs.get("high", 51)    else
                     _YELLOW if m["fail_rate"] > thrs.get("medium", 35)  else _GREEN)
                    for m in mkt_data
                ]
                fig = go.Figure(go.Bar(
                    x=[m["market"] for m in mkt_data],
                    y=[m["fail_rate"] for m in mkt_data],
                    marker_color=bar_colors,
                    text=[f"{m['fail_rate']}%" for m in mkt_data],
                    textposition="outside",
                ))
                fig.update_layout(
                    height=260, margin=dict(l=0, r=0, t=10, b=40),
                    yaxis_title="NSL Fail %", xaxis_title="Market",
                    plot_bgcolor="white", paper_bgcolor="white", font=dict(size=12),
                )
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        left2, right2 = st.columns(2)

        # ── Top risky hubs ───────────────────────────────────
        with left2:
            st.markdown("#### Top 5 Riskiest Origin Hubs")
            for h in summ.get("top_risky_hubs", []):
                pct   = h["fail_rate"]
                color = (_RED if pct > thrs.get("critical", 70)
                         else _ORANGE if pct > thrs.get("high", 51) else _YELLOW)
                st.markdown(f"""
                <div style="background:#FAFAFA;border-left:4px solid {color};border-radius:6px;
                    padding:10px 14px;margin:6px 0;display:flex;justify-content:space-between;
                    align-items:center;">
                    <div style="font-weight:700;color:#1A1A1A;font-size:13px;">{h['hub']}</div>
                    <div>
                        <span style="background:{color};color:#fff;padding:3px 10px;
                            border-radius:20px;font-size:12px;font-weight:700;">{pct}%</span>
                        <span style="color:#888;font-size:11px;margin-left:8px;">{h['volume']:,} pkgs</span>
                    </div>
                </div>""", unsafe_allow_html=True)

        # ── POF causes ───────────────────────────────────────
        with right2:
            st.markdown("#### Top Failure Causes (POF)")
            sev_color = {"high": _RED, "medium": _ORANGE, "low": _YELLOW}
            for p in summ.get("top_pof_causes", [])[:8]:
                col = sev_color.get(p["severity"], _GREY)
                st.markdown(f"""
                <div style="background:#FAFAFA;border-left:4px solid {col};border-radius:6px;
                    padding:8px 14px;margin:5px 0;display:flex;justify-content:space-between;">
                    <div>
                        <span style="font-weight:700;color:#1A1A1A;font-size:12px;">{p['code']}</span>
                        <span style="color:#555;font-size:11px;margin-left:8px;">{p['desc']}</span>
                    </div>
                    <span style="color:#888;font-size:11px;white-space:nowrap;">{p['count']:,}×</span>
                </div>""", unsafe_allow_html=True)

        # ── Transit stats ────────────────────────────────────
        ts = summ.get("transit_stats", {})
        if ts:
            st.markdown("---")
            st.markdown("#### Transit Time Distribution")
            tc1, tc2 = st.columns(2)

            def _transit_card(col, label, stats, color):
                if not stats or stats.get("mean", 0) == 0:
                    return
                col.markdown(f"""
                <div style="background:#FAFAFA;border-left:5px solid {color};
                    border-radius:8px;padding:14px 16px;">
                    <div style="font-weight:800;color:{color};font-size:12px;
                        text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">{label}</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;
                        font-size:12px;color:#333;">
                        <div>Mean: <b>{stats['mean']}d</b></div>
                        <div>Median: <b>{stats['median']}d</b></div>
                        <div>P25: <b>{stats['p25']}d</b></div>
                        <div>P75: <b>{stats['p75']}d</b></div>
                        <div>P95: <b>{stats['p95']}d</b></div>
                        <div>Std Dev: <b>{stats['std']}d</b></div>
                    </div>
                </div>""", unsafe_allow_html=True)

            _transit_card(tc1, "On-Time Shipments", ts.get("on_time"), _GREEN)
            _transit_card(tc2, "Delayed Shipments",  ts.get("delayed"), _RED)


# ════════════════════════════════════════════════════════════
# TAB 3 — DAILY AWB PREDICTION
# ════════════════════════════════════════════════════════════
with tab_predict:

    active_model = st.session_state.get("svc_model")

    if not active_model or active_model.get("empty"):
        st.warning(
            "⚠️ No model trained. Go to **Training Data** tab, upload your NSL file, "
            "and click **Train Model** first."
        )
    else:
        thrs = active_model.get("thresholds", {})

        render_info_banner(
            "Upload Today's AWB Data",
            "Upload a .csv or .xlsx file with AWBs to score. The engine predicts each package's "
            "delay risk based on its origin, destination, service type, and commit date.<br><br>"
            "<b>Required:</b> orig_loc_cd &nbsp;·&nbsp; dest_loc_cd "
            "&nbsp;&nbsp;|&nbsp;&nbsp; "
            "<b>Recommended:</b> shp_trk_nbr &nbsp;·&nbsp; shp_dt &nbsp;·&nbsp; "
            "svc_commit_dt &nbsp;·&nbsp; Service &nbsp;·&nbsp; dest_market_cd &nbsp;·&nbsp; pof_cause",
        )

        awb_file = st.file_uploader(
            "Drop AWB file here",
            type=["csv", "xlsx", "xls", "txt"],
            key="awb_upload",
        )

        if awb_file:
            with st.spinner(f"Parsing {awb_file.name} …"):
                try:
                    df_awb, awb_meta = parse_awb_file(awb_file.read(), awb_file.name)
                    st.session_state["svc_awb_df"]   = df_awb
                    st.session_state["svc_awb_meta"] = awb_meta
                    st.session_state["svc_pred_df"]  = None
                    st.success(f"✅ Loaded {awb_meta['total_awbs']:,} AWBs.")
                except Exception as e:
                    st.error(f"❌ {e}")
                    st.session_state.pop("svc_awb_df", None)

        df_awb   = st.session_state.get("svc_awb_df")
        awb_meta = st.session_state.get("svc_awb_meta")
        pred_df  = st.session_state.get("svc_pred_df")

        if df_awb is not None:
            st.caption(
                f"{awb_meta['total_awbs']:,} AWBs ready  |  "
                f"Columns: {', '.join(awb_meta['columns'][:10])}"
            )

            col_run, col_save = st.columns([3, 1])
            with col_run:
                run_btn = st.button(
                    "🔮  Run Prediction on All AWBs", type="primary", use_container_width=True,
                )
            with col_save:
                save_btn = st.button(
                    "💾  Save Session", use_container_width=True,
                    disabled=(pred_df is None or pred_df.empty),
                )

            if run_btn:
                with st.spinner(f"Scoring {awb_meta['total_awbs']:,} AWBs …"):
                    pred_df = predict_batch(active_model, df_awb)
                    st.session_state["svc_pred_df"] = pred_df

            if save_btn and pred_df is not None and not pred_df.empty:
                save_prediction_results(pred_df, session_label=awb_meta.get("filename", ""))
                st.success("✅ Prediction session saved to History tab.")

        # ── Results ──────────────────────────────────────────
        if pred_df is not None and not pred_df.empty:
            st.markdown("---")
            total   = len(pred_df)
            crit    = int((pred_df["Risk Level"] == "Critical").sum())
            high    = int((pred_df["Risk Level"] == "High Risk").sum())
            at_risk = int((pred_df["Risk Level"] == "At Risk").sum())
            passing = int((pred_df["Risk Level"] == "Passing").sum())

            st.markdown("### Prediction Summary")
            render_kpi_row([
                {"label": "Total AWBs", "value": f"{total:,}"},
                {"label": "Critical",   "value": f"{crit:,}",    "color": _RED},
                {"label": "High Risk",  "value": f"{high:,}",    "color": _ORANGE},
                {"label": "At Risk",    "value": f"{at_risk:,}", "color": _YELLOW},
                {"label": "Passing",    "value": f"{passing:,}", "color": _GREEN},
            ])

            # Donut chart
            if total > 0:
                st.markdown("<br>", unsafe_allow_html=True)
                fig_d = go.Figure(go.Pie(
                    labels=["Critical", "High Risk", "At Risk", "Passing"],
                    values=[crit, high, at_risk, passing],
                    hole=0.55,
                    marker_colors=[_RED, _ORANGE, _YELLOW, _GREEN],
                    textinfo="label+percent", textfont_size=12,
                ))
                fig_d.update_layout(
                    height=280, margin=dict(l=0, r=0, t=10, b=10),
                    showlegend=False, paper_bgcolor="white",
                )
                st.plotly_chart(fig_d, use_container_width=True)

            # ── Filterable table ─────────────────────────────
            st.markdown("### AWB Risk Table")
            fc1, fc2 = st.columns(2)
            with fc1:
                filter_level = st.multiselect(
                    "Filter by Risk Level",
                    ["Critical", "High Risk", "At Risk", "Passing"],
                    default=["Critical", "High Risk", "At Risk", "Passing"],
                    key="pred_filter_level",
                )
            with fc2:
                market_opts  = sorted(pred_df["Market"].dropna().unique().tolist())
                filter_market = st.multiselect("Filter by Market", market_opts, key="pred_filter_mkt")

            view_df = pred_df.copy()
            if filter_level:
                view_df = view_df[view_df["Risk Level"].isin(filter_level)]
            if filter_market:
                view_df = view_df[view_df["Market"].isin(filter_market)]

            disp_cols = [c for c in [
                "AWB", "Lane", "Market", "Service", "Risk %", "Risk Level", "Top Reason", "Action"
            ] if c in view_df.columns]
            disp_df = view_df[disp_cols].copy()

            _row_colors = {
                "Critical":  "background-color:#FFECEC",
                "High Risk": "background-color:#FFF3E6",
                "At Risk":   "background-color:#FFFAE6",
                "Passing":   "background-color:#EDFAED",
            }

            def _style_row(row):
                return [_row_colors.get(row.get("Risk Level", ""), "")] * len(row)

            styled = disp_df.style.apply(_style_row, axis=1)
            if "Risk %" in disp_df.columns:
                styled = styled.format({"Risk %": "{:.0f}%"})

            st.dataframe(styled, use_container_width=True, height=420)
            st.caption(f"Showing {len(view_df):,} of {total:,} AWBs")

            csv_bytes = view_df.drop(
                columns=[c for c in view_df.columns if c.startswith("_")], errors="ignore"
            ).to_csv(index=False).encode()
            st.download_button(
                "⬇️  Download Results as CSV", data=csv_bytes,
                file_name="AERO_delay_predictions.csv", mime="text/csv",
            )

            # ── Drilldown ────────────────────────────────────
            st.markdown("---")
            st.markdown("### AWB Drilldown")
            awb_options = view_df["AWB"].dropna().tolist()
            if awb_options:
                selected = st.selectbox("Select AWB", awb_options, key="drilldown_awb")
                row      = view_df[view_df["AWB"] == selected]
                if not row.empty:
                    r     = row.iloc[0]
                    color = r.get("_color", _GREY)
                    emoji = r.get("_emoji", "⚪")
                    risk  = r.get("Risk %", 0)
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#FFFFFF,#F7F3FF);
                        border-left:6px solid {color};border-radius:10px;
                        padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span style="font-size:20px;font-weight:900;color:#1A1A1A;">
                                    {emoji} AWB {r['AWB']}
                                </span>
                                <span style="margin-left:12px;background:{color};color:#fff;
                                    padding:4px 14px;border-radius:20px;font-size:13px;
                                    font-weight:700;">{r['Risk Level']}</span>
                            </div>
                            <div style="font-size:36px;font-weight:900;color:{color};">
                                {risk:.0f}%
                            </div>
                        </div>
                        <div style="margin-top:10px;font-size:13px;color:#444;">
                            <b>Lane:</b> {r['Lane']} &nbsp;|&nbsp;
                            <b>Market:</b> {r.get('Market','—')} &nbsp;|&nbsp;
                            <b>Service:</b> {r.get('Service','—')}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.markdown("**Risk Signals**")
                        st.markdown(f"- {r.get('Top Reason', '—')}")
                    with dc2:
                        st.markdown("**Recommended Action**")
                        st.markdown(f"- {r.get('Action', '—')}")


# ════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("### Past Prediction Sessions")
    history = load_prediction_history()

    if not history:
        st.info(
            "No prediction sessions saved yet. Run a prediction in the "
            "**Daily Prediction** tab and click **Save Session**."
        )
    else:
        sessions         = sorted(history.keys(), reverse=True)
        selected_session = st.selectbox("Select session", sessions, key="hist_session")
        if selected_session:
            df_h    = history[selected_session]
            total_h = len(df_h)

            if "Risk Level" in df_h.columns:
                render_kpi_row([
                    {"label": "Total",    "value": f"{total_h:,}"},
                    {"label": "Critical", "value": f"{int((df_h['Risk Level']=='Critical').sum()):,}",  "color": _RED},
                    {"label": "High Risk","value": f"{int((df_h['Risk Level']=='High Risk').sum()):,}", "color": _ORANGE},
                    {"label": "At Risk",  "value": f"{int((df_h['Risk Level']=='At Risk').sum()):,}",  "color": _YELLOW},
                    {"label": "Passing",  "value": f"{int((df_h['Risk Level']=='Passing').sum()):,}",  "color": _GREEN},
                ])
                st.markdown("<br>", unsafe_allow_html=True)

            st.dataframe(df_h, use_container_width=True, height=400)
            st.download_button(
                f"⬇️  Download {selected_session}",
                data=df_h.to_csv(index=False).encode(),
                file_name=f"AERO_predictions_{selected_session}.csv",
                mime="text/csv",
            )

render_footer("SERVICES")
