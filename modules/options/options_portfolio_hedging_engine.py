"""
Sprint 7 Phase 1 — Portfolio Hedging Intelligence Engine.

Institutional hedging analytics for options portfolios:
- Portfolio hedge need detection
- Delta hedge requirement
- Vega hedge requirement
- Tail-risk hedge sizing
- Protective put / collar / index hedge recommendations
- Hedge effectiveness score
- Hedge candidate ranking

Consumes positions from the existing portfolio engine and normalizes through:
modules.options.options_portfolio_risk_engine.normalize_risk_positions
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_HEDGE_POLICY = {
    "target_delta_neutrality": 0.20,      # desired net-delta / notional proxy
    "max_delta_ratio": 0.35,
    "max_vega_ratio": 0.25,
    "tail_hedge_budget_pct": 0.02,
    "crash_shock": -0.15,
    "vol_spike": 0.40,
    "min_hedge_score": 60,
}


def _empty(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _notional(df: pd.DataFrame) -> float:
    return max(
        1.0,
        float(df.get("notional_proxy", pd.Series(dtype=float)).abs().sum() or 0),
        abs(float(df.get("market_value", pd.Series(dtype=float)).sum() or 0)),
    )


def calculate_hedge_need(
    positions: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_HEDGE_POLICY
    df = normalize_risk_positions(positions)

    if df.empty:
        return _empty("No positions available.")

    gross_notional = _notional(df)

    net_delta = float(_num(df.get("net_delta", pd.Series(dtype=float))).sum())
    net_gamma = float(_num(df.get("net_gamma", pd.Series(dtype=float))).sum())
    net_theta = float(_num(df.get("net_theta", pd.Series(dtype=float))).sum())
    net_vega = float(_num(df.get("net_vega", pd.Series(dtype=float))).sum())

    delta_ratio = abs(net_delta) / gross_notional
    vega_ratio = abs(net_vega) / gross_notional
    gamma_ratio = abs(net_gamma) / gross_notional

    crash_shock = float(policy.get("crash_shock", -0.15))
    vol_spike = float(policy.get("vol_spike", 0.40))

    crash_pnl = (
        net_delta * crash_shock
        + 0.5 * net_gamma * crash_shock ** 2
        + net_vega * vol_spike
        + net_theta * 3
    )

    hedge_need_score = 0.0
    drivers = []

    if delta_ratio > float(policy.get("max_delta_ratio", 0.35)):
        hedge_need_score += 35
        drivers.append("Net delta exceeds policy threshold.")
    elif delta_ratio > float(policy.get("target_delta_neutrality", 0.20)):
        hedge_need_score += 20
        drivers.append("Net delta is above target neutrality range.")

    if vega_ratio > float(policy.get("max_vega_ratio", 0.25)):
        hedge_need_score += 25
        drivers.append("Net vega exceeds policy threshold.")
    elif vega_ratio > 0.15:
        hedge_need_score += 12
        drivers.append("Vega exposure is elevated.")

    if gamma_ratio > 0.10:
        hedge_need_score += 15
        drivers.append("Gamma exposure is elevated.")

    crash_loss_pct = abs(min(0.0, crash_pnl)) / gross_notional * 100
    if crash_loss_pct > 10:
        hedge_need_score += 25
        drivers.append("Crash shock loss exceeds 10% notional.")
    elif crash_loss_pct > 5:
        hedge_need_score += 12
        drivers.append("Crash shock loss exceeds 5% notional.")

    hedge_need_score = round(min(100, hedge_need_score), 2)

    if hedge_need_score >= 75:
        level = "URGENT"
    elif hedge_need_score >= 50:
        level = "HIGH"
    elif hedge_need_score >= 25:
        level = "MODERATE"
    else:
        level = "LOW"

    return {
        "available": True,
        "gross_notional": round(gross_notional, 2),
        "net_delta": round(net_delta, 4),
        "net_gamma": round(net_gamma, 4),
        "net_theta": round(net_theta, 4),
        "net_vega": round(net_vega, 4),
        "delta_ratio": round(delta_ratio, 4),
        "vega_ratio": round(vega_ratio, 4),
        "gamma_ratio": round(gamma_ratio, 4),
        "crash_shock_pnl": round(crash_pnl, 2),
        "crash_loss_pct_notional": round(crash_loss_pct, 2),
        "hedge_need_score": hedge_need_score,
        "hedge_need_level": level,
        "drivers": drivers or ["No major hedge need detected."],
    }


def calculate_delta_hedge(positions: Any, hedge_instrument_price: float = 500.0) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    net_delta = float(_num(df.get("net_delta", pd.Series(dtype=float))).sum())

    # For ETF/share hedge, one share has delta ≈ 1.
    shares_to_hedge = int(round(-net_delta))
    notional_to_trade = shares_to_hedge * float(hedge_instrument_price)

    side = "BUY" if shares_to_hedge > 0 else "SELL" if shares_to_hedge < 0 else "NONE"

    return {
        "available": True,
        "net_delta": round(net_delta, 4),
        "hedge_instrument_price": round(float(hedge_instrument_price), 2),
        "shares_to_hedge": shares_to_hedge,
        "hedge_side": side,
        "estimated_notional": round(abs(notional_to_trade), 2),
        "description": (
            f"{side} {abs(shares_to_hedge):,} hedge shares/contracts"
            if side != "NONE"
            else "Delta is already near neutral."
        ),
    }


def calculate_vega_hedge(positions: Any, vega_per_contract: float = 25.0) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    net_vega = float(_num(df.get("net_vega", pd.Series(dtype=float))).sum())
    contracts = 0
    if vega_per_contract > 0:
        contracts = int(round(abs(net_vega) / float(vega_per_contract)))

    side = "SELL VOL" if net_vega > 0 else "BUY VOL" if net_vega < 0 else "NONE"

    return {
        "available": True,
        "net_vega": round(net_vega, 4),
        "vega_per_contract": round(float(vega_per_contract), 2),
        "contracts_to_hedge": max(0, contracts),
        "hedge_side": side,
        "description": (
            f"{side} using approximately {contracts:,} vega hedge contracts."
            if side != "NONE"
            else "Vega is already near neutral."
        ),
    }


def estimate_tail_hedge_budget(
    portfolio_value: float,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_HEDGE_POLICY
    budget_pct = float(policy.get("tail_hedge_budget_pct", 0.02))
    budget = max(0.0, float(portfolio_value) * budget_pct)

    return {
        "available": True,
        "portfolio_value": round(float(portfolio_value), 2),
        "tail_hedge_budget_pct": round(budget_pct * 100, 2),
        "tail_hedge_budget": round(budget, 2),
    }


def build_hedge_candidates(
    positions: Any,
    portfolio_value: float = 100000.0,
    hedge_instrument_price: float = 500.0,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_HEDGE_POLICY
    hedge_need = calculate_hedge_need(positions, policy)

    if not hedge_need.get("available"):
        return hedge_need

    delta_hedge = calculate_delta_hedge(positions, hedge_instrument_price)
    vega_hedge = calculate_vega_hedge(positions)
    tail_budget = estimate_tail_hedge_budget(portfolio_value, policy)

    need_score = float(hedge_need.get("hedge_need_score", 0))
    crash_loss_pct = float(hedge_need.get("crash_loss_pct_notional", 0))
    delta_ratio = float(hedge_need.get("delta_ratio", 0))
    vega_ratio = float(hedge_need.get("vega_ratio", 0))

    rows = []

    protective_score = min(100, need_score + crash_loss_pct * 2 + delta_ratio * 40)
    collar_score = min(100, need_score * 0.85 + delta_ratio * 35)
    delta_score = min(100, delta_ratio * 200 + need_score * 0.50)
    vega_score = min(100, vega_ratio * 200 + need_score * 0.35)
    cash_score = min(100, crash_loss_pct * 4)

    rows.append({
        "Hedge Type": "Protective Put",
        "Primary Risk": "Tail / Downside",
        "Recommended Use": "Crash protection when downside convexity is needed.",
        "Estimated Budget": tail_budget.get("tail_hedge_budget", 0),
        "Sizing Guidance": f"Use up to {tail_budget.get('tail_hedge_budget_pct', 0)}% of portfolio value.",
        "Hedge Score": round(protective_score, 2),
        "Complexity": "Medium",
    })

    rows.append({
        "Hedge Type": "Collar",
        "Primary Risk": "Downside with cost control",
        "Recommended Use": "Finance put protection by selling upside call premium.",
        "Estimated Budget": round(tail_budget.get("tail_hedge_budget", 0) * 0.50, 2),
        "Sizing Guidance": "Cover concentrated long exposure or high-delta sleeves.",
        "Hedge Score": round(collar_score, 2),
        "Complexity": "Medium",
    })

    rows.append({
        "Hedge Type": "Delta Hedge",
        "Primary Risk": "Directional exposure",
        "Recommended Use": delta_hedge.get("description", "Neutralize directional exposure."),
        "Estimated Budget": delta_hedge.get("estimated_notional", 0),
        "Sizing Guidance": f"{delta_hedge.get('hedge_side', 'NONE')} {abs(delta_hedge.get('shares_to_hedge', 0)):,} shares/contracts.",
        "Hedge Score": round(delta_score, 2),
        "Complexity": "Low",
    })

    rows.append({
        "Hedge Type": "Vega Hedge",
        "Primary Risk": "Volatility exposure",
        "Recommended Use": vega_hedge.get("description", "Neutralize volatility exposure."),
        "Estimated Budget": 0,
        "Sizing Guidance": f"{vega_hedge.get('hedge_side', 'NONE')} {vega_hedge.get('contracts_to_hedge', 0):,} contracts.",
        "Hedge Score": round(vega_score, 2),
        "Complexity": "High",
    })

    rows.append({
        "Hedge Type": "Cash / Exposure Reduction",
        "Primary Risk": "Portfolio drawdown",
        "Recommended Use": "Reduce gross exposure when hedges are expensive or liquidity is poor.",
        "Estimated Budget": 0,
        "Sizing Guidance": "Trim largest risk contributors first.",
        "Hedge Score": round(cash_score, 2),
        "Complexity": "Low",
    })

    table = pd.DataFrame(rows).sort_values("Hedge Score", ascending=False).reset_index(drop=True)

    return {
        "available": True,
        "hedge_candidates": table,
        "hedge_need": hedge_need,
        "delta_hedge": delta_hedge,
        "vega_hedge": vega_hedge,
        "tail_budget": tail_budget,
    }


def score_hedge_effectiveness(
    positions: Any,
    hedge_candidates: Any,
) -> dict[str, Any]:
    hedge_need = calculate_hedge_need(positions)
    candidates = hedge_candidates if isinstance(hedge_candidates, pd.DataFrame) else pd.DataFrame()

    if not hedge_need.get("available"):
        return hedge_need

    if candidates.empty:
        return _empty("No hedge candidates available.")

    top_score = float(candidates["Hedge Score"].max()) if "Hedge Score" in candidates.columns else 0.0
    need_score = float(hedge_need.get("hedge_need_score", 0))

    if need_score <= 0:
        effectiveness = 100.0
    else:
        effectiveness = min(100.0, top_score / max(1.0, need_score) * 75.0)

    if effectiveness >= 80:
        level = "STRONG"
    elif effectiveness >= 60:
        level = "ADEQUATE"
    elif effectiveness >= 40:
        level = "WEAK"
    else:
        level = "INSUFFICIENT"

    return {
        "available": True,
        "hedge_effectiveness_score": round(effectiveness, 2),
        "hedge_effectiveness_level": level,
        "top_hedge_score": round(top_score, 2),
        "hedge_need_score": round(need_score, 2),
    }


def build_portfolio_hedging_report(
    positions: Any,
    portfolio_value: float = 100000.0,
    hedge_instrument_price: float = 500.0,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No options positions available.",
            "positions": df,
        }

    candidates = build_hedge_candidates(
        positions=df,
        portfolio_value=portfolio_value,
        hedge_instrument_price=hedge_instrument_price,
        policy=policy,
    )

    if not candidates.get("available"):
        return candidates

    effectiveness = score_hedge_effectiveness(df, candidates.get("hedge_candidates"))

    return {
        "available": True,
        "positions": df,
        "hedge_need": candidates.get("hedge_need"),
        "delta_hedge": candidates.get("delta_hedge"),
        "vega_hedge": candidates.get("vega_hedge"),
        "tail_budget": candidates.get("tail_budget"),
        "hedge_candidates": candidates.get("hedge_candidates"),
        "effectiveness": effectiveness,
    }


def summarize_portfolio_hedging(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Hedging intelligence unavailable: {report.get('reason', 'unknown reason')}"

    need = report.get("hedge_need", {})
    effectiveness = report.get("effectiveness", {})
    candidates = report.get("hedge_candidates")

    top = "—"
    if isinstance(candidates, pd.DataFrame) and not candidates.empty:
        top = str(candidates.iloc[0].get("Hedge Type", "—"))

    return (
        f"Hedge need is {need.get('hedge_need_level')} "
        f"({need.get('hedge_need_score')}/100). "
        f"Top hedge candidate is {top}. "
        f"Hedge effectiveness is {effectiveness.get('hedge_effectiveness_level')} "
        f"({effectiveness.get('hedge_effectiveness_score')}/100)."
    )
