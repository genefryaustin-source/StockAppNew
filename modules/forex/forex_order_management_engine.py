"""
modules/forex/forex_order_management_engine.py

Order lifecycle management for the Forex subsystem.

Phase 3 delegates submission/cancellation to the terminal execution service so
orders and positions stay synchronized with ForexPortfolioEngine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text = None


class ForexOrderManagementEngine:

    def __init__(self, db=None):
        self.db = db

    def submit(self, **kwargs):
        from modules.forex.forex_terminal_execution_service import (
            get_forex_terminal_execution_service,
        )
        return get_forex_terminal_execution_service(db=self.db).submit_order(**kwargs)

    def cancel(self, broker_order_id: str) -> Dict[str, Any]:
        from modules.forex.forex_terminal_execution_service import (
            get_forex_terminal_execution_service,
        )
        return get_forex_terminal_execution_service(db=self.db).cancel_order(broker_order_id)

    def open_orders(self) -> List[Dict[str, Any]]:
        return self._orders_by_status({"open", "pending", "submitted", "new"})

    def filled_orders(self) -> List[Dict[str, Any]]:
        return self._orders_by_status({"filled", "complete", "completed", "closed"})

    def order_status(self, broker_order_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None or text is None:
            return None
        self._ensure_table()
        row = self.db.execute(
            text("""
                SELECT *
                FROM forex_trade_orders
                WHERE broker_order_id = :id
                LIMIT 1
            """),
            {"id": broker_order_id},
        ).fetchone()
        return dict(row._mapping) if row else None

    def _orders_by_status(self, statuses) -> List[Dict[str, Any]]:
        if self.db is None or text is None:
            return []
        self._ensure_table()
        rows = self.db.execute(
            text("""
                SELECT *
                FROM forex_trade_orders
                WHERE lower(status) = ANY(:statuses)
                ORDER BY COALESCE(filled_at, submitted_at, created_at) DESC
            """),
            {"statuses": list(statuses)},
        ).fetchall()
        return [dict(r._mapping) for r in rows]

    def _ensure_table(self) -> None:
        if self.db is None or text is None:
            return
        try:
            from modules.forex.forex_terminal_execution_service import (
                get_forex_terminal_execution_service,
            )
            get_forex_terminal_execution_service(db=self.db).ensure_order_tables()
        except Exception:
            pass


_ENGINE = None


def get_forex_order_management_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexOrderManagementEngine(db=db)
    return _ENGINE
