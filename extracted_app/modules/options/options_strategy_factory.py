"""
Sprint 4 Phase 5 — Institutional Strategy Factory.

Transforms option opportunities into structured trade templates.
"""
from __future__ import annotations

from typing import Any


def build_strategy_template(candidate: dict[str, Any]) -> dict[str, Any]:
    strategy = str(candidate.get("strategy") or "Watchlist")
    direction = str(candidate.get("direction") or "NEUTRAL")
    strike = candidate.get("primary_strike")
    expiry = candidate.get("expiry")
    opt_type = candidate.get("option_type")

    legs: list[dict[str, Any]] = []

    if strategy == "Bull Call Spread":
        legs = [
            {"side": "buy", "type": "call", "strike": strike, "expiry": expiry, "qty": 1},
            {"side": "sell", "type": "call", "strike": None, "expiry": expiry, "qty": 1, "note": "Select higher strike"},
        ]
        risk_profile = "DEFINED_RISK_BULLISH"

    elif strategy == "Bear Put Spread":
        legs = [
            {"side": "buy", "type": "put", "strike": strike, "expiry": expiry, "qty": 1},
            {"side": "sell", "type": "put", "strike": None, "expiry": expiry, "qty": 1, "note": "Select lower strike"},
        ]
        risk_profile = "DEFINED_RISK_BEARISH"

    elif strategy == "Iron Condor":
        legs = [
            {"side": "sell", "type": "put", "strike": None, "expiry": expiry, "qty": 1, "note": "Short put wing"},
            {"side": "buy", "type": "put", "strike": None, "expiry": expiry, "qty": 1, "note": "Long put hedge"},
            {"side": "sell", "type": "call", "strike": None, "expiry": expiry, "qty": 1, "note": "Short call wing"},
            {"side": "buy", "type": "call", "strike": None, "expiry": expiry, "qty": 1, "note": "Long call hedge"},
        ]
        risk_profile = "DEFINED_RISK_NEUTRAL_PREMIUM"

    elif strategy == "Calendar Spread":
        legs = [
            {"side": "sell", "type": opt_type or "call", "strike": strike, "expiry": expiry, "qty": 1, "note": "Front month"},
            {"side": "buy", "type": opt_type or "call", "strike": strike, "expiry": None, "qty": 1, "note": "Back month"},
        ]
        risk_profile = "TERM_STRUCTURE"

    elif strategy == "Short Premium Basket":
        legs = [{"side": "sell", "type": "multi-leg", "strike": None, "expiry": expiry, "qty": 1}]
        risk_profile = "PREMIUM_SELLING"

    elif strategy == "Long Volatility Basket":
        legs = [{"side": "buy", "type": "multi-leg", "strike": None, "expiry": expiry, "qty": 1}]
        risk_profile = "LONG_VOLATILITY"

    else:
        legs = [{"side": "watch", "type": opt_type or "option", "strike": strike, "expiry": expiry, "qty": 0}]
        risk_profile = "WATCHLIST"

    return {
        "ticker": candidate.get("ticker"),
        "strategy": strategy,
        "direction": direction,
        "risk_profile": risk_profile,
        "expiry": expiry,
        "primary_strike": strike,
        "reference_contract": candidate.get("reference_contract"),
        "legs": legs,
        "rationale": candidate.get("rationale", ""),
    }


def build_strategy_templates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_strategy_template(c) for c in candidates or []]
