"""
Phase 12 — Hedge Fund Capital Engine.
Capital allocation, sleeve budgeting, capacity, and liquidity scoring.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v if v is not None else default)
    except Exception:
        return default


@dataclass
class CapitalSleeve:
    name: str
    target_pct: float
    current_pct: float
    capital: float
    risk_budget_pct: float
    utilization_pct: float
    status: str


def build_capital_plan(account: dict[str, Any] | None = None, nav: float | None = None) -> dict[str, Any]:
    account = account or {}
    portfolio_value = _num(nav, _num(account.get('portfolio_value'), _num(account.get('equity'), 100000.0)))
    buying_power = _num(account.get('buying_power'), portfolio_value * 0.35)
    cash = _num(account.get('cash'), portfolio_value * 0.15)
    sleeves = [
        CapitalSleeve('Core Equity / ETF', 0.30, 0.28, portfolio_value * 0.28, 0.20, 0.72, 'On Plan'),
        CapitalSleeve('Income Options', 0.22, 0.20, portfolio_value * 0.20, 0.18, 0.64, 'Underweight'),
        CapitalSleeve('Volatility / Event', 0.14, 0.13, portfolio_value * 0.13, 0.16, 0.58, 'On Plan'),
        CapitalSleeve('Directional Options', 0.12, 0.10, portfolio_value * 0.10, 0.14, 0.55, 'Underweight'),
        CapitalSleeve('Hedges / Protection', 0.12, 0.09, portfolio_value * 0.09, 0.20, 0.45, 'Underweight'),
        CapitalSleeve('Cash / Dry Powder', 0.10, cash / portfolio_value if portfolio_value else 0.0, cash, 0.12, 0.25, 'Available'),
    ]
    utilization = 1.0 - (cash / portfolio_value if portfolio_value else 0.0)
    return {
        'portfolio_value': portfolio_value,
        'buying_power': buying_power,
        'cash': cash,
        'capital_utilization_pct': round(utilization * 100, 1),
        'liquidity_score': round(min(100, max(0, (cash / max(portfolio_value,1)) * 300)), 1),
        'sleeves': [asdict(s) for s in sleeves],
        'recommended_cash_floor_pct': 10.0,
        'max_single_trade_risk_pct': 2.0,
        'max_strategy_sleeve_risk_pct': 18.0,
    }


def rebalance_recommendations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    recs=[]
    nav=_num(plan.get('portfolio_value'),1)
    for s in plan.get('sleeves',[]):
        diff=_num(s.get('target_pct'))-_num(s.get('current_pct'))
        if abs(diff)>=0.02:
            recs.append({
                'sleeve':s.get('name'),
                'action':'Increase' if diff>0 else 'Reduce',
                'target_change_pct':round(diff*100,1),
                'capital_change':round(diff*nav,2),
                'priority':'High' if abs(diff)>=0.05 else 'Medium',
            })
    return recs
