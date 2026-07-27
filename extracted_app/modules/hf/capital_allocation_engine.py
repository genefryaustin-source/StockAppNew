from __future__ import annotations
from typing import Any
import math

def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        if isinstance(v, float) and math.isnan(v):
            return default
        return float(v)
    except Exception:
        return default

def allocate_capital(portfolio_value: float, target_positions: list[dict[str, Any]], cash_reserve_pct: float = 0.05) -> dict[str, Any]:
    portfolio_value = max(0.0, _num(portfolio_value))
    deployable = portfolio_value * max(0.0, min(1.0, 1.0 - cash_reserve_pct))
    allocations = []
    for p in target_positions or []:
        weight = _num(p.get("target_weight"))
        dollars = deployable * weight
        allocations.append({**p, "target_dollars": round(dollars, 2), "cash_reserve_pct": cash_reserve_pct})
    return {"portfolio_value": portfolio_value, "deployable_capital": round(deployable, 2), "cash_reserve": round(portfolio_value - deployable, 2), "allocations": allocations}

def capital_efficiency_score(position: dict[str, Any]) -> float:
    alpha = _num(position.get("alpha_score"), 50)
    risk = _num(position.get("risk_score"), 50)
    weight = _num(position.get("target_weight"))
    score = alpha * 0.7 + (100 - risk) * 0.2 + min(10, weight * 100) * 0.1
    return round(max(0, min(100, score)), 2)
