"""
modules/forex/forex_trade_gatekeeper.py

Phase 18B — Pre-trade gatekeeper.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexTradeGatekeeper:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def review(self, trade: Dict[str, Any], snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_position_limit_engine import get_forex_position_limit_engine
        from modules.forex.forex_portfolio_constraints import get_forex_portfolio_constraints

        limits = get_forex_position_limit_engine(db=self.db).check(trade, snapshot=snapshot)
        constraints = get_forex_portfolio_constraints(db=self.db).evaluate(snapshot=snapshot)

        errors = []
        warnings = []
        if not limits.get("approved"):
            errors.append(limits.get("message"))
        if not constraints.get("approved"):
            errors.extend(constraints.get("errors", []))
        warnings.extend(constraints.get("warnings", []))

        return {
            "approved": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "position_limits": limits,
            "portfolio_constraints": constraints,
        }


_ENGINE = None


def get_forex_trade_gatekeeper(db: Optional[Any] = None) -> ForexTradeGatekeeper:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeGatekeeper(db=db)
    return _ENGINE
