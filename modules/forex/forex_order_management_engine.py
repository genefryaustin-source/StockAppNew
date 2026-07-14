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

from modules.execution.execution_service import (
    get_execution_service,
)

from modules.forex.forex_portfolio_engine import (
    get_forex_portfolio_engine,
)
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
        if self.db is None:
            return None
        return self._order_repository().get_order(broker_order_id=broker_order_id)

    def _orders_by_status(self, statuses) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        # Delegate to ExecutionOrderRepository instead of hand-rolling raw
        # SQL here: it already owns the forex_trade_orders schema, handles
        # Postgres vs SQLite differences, and is the single source of truth
        # every other part of the execution pipeline writes through.
        return self._order_repository().list_orders(statuses=list(statuses))

    def _order_repository(self):
        from modules.execution.execution_order_repository import (
            ExecutionOrderRepository,
        )
        return ExecutionOrderRepository(self.db)

    def _ensure_execution_tables(self) -> None:

        if self.db is None or text is None:
            return

        try:

            portfolio_engine = get_forex_portfolio_engine(
                db=self.db,
            )

            execution = get_execution_service(
                db=self.db,
                portfolio_engine=portfolio_engine,
            )

            execution.ensure_order_tables()

        except Exception:
            pass


_ENGINE = None


def get_forex_order_management_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexOrderManagementEngine(db=db)
    return _ENGINE
