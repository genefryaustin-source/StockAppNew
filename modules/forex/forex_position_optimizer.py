"""
modules/forex/forex_position_optimizer.py

Phase 14B — Position sizing optimizer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexPositionOptimizer:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def optimize_position(self, *, equity: float, risk_pct: float, stop_pips: float, pip_value_per_lot: float = 10.0) -> Dict[str, Any]:
        risk_dollars = equity * risk_pct / 100.0
        lots = risk_dollars / max(stop_pips * pip_value_per_lot, 1e-9)
        return {
            "equity": equity,
            "risk_pct": risk_pct,
            "risk_dollars": round(risk_dollars, 2),
            "stop_pips": stop_pips,
            "recommended_lots": round(lots, 4),
            "recommended_units": round(lots * 100000, 2),
        }


_OPT = None


def get_forex_position_optimizer(db: Optional[Any] = None) -> ForexPositionOptimizer:
    global _OPT
    if _OPT is None or (db is not None and _OPT.db is None):
        _OPT = ForexPositionOptimizer(db=db)
    return _OPT
