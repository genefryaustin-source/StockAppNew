"""
modules/forex/forex_trade_feedback_engine.py

Phase 20B — Trade feedback engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexTradeFeedbackEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def feedback(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "completed_trades_analyzed": 0,
            "feedback": [
                {"topic": "confidence_calibration", "message": "Awaiting completed paper trades."},
                {"topic": "stop_quality", "message": "No closed-trade sample available yet."},
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_trade_feedback_engine(db: Optional[Any] = None) -> ForexTradeFeedbackEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeFeedbackEngine(db=db)
    return _ENGINE
