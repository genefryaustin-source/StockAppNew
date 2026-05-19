from __future__ import annotations


def execution_risk_flags(side, order_type, spread_bps, adv_ratio):
    flags = []

    if order_type == "market":
        flags.append("Market order → slippage risk")

    if spread_bps and spread_bps > 50:
        flags.append("Wide spread")

    if adv_ratio and adv_ratio > 0.1:
        flags.append("Order too large vs volume")

    return flags


def suggest_order_strategy(spread_bps: float | None, volatility_pct: float | None):
    if spread_bps is not None and spread_bps > 20:
        return "Consider using a limit order"
    if volatility_pct is not None and volatility_pct > 4:
        return "Consider smaller slices due to high volatility"
    return "Standard execution acceptable"

