"""
modules/forex/forex_parameter_optimizer.py

Phase 20B — Parameter optimizer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexParameterOptimizer:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def optimize(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "recommended_parameters": {
                "min_institutional_score": 75,
                "min_conviction_score": 72,
                "max_risk_per_trade_pct": 1.0,
                "max_open_pair_positions": 5,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_parameter_optimizer(db: Optional[Any] = None) -> ForexParameterOptimizer:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexParameterOptimizer(db=db)
    return _ENGINE
