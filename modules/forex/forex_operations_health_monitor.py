"""
modules/forex/forex_operations_health_monitor.py

Phase 11 operations and health monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexOperationsHealthMonitor:
    def __init__(self, db=None):
        self.db = db

    def snapshot(self) -> Dict[str, Any]:
        broker_health = []
        try:
            from modules.forex.forex_broker_router import get_forex_broker_router
            broker_health = get_forex_broker_router(db=self.db).health()
        except Exception as exc:
            broker_health = [{"status": "ERROR", "error": str(exc)}]

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": self._db_health(),
            "brokers": broker_health,
            "providers": self._provider_health(),
            "runtime": {
                "terminal": "READY",
                "execution": "READY",
                "risk": "READY",
                "ai_supervisor": "READY",
            },
        }

    def _db_health(self):
        if self.db is None:
            return {"status": "UNAVAILABLE"}
        try:
            self.db.execute("SELECT 1")
            return {"status": "HEALTHY"}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def _provider_health(self):
        try:
            from modules.forex.forex_terminal_api import get_forex_terminal_api
            return get_forex_terminal_api(db=self.db).provider_health()
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}


_MON = None


def get_forex_operations_health_monitor(db=None):
    global _MON
    if _MON is None or (db is not None and _MON.db is None):
        _MON = ForexOperationsHealthMonitor(db=db)
    return _MON
