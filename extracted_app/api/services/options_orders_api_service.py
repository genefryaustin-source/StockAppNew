"""
api/services/options_orders_api_service.py

Options Orders API Service

Backs POST /api/v1/options/orders, GET /api/v1/options/orders/{id},
GET /api/v1/options/orders, POST /api/v1/options/orders/reconcile, and
GET /api/v1/options/positions.

Wraps modules.options.options_trading_service.OptionsTradingService
(create, reconcile) and modules.options.options_models (order history,
single-order lookup, positions) -- all real, tenant-scoped functions
that already existed from when OptionsTradingService was built. The
only new piece is get_order_by_id in options_models.py; everything
else here is a thin wrap plus rollback safety.

Not portfolio-scoped: unlike stocks, options_orders/options_positions
only have tenant_id, no portfolio_id column -- tenant_id (always from
the authenticated caller, never client-supplied) is the only scoping
boundary here.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class OptionsOrdersAPIService:
    """API service for options order lifecycle and positions."""

    def __init__(self, db):
        self.db = db

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_order(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        option_symbol: str,
        qty: int,
        side: str,
        position_intent: str = "buy_to_open",
        order_type: str = "limit",
        tif: str = "day",
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        """
        Submit a new options order via OptionsTradingService. Always
        returns a dict (OptionsExecutionResult as JSON) -- check its
        "success" field for whether the order actually executed, not
        the HTTP status; a rejected order (broker error, invalid
        contract, etc.) is still a normal response, since a valid
        request was processed and produced a real outcome.
        """

        _safe_rollback(self.db)

        from modules.options.options_trading_service import OptionsTradingService

        service = OptionsTradingService(self.db)

        result = service.submit_order(
            tenant_id=tenant_id,
            user_id=user_id or "",
            option_symbol=option_symbol,
            qty=qty,
            side=side,
            position_intent=position_intent,
            order_type=order_type,
            tif=tif,
            limit_price=limit_price,
        )

        return self._serialize_result(result)

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    def get_order(
        self,
        *,
        tenant_id: str,
        order_id: str,
    ) -> dict[str, Any] | None:
        """Single options order by id, scoped to tenant_id."""

        _safe_rollback(self.db)

        from modules.options.options_models import get_order_by_id

        return get_order_by_id(self.db, tenant_id, order_id)

    def get_order_history(
        self,
        *,
        tenant_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Most recent options orders for a tenant."""

        _safe_rollback(self.db)

        from modules.options.options_models import get_order_history

        orders = get_order_history(self.db, tenant_id, limit=limit)

        return {
            "tenant_id": tenant_id,
            "order_count": len(orders),
            "orders": orders,
        }

    def get_positions(
        self,
        *,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Current options positions for a tenant (persisted snapshot, refreshed on every fill)."""

        _safe_rollback(self.db)

        from modules.options.options_models import get_positions

        positions = get_positions(self.db, tenant_id)

        return {
            "tenant_id": tenant_id,
            "position_count": len(positions),
            "positions": positions,
        }

    # ---------------------------------------------------------
    # Reconcile
    # ---------------------------------------------------------

    def reconcile(
        self,
        *,
        tenant_id: str,
    ) -> dict[str, Any]:
        """
        Poll the broker for status on locally-open options orders and
        persist any fills that happened after submission returned --
        the common case for real (non-marketable) limit orders. Never
        raises; returns {"checked", "newly_filled", "errors"}.
        """

        _safe_rollback(self.db)

        from modules.options.options_trading_service import OptionsTradingService

        service = OptionsTradingService(self.db)

        return service.reconcile_pending_orders(tenant_id=tenant_id)

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    @staticmethod
    def _serialize_result(result: Any) -> dict[str, Any]:
        data = asdict(result)
        if data.get("executed_at") is not None:
            data["executed_at"] = data["executed_at"].isoformat()
        return data