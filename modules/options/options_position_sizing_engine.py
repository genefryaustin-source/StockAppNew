"""Position sizing helpers for options trading."""
from __future__ import annotations
from typing import Any


def _n(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def calculate_position_size(account_equity: float, max_risk_pct: float, max_loss_per_contract: float, heat_limit_pct: float = 0.20) -> dict[str, Any]:
    account_equity = _n(account_equity)
    max_loss = max(_n(max_loss_per_contract), 0.01)
    risk_budget = account_equity * max_risk_pct
    heat_budget = account_equity * heat_limit_pct
    contracts_by_risk = int(risk_budget // max_loss)
    contracts_by_heat = int(heat_budget // max_loss)
    recommended = max(0, min(contracts_by_risk, contracts_by_heat))
    return {
        "account_equity": account_equity,
        "max_risk_pct": max_risk_pct,
        "risk_budget": risk_budget,
        "heat_budget": heat_budget,
        "max_loss_per_contract": max_loss,
        "contracts_by_risk": contracts_by_risk,
        "contracts_by_heat": contracts_by_heat,
        "recommended_contracts": recommended,
    }


def kelly_fraction(prob_win: float, avg_win: float, avg_loss: float) -> float:
    p = max(0.0, min(1.0, _n(prob_win)))
    q = 1.0 - p
    b = _n(avg_win) / max(_n(avg_loss), 0.01)
    if b <= 0:
        return 0.0
    return max(0.0, min(0.25, (b * p - q) / b))
