"""
modules/forex/forex_service_registry.py

Phase 20F — Forex service registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexServiceRegistry:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def services(self) -> Dict[str, Any]:
        rows = [
            {"service": "terminal", "status": "READY"},
            {"service": "decision_engine", "status": "READY"},
            {"service": "data_fabric", "status": "READY"},
            {"service": "broker_router", "status": "SAFETY_LOCKED"},
            {"service": "learning_engine", "status": "READY"},
            {"service": "execution_supervisor", "status": "READY"},
        ]
        return {
            "status": "READY",
            "services": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_service_registry(db: Optional[Any] = None) -> ForexServiceRegistry:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexServiceRegistry(db=db)
    return _ENGINE
