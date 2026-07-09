"""
modules/execution/execution_event_recorder.py

Sprint 26
Institutional Execution Framework

Central execution event recorder.

Every execution pipeline records immutable events through this class.

Forex
Equities
Options
Crypto

all use the same recorder.
"""

from __future__ import annotations

from typing import Optional

from .execution_context import ExecutionContext
from .execution_event_engine import ExecutionEventEngine
from .execution_models import (
    AssetClass,
    ExecutionActor,
    ExecutionSource,
)


class ExecutionEventRecorder:
    """
    Institutional wrapper around ExecutionEventEngine.

    Pipelines should NEVER call ExecutionEventEngine directly.
    """

    def __init__(
        self,
        engine: ExecutionEventEngine,
        actor: ExecutionActor = ExecutionActor.SYSTEM,
        source: ExecutionSource = ExecutionSource.UI,
    ):
        self.engine = engine
        self.actor = actor
        self.source = source

    # ---------------------------------------------------------
    # Internal helper
    # ---------------------------------------------------------

    def _store(self, context: ExecutionContext, event):
        if event is not None:
            context.add_event(event)
        return event

    def _asset(self, context: ExecutionContext):
        try:
            return AssetClass(context.asset_class)
        except Exception:
            return AssetClass.FOREX

    def _price(
            self,
            context,
    ):
        return (
                context.execution_price
                or context.requested_price
        )

    def _symbol(
            self,
            context,
    ):
        return context.symbol or context.pair

    def _quantity(
            self,
            context,
    ):
        return context.units or context.quantity

    def _payload(
            self,
            context,
    ):
        return context.raw_request or {}

    # ---------------------------------------------------------
    # Order Events
    # ---------------------------------------------------------

    def new_order(self, context: ExecutionContext):

        return self._record(
            context,
            self.engine.record_new_order,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_validated(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_validated,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_pending(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_pending,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_accepted(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_accepted,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_modified(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_modified,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_cancelled(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_cancelled,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_expired(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_expired,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            quantity=self._quantity(context),
            price=context.requested_price,
            payload=self._payload(context),
        )

    def order_partially_filled(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_order_partially_filled,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )






    def order_filled(self, context: ExecutionContext):

        event = self.engine.record_order_filled(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)



    # ---------------------------------------------------------
    # Position Events
    # ---------------------------------------------------------

    def position_opened(self, context: ExecutionContext):

        return self._record(
            context,
            self.engine.record_position_opened,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )



    def position_closed(self, context: ExecutionContext):

        event = self.engine.record_position_closed(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)

    def position_modified(self, context: ExecutionContext):

        event = self.engine.record_position_modified(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)

    def position_scaled_in(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_position_scaled_in,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )

    def position_scaled_out(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_position_scaled_out,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )

    def position_partially_closed(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_position_partially_closed,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )


    def position_reversed(self, context: ExecutionContext):

        event = self.engine.record_position_reversed(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)

    # ---------------------------------------------------------
    # Risk Events
    # ---------------------------------------------------------

    def stop_loss_triggered(self, context: ExecutionContext):

        event = self.engine.record_stop_loss_triggered(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)

    def take_profit_triggered(self, context: ExecutionContext):

        event = self.engine.record_take_profit_triggered(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)

    def trailing_stop_triggered(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_trailing_stop_triggered,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )

    def margin_call(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_margin_call,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )



    def flatten_all(self, context: ExecutionContext):

        event = self.engine.record_flatten_all(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            payload={
                "reason": "Flatten All",
            },
        )

        return self._store(context, event)

    def account_synchronized(
            self,
            context: ExecutionContext,
    ):

        return self._record(
            context,
            self.engine.record_account_synchronized,
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
            payload=self._payload(context),
        )

    def _record(
            self,
            context: ExecutionContext,
            recorder,
            **kwargs,
    ):

        event = recorder(**kwargs)

        return self._store(
            context,
            event,
        )

    def position_partially_closed(
            self,
            context: ExecutionContext,
    ):
        event = self.engine.record_position_partially_closed(
            asset_class=self._asset(context),
            correlation_id=context.correlation_id,
            actor=self.actor,
            source=self.source,
            portfolio_id=context.portfolio_id,
            account_id=context.account_id,
            symbol=self._symbol(context),
            order_id=context.broker_order_id,
            position_id=context.position_id,
            quantity=self._quantity(context),
            price=self._price(context),
        )

        return self._store(context, event)