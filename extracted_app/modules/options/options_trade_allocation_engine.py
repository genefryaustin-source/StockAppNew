"""Trade allocation engine for portfolio-aware options trades."""
from __future__ import annotations
from typing import Any


def allocate_trade_candidates(candidates: list[dict[str, Any]], capital_budget: float) -> list[dict[str, Any]]:
    if not candidates:
        return []
    remaining = float(capital_budget or 0)
    ranked = sorted(candidates, key=lambda x: float(x.get("score") or x.get("total_score") or 0), reverse=True)
    allocations = []
    for item in ranked:
        est_cost = abs(float(item.get("max_loss") or item.get("debit") or item.get("estimated_cost") or 100))
        if est_cost <= 0:
            est_cost = 100.0
        contracts = int(remaining // est_cost)
        contracts = max(0, min(contracts, int(item.get("max_contracts", 5) or 5)))
        if contracts <= 0:
            continue
        allocation = dict(item)
        allocation["recommended_contracts"] = contracts
        allocation["allocated_capital"] = contracts * est_cost
        allocations.append(allocation)
        remaining -= contracts * est_cost
        if remaining <= 0:
            break
    return allocations
