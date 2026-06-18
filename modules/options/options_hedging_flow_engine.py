"""
Sprint 4 Phase 3 — Dealer Hedging Flow Engine.

Estimates whether dealer hedging pressure is likely to amplify or dampen moves.
"""
from __future__ import annotations

from typing import Any


def calculate_hedging_flow(
    dealer_positioning: dict[str, Any],
    gamma_flip: dict[str, Any],
    underlying_price: float | None = None,
) -> dict[str, Any]:
    if not dealer_positioning.get("available"):
        return {"available": False, "reason": dealer_positioning.get("reason", "Dealer positioning unavailable.")}

    gamma_regime = dealer_positioning.get("gamma_regime", "NEUTRAL_GAMMA")
    delta_bias = dealer_positioning.get("delta_bias", "DEALER_NEUTRAL_DELTA")
    flip = gamma_flip.get("gamma_flip") if gamma_flip.get("available") else None

    distance_to_flip_pct = None
    if underlying_price and flip:
        distance_to_flip_pct = round(((float(underlying_price) - float(flip)) / float(underlying_price)) * 100, 2)

    if gamma_regime == "SHORT_GAMMA":
        move_behavior = "AMPLIFY_MOVES"
        hedging_description = "Dealers may buy strength and sell weakness, increasing realized volatility."
    elif gamma_regime == "LONG_GAMMA":
        move_behavior = "DAMPEN_MOVES"
        hedging_description = "Dealers may sell strength and buy weakness, suppressing realized volatility."
    else:
        move_behavior = "NEUTRAL"
        hedging_description = "Dealer hedging behavior appears mixed or neutral."

    if delta_bias == "DEALER_SHORT_DELTA":
        directional_pressure = "BUYING_PRESSURE_ON_UP_MOVES"
    elif delta_bias == "DEALER_LONG_DELTA":
        directional_pressure = "SELLING_PRESSURE_ON_DOWN_MOVES"
    else:
        directional_pressure = "BALANCED_DIRECTIONAL_PRESSURE"

    risk_score = 50
    if move_behavior == "AMPLIFY_MOVES":
        risk_score += 25
    elif move_behavior == "DAMPEN_MOVES":
        risk_score -= 10

    if distance_to_flip_pct is not None and abs(distance_to_flip_pct) <= 2:
        risk_score += 15

    risk_score = max(0, min(100, risk_score))

    if risk_score >= 75:
        risk_level = "HIGH"
    elif risk_score >= 55:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "available": True,
        "move_behavior": move_behavior,
        "directional_pressure": directional_pressure,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "distance_to_gamma_flip_pct": distance_to_flip_pct,
        "hedging_description": hedging_description,
    }


def summarize_hedging_flow(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Hedging flow unavailable: {result.get('reason', 'unknown reason')}"
    return (
        f"Hedging behavior: {result.get('move_behavior')} with "
        f"{result.get('risk_level')} hedging risk."
    )
