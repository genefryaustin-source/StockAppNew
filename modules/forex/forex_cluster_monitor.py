"""
modules/forex/forex_cluster_monitor.py

Phase 20F — Cluster monitor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexClusterMonitor:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def monitor(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "nodes": [{"node": "local_streamlit", "status": "READY", "role": "primary"}],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_cluster_monitor(db: Optional[Any] = None) -> ForexClusterMonitor:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexClusterMonitor(db=db)
    return _ENGINE
