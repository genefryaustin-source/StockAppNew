"""
modules/stocks/stock_trading_service.py

Canonical Stock Trading Service

This is the ONLY public entry point for stock order execution.

UI
    ->
StockTradingService
    ->
OrderService
    ->
Broker
    ->
Execution Event Service
    ->
Execution Audit
    ->
Trade Attribution
    ->
AI Trade Review
    ->
Dashboard Services

Responsibilities
----------------
- Validate the request.
- Route execution to OrderService.
- Run the post-execution pipeline (events, audit, attribution, AI review).
- Notify downstream listeners (lifecycle).
- Return a standardized ExecutionResult.

Does not generate recommendations, perform analytics, or update dashboards.
Those are downstream consumers of the data this service produces.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from types import SimpleNamespace
from typing import Any, Optional

from models.trading import PortfolioPosition
from modules.portfolio.order_service import OrderService
from modules.stocks.stock_execution_event_service import (
    get_stock_execution_event_service,
)
from modules.stocks.stock_trade_attribution_service import (
    get_stock_trade_attribution_service,
)
from modules.stocks.stock_ai_trade_review_service import (
    get_stock_ai_trade_review_service,
)
from modules.stocks.stock_execution_audit_service import (
    get_stock_execution_audit_service,
)

try:
    from modules.stocks.stock_lifecycle_service import StockLifecycleService
except ImportError:
    StockLifecycleService = None

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    status: str

    order_id: Optional[int] = None
    fill_id: Optional[int] = None
    position_id: Optional[int] = None

    broker: Optional[str] = None
    broker_order_id: Optional[str] = None

    symbol: Optional[str] = None
    side: Optional[str] = None

    quantity: Optional[float] = None
    filled_price: Optional[float] = None

    commission: float = 0.0
    slippage: float = 0.0

    executed_at: Optional[datetime] = None

    message: str = ""


class StockTradingService:
    """
    Canonical entry point for all stock execution.

    submit_order() is the only public execution method. Everything else
    in the pipeline is a private, ordered, best-effort side effect.
    """

    def __init__(self, db, *, broker=None, market_data_service=None):
        self.db = db

        self.order_service = OrderService(
            db_session=db,
            broker=broker,
            market_data_service=market_data_service,
        )

        self.lifecycle_service = (
            StockLifecycleService(db) if StockLifecycleService else None
        )

        self.execution_events = get_stock_execution_event_service(db)
        self.trade_attribution = get_stock_trade_attribution_service(db)
        self.ai_trade_review = get_stock_ai_trade_review_service(db)
        self.execution_audit = get_stock_execution_audit_service(db)

    # =====================================================
    # PUBLIC
    # =====================================================

    def submit_order(
        self,
        *,
        portfolio_id,
        user_id,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        tif: str = "day",
        limit_price=None,
        stop_price=None,
        recommendation_id: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Canonical order submission. All callers use this method.
        """

        try:
            self._validate_request(symbol=symbol, side=side, qty=qty)

            order = self.order_service.submit_order(
                portfolio_id=portfolio_id,
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type=order_type,
                tif=tif,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            self._post_execution_pipeline(order=order)
            self._notify_post_execution(
                order=order,
                recommendation_id=recommendation_id,
            )

            return ExecutionResult(
                success=True,
                status=str(order.status),
                order_id=getattr(order, "id", None),
                broker=getattr(order, "broker", None),
                broker_order_id=getattr(order, "broker_order_id", None),
                symbol=getattr(order, "symbol", symbol),
                side=getattr(order, "side", side),
                quantity=float(getattr(order, "filled_qty", qty) or qty),
                filled_price=getattr(order, "avg_fill_price", None),
                commission=float(getattr(order, "actual_commission", 0.0) or 0.0),
                slippage=float(getattr(order, "actual_slippage", 0.0) or 0.0),
                executed_at=getattr(order, "filled_at", None) or datetime.now(UTC),
                message="Order executed successfully.",
            )

        except Exception as exc:
            logger.exception(
                "Stock order submission failed | %s | %s | %s",
                symbol,
                side,
                qty,
            )

            self._record_rejected_order(
                portfolio_id=portfolio_id,
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=qty,
                recommendation_id=recommendation_id,
                error=exc,
            )

            return ExecutionResult(
                success=False,
                status="rejected",
                symbol=symbol,
                side=side,
                quantity=qty,
                executed_at=datetime.now(UTC),
                message=str(exc),
            )

    # =====================================================
    # PRIVATE
    # =====================================================

    def _validate_request(self, *, symbol: str, side: str, qty: float) -> None:
        if not symbol or not str(symbol).strip():
            raise ValueError("Symbol is required.")

        if str(side).lower().strip() not in ("buy", "sell"):
            raise ValueError(f"Invalid order side: {side!r}")

        if qty is None or float(qty) <= 0:
            raise ValueError(f"Quantity must be positive: {qty!r}")

    def _post_execution_pipeline(self, *, order: Any) -> None:
        """
        Institutional post-trade workflow.

        Execution Events -> Audit -> Trade Attribution ->
        Persist Attribution -> AI Review -> Persist AI Review

        Never raises. Logs failures. Does not stop execution.
        """

        event = None
        try:
            event = self.execution_events.order_filled(order)
        except Exception:
            logger.exception(
                "Execution event recording failed | order_id=%s",
                getattr(order, "id", None),
            )

        if event is not None:
            try:
                self.execution_audit.record_event(event)
            except Exception:
                logger.exception(
                    "Execution audit recording failed | order_id=%s",
                    getattr(order, "id", None),
                )

        position = self._load_position(order)

        attribution = None
        if position is not None:
            try:
                attribution = self.trade_attribution.analyze_trade(
                    order=order,
                    position=position,
                )
            except Exception:
                logger.exception(
                    "Trade attribution failed | order_id=%s",
                    getattr(order, "id", None),
                )

        if attribution is None:
            return

        try:
            self.trade_attribution._persist_attribution(attribution)
        except Exception:
            logger.exception(
                "Persisting trade attribution failed | order_id=%s",
                getattr(order, "id", None),
            )

        review = None
        try:
            review = self.ai_trade_review.review_trade(attribution=attribution)
        except Exception:
            logger.exception(
                "AI trade review failed | order_id=%s",
                getattr(order, "id", None),
            )

        if review is None:
            return

        try:
            self.ai_trade_review._persist_review(review)
        except Exception:
            logger.exception(
                "Persisting AI trade review failed | order_id=%s",
                getattr(order, "id", None),
            )

    def _notify_post_execution(
        self,
        *,
        order: Any,
        recommendation_id: Optional[int],
    ) -> None:
        """
        Notify downstream listeners only. Never generates execution
        events, attribution, audit, or AI review records — those
        belong exclusively to _post_execution_pipeline().

        Downstream failures must never fail the trade itself.
        """

        if self.lifecycle_service is None:
            return

        try:
            self.lifecycle_service.mark_order_filled(
                recommendation_id=recommendation_id,
                order=order,
            )
        except Exception:
            logger.exception(
                "Lifecycle notification failed | order_id=%s",
                getattr(order, "id", None),
            )

    def _load_position(self, order: Any) -> Optional[PortfolioPosition]:
        symbol = getattr(order, "symbol", None)
        if not symbol:
            return None

        if float(getattr(order, "filled_qty", 0.0) or 0.0) <= 0:
            return None

        try:
            return (
                self.db.query(PortfolioPosition)
                .filter(
                    PortfolioPosition.portfolio_id == order.portfolio_id,
                    PortfolioPosition.symbol == symbol,
                )
                .one_or_none()
            )
        except Exception:
            logger.exception(
                "Position lookup failed | order_id=%s",
                getattr(order, "id", None),
            )
            return None

    def _record_rejected_order(
        self,
        *,
        portfolio_id,
        user_id,
        symbol,
        side,
        qty,
        recommendation_id,
        error: Exception,
    ) -> None:
        try:
            failed_order = SimpleNamespace(
                id=None,
                tenant_id=None,
                portfolio_id=portfolio_id,
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=qty,
                filled_qty=None,
                avg_fill_price=None,
                status="rejected",
                broker=None,
                broker_order_id=None,
                position_id=None,
                recommendation_id=recommendation_id,
            )

            self.execution_events.order_rejected(
                failed_order,
                metadata={"exception": str(error)},
            )
        except Exception:
            logger.exception(
                "Failed to record ORDER_REJECTED event | %s",
                symbol,
            )