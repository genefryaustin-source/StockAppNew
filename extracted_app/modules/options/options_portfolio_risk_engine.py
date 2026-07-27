"""
Sprint 5 Phase 1 — Options Portfolio Risk Engine.

Portfolio-level risk analytics for options positions:
- Net Greeks
- Underlying concentration
- Expiration concentration
- Shock scenarios
- Largest risk contributors
- Portfolio risk score
"""
from __future__ import annotations

from typing import Any
import pandas as pd


GREEK_COLUMNS = ["delta", "gamma", "theta", "vega", "rho", "charm", "vanna", "vomma"]


def _as_positions_frame(positions: Any) -> pd.DataFrame:
    if positions is None:
        return pd.DataFrame()
    if isinstance(positions, pd.DataFrame):
        return positions.copy()
    if isinstance(positions, list):
        return pd.DataFrame(positions)
    return pd.DataFrame()


def _num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def normalize_risk_positions(positions: Any) -> pd.DataFrame:
    df = _as_positions_frame(positions)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "symbol": "",
        "option_symbol": "",
        "option_type": "",
        "type": "",
        "expiry": "",
        "strategy": "Unclassified",
        "qty": 0,
        "quantity": 0,
        "strike": 0,
        "avg_cost": 0,
        "market_value": 0,
        "unrealized_pnl": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "rho": 0,
        "charm": 0,
        "vanna": 0,
        "vomma": 0,
        "dte": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    symbol_guess = (
        df["symbol"]
        .fillna("")
        .astype(str)
        .str.extract(r"^([A-Z]{1,6})", expand=False)
        .fillna("")
    )

    df["underlying"] = (
        df["underlying"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(symbol_guess)
        .fillna("")
        .astype(str)
        .str.upper()
    )

    df["option_type"] = (
        df["option_type"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["type"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.lower()
    )

    df["qty"] = _num(df["qty"]).where(_num(df["qty"]) != 0, _num(df["quantity"]))

    for col in ["strike", "avg_cost", "market_value", "unrealized_pnl", "dte"]:
        df[col] = _num(df[col])

    for col in GREEK_COLUMNS:
        df[col] = _num(df[col])

    df["multiplier"] = df["option_type"].apply(lambda x: 1 if str(x).lower() == "stock" else 100)
    df["signed_qty"] = df["qty"]

    for greek in GREEK_COLUMNS:
        df[f"net_{greek}"] = df[greek] * df["signed_qty"] * df["multiplier"]

    df["abs_market_value"] = df["market_value"].abs()
    df["notional_proxy"] = (df["strike"].abs() * df["signed_qty"].abs() * df["multiplier"]).fillna(0)

    return df


def calculate_net_greeks(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available.", "greeks": {}}

    greeks = {}
    for greek in GREEK_COLUMNS:
        col = f"net_{greek}"
        greeks[greek] = round(float(df[col].sum()), 4) if col in df.columns else 0.0

    return {
        "available": True,
        "greeks": greeks,
        "position_count": int(len(df)),
        "market_value": round(float(df["market_value"].sum()), 2),
        "gross_notional_proxy": round(float(df["notional_proxy"].sum()), 2),
    }


def calculate_concentration_risk(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available."}

    total_abs = max(1.0, float(df["abs_market_value"].sum() or df["notional_proxy"].sum() or 1.0))

    by_underlying = (
        df.groupby("underlying", as_index=False)
        .agg(
            market_value=("market_value", "sum"),
            abs_market_value=("abs_market_value", "sum"),
            notional_proxy=("notional_proxy", "sum"),
            positions=("underlying", "size"),
        )
        .sort_values("abs_market_value", ascending=False)
        .reset_index(drop=True)
    )
    by_underlying["portfolio_share"] = (by_underlying["abs_market_value"] / total_abs * 100).round(2)

    by_expiry = (
        df.groupby("expiry", as_index=False)
        .agg(
            market_value=("market_value", "sum"),
            abs_market_value=("abs_market_value", "sum"),
            notional_proxy=("notional_proxy", "sum"),
            positions=("expiry", "size"),
        )
        .sort_values("abs_market_value", ascending=False)
        .reset_index(drop=True)
    )
    by_expiry["portfolio_share"] = (by_expiry["abs_market_value"] / total_abs * 100).round(2)

    top_underlying_share = float(by_underlying.iloc[0]["portfolio_share"]) if not by_underlying.empty else 0.0
    top_expiry_share = float(by_expiry.iloc[0]["portfolio_share"]) if not by_expiry.empty else 0.0

    score = 0
    if top_underlying_share > 50:
        score += 35
    elif top_underlying_share > 35:
        score += 25
    elif top_underlying_share > 20:
        score += 15

    if top_expiry_share > 50:
        score += 35
    elif top_expiry_share > 35:
        score += 25
    elif top_expiry_share > 20:
        score += 15

    if len(by_underlying) <= 2 and len(df) >= 3:
        score += 15

    score = min(100, score)

    if score >= 70:
        risk_level = "HIGH"
    elif score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "available": True,
        "risk_score": score,
        "risk_level": risk_level,
        "top_underlying_share": round(top_underlying_share, 2),
        "top_expiry_share": round(top_expiry_share, 2),
        "by_underlying": by_underlying,
        "by_expiry": by_expiry,
    }


def run_shock_scenarios(
    positions: Any,
    underlying_shocks: list[float] | None = None,
    vol_shocks: list[float] | None = None,
    days_forward: list[int] | None = None,
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available.", "scenarios": pd.DataFrame()}

    underlying_shocks = underlying_shocks or [-0.10, -0.05, 0.0, 0.05, 0.10]
    vol_shocks = vol_shocks or [-0.10, 0.0, 0.10]
    days_forward = days_forward or [0, 1, 5]

    rows = []
    base_value = float(df["market_value"].sum())

    net_delta = float(df["net_delta"].sum())
    net_gamma = float(df["net_gamma"].sum())
    net_vega = float(df["net_vega"].sum())
    net_theta = float(df["net_theta"].sum())

    notional = max(1.0, float(df["notional_proxy"].sum() or abs(base_value) or 1.0))

    for shock in underlying_shocks:
        for vol in vol_shocks:
            for days in days_forward:
                delta_pnl = net_delta * shock
                gamma_pnl = 0.5 * net_gamma * (shock ** 2)
                vega_pnl = net_vega * vol
                theta_pnl = net_theta * days
                total_pnl = delta_pnl + gamma_pnl + vega_pnl + theta_pnl

                rows.append({
                    "Underlying Shock": f"{shock:+.0%}",
                    "Vol Shock": f"{vol:+.0%}",
                    "Days Forward": days,
                    "Delta P&L": round(delta_pnl, 2),
                    "Gamma P&L": round(gamma_pnl, 2),
                    "Vega P&L": round(vega_pnl, 2),
                    "Theta P&L": round(theta_pnl, 2),
                    "Estimated P&L": round(total_pnl, 2),
                    "Estimated P&L % Notional": round(total_pnl / notional * 100, 2),
                })

    scenarios = pd.DataFrame(rows)

    worst = scenarios.sort_values("Estimated P&L").head(1).to_dict("records")[0] if not scenarios.empty else {}
    best = scenarios.sort_values("Estimated P&L", ascending=False).head(1).to_dict("records")[0] if not scenarios.empty else {}

    return {
        "available": True,
        "scenarios": scenarios,
        "worst_case": worst,
        "best_case": best,
        "base_market_value": round(base_value, 2),
        "gross_notional_proxy": round(notional, 2),
    }


def find_largest_risk_contributors(positions: Any, limit: int = 10) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available.", "contributors": pd.DataFrame()}

    df = df.copy()
    df["risk_contribution"] = (
        df["net_delta"].abs() * 0.25
        + df["net_gamma"].abs() * 0.25
        + df["net_vega"].abs() * 0.20
        + df["net_theta"].abs() * 0.15
        + df["abs_market_value"] * 0.15
    )

    cols = [
        "underlying",
        "option_symbol",
        "option_type",
        "expiry",
        "strike",
        "qty",
        "market_value",
        "unrealized_pnl",
        "net_delta",
        "net_gamma",
        "net_theta",
        "net_vega",
        "risk_contribution",
    ]

    contributors = (
        df.sort_values("risk_contribution", ascending=False)
        [[c for c in cols if c in df.columns]]
        .head(limit)
        .reset_index(drop=True)
    )

    return {"available": True, "contributors": contributors}


def calculate_portfolio_risk_score(
    net_greeks: dict[str, Any],
    concentration: dict[str, Any],
    scenarios: dict[str, Any],
) -> dict[str, Any]:
    score = 0.0
    drivers: list[str] = []

    greeks = net_greeks.get("greeks", {}) if net_greeks.get("available") else {}
    gross_notional = max(1.0, float(net_greeks.get("gross_notional_proxy", 1) or 1))

    delta_ratio = abs(float(greeks.get("delta", 0))) / gross_notional
    gamma_ratio = abs(float(greeks.get("gamma", 0))) / gross_notional
    vega_ratio = abs(float(greeks.get("vega", 0))) / gross_notional
    theta_ratio = abs(float(greeks.get("theta", 0))) / gross_notional

    greek_score = min(45.0, (delta_ratio * 5000) + (gamma_ratio * 8000) + (vega_ratio * 2000) + (theta_ratio * 1000))
    score += greek_score
    if greek_score > 25:
        drivers.append("Large net Greek exposure")

    if concentration.get("available"):
        conc_score = float(concentration.get("risk_score", 0)) * 0.30
        score += conc_score
        if concentration.get("risk_level") in {"MEDIUM", "HIGH"}:
            drivers.append(f"{concentration.get('risk_level')} concentration risk")

    if scenarios.get("available"):
        worst = scenarios.get("worst_case", {})
        worst_pct = abs(float(worst.get("Estimated P&L % Notional", 0) or 0))
        scenario_score = min(25.0, worst_pct * 2.5)
        score += scenario_score
        if scenario_score > 12:
            drivers.append("Adverse shock scenario sensitivity")

    score = round(max(0, min(100, score)), 2)

    if score >= 75:
        level = "HIGH"
    elif score >= 50:
        level = "MEDIUM"
    elif score >= 25:
        level = "LOW"
    else:
        level = "VERY_LOW"

    return {
        "risk_score": score,
        "risk_level": level,
        "drivers": drivers or ["No dominant risk driver detected"],
    }


def build_portfolio_risk_report(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No options positions available.", "positions": df}

    net_greeks = calculate_net_greeks(df)
    concentration = calculate_concentration_risk(df)
    scenarios = run_shock_scenarios(df)
    contributors = find_largest_risk_contributors(df)
    score = calculate_portfolio_risk_score(net_greeks, concentration, scenarios)

    return {
        "available": True,
        "positions": df,
        "net_greeks": net_greeks,
        "concentration": concentration,
        "scenarios": scenarios,
        "contributors": contributors,
        "risk_score": score,
    }


def summarize_portfolio_risk(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Portfolio risk unavailable: {report.get('reason', 'unknown reason')}"

    score = report.get("risk_score", {})
    greeks = report.get("net_greeks", {}).get("greeks", {})

    return (
        f"Portfolio risk is {score.get('risk_level')} "
        f"({score.get('risk_score')}/100). "
        f"Net delta {greeks.get('delta', 0):,.2f}, "
        f"net gamma {greeks.get('gamma', 0):,.2f}, "
        f"net theta {greeks.get('theta', 0):,.2f}, "
        f"net vega {greeks.get('vega', 0):,.2f}."
    )

def score_portfolio_risk(
    summary,
    exposure=None,
    *args,
    **kwargs
):
    """
    Backward compatibility wrapper.
    """

    if isinstance(summary, dict):
        return summary

    return {
        "available": True,
        "risk_score": 0,
        "summary": summary,
        "exposure": exposure,
    }
