"""
modules/forex/forex_portfolio_constraints.py

Phase 18B — Portfolio constraints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexPortfolioConstraints:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def evaluate(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = snapshot or {}
        margin = snapshot.get("margin") or {}
        risk = snapshot.get("risk") or {}
        margin_util = float(margin.get("margin_utilization_pct") or 0)
        risk_score = float(risk.get("risk_score") or 75)

        errors = []
        warnings = []

        if margin_util > 80:
            errors.append("Margin utilization above 80%.")
        elif margin_util > 60:
            warnings.append("Margin utilization above 60%.")

        if risk_score < 50:
            errors.append("Risk score below 50.")
        elif risk_score < 65:
            warnings.append("Risk score below 65.")

        return {
            "approved": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "margin_utilization_pct": margin_util,
            "risk_score": risk_score,
        }


_ENGINE = None


def get_forex_portfolio_constraints(db: Optional[Any] = None) -> ForexPortfolioConstraints:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexPortfolioConstraints(db=db)
    return _ENGINE
