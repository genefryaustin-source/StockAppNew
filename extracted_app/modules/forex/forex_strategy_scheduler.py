"""
modules/forex/forex_strategy_scheduler.py

Phase 20A — Strategy scheduler.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexStrategyScheduler:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def schedule(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "cadence": "hourly_paper_research",
            "jobs": [
                {"job": "quant_research", "frequency": "hourly", "enabled": True},
                {"job": "decision_engine", "frequency": "hourly", "enabled": True},
                {"job": "risk_committee", "frequency": "hourly", "enabled": True},
                {"job": "learning_engine", "frequency": "daily", "enabled": True},
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_strategy_scheduler(db: Optional[Any] = None) -> ForexStrategyScheduler:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexStrategyScheduler(db=db)
    return _ENGINE
