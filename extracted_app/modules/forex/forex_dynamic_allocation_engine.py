"""
modules/forex/forex_dynamic_allocation_engine.py

Phase 20D — Autonomous portfolio allocation engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexDynamicAllocationEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self) -> Dict[str, Any]:
        from modules.forex.forex_capital_allocator import get_forex_capital_allocator
        from modules.forex.forex_rebalancing_engine import get_forex_rebalancing_engine
        from modules.forex.forex_strategy_rotation_engine import get_forex_strategy_rotation_engine

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "capital_allocation": get_forex_capital_allocator(db=self.db).allocate(),
            "rebalancing": get_forex_rebalancing_engine(db=self.db).rebalance(),
            "strategy_rotation": get_forex_strategy_rotation_engine(db=self.db).rotation(),
        }


_ENGINE = None


def get_forex_dynamic_allocation_engine(db: Optional[Any] = None) -> ForexDynamicAllocationEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexDynamicAllocationEngine(db=db)
    return _ENGINE
