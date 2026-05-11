# ============================================================
# AERO — Delay Prediction Engine
# Bayesian-statistical model ported from FedEx OpsPulse
# PredictiveService.js (Node.js → Python/pandas)
#
# Architecture:
#   build_model(df)          → model dict (in-memory profile)
#   predict_delay(model, row) → prediction dict per AWB
#   predict_batch(model, df)  → vectorized, returns DataFrame
#
# No heavy ML dependencies — pure statistics over NSL data.
# ============================================================
from __future__ import annotations

import math
from datetime import datetime, date
from typing import Any

import pandas as pd
import numpy as np

# ── POF cause label map (common subcode → description) ──────
_POF_CUSTOM_MAP: dict[str, dict] = {
    "55": {"desc": "Regulatory Agency Clearance Delay", "severity": "high",    "cat": "Customs"},
    "84": {"desc": "Delay Beyond Our Control",           "severity": "medium",  "cat": "External"},
    "85": {"desc": "Mechanical Delay",                   "severity": "high",    "cat": "Equipment"},
    "22": {"desc": "Pkg Missed Aircraft/Truck",          "severity": "high",    "cat": "Hub"},
    "32": {"desc": "Plane Arrived Late",                 "severity": "high",    "cat": "Air"},
    "03": {"desc": "Incorrect Address",                  "severity": "medium",  "cat": "Delivery"},
    "07": {"desc": "Shipment Refused by Recipient",      "severity": "medium",  "cat": "Delivery"},
    "08": {"desc": "Recipient Not In / Business Closed", "severity": "low",     "cat": "Delivery"},
    "10": {"desc": "Damaged — Delivery Not Completed",   "severity": "high",    "cat": "Damage"},
    "37": {"desc": "Observed Package Damage",            "severity": "high",    "cat": "Damage"},
    "EH": {"desc": "Export Hold / Clearance Delay",      "severity": "high",    "cat": "Customs"},
    "TD": {"desc": "Transit Delay",                      "severity": "medium",  "cat": "Delay"},
    "CD": {"desc": "Customs Delay",                      "severity": "high",    "cat": "Customs"},
    "HH": {"desc": "Hub Handling Delay",                 "severity": "medium",  "cat": "Hub"},
    "AT": {"desc": "Arrival Timing Issue",               "severity": "medium",  "cat": "Timing"},
    "OD": {"desc": "Origin Departure Delay",             "severity": "medium",  "cat": "Origin"},
    "LD": {"desc": "Linehaul Delay",                     "severity": "high",    "cat": "Transit"},
    "TY": {"desc": "Temporary Yield / Congestion",       "severity": "medium",  "cat": "Hub"},
    "TH": {"desc": "Third-Party Handling Delay",         "severity": "medium",  "cat": "External"},
    "R55": {"desc": "Regulatory Agency Clearance Delay", "severity": "high",    "cat": "Customs"},
    "R":   {"desc": "Reroute / Regulatory Hold",         "severity": "medium",  "cat": "Customs"},
}


def _resolve_pof(code: str | None) -> dict:
    """Map a POF cause code to a human-readable descriptor."""
    if not code:
        return {"code": None, "desc": "Unknown", "severity": "medium", "cat": "Unknown"}
    code = str(code).strip()
    if code in _POF_CUSTOM_MAP:
        return {"code": code, **_POF_CUSTOM_MAP[code]}
    # Try stripping common prefixes (STAT55 → 55)
    for prefix in ("STAT", "DEX", "PUX", "HEX", "SEP", "DDEX"):
        if code.startswith(prefix):
            sub = code[len(prefix):]
            if sub in _POF_CUSTOM_MAP:
                return {"code": code, **_POF_CUSTOM_MAP[sub]}
    return {"code": code, "desc": f"POF Code {code}", "severity": "medium", "cat": "Unknown"}


def _pct_stats(arr: list[float]) -> dict:
    """Compute mean + percentile stats from a list of floats."""
    if not arr:
        return {"mean": 0, "median": 0, "p5": 0, "p25": 0, "p75": 0, "p95": 0, "std": 0}
    s = sorted(arr)
    n = len(s)
    mean = sum(s) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in s) / n) if n > 1 else 0
    return {
        "mean":   round(mean, 1),
        "median": round(s[n // 2], 1),
        "p5":     round(s[max(0, int(n * 0.05))], 1),
        "p25":    round(s[max(0, int(n * 0.25))], 1),
        "p75":    round(s[min(n - 1, int(n * 0.75))], 1),
        "p95":    round(s[min(n - 1, int(n * 0.95))], 1),
        "std":    round(std, 2),
    }


# ────────────────────────────────────────────────────────────
# build_model()
# ────────────────────────────────────────────────────────────
def build_model(df: pd.DataFrame) -> dict[str, Any]:
    """
    Build a statistical model profile from a cleaned NSL DataFrame.

    Expected columns (after normalisation by nsl_store.parse_nsl):
        awb, orig_loc, dest_loc, dest_market, service_type,
        ship_date (date), commit_date (date), pod_date (date),
        nsl_ot (int 0/1), mbg_ot (int 0/1), pof_cause (str|None)

    Returns a dict that can be JSON-serialised and cached.
    """
    if df is None or df.empty:
        return {"empty": True}

    total = len(df)
    m: dict[str, Any] = {
        "total":     total,
        "lanes":     {},   # "ORIG→DEST"
        "hubs":      {},   # orig_loc
        "markets":   {},   # dest_market
        "services":  {},   # service_type
        "dow":       {i: {"total": 0, "fail": 0} for i in range(7)},
        "months":    {},   # "YYYY-MM"
        "pof_causes":{},
        "transit": {"on_time": [], "delayed": []},
        "nsl_fail_rate": 0.0,
        "mbg_fail_rate": 0.0,
        "thresholds": {},
    }

    nsl_fail = 0
    mbg_fail = 0

    for _, r in df.iterrows():
        orig      = str(r.get("orig_loc", "UNK") or "UNK").strip()
        dest      = str(r.get("dest_loc", "UNK") or "UNK").strip()
        market    = str(r.get("dest_market", "UNK") or "UNK").strip()
        svc       = str(r.get("service_type", "Priority") or "Priority").strip()
        nsl_ot    = int(r.get("nsl_ot", 0) or 0)
        mbg_ot    = int(r.get("mbg_ot", 0) or 0)
        pof_cause = r.get("pof_cause") or None
        ship_dt   = r.get("ship_date")
        pod_dt    = r.get("pod_date")

        nsl_failed = nsl_ot == 0
        mbg_failed = mbg_ot == 0
        if nsl_failed: nsl_fail += 1
        if mbg_failed: mbg_fail += 1

        lane_key = f"{orig}→{dest}"

        # ── Lane ────────────────────────────────────────────
        if lane_key not in m["lanes"]:
            m["lanes"][lane_key] = {
                "total": 0, "nsl_fail": 0, "mbg_fail": 0,
                "pof_causes": {}, "transit_days": [],
                "avg_transit": 0, "median_transit": 0,
                "p25": 0, "p75": 0, "p95": 0, "std": 0,
            }
        ln = m["lanes"][lane_key]
        ln["total"] += 1
        if nsl_failed: ln["nsl_fail"] += 1
        if mbg_failed: ln["mbg_fail"] += 1
        if pof_cause:
            ln["pof_causes"][str(pof_cause)] = ln["pof_causes"].get(str(pof_cause), 0) + 1

        # Transit time
        try:
            if ship_dt and pod_dt:
                sd = pd.to_datetime(ship_dt)
                pd_ = pd.to_datetime(pod_dt)
                td = (pd_ - sd).days
                if 0 < td < 60:
                    ln["transit_days"].append(td)
                    key = "on_time" if not nsl_failed else "delayed"
                    m["transit"][key].append(td)
        except Exception:
            pass

        # ── Hub (origin) ────────────────────────────────────
        if orig not in m["hubs"]:
            m["hubs"][orig] = {"total": 0, "nsl_fail": 0}
        m["hubs"][orig]["total"] += 1
        if nsl_failed: m["hubs"][orig]["nsl_fail"] += 1

        # ── Market ──────────────────────────────────────────
        if market not in m["markets"]:
            m["markets"][market] = {"total": 0, "nsl_fail": 0}
        m["markets"][market]["total"] += 1
        if nsl_failed: m["markets"][market]["nsl_fail"] += 1

        # ── Service ─────────────────────────────────────────
        if svc not in m["services"]:
            m["services"][svc] = {"total": 0, "nsl_fail": 0}
        m["services"][svc]["total"] += 1
        if nsl_failed: m["services"][svc]["nsl_fail"] += 1

        # ── POF causes ──────────────────────────────────────
        if pof_cause:
            m["pof_causes"][str(pof_cause)] = m["pof_causes"].get(str(pof_cause), 0) + 1

        # ── Day of week ─────────────────────────────────────
        try:
            if ship_dt:
                dow = pd.to_datetime(ship_dt).dayofweek  # 0=Mon … 6=Sun
                m["dow"][dow]["total"] += 1
                if nsl_failed: m["dow"][dow]["fail"] += 1
        except Exception:
            pass

        # ── Month ───────────────────────────────────────────
        try:
            if ship_dt:
                mkey = pd.to_datetime(ship_dt).strftime("%Y-%m")
                if mkey not in m["months"]:
                    m["months"][mkey] = {"total": 0, "nsl_fail": 0}
                m["months"][mkey]["total"] += 1
                if nsl_failed: m["months"][mkey]["nsl_fail"] += 1
        except Exception:
            pass

    # ── Finalise lane transit stats ──────────────────────────
    for ln in m["lanes"].values():
        td = ln.pop("transit_days", [])
        if td:
            st = _pct_stats(td)
            ln["avg_transit"]    = st["mean"]
            ln["median_transit"] = st["median"]
            ln["p25"]            = st["p25"]
            ln["p75"]            = st["p75"]
            ln["p95"]            = st["p95"]
            ln["std"]            = st["std"]

    # ── Global rates ─────────────────────────────────────────
    m["nsl_fail_rate"] = round(nsl_fail / total * 100, 1) if total else 0.0
    m["mbg_fail_rate"] = round(mbg_fail / total * 100, 1) if total else 0.0

    # ── Transit distribution ─────────────────────────────────
    m["transit_stats"] = {
        "on_time": _pct_stats(m["transit"]["on_time"]),
        "delayed": _pct_stats(m["transit"]["delayed"]),
    }
    del m["transit"]

    # ── Dynamic thresholds ───────────────────────────────────
    nfr = m["nsl_fail_rate"]
    m["thresholds"] = {
        "critical": round(min(90, nfr * 1.8)),
        "high":     round(min(75, nfr * 1.3)),
        "medium":   round(min(60, nfr * 0.9)),
    }

    return m


# ────────────────────────────────────────────────────────────
# predict_delay()
# ────────────────────────────────────────────────────────────
def predict_delay(model: dict, awb: dict) -> dict:
    """
    Predict NSL delay risk for a single AWB.

    awb keys (all optional except orig_loc / dest_loc):
        awb_number, orig_loc, dest_loc, dest_market,
        service_type, ship_date, commit_date, pof_cause

    Returns:
        {
          "awb": str,
          "lane": str,
          "probability": int (0-100),
          "risk_level": "Critical" | "High Risk" | "At Risk" | "Passing",
          "risk_color": "#hex",
          "reasons": [str, ...],
          "recommendations": [str, ...],
          "risk_factors": dict,
        }
    """
    if model.get("empty"):
        return _fallback(awb)

    orig    = str(awb.get("orig_loc", "UNK") or "UNK").strip()
    dest    = str(awb.get("dest_loc", "UNK") or "UNK").strip()
    market  = str(awb.get("dest_market", "UNK") or "UNK").strip()
    svc     = str(awb.get("service_type", "Priority") or "Priority").strip()
    lane_k  = f"{orig}→{dest}"

    reasons: list[str] = []
    recs:    list[str] = []
    rfs:     dict      = {}

    nfr = model["nsl_fail_rate"]

    # ── STEP 1: Base probability from lane fail rate ─────────
    lane = model["lanes"].get(lane_k)
    if lane and lane["total"] >= 3:
        k = 30
        sw = lane["total"] / (lane["total"] + k)
        lane_fr = lane["nsl_fail"] / lane["total"] * 100
        base = sw * lane_fr + (1 - sw) * nfr

        rfs["lane_fail_rate"] = round(lane_fr, 1)
        rfs["lane_samples"]   = lane["total"]
        rfs["lane_avg_transit"] = lane.get("avg_transit", 0)

        if lane_fr > 60:
            reasons.append(f"Lane {lane_k} has {lane_fr:.0f}% failure rate ({lane['total']} shipments) — high-risk corridor")
            recs.append(f"Consider alternative routing for {lane_k}")
        elif lane_fr > nfr + 10:
            reasons.append(f"Lane {lane_k}: {lane_fr:.0f}% fail rate — above network avg of {nfr:.0f}%")
        elif lane_fr < nfr - 10:
            reasons.append(f"Lane {lane_k}: {lane_fr:.0f}% fail rate — below network avg (good performance)")

        # Top POF on this lane
        if lane["pof_causes"]:
            top_pof_code = max(lane["pof_causes"], key=lane["pof_causes"].get)
            top_pof_cnt  = lane["pof_causes"][top_pof_code]
            pof_info     = _resolve_pof(top_pof_code)
            rfs["lane_top_pof"]  = pof_info["desc"]
            rfs["lane_top_pof_severity"] = pof_info["severity"]
            reasons.append(
                f"Top lane failure cause: {pof_info['desc']} [{top_pof_code}] "
                f"({top_pof_cnt}×, {pof_info['severity']})"
            )
    else:
        base = nfr
        reasons.append(f"No lane history for {lane_k} — using network baseline ({nfr:.0f}%)")

    adjusted = base

    # ── STEP 2A: Origin hub ──────────────────────────────────
    hub = model["hubs"].get(orig)
    if hub and hub["total"] >= 10:
        hub_fr    = hub["nsl_fail"] / hub["total"] * 100
        hub_ratio = hub_fr / nfr if nfr else 1
        adjusted *= (1 + 0.3 * (hub_ratio - 1))
        rfs["hub_fail_rate"] = round(hub_fr, 1)
        rfs["hub_volume"]    = hub["total"]
        if hub_fr > nfr + 10:
            reasons.append(f"Origin hub {orig}: {hub_fr:.0f}% fail rate — {hub_fr - nfr:.0f}pp above network")
            recs.append(f"Escalate to hub supervisor at {orig}")

    # ── STEP 2B: Destination market ──────────────────────────
    mkt = model["markets"].get(market)
    if mkt and mkt["total"] >= 10:
        mkt_fr    = mkt["nsl_fail"] / mkt["total"] * 100
        mkt_ratio = mkt_fr / nfr if nfr else 1
        adjusted *= (1 + 0.25 * (mkt_ratio - 1))
        rfs["market_fail_rate"] = round(mkt_fr, 1)
        rfs["dest_market"]      = market
        if mkt_fr > nfr + 10:
            reasons.append(f"Market {market}: {mkt_fr:.0f}% fail rate — customs/regulatory complexity")
            recs.append(f"Pre-clear customs documentation for {market}")

    # ── STEP 2C: Service type ────────────────────────────────
    svc_stats = model["services"].get(svc)
    if svc_stats and svc_stats["total"] >= 10:
        svc_fr    = svc_stats["nsl_fail"] / svc_stats["total"] * 100
        svc_ratio = svc_fr / nfr if nfr else 1
        adjusted *= (1 + 0.2 * (svc_ratio - 1))
        rfs["service_fail_rate"] = round(svc_fr, 1)
        if svc_fr > nfr + 5:
            reasons.append(f"{svc} service: {svc_fr:.0f}% fail rate")

    # ── STEP 2D: Day of week ─────────────────────────────────
    ship_date = awb.get("ship_date")
    commit_date = awb.get("commit_date")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_names_long = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    try:
        if ship_date:
            sd = pd.to_datetime(ship_date)
            dow = sd.dayofweek
            dow_s = model["dow"].get(dow, {})
            if dow_s.get("total", 0) > 100:
                dow_fr    = dow_s["fail"] / dow_s["total"] * 100
                dow_ratio = dow_fr / nfr if nfr else 1
                adjusted *= (1 + 0.15 * (dow_ratio - 1))
                rfs["day_of_week"]   = day_names[dow]
                rfs["dow_fail_rate"] = round(dow_fr, 1)
                if dow_fr > nfr + 3:
                    reasons.append(
                        f"{day_names_long[dow]}: {dow_fr:.0f}% fail rate "
                        f"({dow_fr - nfr:.1f}pp above avg)"
                    )
    except Exception:
        pass

    # ── STEP 2E: Transit time vs commit window ───────────────
    try:
        if lane and lane.get("avg_transit") and ship_date and commit_date:
            sd   = pd.to_datetime(ship_date)
            cd   = pd.to_datetime(commit_date)
            commit_days = (cd - sd).days
            if commit_days > 0:
                t_ratio = lane["avg_transit"] / commit_days
                rfs["transit_ratio"]  = round(t_ratio, 2)
                rfs["transit_avg"]    = lane["avg_transit"]
                rfs["commit_days"]    = commit_days
                if t_ratio > 1.0:
                    adjusted *= (1 + 0.4 * (t_ratio - 1))
                    reasons.append(
                        f"Lane avg transit ({lane['avg_transit']}d) exceeds commit window ({commit_days}d)"
                    )
                    recs.append("Proactively notify customer; consider expedited routing")
                elif t_ratio < 0.7:
                    adjusted *= 0.85
                    reasons.append(
                        f"Lane has comfortable transit margin ({lane['avg_transit']}d avg vs {commit_days}d commit)"
                    )
            # P95 tail risk
            if lane.get("p95") and commit_days > 0 and lane["p95"] > commit_days:
                p95_ratio = lane["p95"] / commit_days
                adjusted *= (1 + 0.2 * (p95_ratio - 1))
                reasons.append(
                    f"Lane P95 transit ({lane['p95']}d) exceeds commit ({commit_days}d) — tail risk"
                )
                rfs["transit_p95"] = lane["p95"]
    except Exception:
        pass

    # ── STEP 2F: Monthly seasonality ────────────────────────
    try:
        if ship_date:
            mkey = pd.to_datetime(ship_date).strftime("%Y-%m")
            mo   = model["months"].get(mkey)
            if mo and mo["total"] > 200:
                mo_fr    = mo["nsl_fail"] / mo["total"] * 100
                mo_ratio = mo_fr / nfr if nfr else 1
                adjusted *= (1 + 0.1 * (mo_ratio - 1))
                rfs["month_fail_rate"] = round(mo_fr, 1)
                rfs["month"] = mkey
                if mo_fr > nfr + 5:
                    reasons.append(f"{mkey}: {mo_fr:.0f}% fail rate — seasonal risk")
    except Exception:
        pass

    # ── STEP 3: Active POF cause (live shipment signal) ──────
    pof_cause = awb.get("pof_cause")
    if pof_cause:
        pof_info = _resolve_pof(str(pof_cause))
        rfs["pof_cause"]    = pof_cause
        rfs["pof_desc"]     = pof_info["desc"]
        rfs["pof_severity"] = pof_info["severity"]
        boost = {"high": 1.4, "medium": 1.2, "low": 1.05}
        adjusted *= boost.get(pof_info["severity"], 1.3)
        reasons.append(
            f"Active failure code: {pof_info['desc']} [{pof_cause}] — {pof_info['severity']} severity"
        )
        network_cnt = model["pof_causes"].get(str(pof_cause), 0)
        recs.append(
            f'Address "{pof_info["desc"]}" ({pof_info["cat"]}) — '
            f"{network_cnt} network occurrences historically"
        )

    # ── STEP 4: Clamp + classify ─────────────────────────────
    prob = max(0, min(100, round(adjusted)))
    thr  = model["thresholds"]

    if prob >= thr["critical"]:
        risk_level = "Critical"
        risk_color = "#DE002E"
        risk_emoji = "🔴"
    elif prob >= thr["high"]:
        risk_level = "High Risk"
        risk_color = "#FF6200"
        risk_emoji = "🟠"
    elif prob >= thr["medium"]:
        risk_level = "At Risk"
        risk_color = "#FFB800"
        risk_emoji = "🟡"
    else:
        risk_level = "Passing"
        risk_color = "#008A00"
        risk_emoji = "🟢"

    if not recs:
        if prob > 60:
            recs.append("Escalate to operations team for priority handling")
        elif prob > 40:
            recs.append("Monitor closely; pre-alert customer if no movement by EOD")

    return {
        "awb":            awb.get("awb_number", "—"),
        "lane":           lane_k,
        "origin":         orig,
        "destination":    dest,
        "market":         market,
        "service":        svc,
        "probability":    prob,
        "risk_level":     risk_level,
        "risk_color":     risk_color,
        "risk_emoji":     risk_emoji,
        "reasons":        reasons,
        "recommendations": recs,
        "risk_factors":   rfs,
    }


# ────────────────────────────────────────────────────────────
# predict_batch()
# ────────────────────────────────────────────────────────────
def predict_batch(model: dict, df: pd.DataFrame) -> pd.DataFrame:
    """
    Run predict_delay() over every row of an AWB DataFrame.
    Returns a results DataFrame ready for display.
    """
    results = []
    for _, row in df.iterrows():
        awb_dict = row.to_dict()
        pred = predict_delay(model, awb_dict)
        results.append({
            "AWB":          pred["awb"],
            "Lane":         pred["lane"],
            "Origin":       pred["origin"],
            "Destination":  pred["destination"],
            "Market":       pred["market"],
            "Service":      pred["service"],
            "Risk %":       pred["probability"],
            "Risk Level":   pred["risk_level"],
            "Top Reason":   pred["reasons"][0] if pred["reasons"] else "—",
            "Action":       pred["recommendations"][0] if pred["recommendations"] else "—",
            "_color":       pred["risk_color"],
            "_emoji":       pred["risk_emoji"],
        })
    out = pd.DataFrame(results)
    if not out.empty:
        out = out.sort_values("Risk %", ascending=False).reset_index(drop=True)
    return out


# ── Fallback (no model trained yet) ─────────────────────────
def _fallback(awb: dict) -> dict:
    orig = str(awb.get("orig_loc", "UNK") or "UNK")
    dest = str(awb.get("dest_loc", "UNK") or "UNK")
    return {
        "awb":            awb.get("awb_number", "—"),
        "lane":           f"{orig}→{dest}",
        "origin":         orig,
        "destination":    dest,
        "market":         str(awb.get("dest_market", "UNK") or "UNK"),
        "service":        str(awb.get("service_type", "Unknown") or "Unknown"),
        "probability":    0,
        "risk_level":     "Unknown",
        "risk_color":     "#888888",
        "risk_emoji":     "⚪",
        "reasons":        ["No model trained — upload NSL data first"],
        "recommendations": ["Train the model on the Services page before running predictions"],
        "risk_factors":   {},
    }


# ── Summary stats helpers (for dashboard display) ────────────
def model_summary(model: dict) -> dict:
    """Return quick stats for the Model dashboard tab."""
    if not model or model.get("empty"):
        return {}
    lanes = model["lanes"]
    hubs  = model["hubs"]
    mkts  = model["markets"]

    # Top 5 riskiest lanes (min 10 shipments)
    lane_risks = [
        {"lane": k, "fail_rate": round(v["nsl_fail"] / v["total"] * 100, 1), "volume": v["total"]}
        for k, v in lanes.items() if v["total"] >= 10
    ]
    lane_risks.sort(key=lambda x: x["fail_rate"], reverse=True)

    # Top 5 riskiest hubs (min 20 shipments)
    hub_risks = [
        {"hub": k, "fail_rate": round(v["nsl_fail"] / v["total"] * 100, 1), "volume": v["total"]}
        for k, v in hubs.items() if v["total"] >= 20
    ]
    hub_risks.sort(key=lambda x: x["fail_rate"], reverse=True)

    # Market breakdown
    mkt_breakdown = [
        {"market": k, "fail_rate": round(v["nsl_fail"] / v["total"] * 100, 1), "volume": v["total"]}
        for k, v in mkts.items() if v["total"] >= 5
    ]
    mkt_breakdown.sort(key=lambda x: x["volume"], reverse=True)

    # Top POF causes
    pof_sorted = sorted(model["pof_causes"].items(), key=lambda x: x[1], reverse=True)[:10]
    pof_enriched = [
        {"code": k, "count": v, "desc": _resolve_pof(k)["desc"], "severity": _resolve_pof(k)["severity"]}
        for k, v in pof_sorted
    ]

    return {
        "total_records":  model["total"],
        "nsl_fail_rate":  model["nsl_fail_rate"],
        "mbg_fail_rate":  model["mbg_fail_rate"],
        "total_lanes":    len(lanes),
        "total_hubs":     len(hubs),
        "total_markets":  len(mkts),
        "thresholds":     model["thresholds"],
        "top_risky_lanes": lane_risks[:5],
        "top_risky_hubs":  hub_risks[:5],
        "market_breakdown": mkt_breakdown,
        "top_pof_causes":   pof_enriched,
        "transit_stats":    model.get("transit_stats", {}),
    }
