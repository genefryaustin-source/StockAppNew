"""
modules/hf/equity_pm_rebalance_engine.py

Rebalance plan generator for HF-4.
"""
from __future__ import annotations
from typing import Any
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def build_rebalance_orders(portfolio_value: float, decisions: list[dict[str, Any]], prices: dict[str, float] | None = None) -> list[dict[str, Any]]:
    prices = prices or {}
    orders = []
    for d in decisions or []:
        action = d.get("action")
        if action == "Hold":
            continue
        sym = str(d.get("symbol")).upper()
        delta_weight = _num(d.get("target_weight")) - _num(d.get("current_weight"))
        dollars = portfolio_value * delta_weight
        price = _num(prices.get(sym), 100.0)
        shares = int(abs(dollars) / max(price, 0.01))
        side = "BUY" if dollars > 0 else "SELL"
        orders.append({
            "symbol": sym,
            "side": side,
            "shares": shares,
            "estimated_dollars": round(abs(dollars), 2),
            "price_assumption": price,
            "source_action": action,
            "approval_required": True,
        })
    return orders


def orders_frame(orders: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(orders or [])
