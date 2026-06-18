"""
Sprint 5 Phase 3 — Greeks Exposure Command Center Engine.

Builds institutional-grade options portfolio Greeks diagnostics:
- Net Greeks
- Greeks by underlying
- Greeks by expiration
- Greeks by strategy
- Concentration diagnostics
- Greek exposure curves
- Greeks risk score

Depends on Sprint 5 Phase 1:
modules.options.options_portfolio_risk_engine.normalize_risk_positions
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


CORE_GREEKS = ["delta", "gamma", "theta", "vega"]
ADVANCED_GREEKS = ["rho", "charm", "vanna", "vomma"]
ALL_GREEKS = CORE_GREEKS + ADVANCED_GREEKS


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _empty(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def calculate_net_greeks_exposure(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    greeks = {}
    abs_greeks = {}

    for greek in ALL_GREEKS:
        col = f"net_{greek}"
        if col not in df.columns:
            df[col] = 0
        greeks[greek] = round(float(_num(df[col]).sum()), 4)
        abs_greeks[greek] = round(float(_num(df[col]).abs().sum()), 4)

    return {
        "available": True,
        "net_greeks": greeks,
        "gross_greeks": abs_greeks,
        "position_count": int(len(df)),
        "gross_notional_proxy": round(float(df.get("notional_proxy", pd.Series(dtype=float)).sum() or 0), 2),
    }


def _group_exposure(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    if group_col not in df.columns:
        df[group_col] = "Unknown"

    agg = {
        "positions": (group_col, "size"),
        "market_value": ("market_value", "sum"),
        "notional_proxy": ("notional_proxy", "sum"),
    }

    for greek in ALL_GREEKS:
        col = f"net_{greek}"
        if col not in df.columns:
            df[col] = 0
        agg[f"net_{greek}"] = (col, "sum")
        agg[f"abs_{greek}"] = (col, lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0).abs().sum()))

    grouped = (
        df.groupby(group_col, as_index=False)
        .agg(**agg)
        .sort_values("notional_proxy", ascending=False)
        .reset_index(drop=True)
    )

    total_notional = max(1.0, float(grouped["notional_proxy"].sum() or 1.0))
    grouped["notional_share"] = (grouped["notional_proxy"] / total_notional * 100).round(2)

    for col in grouped.columns:
        if col.startswith("net_") or col.startswith("abs_") or col in {"market_value", "notional_proxy"}:
            grouped[col] = pd.to_numeric(grouped[col], errors="coerce").fillna(0).round(4)

    return grouped


def calculate_greeks_by_underlying(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")
    return {"available": True, "by_underlying": _group_exposure(df, "underlying")}


def calculate_greeks_by_expiry(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")
    return {"available": True, "by_expiry": _group_exposure(df, "expiry")}


def calculate_greeks_by_strategy(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")
    if "strategy" not in df.columns:
        df["strategy"] = "Unclassified"
    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified")
    return {"available": True, "by_strategy": _group_exposure(df, "strategy")}


def calculate_greek_concentration(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    rows = []
    for greek in CORE_GREEKS:
        col = f"net_{greek}"
        if col not in df.columns:
            df[col] = 0

        total_abs = max(1.0, float(_num(df[col]).abs().sum()))
        temp = df.copy()
        temp["abs_exposure"] = _num(temp[col]).abs()
        top = temp.sort_values("abs_exposure", ascending=False).head(1)

        if top.empty:
            rows.append({
                "Greek": greek.title(),
                "Top Contributor": "—",
                "Top Share": 0,
                "Total Abs Exposure": 0,
                "Concentration Level": "LOW",
            })
            continue

        share = float(top.iloc[0]["abs_exposure"] / total_abs * 100)
        level = "HIGH" if share >= 50 else "MEDIUM" if share >= 30 else "LOW"

        rows.append({
            "Greek": greek.title(),
            "Top Contributor": top.iloc[0].get("option_symbol") or top.iloc[0].get("underlying") or "Unknown",
            "Top Share": round(share, 2),
            "Total Abs Exposure": round(total_abs, 4),
            "Concentration Level": level,
        })

    table = pd.DataFrame(rows)

    high_count = int((table["Concentration Level"] == "HIGH").sum()) if not table.empty else 0
    medium_count = int((table["Concentration Level"] == "MEDIUM").sum()) if not table.empty else 0

    if high_count:
        overall = "HIGH"
    elif medium_count:
        overall = "MEDIUM"
    else:
        overall = "LOW"

    return {
        "available": True,
        "concentration_level": overall,
        "concentration": table,
    }


def build_greek_exposure_curves(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    curve_source = df.copy()

    if "strike" not in curve_source.columns:
        curve_source["strike"] = 0

    curve_source["strike_bucket"] = pd.to_numeric(curve_source["strike"], errors="coerce").fillna(0).round(0)

    curve = (
        curve_source.groupby("strike_bucket", as_index=False)
        .agg(
            net_delta=("net_delta", "sum"),
            net_gamma=("net_gamma", "sum"),
            net_theta=("net_theta", "sum"),
            net_vega=("net_vega", "sum"),
            notional_proxy=("notional_proxy", "sum"),
            positions=("strike_bucket", "size"),
        )
        .sort_values("strike_bucket")
        .reset_index(drop=True)
    )

    for col in ["net_delta", "net_gamma", "net_theta", "net_vega", "notional_proxy"]:
        curve[col] = pd.to_numeric(curve[col], errors="coerce").fillna(0).round(4)

    return {"available": True, "curve": curve}


def score_greeks_exposure(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    net = calculate_net_greeks_exposure(df)
    concentration = calculate_greek_concentration(df)

    gross_notional = max(1.0, float(df.get("notional_proxy", pd.Series(dtype=float)).sum() or 1.0))
    greeks = net.get("net_greeks", {}) if net.get("available") else {}
    gross = net.get("gross_greeks", {}) if net.get("available") else {}

    delta_score = min(25, abs(float(greeks.get("delta", 0))) / gross_notional * 5000)
    gamma_score = min(25, abs(float(greeks.get("gamma", 0))) / gross_notional * 10000)
    vega_score = min(20, abs(float(greeks.get("vega", 0))) / gross_notional * 3000)
    theta_score = min(15, abs(float(greeks.get("theta", 0))) / gross_notional * 2000)

    conc_score = 0
    if concentration.get("available"):
        if concentration.get("concentration_level") == "HIGH":
            conc_score = 15
        elif concentration.get("concentration_level") == "MEDIUM":
            conc_score = 8

    score = round(min(100, delta_score + gamma_score + vega_score + theta_score + conc_score), 2)

    if score >= 75:
        level = "HIGH"
    elif score >= 50:
        level = "MEDIUM"
    elif score >= 25:
        level = "LOW"
    else:
        level = "VERY_LOW"

    drivers = []
    if delta_score >= 15:
        drivers.append("Large net delta exposure")
    if gamma_score >= 15:
        drivers.append("Large net gamma exposure")
    if vega_score >= 12:
        drivers.append("Large net vega exposure")
    if theta_score >= 10:
        drivers.append("Large theta burn")
    if conc_score >= 8:
        drivers.append(f"{concentration.get('concentration_level')} Greek concentration")

    return {
        "available": True,
        "greeks_risk_score": score,
        "greeks_risk_level": level,
        "drivers": drivers or ["No dominant Greeks risk driver detected"],
        "component_scores": {
            "delta": round(delta_score, 2),
            "gamma": round(gamma_score, 2),
            "vega": round(vega_score, 2),
            "theta": round(theta_score, 2),
            "concentration": round(conc_score, 2),
        },
        "gross_greeks": gross,
    }


def build_greeks_exposure_report(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No options positions available.", "positions": df}

    net = calculate_net_greeks_exposure(df)
    by_underlying = calculate_greeks_by_underlying(df)
    by_expiry = calculate_greeks_by_expiry(df)
    by_strategy = calculate_greeks_by_strategy(df)
    concentration = calculate_greek_concentration(df)
    curves = build_greek_exposure_curves(df)
    score = score_greeks_exposure(df)

    return {
        "available": True,
        "positions": df,
        "net": net,
        "by_underlying": by_underlying,
        "by_expiry": by_expiry,
        "by_strategy": by_strategy,
        "concentration": concentration,
        "curves": curves,
        "score": score,
    }


def summarize_greeks_exposure(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Greeks exposure unavailable: {report.get('reason', 'unknown reason')}"

    score = report.get("score", {})
    greeks = report.get("net", {}).get("net_greeks", {})

    return (
        f"Greeks risk is {score.get('greeks_risk_level')} "
        f"({score.get('greeks_risk_score')}/100). "
        f"Net delta {greeks.get('delta', 0):,.2f}, "
        f"net gamma {greeks.get('gamma', 0):,.2f}, "
        f"net theta {greeks.get('theta', 0):,.2f}, "
        f"net vega {greeks.get('vega', 0):,.2f}."
    )
