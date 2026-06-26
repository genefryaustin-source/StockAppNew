"""
modules/forex/forex_execution_analytics.py

Phase 11 execution analytics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ForexExecutionAnalytics:
    def __init__(self, db=None):
        self.db = db

    def analyze(self, orders: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if orders is None:
            try:
                from modules.forex.forex_execution_monitor import get_forex_execution_monitor
                orders = get_forex_execution_monitor(db=self.db).blotter(limit=500).get("orders", [])
            except Exception:
                orders = []
        total = len(orders)
        filled = sum(1 for o in orders if str(o.get("status", "")).lower() == "filled")
        rejected = sum(1 for o in orders if str(o.get("status", "")).lower() in {"rejected", "error"})
        return {
            "order_count": total,
            "filled_count": filled,
            "rejected_count": rejected,
            "fill_rate": round(filled / total * 100, 2) if total else 0,
            "reject_rate": round(rejected / total * 100, 2) if total else 0,
            "avg_latency_ms": 0,
            "avg_slippage_pips": 0,
            "broker_stats": self._broker_stats(orders),
        }

    def _broker_stats(self, orders):
        stats = {}
        for o in orders:
            broker = o.get("broker") or "unknown"
            stats.setdefault(broker, {"orders": 0, "filled": 0})
            stats[broker]["orders"] += 1
            if str(o.get("status", "")).lower() == "filled":
                stats[broker]["filled"] += 1
        return stats


_ANALYTICS = None


def get_forex_execution_analytics(db=None):
    global _ANALYTICS
    if _ANALYTICS is None or (db is not None and _ANALYTICS.db is None):
        _ANALYTICS = ForexExecutionAnalytics(db=db)
    return _ANALYTICS
