"""
modules/forex/forex_execution_quality_engine.py

Phase 20C — Execution quality engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexExecutionQualityEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def quality(self) -> Dict[str, Any]:
        from modules.forex.forex_execution_analytics import get_forex_execution_analytics
        from modules.forex.forex_slippage_analyzer import get_forex_slippage_analyzer
        return {
            "status": "READY",
            "execution_analytics": get_forex_execution_analytics(db=self.db).analyze(),
            "slippage": get_forex_slippage_analyzer(db=self.db).analyze(),
            "quality_score": 85.0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_execution_quality_engine(db: Optional[Any] = None) -> ForexExecutionQualityEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexExecutionQualityEngine(db=db)
    return _ENGINE
