"""Spread strategy builders for Phase 5 Strategy Command Center."""
from __future__ import annotations
from typing import Any


def _num(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def _contract(symbol: str, side: str, option_type: str, strike: float, expiry: str, premium: float, qty: int = 1) -> dict[str, Any]:
    return {
        "option_symbol": symbol,
        "side": side,
        "type": option_type,
        "strike": strike,
        "expiry": expiry,
        "premium": premium,
        "qty": qty,
    }


def build_vertical_spread(ticker: str, spot: float, expiry: str, bias: str = "bullish", width: float | None = None) -> dict[str, Any]:
    width = width or max(1.0, round(spot * 0.03, 0))
    bias = bias.lower()
    if bias == "bearish":
        high = round(spot * 1.01, 2)
        low = round(high - width, 2)
        legs = [
            _contract(f"{ticker} {expiry} P{high}", "buy", "put", high, expiry, max(0.5, width * 0.42)),
            _contract(f"{ticker} {expiry} P{low}", "sell", "put", low, expiry, max(0.2, width * 0.18)),
        ]
        name = "Bear Put Spread"
    elif bias == "income_bullish":
        high = round(spot * 0.98, 2)
        low = round(high - width, 2)
        legs = [
            _contract(f"{ticker} {expiry} P{low}", "buy", "put", low, expiry, max(0.2, width * 0.12)),
            _contract(f"{ticker} {expiry} P{high}", "sell", "put", high, expiry, max(0.4, width * 0.32)),
        ]
        name = "Bull Put Spread"
    elif bias == "income_bearish":
        low = round(spot * 1.02, 2)
        high = round(low + width, 2)
        legs = [
            _contract(f"{ticker} {expiry} C{low}", "sell", "call", low, expiry, max(0.4, width * 0.32)),
            _contract(f"{ticker} {expiry} C{high}", "buy", "call", high, expiry, max(0.2, width * 0.12)),
        ]
        name = "Bear Call Spread"
    else:
        low = round(spot * 0.99, 2)
        high = round(low + width, 2)
        legs = [
            _contract(f"{ticker} {expiry} C{low}", "buy", "call", low, expiry, max(0.5, width * 0.42)),
            _contract(f"{ticker} {expiry} C{high}", "sell", "call", high, expiry, max(0.2, width * 0.18)),
        ]
        name = "Bull Call Spread"
    return {"strategy_name": name, "ticker": ticker, "expiry": expiry, "legs": legs}


def summarize_defined_risk_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    legs = list(strategy.get("legs") or [])
    credit = 0.0
    debit = 0.0
    strikes = []
    for leg in legs:
        prem = _num(leg.get("premium")) * 100 * abs(_num(leg.get("qty"), 1))
        if leg.get("side") == "sell":
            credit += prem
        else:
            debit += prem
        strikes.append(_num(leg.get("strike")))
    width = max(strikes) - min(strikes) if len(strikes) >= 2 else 0.0
    net_credit = credit - debit
    net_debit = debit - credit
    max_loss = max(0.0, width * 100 - max(0.0, net_credit)) if net_credit >= 0 else net_debit
    max_profit = max(0.0, net_credit) if net_credit >= 0 else max(0.0, width * 100 - net_debit)
    pop = 0.62 if net_credit >= 0 else 0.48
    ev = pop * max_profit - (1 - pop) * max_loss
    return {
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "net_credit": round(max(0.0, net_credit), 2),
        "net_debit": round(max(0.0, net_debit), 2),
        "capital_required": round(max_loss, 2),
        "probability_profit": pop,
        "expected_value": round(ev, 2),
        "theta": 0.12 if net_credit >= 0 else -0.05,
        "vega": -0.08 if net_credit >= 0 else 0.06,
        "gamma": 0.04,
    }
