"""
modules/forex/forex_manager_dashboard.py

Phase 20E — Manager dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexManagerDashboard:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self) -> Dict[str, Any]:
        from modules.forex.forex_performance_attribution_v2 import get_forex_performance_attribution_v2
        from modules.forex.forex_benchmark_engine import get_forex_benchmark_engine
        from modules.forex.forex_strategy_scorecard import get_forex_strategy_scorecard

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "performance_attribution": get_forex_performance_attribution_v2(db=self.db).attribution(),
            "benchmark": get_forex_benchmark_engine(db=self.db).benchmark(),
            "strategy_scorecard": get_forex_strategy_scorecard(db=self.db).scorecard(),
        }


_ENGINE = None


def get_forex_manager_dashboard(db: Optional[Any] = None) -> ForexManagerDashboard:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexManagerDashboard(db=db)
    return _ENGINE
