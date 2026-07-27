"""
modules/forex/forex_strategy_allocator.py

Phase 20A — Strategy capital allocator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexStrategyAllocator:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def allocate(self, strategies: List[str], capital: float = 100000.0) -> Dict[str, Any]:
        if not strategies:
            return {"status": "READY", "allocations": []}
        weight = 1.0 / len(strategies)
        rows = [
            {
                "strategy": strategy,
                "weight": round(weight, 4),
                "capital": round(capital * weight, 2),
                "risk_budget_pct": round(5.0 * weight, 4),
            }
            for strategy in strategies
        ]
        return {
            "status": "READY",
            "capital": capital,
            "allocations": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_strategy_allocator(db: Optional[Any] = None) -> ForexStrategyAllocator:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexStrategyAllocator(db=db)
    return _ENGINE
