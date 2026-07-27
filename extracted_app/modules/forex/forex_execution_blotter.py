"""
modules/forex/forex_execution_blotter.py

Bloomberg-style execution blotter wrapper.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ForexExecutionBlotter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def blotter(self, limit: int = 250, **kwargs) -> Dict[str, Any]:
        try:
            from modules.forex.forex_execution_monitor import get_forex_execution_monitor
            return get_forex_execution_monitor(db=self.db).blotter(limit=limit, status=kwargs.get("status"))
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc), "orders": [], "summary": {}}


_BLOTTER = None


def get_forex_execution_blotter(db: Optional[Any] = None) -> ForexExecutionBlotter:
    global _BLOTTER
    if _BLOTTER is None or (db is not None and _BLOTTER.db is None):
        _BLOTTER = ForexExecutionBlotter(db=db)
    return _BLOTTER
