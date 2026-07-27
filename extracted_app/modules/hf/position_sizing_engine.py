from __future__ import annotations
from typing import Any

def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default

def kelly_fraction(win_probability: float, win_loss_ratio: float, max_fraction: float = 0.10) -> float:
    p = max(0.0, min(1.0, _num(win_probability)))
    b = max(0.01, _num(win_loss_ratio, 1.0))
    q = 1.0 - p
    k = (b * p - q) / b
    return round(max(0.0, min(max_fraction, k)), 4)

def risk_based_position_size(portfolio_value: float, entry_price: float, stop_price: float, risk_budget_pct: float = 0.01) -> dict[str, Any]:
    pv = max(0.0, _num(portfolio_value))
    entry = max(0.01, _num(entry_price))
    stop = max(0.01, _num(stop_price))
    risk_per_share = abs(entry - stop)
    budget = pv * max(0.0, _num(risk_budget_pct))
    shares = int(budget / risk_per_share) if risk_per_share > 0 else 0
    dollars = shares * entry
    return {"risk_budget_dollars": round(budget, 2), "risk_per_share": round(risk_per_share, 2), "shares": shares, "position_dollars": round(dollars, 2), "position_weight": round(dollars / pv, 4) if pv else 0.0}
