"""
modules/forex/forex_learning_engine.py

Phase 20B — Continuous AI learning engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexLearningEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self) -> Dict[str, Any]:
        from modules.forex.forex_trade_feedback_engine import get_forex_trade_feedback_engine
        from modules.forex.forex_model_evaluator import get_forex_model_evaluator
        from modules.forex.forex_parameter_optimizer import get_forex_parameter_optimizer

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trade_feedback": get_forex_trade_feedback_engine(db=self.db).feedback(),
            "model_evaluation": get_forex_model_evaluator(db=self.db).evaluate(),
            "parameter_optimization": get_forex_parameter_optimizer(db=self.db).optimize(),
            "learning_mode": "paper_trade_feedback_only",
        }


_ENGINE = None


def get_forex_learning_engine(db: Optional[Any] = None) -> ForexLearningEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexLearningEngine(db=db)
    return _ENGINE
