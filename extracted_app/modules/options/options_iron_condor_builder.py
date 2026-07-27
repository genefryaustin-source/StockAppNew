"""Iron condor and iron butterfly builders."""
from __future__ import annotations
from typing import Any
from modules.options.options_spread_builder import summarize_defined_risk_strategy


def build_iron_condor(ticker: str, spot: float, expiry: str, width: float | None = None, short_delta_width: float | None = None) -> dict[str, Any]:
    width = width or max(1.0, round(spot * 0.025, 0))
    short_delta_width = short_delta_width or max(width, round(spot * 0.05, 0))
    sp = round(spot - short_delta_width, 2)
    lp = round(sp - width, 2)
    sc = round(spot + short_delta_width, 2)
    lc = round(sc + width, 2)
    legs = [
        {"option_symbol": f"{ticker} {expiry} P{lp}", "side": "buy", "type": "put", "strike": lp, "expiry": expiry, "premium": max(0.1, width * 0.08), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} P{sp}", "side": "sell", "type": "put", "strike": sp, "expiry": expiry, "premium": max(0.2, width * 0.22), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} C{sc}", "side": "sell", "type": "call", "strike": sc, "expiry": expiry, "premium": max(0.2, width * 0.22), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} C{lc}", "side": "buy", "type": "call", "strike": lc, "expiry": expiry, "premium": max(0.1, width * 0.08), "qty": 1},
    ]
    return {"strategy_name": "Iron Condor", "ticker": ticker, "expiry": expiry, "legs": legs, "metrics": summarize_defined_risk_strategy({"legs": legs})}


def build_iron_butterfly(ticker: str, spot: float, expiry: str, width: float | None = None) -> dict[str, Any]:
    width = width or max(1.0, round(spot * 0.03, 0))
    mid = round(spot, 2)
    lp = round(mid - width, 2)
    lc = round(mid + width, 2)
    legs = [
        {"option_symbol": f"{ticker} {expiry} P{lp}", "side": "buy", "type": "put", "strike": lp, "expiry": expiry, "premium": max(0.1, width * 0.08), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} P{mid}", "side": "sell", "type": "put", "strike": mid, "expiry": expiry, "premium": max(0.4, width * 0.30), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} C{mid}", "side": "sell", "type": "call", "strike": mid, "expiry": expiry, "premium": max(0.4, width * 0.30), "qty": 1},
        {"option_symbol": f"{ticker} {expiry} C{lc}", "side": "buy", "type": "call", "strike": lc, "expiry": expiry, "premium": max(0.1, width * 0.08), "qty": 1},
    ]
    return {"strategy_name": "Iron Butterfly", "ticker": ticker, "expiry": expiry, "legs": legs, "metrics": summarize_defined_risk_strategy({"legs": legs})}
