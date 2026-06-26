"""
modules/forex/forex_execution_monitor.py

Phase 5 — Live Execution Monitor.

Provides a Bloomberg-style execution blotter sourced from forex_trade_orders.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text = None


class ForexExecutionMonitor:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def blotter(self, limit: int = 250, status: Optional[str] = None) -> Dict[str, Any]:
        rows = self._load_orders(limit=limit, status=status)
        return {
            "status": "READY",
            "count": len(rows),
            "orders": rows,
            "summary": self._summary(rows),
        }

    def _load_orders(self, limit: int, status: Optional[str]) -> List[Dict[str, Any]]:
        if self.db is None or text is None:
            return []

        try:
            where = ""
            params = {"limit": int(limit)}
            if status:
                where = "WHERE lower(status) = :status"
                params["status"] = str(status).lower()

            rows = self.db.execute(
                text(f"""
                    SELECT *
                    FROM forex_trade_orders
                    {where}
                    ORDER BY COALESCE(filled_at, submitted_at, created_at) DESC
                    LIMIT :limit
                """),
                params,
            ).fetchall()
            return [dict(r._mapping) for r in rows]
        except Exception:
            return []

    def _summary(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        total_units = 0.0
        total_filled = 0.0
        for row in rows:
            status = str(row.get("status") or "unknown").lower()
            status_counts[status] = status_counts.get(status, 0) + 1
            total_units += float(row.get("units") or row.get("quantity") or 0)
            total_filled += float(row.get("filled_qty") or 0)
        return {
            "status_counts": status_counts,
            "total_units": total_units,
            "total_filled": total_filled,
            "fill_rate": (total_filled / total_units * 100.0) if total_units else 0.0,
        }


_MONITOR = None


def get_forex_execution_monitor(db: Optional[Any] = None) -> ForexExecutionMonitor:
    global _MONITOR
    if _MONITOR is None or (db is not None and _MONITOR.db is None):
        _MONITOR = ForexExecutionMonitor(db=db)
    return _MONITOR
