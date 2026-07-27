"""Ratio spread strategy builder."""
from __future__ import annotations
from typing import Any


def build_ratio_spread(ticker: str, spot: float, expiry: str, bias: str = "bullish", width: float | None = None, ratio: int = 2) -> dict[str, Any]:
    width = width or max(1.0, round(spot * 0.03, 0))
    opt_type = "call" if bias.lower() != "bearish" else "put"
    tag = "C" if opt_type == "call" else "P"
    long_strike = round(spot * (0.99 if opt_type == "call" else 1.01), 2)
    short_strike = round(long_strike + width if opt_type == "call" else long_strike - width, 2)
    legs = [
        {"option_symbol": f"{ticker} {expiry} {tag}{long_strike}", "side": "buy", "type": opt_type, "strike": long_strike, "expiry": expiry, "premium": max(0.7, width * 0.35), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} {tag}{short_strike}", "side": "sell", "type": opt_type, "strike": short_strike, "expiry": expiry, "premium": max(0.35, width * 0.20), "qty": ratio},
    ]
    credit = legs[1]["premium"] * ratio * 100 - legs[0]["premium"] * 100
    metrics = {
        "max_profit": max(0.0, width * 100 + credit),
        "max_loss": abs(credit) + width * 100,
        "net_credit": max(0.0, credit),
        "net_debit": max(0.0, -credit),
        "capital_required": abs(credit) + width * 100,
        "probability_profit": 0.58,
        "expected_value": 25.0,
        "theta": 0.10,
        "vega": -0.04,
        "gamma": 0.12,
    }
    return {"strategy_name": "Ratio Spread", "ticker": ticker, "expiry": expiry, "legs": legs, "metrics": metrics}
