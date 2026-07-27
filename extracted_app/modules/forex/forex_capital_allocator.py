"""
modules/forex/forex_capital_allocator.py

Phase 20D — Capital allocator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexCapitalAllocator:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def allocate(self, capital: float = 100000.0) -> Dict[str, Any]:
        return {
            "status": "READY",
            "capital": capital,
            "allocations": [
                {"bucket": "trend_following", "weight": 0.35, "capital": round(capital * 0.35, 2)},
                {"bucket": "mean_reversion", "weight": 0.20, "capital": round(capital * 0.20, 2)},
                {"bucket": "macro_factor", "weight": 0.30, "capital": round(capital * 0.30, 2)},
                {"bucket": "cash_reserve", "weight": 0.15, "capital": round(capital * 0.15, 2)},
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_capital_allocator(db: Optional[Any] = None) -> ForexCapitalAllocator:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexCapitalAllocator(db=db)
    return _ENGINE
