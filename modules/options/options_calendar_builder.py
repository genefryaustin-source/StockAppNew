"""Calendar spread strategy builder."""
from __future__ import annotations
from typing import Any


def build_calendar_spread(ticker: str, spot: float, near_expiry: str, far_expiry: str, strike: float | None = None, option_type: str = "call") -> dict[str, Any]:
    strike = round(strike or spot, 2)
    tag = "C" if option_type == "call" else "P"
    legs = [
        {"option_symbol": f"{ticker} {near_expiry} {tag}{strike}", "side": "sell", "type": option_type, "strike": strike, "expiry": near_expiry, "premium": max(0.4, spot * 0.008), "qty": 1},
        {"option_symbol": f"{ticker} {far_expiry} {tag}{strike}", "side": "buy", "type": option_type, "strike": strike, "expiry": far_expiry, "premium": max(0.7, spot * 0.014), "qty": 1},
    ]
    debit = (legs[1]["premium"] - legs[0]["premium"]) * 100
    metrics = {
        "max_profit": debit * 1.8,
        "max_loss": debit,
        "net_debit": debit,
        "capital_required": debit,
        "probability_profit": 0.55,
        "expected_value": debit * 0.10,
        "theta": 0.08,
        "vega": 0.16,
        "gamma": 0.03,
    }
    return {"strategy_name": "Calendar Spread", "ticker": ticker, "expiry": f"{near_expiry} / {far_expiry}", "legs": legs, "metrics": metrics}
