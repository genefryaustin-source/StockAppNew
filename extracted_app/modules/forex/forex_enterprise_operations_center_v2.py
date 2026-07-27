"""
modules/forex/forex_enterprise_operations_center_v2.py

Phase 20F — Enterprise operations center v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexEnterpriseOperationsCenterV2:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self) -> Dict[str, Any]:
        from modules.forex.forex_system_health_dashboard import get_forex_system_health_dashboard
        from modules.forex.forex_cluster_monitor import get_forex_cluster_monitor
        from modules.forex.forex_service_registry import get_forex_service_registry

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system_health": get_forex_system_health_dashboard(db=self.db).dashboard(),
            "cluster": get_forex_cluster_monitor(db=self.db).monitor(),
            "service_registry": get_forex_service_registry(db=self.db).services(),
        }


_ENGINE = None


def get_forex_enterprise_operations_center_v2(db: Optional[Any] = None) -> ForexEnterpriseOperationsCenterV2:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexEnterpriseOperationsCenterV2(db=db)
    return _ENGINE
