"""
modules/options/options_market_maker_intelligence.py

Phase 3 — Market maker/dealer intelligence interpretation layer.
"""
from __future__ import annotations

from typing import Any


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def interpret_market_maker_positioning(ticker: str, dealer_report: dict[str, Any] | None, positioning: dict[str, Any]) -> dict[str, Any]:
    dealer_report = dealer_report or {}
    summary = dealer_report.get("dealer_summary") or dealer_report
    net_gex = _num(summary.get("net_gex"), 0)
    zero_gamma = summary.get("zero_gamma")
    gamma_wall = summary.get("largest_gamma_wall") or summary.get("gamma_wall")
    strike_magnet = (positioning.get("strike_magnet") or {}).get("value")

    if net_gex > 0:
        hedging = "Stabilizing / long-gamma dealer environment"
        pressure = "Dealers may dampen intraday moves near large strikes."
    elif net_gex < 0:
        hedging = "Destabilizing / short-gamma dealer environment"
        pressure = "Dealers may chase moves and amplify volatility."
    else:
        hedging = "Neutral dealer exposure"
        pressure = "Dealer hedging pressure is unclear."

    watch_levels = []
    for level in [zero_gamma, gamma_wall, strike_magnet]:
        if level is not None and level not in watch_levels:
            watch_levels.append(level)

    return {
        "ticker": ticker.upper(),
        "hedging_regime": hedging,
        "hedging_pressure": pressure,
        "zero_gamma": zero_gamma,
        "gamma_wall": gamma_wall,
        "strike_magnet": strike_magnet,
        "watch_levels": watch_levels,
        "summary": f"{hedging}. Watch levels: {', '.join(map(str, watch_levels)) if watch_levels else 'N/A'}.",
    }
