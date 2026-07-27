"""Diagonal spread strategy builder."""
from __future__ import annotations
from typing import Any


def build_diagonal_spread(ticker: str, spot: float, near_expiry: str, far_expiry: str, bias: str = "bullish", width: float | None = None) -> dict[str, Any]:
    width = width or max(1.0, round(spot * 0.04, 0))
    opt_type = "call" if bias.lower() != "bearish" else "put"
    tag = "C" if opt_type == "call" else "P"
    long_strike = round(spot * (0.97 if opt_type == "call" else 1.03), 2)
    short_strike = round(long_strike + width if opt_type == "call" else long_strike - width, 2)
    legs = [
        {"option_symbol": f"{ticker} {far_expiry} {tag}{long_strike}", "side": "buy", "type": opt_type, "strike": long_strike, "expiry": far_expiry, "premium": max(1.0, spot * 0.025), "qty": 1},
        {"option_symbol": f"{ticker} {near_expiry} {tag}{short_strike}", "side": "sell", "type": opt_type, "strike": short_strike, "expiry": near_expiry, "premium": max(0.4, spot * 0.010), "qty": 1},
    ]
    debit = (legs[0]["premium"] - legs[1]["premium"]) * 100
    metrics = {
        "max_profit": debit * 2.2,
        "max_loss": debit,
        "net_debit": debit,
        "capital_required": debit,
        "probability_profit": 0.52,
        "expected_value": debit * 0.12,
        "theta": 0.04,
        "vega": 0.18,
        "gamma": 0.05,
    }
    return {"strategy_name": "Diagonal Spread", "ticker": ticker, "expiry": f"{near_expiry} / {far_expiry}", "legs": legs, "metrics": metrics}
