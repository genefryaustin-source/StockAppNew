"""
modules/execution/execution_pending_order_pipeline.py

Sprint 26
Institutional Execution Framework

Execution Pending Order Pipeline

Responsible for the complete lifecycle of pending orders.

LIMIT
STOP
STOP_LIMIT
TRAILING_STOP

This pipeline owns:

Pending order creation
Pending order modification
Pending order cancellation
Pending order activation
Pending order expiration
Pending order fills

Shared by:

- Forex
- Equities
- Options
- Crypto
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .execution_context import ExecutionContext
from .execution_event_recorder import ExecutionEventRecorder
from .execution_order_state_machine import ExecutionOrderState


class ExecutionPendingOrderPipeline:
    """
    Institutional Pending Order Pipeline.

    This pipeline owns every order that does not execute immediately.
    """

    def __init__(
            self,
            *,
            order_repository,
            snapshot_pipeline,
            fill_pipeline,
            recorder,
            order_state_machine,
            position_state_machine,
    ):
        self.order_repository = order_repository
        self.snapshot_pipeline = snapshot_pipeline
        self.fill_pipeline = fill_pipeline
        self.recorder = recorder
        self.order_state_machine = order_state_machine
        self.position_state_machine = position_state_machine

    # ==========================================================
    # Create Pending Order
    # ==========================================================

    def create(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        try:

            self.order_repository.insert_pending_order(
                context=context,
            )

            self.commit()

        except Exception as exc:

            return self.rollback(
                context,
                exc,
            )

        #
        # NEW_ORDER was already recorded by
        # ExecutionOrderPipeline.
        #

        context.mark_pending()

        context.message = "Pending order created."

        context.mark_completed()

        try:

            self.snapshot_pipeline.refresh(
                context
            )

        except Exception as exc:

            context.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

            context.verified = self.verify(
                context
            )

        return context

    # ==========================================================
    # Modify Pending Order
    # ==========================================================

    def modify(
        self,
        context: ExecutionContext,
        *,
        limit_price=None,
        stop_price=None,
        target_price=None,
        quantity=None,
    ) -> ExecutionContext:

        updated = self.order_repository.modify_pending_order(

            broker_order_id=context.broker_order_id,

            limit_price=limit_price,

            stop_price=stop_price,

            target_price=target_price,

            quantity=quantity,

        )

        if quantity is not None:
            context.quantity = quantity
            context.units = quantity

        if limit_price is not None:
            context.requested_price = limit_price

        if stop_price is not None:
            context.stop_price = stop_price

        if target_price is not None:
            context.target_price = target_price

        #
        # Record modification.
        #

        #
        # Transition order state
        #

        try:

            context = self.order_state_machine.transition(

                context,

                ExecutionOrderState.ACCEPTED,

            )

            #
            # Emit ORDER_MODIFIED
            #

            self.recorder.order_modified(
                context
            )

        except Exception as exc:

            context.add_warning(
                f"Order modification failed: {exc}"
            )

        try:

            self.snapshot_pipeline.refresh(
                context
            )

        except Exception as exc:

            context.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        if hasattr(context, "advance_stage"):
            context.advance_stage(
                "ORDER_MODIFIED"
            )

        context.message = "Pending order modified."
        context.mark_completed()
        context.verified = self.verify(
            context
        )
        return context

    # ==========================================================
    # Cancel
    # ==========================================================

    def cancel(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        self.order_repository.cancel_pending_order(

            broker_order_id=context.broker_order_id,

        )

        try:

            self.snapshot_pipeline.refresh(
                context
            )

        except Exception as exc:

            context.add_warning(
                f"Snapshot refresh failed: {exc}"
            )


        context.mark_cancelled()
        context.message = "Pending order cancelled."

        context.mark_completed()
        context.verified = self.verify(
            context
        )

        return context

    # ==========================================================
    # Activate
    # ==========================================================

    def activate(
        self,
        context: ExecutionContext,
        *,
        market_price: float,
    ) -> ExecutionContext:

        context.execution_price = market_price

        context.requested_price = market_price

        context.status = "ACTIVATED"

        context.message = "Pending order activated."

        #
        # Order transitions into the
        # market fill pipeline.
        #

        return self.fill_pipeline.execute_fill_only(
            context
        )

    # ==========================================================
    # Expire
    # ==========================================================

    def expire(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        self.order_repository.expire_pending_order(

            broker_order_id=context.broker_order_id,

        )

        try:

            self.snapshot_pipeline.refresh(
                context
            )

        except Exception as exc:

            context.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        context.mark_expired()

        context.message = "Pending order expired."

        context.mark_completed()
        context.verified = self.verify(
            context
        )

        return context

    # ==========================================================
    # Reject
    # ==========================================================

    def reject(
        self,
        context: ExecutionContext,
        *,
        reason: str,
    ) -> ExecutionContext:

        context.mark_rejected(reason)

        context.message = reason

        context.add_error(reason)

        context.mark_completed()

        return context

    # ==========================================================
    # Broker Fill
    # ==========================================================

    def broker_fill(
        self,
        context: ExecutionContext,
        *,
        fill_price: float,
    ) -> ExecutionContext:

        context.mark_execution(
            execution_price=fill_price,
        )

        context.requested_price = fill_price

        try:

            self.order_repository.mark_order_filled(
                broker_order_id=context.broker_order_id,
                fill_price=fill_price,
            )

            self.commit()

        except Exception as exc:

            return self.rollback(
                context,
                exc,
            )

        #
        # Continue through the
        # institutional fill pipeline.
        #

        return self.fill_pipeline.execute_fill_only(
            context
        )

    # ==========================================================
    # Refresh
    # ==========================================================

    def refresh(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        try:

            self.snapshot_pipeline.refresh(
                context
            )

        except Exception as exc:

            context.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        return context

    def verify(
            self,
            context: ExecutionContext,
    ) -> bool:

        if hasattr(
                self.snapshot_pipeline,
                "verify_execution",
        ):
            return self.snapshot_pipeline.verify_execution(
                context
            )

        if hasattr(
                self.snapshot_pipeline,
                "verify",
        ):
            return self.snapshot_pipeline.verify(
                context
            )

        return True

    # ==========================================================
    # Commit
    # ==========================================================

    def commit(self) -> None:

        if hasattr(
                self.order_repository,
                "commit",
        ):
            self.order_repository.commit()
    # ==========================================================
    # Rollback
    # ==========================================================

    def rollback(
        self,
        context: ExecutionContext,
        exc: Exception,
    ) -> ExecutionContext:

        try:
            self.order_repository.rollback()
        except Exception:
            pass

        context.status = "ERROR"

        context.add_error(str(exc))

        return context