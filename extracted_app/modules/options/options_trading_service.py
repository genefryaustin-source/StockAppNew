"""
modules/options/options_trading_service.py

Canonical Options Trading Service

This is the ONLY intended entry point for options order execution --
mirrors modules.stocks.stock_trading_service.StockTradingService, adapted
for a real broker (Alpaca) instead of an in-process paper broker.

That difference matters for the whole design here: the stock paper
broker fills synchronously inside the same call that submits the order,
so StockTradingService's post-execution pipeline always runs right after
submission. Alpaca options orders often don't -- a limit order can sit
"accepted" or "new" for seconds, minutes, or longer before it fills, if
it fills at all. So "persist on every fill" has to cover two paths:

  1. submit_order() -- handles the case where the broker's response to
     submission already reports a fill (fast-filling market/marketable
     limit orders).
  2. reconcile_pending_orders() -- polls the broker for status on
     locally-open orders and catches fills that happened after
     submission returned. This must be called periodically (a UI action,
     a scheduled job, or an API endpoint) for orders that don't fill
     immediately to ever get persisted.

Both paths funnel through the same _post_execution_pipeline(), so a fill
is recorded identically regardless of which path caught it.

On any fill, the position snapshot is refreshed by re-fetching the full
current position list from the broker (not by locally re-deriving
average cost/PnL from the fill) -- Alpaca is the source of truth for the
account's actual state, and re-deriving that math locally would just be
a second, less reliable copy of accounting the broker already does
correctly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional

from modules.options.options_broker import (
    AlpacaOptionsBroker,
    OptionsOrderRequest,
    OptionsOrderResponse,
)
from modules.options.options_models import (
    save_order,
    get_open_orders,
    update_order_status,
    upsert_positions,
)
from modules.options.options_execution_event_service import (
    OptionsExecutionEventType,
    get_options_execution_event_service,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OptionsExecutionResult:
    success: bool
    status: str

    order_id: Optional[str] = None
    broker_order_id: Optional[str] = None

    option_symbol: Optional[str] = None
    side: Optional[str] = None

    qty: float = 0.0
    filled_qty: float = 0.0
    fill_price: Optional[float] = None

    executed_at: Optional[datetime] = None

    message: str = ""


class OptionsTradingService:
    """
    Canonical entry point for all options execution.

    submit_order() and reconcile_pending_orders() are the only public
    methods. Everything else is a private, ordered, best-effort side
    effect that never raises out of this class.
    """

    def __init__(self, db, *, paper: bool = True, broker=None):
        self.db = db
        self.paper = paper

        self.broker = broker if broker is not None else AlpacaOptionsBroker(paper=paper)
        self.execution_events = get_options_execution_event_service(db)

    # =====================================================
    # PUBLIC
    # =====================================================

    def submit_order(
        self,
        *,
        tenant_id: str,
        user_id: str,
        option_symbol: str,
        qty: int,
        side: str,
        position_intent: str = "buy_to_open",
        order_type: str = "limit",
        tif: str = "day",
        limit_price: Optional[float] = None,
    ) -> OptionsExecutionResult:
        """
        Canonical order submission. All callers should use this method.
        """

        try:
            self._validate_request(option_symbol=option_symbol, qty=qty, side=side)

            req = OptionsOrderRequest(
                option_symbol=option_symbol,
                qty=qty,
                side=side,
                position_intent=position_intent,
                order_type=order_type,
                tif=tif,
                limit_price=limit_price,
            )

            resp = self.broker.submit_order(req)

            if resp.status == "error" or not resp.order_id:
                return self._reject(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    req=req,
                    resp=resp,
                )

            order_id = save_order(self.db, tenant_id, user_id, req, resp)

            self._post_execution_pipeline(
                tenant_id=tenant_id,
                user_id=user_id,
                order_id=order_id,
                option_symbol=resp.symbol,
                side=resp.side,
                qty=float(resp.qty),
                filled_qty=float(resp.filled_qty or 0.0),
                fill_price=resp.fill_price,
                status=resp.status,
                broker_order_id=resp.order_id,
                event_type=self._fill_event_type(resp.filled_qty, resp.qty),
            )

            return OptionsExecutionResult(
                success=True,
                status=resp.status,
                order_id=order_id,
                broker_order_id=resp.order_id,
                option_symbol=resp.symbol,
                side=resp.side,
                qty=float(resp.qty),
                filled_qty=float(resp.filled_qty or 0.0),
                fill_price=resp.fill_price,
                executed_at=datetime.now(UTC),
                message=(
                    "Order filled."
                    if float(resp.filled_qty or 0.0) >= float(resp.qty)
                    else "Order submitted."
                ),
            )

        except Exception as exc:
            logger.exception(
                "Options order submission failed | %s | %s | %s",
                option_symbol,
                side,
                qty,
            )

            try:
                self.execution_events.record(
                    event_type=OptionsExecutionEventType.ORDER_REJECTED,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    order_id=None,
                    broker_order_id=None,
                    option_symbol=option_symbol,
                    side=side,
                    qty=float(qty or 0),
                    status="rejected",
                    metadata={"exception": str(exc)},
                )
            except Exception:
                logger.exception(
                    "Failed to record ORDER_REJECTED event | %s",
                    option_symbol,
                )

            return OptionsExecutionResult(
                success=False,
                status="rejected",
                option_symbol=option_symbol,
                side=side,
                qty=float(qty or 0),
                executed_at=datetime.now(UTC),
                message=str(exc),
            )

    def reconcile_pending_orders(self, *, tenant_id: str) -> dict:
        """
        Poll the broker for status on locally-open options orders. Any
        order whose filled_qty has increased since we last checked gets
        run through the same post-execution pipeline submit_order() uses
        -- this is how a fill that happens after submission returns
        (the common case for real limit orders) still gets persisted.

        Never raises. Returns a summary of what changed.
        """

        checked = 0
        newly_filled = 0
        errors = 0

        for row in get_open_orders(self.db, tenant_id):
            checked += 1

            try:
                broker_order_id = row.get("broker_order_id")
                if not broker_order_id:
                    continue

                broker_state = self.broker.get_order(broker_order_id)
                if not broker_state:
                    continue

                new_status = broker_state.get("status", row.get("status"))
                new_filled_qty = float(broker_state.get("filled_qty") or 0.0)
                new_fill_price = (
                    float(broker_state["filled_avg_price"])
                    if broker_state.get("filled_avg_price")
                    else None
                )

                prior_filled_qty = float(row.get("filled_qty") or 0.0)

                update_order_status(
                    db=self.db,
                    broker_order_id=broker_order_id,
                    status=new_status,
                    fill_price=new_fill_price,
                    filled_qty=new_filled_qty,
                )

                if new_filled_qty > prior_filled_qty:
                    newly_filled += 1

                    self._post_execution_pipeline(
                        tenant_id=row.get("tenant_id") or tenant_id,
                        user_id=row.get("user_id"),
                        order_id=row.get("id"),
                        option_symbol=row.get("option_symbol"),
                        side=row.get("side"),
                        qty=float(row.get("qty") or 0.0),
                        filled_qty=new_filled_qty,
                        fill_price=new_fill_price,
                        status=new_status,
                        broker_order_id=broker_order_id,
                        event_type=self._fill_event_type(
                            new_filled_qty, row.get("qty") or 0.0
                        ),
                    )

            except Exception:
                errors += 1
                logger.exception(
                    "Reconciliation failed for options order | %s",
                    row.get("broker_order_id"),
                )

        return {
            "checked": checked,
            "newly_filled": newly_filled,
            "errors": errors,
        }

    # =====================================================
    # PRIVATE
    # =====================================================

    @staticmethod
    def _validate_request(*, option_symbol: str, qty, side: str) -> None:
        if not option_symbol or not str(option_symbol).strip():
            raise ValueError("Option symbol is required.")

        if str(side).lower().strip() not in ("buy", "sell"):
            raise ValueError(f"Invalid order side: {side!r}")

        if qty is None or float(qty) <= 0:
            raise ValueError(f"Quantity must be positive: {qty!r}")

    @staticmethod
    def _fill_event_type(filled_qty, qty) -> OptionsExecutionEventType:
        filled_qty = float(filled_qty or 0.0)
        qty = float(qty or 0.0)

        if filled_qty <= 0:
            return OptionsExecutionEventType.ORDER_SUBMITTED
        if filled_qty >= qty:
            return OptionsExecutionEventType.ORDER_FILLED

        return OptionsExecutionEventType.ORDER_PARTIALLY_FILLED

    def _post_execution_pipeline(
        self,
        *,
        tenant_id: Optional[str],
        user_id: Optional[str],
        order_id: Optional[str],
        option_symbol: str,
        side: Optional[str],
        qty: float,
        filled_qty: float,
        fill_price: Optional[float],
        status: Optional[str],
        broker_order_id: Optional[str],
        event_type: OptionsExecutionEventType,
    ) -> None:
        """
        Never raises. Logs failures. Does not stop execution.
        """

        try:
            self.execution_events.record(
                event_type=event_type,
                tenant_id=tenant_id,
                user_id=user_id,
                order_id=order_id,
                broker_order_id=broker_order_id,
                option_symbol=option_symbol,
                side=side,
                qty=qty,
                filled_qty=filled_qty,
                fill_price=fill_price,
                status=status,
            )
        except Exception:
            logger.exception(
                "Execution event recording failed | order_id=%s",
                order_id,
            )

        if filled_qty > 0:
            try:
                self._sync_positions(tenant_id=tenant_id, user_id=user_id)
            except Exception:
                logger.exception(
                    "Position sync failed after fill | order_id=%s",
                    order_id,
                )

    def _sync_positions(self, *, tenant_id: Optional[str], user_id: Optional[str]) -> int:
        """
        Refresh the persisted position snapshot from the broker's current,
        authoritative account state.
        """

        if not tenant_id:
            return 0

        positions = self.broker.list_options_positions()
        return upsert_positions(self.db, tenant_id, user_id or "", positions)

    def _reject(self, *, tenant_id, user_id, req: OptionsOrderRequest, resp: OptionsOrderResponse) -> OptionsExecutionResult:
        try:
            self.execution_events.record(
                event_type=OptionsExecutionEventType.ORDER_REJECTED,
                tenant_id=tenant_id,
                user_id=user_id,
                order_id=None,
                broker_order_id=resp.order_id or None,
                option_symbol=req.option_symbol,
                side=req.side,
                qty=float(req.qty),
                status="rejected",
                metadata={"error": resp.error},
            )
        except Exception:
            logger.exception(
                "Failed to record ORDER_REJECTED event | %s",
                req.option_symbol,
            )

        return OptionsExecutionResult(
            success=False,
            status="rejected",
            option_symbol=req.option_symbol,
            side=req.side,
            qty=float(req.qty),
            executed_at=datetime.now(UTC),
            message=resp.error or "Order rejected by broker.",
        )