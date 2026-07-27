"""
modules/options/options_trade_recommendation_engine.py

Phase 3 — Institutional options trade recommendation helper.
Produces strategy ideas from smart-money, dealer, and positioning data.
"""
from __future__ import annotations

from typing import Any


def recommend_institutional_option_setups(ticker: str, reasoning: dict[str, Any], positioning: dict[str, Any], mm: dict[str, Any], conviction: dict[str, Any]) -> list[dict[str, Any]]:
    direction = reasoning.get("direction", "Mixed")
    strike = (positioning.get("strike_magnet") or {}).get("value")
    expiry = (positioning.get("expiry_magnet") or {}).get("value")
    score = float(conviction.get("score") or 0)
    regime = mm.get("hedging_regime", "")

    setups: list[dict[str, Any]] = []
    if "Bullish" in direction:
        setups.append({
            "setup": "Bull Call Spread / Call Debit Spread",
            "bias": "Bullish",
            "strike_focus": strike,
            "expiry_focus": expiry,
            "rationale": "Aligns with bullish premium/whale positioning while defining risk.",
            "risk_note": "Avoid overpaying for IV; confirm liquidity and bid/ask spread.",
        })
        if score >= 70:
            setups.append({
                "setup": "Call Calendar Near Strike Magnet",
                "bias": "Bullish / Pin-aware",
                "strike_focus": strike,
                "expiry_focus": expiry,
                "rationale": "Uses institutional strike concentration as a potential magnet.",
                "risk_note": "Calendar spreads are sensitive to IV term structure and assignment risk.",
            })
    elif "Bearish" in direction:
        setups.append({
            "setup": "Bear Put Spread / Put Debit Spread",
            "bias": "Bearish",
            "strike_focus": strike,
            "expiry_focus": expiry,
            "rationale": "Aligns with bearish premium/hedging flow while defining max loss.",
            "risk_note": "Confirm whether put flow is directional bearish or protective hedging.",
        })
    else:
        setups.append({
            "setup": "Iron Condor / Defined-Risk Range Trade",
            "bias": "Neutral / Range",
            "strike_focus": strike,
            "expiry_focus": expiry,
            "rationale": "Mixed flow and strike concentration can support a range thesis.",
            "risk_note": "Avoid neutral premium-selling structures if dealer regime is short gamma.",
        })

    if "short-gamma" in regime.lower():
        setups.append({
            "setup": "Long Straddle / Long Strangle Watchlist",
            "bias": "Volatility Expansion",
            "strike_focus": strike,
            "expiry_focus": expiry,
            "rationale": "Short-gamma dealer regime can amplify moves after key levels break.",
            "risk_note": "Requires movement large enough to overcome premium decay.",
        })

    return setups
