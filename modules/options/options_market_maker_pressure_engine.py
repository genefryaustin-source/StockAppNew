"""
Sprint 4 Phase 3 — Market Maker Pressure Engine.

Combines dealer positioning, gamma flip, and hedging flow into a market-maker
pressure regime.
"""
from __future__ import annotations

from typing import Any

from modules.options.options_dealer_positioning_engine import calculate_dealer_positioning, summarize_dealer_positioning
from modules.options.options_gamma_flip_engine import calculate_gamma_flip, summarize_gamma_flip
from modules.options.options_hedging_flow_engine import calculate_hedging_flow, summarize_hedging_flow


def build_market_maker_pressure_report(
    chain_data: dict[str, Any] | None,
    expiry: str | None = None,
    underlying_price: float | None = None,
) -> dict[str, Any]:
    dealer = calculate_dealer_positioning(
        chain_data=chain_data,
        selected_expiry=expiry,
    )
    gamma_flip = calculate_gamma_flip(chain_data, expiry)
    hedging = calculate_hedging_flow(dealer, gamma_flip, underlying_price=underlying_price)

    if not dealer.get("available"):
        return {
            "available": False,
            "reason": dealer.get("reason", "Dealer positioning unavailable."),
            "dealer": dealer,
            "gamma_flip": gamma_flip,
            "hedging": hedging,
        }

    score = 50
    if dealer.get("gamma_regime") == "SHORT_GAMMA":
        score += 25
    elif dealer.get("gamma_regime") == "LONG_GAMMA":
        score -= 10

    if hedging.get("available"):
        score = (score * 0.55) + (float(hedging.get("risk_score", 50)) * 0.45)

    score = round(max(0, min(100, score)), 2)

    if score >= 75:
        regime = "HIGH_MARKET_MAKER_PRESSURE"
    elif score >= 55:
        regime = "MODERATE_MARKET_MAKER_PRESSURE"
    elif score >= 35:
        regime = "LOW_MARKET_MAKER_PRESSURE"
    else:
        regime = "SUPPRESSED_VOLATILITY_PRESSURE"

    return {
        "available": True,
        "expiry": expiry,
        "pressure_score": score,
        "pressure_regime": regime,
        "dealer": dealer,
        "gamma_flip": gamma_flip,
        "hedging": hedging,
        "summary": [
            summarize_dealer_positioning(dealer),
            summarize_gamma_flip(gamma_flip),
            summarize_hedging_flow(hedging),
        ],
    }


def summarize_market_maker_pressure(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Market maker pressure unavailable: {report.get('reason', 'unknown reason')}"
    return f"Market maker pressure is {report.get('pressure_regime')} with score {report.get('pressure_score')}/100."
