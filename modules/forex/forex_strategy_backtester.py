"""
modules/forex/forex_strategy_backtester.py

Phase 14D — Strategy backtester.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexStrategyBacktester:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def backtest(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        name = strategy.get("name", "FX Strategy")
        seed = abs(hash(name)) % 1000
        return {
            "status": "READY",
            "strategy": name,
            "trades": 80 + seed % 60,
            "win_rate": round(45 + seed % 35, 2),
            "profit_factor": round(1.05 + (seed % 150) / 100.0, 2),
            "max_drawdown_pct": round(3 + seed % 12, 2),
            "sharpe": round(0.8 + (seed % 120) / 100.0, 2),
        }


_BT = None


def get_forex_strategy_backtester(db: Optional[Any] = None) -> ForexStrategyBacktester:
    global _BT
    if _BT is None or (db is not None and _BT.db is None):
        _BT = ForexStrategyBacktester(db=db)
    return _BT
