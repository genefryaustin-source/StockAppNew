"""
modules/forex/forex_paper_broker.py

Paper broker adapter using Phase 4 execution service.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from modules.forex.forex_broker_base import ForexBrokerBase, ForexBrokerOrderRequest, ForexBrokerOrderResult


class ForexPaperBroker(ForexBrokerBase):
    name = "paper"
    supports_live = False

    def health(self) -> Dict[str, Any]:
        return {"broker": self.name, "status": "HEALTHY", "mode": "paper"}

    def submit_order(self, request: ForexBrokerOrderRequest) -> ForexBrokerOrderResult:
        from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service

        result = get_forex_terminal_execution_service(db=self.db).submit_order(
            pair=request.pair,
            side=request.side,
            units=request.units,
            order_type=request.order_type,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            take_profit=request.take_profit,
            account_id=request.account_id,
            portfolio_id=request.portfolio_id,
            broker="paper",
            **(request.metadata or {}),
        )

        return ForexBrokerOrderResult(
            status=result.get("status", "UNKNOWN"),
            broker="paper",
            broker_order_id=result.get("broker_order_id"),
            message=result.get("message", "Paper order processed."),
            pair=result.get("pair"),
            side=result.get("side"),
            units=result.get("units"),
            avg_fill_price=result.get("avg_fill_price"),
            filled_qty=result.get("filled_qty"),
            submitted_at=result.get("submitted_at"),
            filled_at=result.get("filled_at"),
            raw=result,
        )

    def cancel_order(self, broker_order_id: str) -> Dict[str, Any]:
        from modules.forex.forex_terminal_execution_service import get_forex_terminal_execution_service
        return get_forex_terminal_execution_service(db=self.db).cancel_order(broker_order_id)
