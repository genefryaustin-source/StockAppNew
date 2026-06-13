"""Butterfly strategy builders."""
from __future__ import annotations
from modules.options.options_spread_builder import summarize_defined_risk_strategy


def build_long_butterfly(ticker: str, spot: float, expiry: str, width: float | None = None, option_type: str = "call") -> dict:
    width = width or max(1.0, round(spot * 0.03, 0))
    mid = round(spot, 2)
    low = round(mid - width, 2)
    high = round(mid + width, 2)
    tag = "C" if option_type == "call" else "P"
    legs = [
        {"option_symbol": f"{ticker} {expiry} {tag}{low}", "side": "buy", "type": option_type, "strike": low, "expiry": expiry, "premium": max(0.2, width * 0.22), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} {tag}{mid}", "side": "sell", "type": option_type, "strike": mid, "expiry": expiry, "premium": max(0.4, width * 0.30), "qty": 2},
        {"option_symbol": f"{ticker} {expiry} {tag}{high}", "side": "buy", "type": option_type, "strike": high, "expiry": expiry, "premium": max(0.2, width * 0.12), "qty": 1},
    ]
    return {"strategy_name": "Long Butterfly", "ticker": ticker, "expiry": expiry, "legs": legs, "metrics": summarize_defined_risk_strategy({"legs": legs})}


def build_broken_wing_butterfly(ticker: str, spot: float, expiry: str, width: float | None = None, option_type: str = "put") -> dict:
    width = width or max(1.0, round(spot * 0.03, 0))
    mid = round(spot * 0.98, 2)
    low = round(mid - width * 1.5, 2)
    high = round(mid + width, 2)
    tag = "P" if option_type == "put" else "C"
    legs = [
        {"option_symbol": f"{ticker} {expiry} {tag}{low}", "side": "buy", "type": option_type, "strike": low, "expiry": expiry, "premium": max(0.1, width * 0.10), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} {tag}{mid}", "side": "sell", "type": option_type, "strike": mid, "expiry": expiry, "premium": max(0.4, width * 0.28), "qty": 2},
        {"option_symbol": f"{ticker} {expiry} {tag}{high}", "side": "buy", "type": option_type, "strike": high, "expiry": expiry, "premium": max(0.3, width * 0.20), "qty": 1},
    ]
    return {"strategy_name": "Broken Wing Butterfly", "ticker": ticker, "expiry": expiry, "legs": legs, "metrics": summarize_defined_risk_strategy({"legs": legs})}
