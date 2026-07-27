"""
modules/forex/forex_risk_budget_engine.py

Phase 14B — Portfolio risk budgeting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ForexRiskBudgetEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def allocate_budget(self, ideas: List[Dict[str, Any]], total_risk_pct: float = 5.0) -> Dict[str, Any]:
        approved = [i for i in ideas if str(i.get("signal")).upper() in {"BUY", "SELL"}]
        if not approved:
            return {"status": "READY", "allocations": []}
        per = total_risk_pct / len(approved)
        rows = []
        for idea in approved:
            rows.append({
                "pair": idea.get("pair"),
                "signal": idea.get("signal"),
                "risk_budget_pct": round(per, 4),
                "capital_weight": round(per / total_risk_pct * 100, 4),
            })
        return {"status": "READY", "total_risk_pct": total_risk_pct, "allocations": rows}


_BUDGET = None


def get_forex_risk_budget_engine(db: Optional[Any] = None) -> ForexRiskBudgetEngine:
    global _BUDGET
    if _BUDGET is None or (db is not None and _BUDGET.db is None):
        _BUDGET = ForexRiskBudgetEngine(db=db)
    return _BUDGET
