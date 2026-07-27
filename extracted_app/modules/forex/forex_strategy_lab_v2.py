"""
modules/forex/forex_strategy_lab_v2.py

Phase 14D — AI Strategy Lab v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexStrategyLabV2:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def run_lab(self, strategy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        strategy = strategy or {
            "name": "Factor Momentum FX",
            "entry": "composite_factor_score > 65",
            "exit": "factor_score < 50 or stop",
            "risk": "1% per trade",
        }
        from modules.forex.forex_strategy_backtester import get_forex_strategy_backtester
        from modules.forex.forex_walk_forward import get_forex_walk_forward
        from modules.forex.forex_monte_carlo import get_forex_monte_carlo

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy,
            "backtest": get_forex_strategy_backtester(db=self.db).backtest(strategy),
            "walk_forward": get_forex_walk_forward(db=self.db).run(strategy),
            "monte_carlo": get_forex_monte_carlo(db=self.db).simulate(strategy),
        }


_LAB = None


def get_forex_strategy_lab_v2(db: Optional[Any] = None) -> ForexStrategyLabV2:
    global _LAB
    if _LAB is None or (db is not None and _LAB.db is None):
        _LAB = ForexStrategyLabV2(db=db)
    return _LAB
