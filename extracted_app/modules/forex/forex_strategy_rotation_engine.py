"""
modules/forex/forex_strategy_rotation_engine.py

Phase 20D — Strategy rotation engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexStrategyRotationEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def rotation(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "current_rotation": "factor_momentum_over_mean_reversion",
            "enabled_strategies": ["factor_momentum", "macro_factor", "trend_following"],
            "disabled_strategies": ["high_volatility_scalping"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_strategy_rotation_engine(db: Optional[Any] = None) -> ForexStrategyRotationEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexStrategyRotationEngine(db=db)
    return _ENGINE
