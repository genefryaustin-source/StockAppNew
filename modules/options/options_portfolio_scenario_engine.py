"""Scenario engine for named options portfolio regimes."""
from __future__ import annotations
from typing import Any


def build_scenario_readouts(stress_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not stress_results:
        return {"best": None, "worst": None, "summary": "No stress data available."}
    best = max(stress_results, key=lambda x: float(x.get("estimated_pnl") or 0))
    worst = min(stress_results, key=lambda x: float(x.get("estimated_pnl") or 0))
    return {
        "best": best,
        "worst": worst,
        "summary": f"Best scenario: {best['scenario']} (${best['estimated_pnl']:,.0f}); worst scenario: {worst['scenario']} (${worst['estimated_pnl']:,.0f}).",
        "volatility_event_risk": abs(float(worst.get("estimated_pnl") or 0)),
    }


def classify_portfolio_scenario_bias(stress_results: list[dict[str, Any]]) -> str:
    if not stress_results:
        return "Unknown"
    rally = sum(float(r.get("estimated_pnl") or 0) for r in stress_results if "Rally" in str(r.get("scenario")))
    selloff = sum(float(r.get("estimated_pnl") or 0) for r in stress_results if "Selloff" in str(r.get("scenario")) or "Crash" in str(r.get("scenario")))
    iv_up = sum(float(r.get("estimated_pnl") or 0) for r in stress_results if "Expansion" in str(r.get("scenario")))
    iv_down = sum(float(r.get("estimated_pnl") or 0) for r in stress_results if "Crush" in str(r.get("scenario")))
    if rally > abs(selloff) and rally > 0:
        return "Bullish Directional"
    if selloff > abs(rally) and selloff > 0:
        return "Bearish / Hedge Biased"
    if iv_up > iv_down:
        return "Long Volatility"
    if iv_down > iv_up:
        return "Short Volatility / Income"
    return "Balanced / Mixed"
