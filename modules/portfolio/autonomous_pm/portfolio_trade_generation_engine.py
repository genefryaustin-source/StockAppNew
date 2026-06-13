"""Generate candidate trades from autonomous portfolio state."""
from __future__ import annotations
from typing import Any


def generate_trade_candidates(ticker: str, state: dict[str, Any], rebalance: dict[str, Any], allocation: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    heat = allocation.get("capital_heat_pct", 0)
    if heat < 30:
        candidates.append({"strategy": "Bull Put Spread", "ticker": ticker.upper(), "objective": "Income with defined risk", "approval": "Review", "size_pct": min(3.0, max(1.0, (30 - heat) / 10))})
        candidates.append({"strategy": "Covered Call / PMCC", "ticker": ticker.upper(), "objective": "Generate theta income", "approval": "Review", "size_pct": 2.0})
    if rebalance.get("rebalance_required"):
        candidates.append({"strategy": "Portfolio Hedge", "ticker": ticker.upper(), "objective": "Reduce aggregate exposure", "approval": "Priority Review", "size_pct": 1.5})
    return candidates or [{"strategy": "Hold", "ticker": ticker.upper(), "objective": "No new trade required", "approval": "None", "size_pct": 0.0}]
