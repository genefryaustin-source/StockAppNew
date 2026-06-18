"""
Sprint 5 Phase 2 — Options Portfolio Stress Testing Engine.

Extends Sprint 5 Phase 1 Portfolio Risk Engine with:
- Market crash scenarios
- Volatility shock scenarios
- Time-decay shocks
- Liquidity/slippage stress
- VaR estimates
- Portfolio survival score
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_MARKET_SCENARIOS = [
    {"name": "Mild Pullback", "underlying_shock": -0.05, "vol_shock": 0.10, "days_forward": 1, "slippage_bps": 50},
    {"name": "Correction", "underlying_shock": -0.10, "vol_shock": 0.20, "days_forward": 2, "slippage_bps": 100},
    {"name": "Crash", "underlying_shock": -0.20, "vol_shock": 0.50, "days_forward": 3, "slippage_bps": 200},
    {"name": "Severe Crash", "underlying_shock": -0.30, "vol_shock": 0.80, "days_forward": 5, "slippage_bps": 350},
    {"name": "Relief Rally", "underlying_shock": 0.08, "vol_shock": -0.15, "days_forward": 1, "slippage_bps": 75},
    {"name": "Vol Crush", "underlying_shock": 0.00, "vol_shock": -0.40, "days_forward": 1, "slippage_bps": 50},
    {"name": "Vol Expansion", "underlying_shock": 0.00, "vol_shock": 0.50, "days_forward": 1, "slippage_bps": 150},
]


def _portfolio_notional(df: pd.DataFrame) -> float:
    return max(
        1.0,
        float(df.get("notional_proxy", pd.Series(dtype=float)).sum() or 0),
        abs(float(df.get("market_value", pd.Series(dtype=float)).sum() or 0)),
    )


def _net(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())


def calculate_scenario_pnl(df: pd.DataFrame, scenario: dict[str, Any]) -> dict[str, Any]:
    shock = float(scenario.get("underlying_shock", 0) or 0)
    vol = float(scenario.get("vol_shock", 0) or 0)
    days = int(scenario.get("days_forward", 0) or 0)
    slippage_bps = float(scenario.get("slippage_bps", 0) or 0)

    net_delta = _net(df, "net_delta")
    net_gamma = _net(df, "net_gamma")
    net_vega = _net(df, "net_vega")
    net_theta = _net(df, "net_theta")
    gross_notional = _portfolio_notional(df)

    delta_pnl = net_delta * shock
    gamma_pnl = 0.5 * net_gamma * (shock ** 2)
    vega_pnl = net_vega * vol
    theta_pnl = net_theta * days
    liquidity_cost = -gross_notional * (slippage_bps / 10000.0)

    total = delta_pnl + gamma_pnl + vega_pnl + theta_pnl + liquidity_cost

    return {
        "Scenario": scenario.get("name", "Custom"),
        "Underlying Shock": f"{shock:+.0%}",
        "Vol Shock": f"{vol:+.0%}",
        "Days": days,
        "Slippage bps": slippage_bps,
        "Delta P&L": round(delta_pnl, 2),
        "Gamma P&L": round(gamma_pnl, 2),
        "Vega P&L": round(vega_pnl, 2),
        "Theta P&L": round(theta_pnl, 2),
        "Liquidity Cost": round(liquidity_cost, 2),
        "Total P&L": round(total, 2),
        "Total P&L % Notional": round(total / gross_notional * 100, 2),
    }


def run_named_stress_scenarios(
    positions: Any,
    scenarios: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available.", "scenarios": pd.DataFrame()}

    scenarios = scenarios or DEFAULT_MARKET_SCENARIOS
    rows = [calculate_scenario_pnl(df, s) for s in scenarios]
    table = pd.DataFrame(rows)

    worst = table.sort_values("Total P&L").head(1).to_dict("records")[0] if not table.empty else {}
    best = table.sort_values("Total P&L", ascending=False).head(1).to_dict("records")[0] if not table.empty else {}

    return {
        "available": True,
        "scenarios": table,
        "worst_case": worst,
        "best_case": best,
        "gross_notional_proxy": round(_portfolio_notional(df), 2),
    }


def calculate_liquidity_stress(
    positions: Any,
    spread_widening_levels: list[float] | None = None,
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available.", "liquidity": pd.DataFrame()}

    spread_widening_levels = spread_widening_levels or [1.0, 1.5, 2.0, 3.0, 5.0]
    gross_notional = _portfolio_notional(df)
    market_value = abs(float(df["market_value"].sum() or 0))
    base_exit_cost = max(gross_notional * 0.0025, market_value * 0.01)

    rows = []
    for level in spread_widening_levels:
        exit_cost = base_exit_cost * float(level)
        rows.append({
            "Spread Widening": f"{level:.1f}x",
            "Estimated Exit Cost": round(exit_cost, 2),
            "Exit Cost % Notional": round(exit_cost / gross_notional * 100, 2),
            "Stress Note": "Normal" if level <= 1.5 else "Stressed" if level <= 3 else "Severe",
        })

    table = pd.DataFrame(rows)
    worst = table.sort_values("Estimated Exit Cost", ascending=False).head(1).to_dict("records")[0]

    return {
        "available": True,
        "liquidity": table,
        "worst_exit_cost": worst,
        "base_exit_cost": round(base_exit_cost, 2),
    }


def calculate_parametric_var(
    positions: Any,
    confidence_levels: list[float] | None = None,
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No positions available.", "var": pd.DataFrame()}

    confidence_levels = confidence_levels or [0.95, 0.99]
    gross_notional = _portfolio_notional(df)

    net_delta = abs(_net(df, "net_delta"))
    net_gamma = abs(_net(df, "net_gamma"))
    net_vega = abs(_net(df, "net_vega"))
    net_theta = abs(_net(df, "net_theta"))

    # Conservative options daily volatility proxy.
    daily_sigma = 0.025
    exposure_proxy = (
        net_delta * daily_sigma
        + 0.5 * net_gamma * daily_sigma ** 2
        + net_vega * 0.10
        + net_theta * 1
    )

    rows = []
    z_map = {0.90: 1.28, 0.95: 1.65, 0.975: 1.96, 0.99: 2.33}
    for conf in confidence_levels:
        z = z_map.get(round(conf, 3), 1.65)
        var = exposure_proxy * z
        rows.append({
            "Confidence": f"{conf:.0%}",
            "1-Day VaR": round(var, 2),
            "1-Day VaR % Notional": round(var / gross_notional * 100, 2),
            "Method": "Greek-based parametric proxy",
        })

    table = pd.DataFrame(rows)

    return {
        "available": True,
        "var": table,
        "exposure_proxy": round(exposure_proxy, 2),
        "gross_notional_proxy": round(gross_notional, 2),
    }


def calculate_survival_score(
    scenarios: dict[str, Any],
    liquidity: dict[str, Any],
    var_result: dict[str, Any],
) -> dict[str, Any]:
    score = 100.0
    drivers = []

    if scenarios.get("available"):
        worst = scenarios.get("worst_case", {})
        worst_pct = abs(float(worst.get("Total P&L % Notional", 0) or 0))
        penalty = min(45, worst_pct * 2.0)
        score -= penalty
        if worst_pct >= 10:
            drivers.append("Large downside stress loss")

    if liquidity.get("available"):
        worst_liq = liquidity.get("worst_exit_cost", {})
        exit_pct = float(worst_liq.get("Exit Cost % Notional", 0) or 0)
        penalty = min(25, exit_pct * 4.0)
        score -= penalty
        if exit_pct >= 3:
            drivers.append("High stressed exit cost")

    if var_result.get("available"):
        table = var_result.get("var")
        if isinstance(table, pd.DataFrame) and not table.empty:
            max_var_pct = float(table["1-Day VaR % Notional"].max())
            penalty = min(30, max_var_pct * 3.0)
            score -= penalty
            if max_var_pct >= 5:
                drivers.append("Elevated VaR")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "STRONG"
    elif score >= 60:
        level = "ADEQUATE"
    elif score >= 40:
        level = "FRAGILE"
    else:
        level = "CRITICAL"

    return {
        "survival_score": score,
        "survival_level": level,
        "drivers": drivers or ["No severe stress driver detected"],
    }


def build_portfolio_stress_report(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No options positions available.", "positions": df}

    scenarios = run_named_stress_scenarios(df)
    liquidity = calculate_liquidity_stress(df)
    var_result = calculate_parametric_var(df)
    survival = calculate_survival_score(scenarios, liquidity, var_result)

    return {
        "available": True,
        "positions": df,
        "scenarios": scenarios,
        "liquidity": liquidity,
        "var": var_result,
        "survival": survival,
    }


def summarize_portfolio_stress(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Portfolio stress unavailable: {report.get('reason', 'unknown reason')}"

    survival = report.get("survival", {})
    worst = report.get("scenarios", {}).get("worst_case", {})

    return (
        f"Portfolio survival is {survival.get('survival_level')} "
        f"({survival.get('survival_score')}/100). "
        f"Worst named scenario: {worst.get('Scenario', '—')} "
        f"with estimated P&L {worst.get('Total P&L', '—')}."
    )
