"""
modules/forex/forex_smart_order_router.py

Phase 14C — Smart order router.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexSmartOrderRouter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def route_plan(self, *, pair: str, side: str, units: float, urgency: str = "normal") -> Dict[str, Any]:
        algo = "TWAP" if urgency == "low" else "VWAP" if urgency == "normal" else "ICEBERG"
        from modules.forex.forex_execution_algorithms import get_forex_execution_algorithms
        plan = get_forex_execution_algorithms(db=self.db).plan(pair=pair, side=side, units=units, algo=algo, slices=5)
        plan["router_decision"] = {"urgency": urgency, "selected_algo": algo}
        return plan


_ROUTER = None


def get_forex_smart_order_router(db: Optional[Any] = None) -> ForexSmartOrderRouter:
    global _ROUTER
    if _ROUTER is None or (db is not None and _ROUTER.db is None):
        _ROUTER = ForexSmartOrderRouter(db=db)
    return _ROUTER
