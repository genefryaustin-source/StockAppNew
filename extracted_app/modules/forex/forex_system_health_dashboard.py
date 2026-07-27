"""
modules/forex/forex_system_health_dashboard.py

Phase 20F — System health dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexSystemHealthDashboard:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self) -> Dict[str, Any]:
        from modules.forex.forex_operations_health_monitor import get_forex_operations_health_monitor
        return {
            "status": "READY",
            "operations": get_forex_operations_health_monitor(db=self.db).snapshot(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_system_health_dashboard(db: Optional[Any] = None) -> ForexSystemHealthDashboard:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexSystemHealthDashboard(db=db)
    return _ENGINE
