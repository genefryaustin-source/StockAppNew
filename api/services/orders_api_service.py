"""
api/services/orders_api_service.py

Orders API Service

Backs POST /api/v1/orders, GET /api/v1/orders/{id},
DELETE /api/v1/orders/{id}, POST /api/v1/orders/{id}/cancel, and
POST /api/v1/orders/{id}/replace.

Order creation wraps modules.stocks.stock_trading_service.
StockTradingService.submit_order() -- the canonical stock execution
entry point. All execution/persistence logic (events, audit,
attribution, AI review) stays there; this adapter validates tenant
ownership, coerces the authenticated user into what TradeOrder expects,
and shapes the response.

Cancel/replace are honest about a real platform limitation: the paper
broker fills every order synchronously and unconditionally
("status='filled'" is hardcoded in OrderService), so there is currently
no such thing as a pending stock order to cancel or replace. Both
methods are still built generally -- checking the order's actual
status rather than assuming -- so they start working correctly the
moment real broker order routing exists, without needing to change.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, UTC
from typing import Any

from models.trading import Portfolio, TradeOrder

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)

# TradeOrder rows in a terminal status can't be canceled or replaced --
# they've already happened. Anything not in this set is treated as
# still-open.
_TERMINAL_STATUSES = ("filled", "canceled", "cancelled", "rejected", "expired")


class OrdersAPIService:
    """
    API service for stock order lifecycle: submit, fetch, cancel,
    replace. Tenant ownership is always verified by joining through
    Portfolio, since TradeOrder itself has no tenant_id column.
    """

    def __init__(self, db):
        self.db = db

    # ======================================================
    # Create
    # ======================================================

    def create_order(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        portfolio_id: str,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        tif: str = "day",
        limit_price: float | None = None,
        stop_price: float | None = None,
        recommendation_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Submit a new order via StockTradingService. Returns the
        ExecutionResult as a dict regardless of whether the order
        succeeded or was rejected -- check the "success" field, not the
        HTTP status, for execution outcome (a rejected order is still a
        200 with success=False, matching how StockTradingService itself
        distinguishes a handled rejection from a real server error).

        Returns None if portfolio_id doesn't exist or doesn't belong to
        tenant_id -- the router turns that into a 404.
        """

        _safe_rollback(self.db)

        portfolio = (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

        if portfolio is None:
            return None

        from modules.stocks.stock_trading_service import StockTradingService

        service = StockTradingService(self.db)

        result = service.submit_order(
            portfolio_id=portfolio_id,
            user_id=self._coerce_user_id(user_id),
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            tif=tif,
            limit_price=limit_price,
            stop_price=stop_price,
            recommendation_id=recommendation_id,
        )

        return self._execution_result_to_dict(result)

    # ======================================================
    # Read
    # ======================================================

    def get_order(
        self,
        *,
        tenant_id: str,
        order_id: int,
    ) -> dict[str, Any] | None:
        """
        Single order by id, scoped to tenant_id via its portfolio.
        Returns None if not found or not owned by this tenant -- the
        router turns that into a 404.
        """

        _safe_rollback(self.db)

        order = self._load_order(tenant_id=tenant_id, order_id=order_id)

        if order is None:
            return None

        from api.serializers.order import serialize_order

        return serialize_order(order)

    # ======================================================
    # Cancel / Replace
    # ======================================================

    def cancel_order(
        self,
        *,
        tenant_id: str,
        order_id: int,
    ) -> dict[str, Any] | None:
        """
        Cancel an order if it's still in a non-terminal status. Returns
        {"cancelled": False, "reason": ...} rather than raising when the
        order is already terminal -- which, today, is every order the
        paper broker has ever produced (see module docstring).

        Returns None if the order doesn't exist or doesn't belong to
        tenant_id -- the router turns that into a 404.
        """

        _safe_rollback(self.db)

        order = self._load_order(tenant_id=tenant_id, order_id=order_id)

        if order is None:
            return None

        status = str(order.status or "").lower()

        if status in _TERMINAL_STATUSES:
            return {
                "order_id": order.id,
                "cancelled": False,
                "status": order.status,
                "reason": f"Order is already {order.status} and cannot be cancelled.",
            }

        try:
            order.status = "canceled"
            order.canceled_at = datetime.now(UTC)
            order.updated_at = datetime.now(UTC)
            self.db.commit()
        except Exception:
            logger.exception("Failed to cancel order | order_id=%s", order_id)
            _safe_rollback(self.db)
            return {
                "order_id": order.id,
                "cancelled": False,
                "status": order.status,
                "reason": "Cancellation failed due to a database error.",
            }

        return {
            "order_id": order.id,
            "cancelled": True,
            "status": order.status,
            "reason": None,
        }

    def replace_order(
        self,
        *,
        tenant_id: str,
        order_id: int,
        qty: float | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Replace (modify) an order's qty/limit_price/stop_price if it's
        still in a non-terminal status. Returns {"replaced": False,
        "reason": ...} rather than raising when the order is already
        terminal -- which, today, is every order the paper broker has
        ever produced (see module docstring).

        Returns None if the order doesn't exist or doesn't belong to
        tenant_id -- the router turns that into a 404.
        """

        _safe_rollback(self.db)

        order = self._load_order(tenant_id=tenant_id, order_id=order_id)

        if order is None:
            return None

        status = str(order.status or "").lower()

        if status in _TERMINAL_STATUSES:
            from api.serializers.order import serialize_order

            return {
                "order_id": order.id,
                "replaced": False,
                "reason": f"Order is already {order.status} and cannot be replaced.",
                "order": serialize_order(order),
            }

        try:
            if qty is not None:
                order.qty = qty
            if limit_price is not None:
                order.limit_price = limit_price
            if stop_price is not None:
                order.stop_price = stop_price
            order.updated_at = datetime.now(UTC)
            self.db.commit()
        except Exception:
            logger.exception("Failed to replace order | order_id=%s", order_id)
            _safe_rollback(self.db)
            return {
                "order_id": order.id,
                "replaced": False,
                "reason": "Replace failed due to a database error.",
                "order": None,
            }

        from api.serializers.order import serialize_order

        return {
            "order_id": order.id,
            "replaced": True,
            "reason": None,
            "order": serialize_order(order),
        }

    # ======================================================
    # Internal
    # ======================================================

    def _load_order(self, *, tenant_id: str, order_id: int) -> TradeOrder | None:
        return (
            self.db.query(TradeOrder)
            .join(Portfolio, Portfolio.id == TradeOrder.portfolio_id)
            .filter(
                TradeOrder.id == order_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

    @staticmethod
    def _coerce_user_id(user_id: str | None) -> int | None:
        """
        AuthenticatedUser.user_id is a string (it can be a dev-mode
        placeholder like "development", not always a real numeric id),
        but TradeOrder.user_id is an Integer column. Falls back to None
        (a nullable column) rather than letting a non-numeric id crash
        order creation.
        """
        if user_id is None:
            return None
        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _execution_result_to_dict(result: Any) -> dict[str, Any]:
        data = asdict(result)
        if data.get("executed_at") is not None:
            data["executed_at"] = data["executed_at"].isoformat()
        return data