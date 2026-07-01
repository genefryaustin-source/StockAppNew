"""
modules/forex/forex_execution_supervisor.py

Phase 20C — Institutional execution supervisor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexExecutionSupervisor:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self) -> Dict[str, Any]:
        from modules.forex.forex_execution_quality_engine import get_forex_execution_quality_engine
        from modules.forex.forex_execution_optimizer import get_forex_execution_optimizer
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "quality": get_forex_execution_quality_engine(db=self.db).quality(),
            "optimizer": get_forex_execution_optimizer(db=self.db).recommendations(),
            "mode": "paper_execution_supervision",
        }


_ENGINE = None


def get_forex_execution_supervisor(db: Optional[Any] = None) -> ForexExecutionSupervisor:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexExecutionSupervisor(db=db)
    return _ENGINE
