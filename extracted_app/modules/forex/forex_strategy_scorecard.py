"""
modules/forex/forex_strategy_scorecard.py

Phase 20E — Strategy scorecard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexStrategyScorecard:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def scorecard(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "rows": [
                {"strategy": "factor_momentum", "score": 82.5, "status": "ACTIVE"},
                {"strategy": "macro_factor", "score": 78.0, "status": "ACTIVE"},
                {"strategy": "mean_reversion", "score": 66.0, "status": "WATCH"},
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_strategy_scorecard(db: Optional[Any] = None) -> ForexStrategyScorecard:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexStrategyScorecard(db=db)
    return _ENGINE
