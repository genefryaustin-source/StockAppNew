"""
modules/forex/forex_position_limit_engine.py

Phase 18B — Position limit engine.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexPositionLimitEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def check(self, trade: Dict[str, Any], snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = snapshot or {}
        positions = snapshot.get("positions") or []
        pair = trade.get("pair")
        same_pair = [p for p in positions if isinstance(p, dict) and (p.get("pair") or p.get("symbol") or p.get("Symbol")) == pair]
        approved = len(same_pair) < 5
        return {
            "approved": approved,
            "pair": pair,
            "current_pair_positions": len(same_pair),
            "max_pair_positions": 5,
            "message": "Within position limits." if approved else "Pair position limit exceeded.",
        }


_ENGINE = None


def get_forex_position_limit_engine(db: Optional[Any] = None) -> ForexPositionLimitEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexPositionLimitEngine(db=db)
    return _ENGINE
