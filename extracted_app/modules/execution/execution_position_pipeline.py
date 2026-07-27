"""
modules/execution/execution_position_pipeline.py

Sprint 26
Institutional Execution Framework

Execution Position Pipeline

Owns the complete position lifecycle.

POSITION_OPENED
POSITION_PARTIALLY_CLOSED
POSITION_CLOSED
POSITION_REVERSED
POSITION_MODIFIED
STOP_LOSS_TRIGGERED
TAKE_PROFIT_TRIGGERED
FLATTEN_ALL

This pipeline is shared by:

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


class ExecutionPositionPipeline:
    """
    Institutional Position Lifecycle Pipeline.

    This pipeline owns every position state transition.
    """

    def __init__(
        self,
        *,
        portfolio_engine,
        order_repository,
        snapshot_pipeline,
        recorder: ExecutionEventRecorder,
    ):
        self.portfolio_engine = portfolio_engine
        self.order_repository = order_repository
        self.snapshot_pipeline = snapshot_pipeline
        self.recorder = recorder

    # ==========================================================
    # Position Open
    # ==========================================================

    def open(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        self.recorder.position_opened(context)

        context.status = "OPEN"

        context.mark_completed()

        self.snapshot_pipeline.refresh(context)

        return context

    # ==========================================================
    # Position Close
    # ==========================================================

    def close(
        self,
        context: ExecutionContext,
        *,
        quantity: Optional[float] = None,
        exit_price: Optional[float] = None,
    ) -> ExecutionContext:

        closed = self.portfolio_engine.close_position(

            position_id=context.position_id,

            quantity=quantity,

            exit_price=exit_price,

            raw=context.raw_request,

        )

        context.position = closed

        context.execution_price = exit_price

        context.mark_completed()

        self.order_repository.persist_position_close(
            context=context,
            position=closed,
        )

        self.recorder.position_closed(context)

        self.snapshot_pipeline.refresh(context)

        context.status = "CLOSED"

        context.message = "Position closed."

        return context

    # ==========================================================
    # Partial Close
    # ==========================================================

    def partial_close(
        self,
        context: ExecutionContext,
        *,
        quantity: float,
        exit_price: Optional[float] = None,
    ) -> ExecutionContext:

        position = self.portfolio_engine.partial_close_position(

            position_id=context.position_id,

            quantity=quantity,

            exit_price=exit_price,

            raw=context.raw_request,

        )

        context.set_position(position)

        context.execution_price = exit_price

        self.order_repository.persist_partial_close(
            context=context,
            position=position,
            quantity=quantity,
        )

        self.recorder.position_partially_closed(
            context
        )

        self.snapshot_pipeline.refresh(
            context
        )

        context.status = "PARTIALLY_CLOSED"

        context.message = "Position partially closed."

        return context

    # ==========================================================
    # Reverse
    # ==========================================================

    def reverse(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        result = self.portfolio_engine.reverse_position(

            position_id=context.position_id,

            raw=context.raw_request,

        )

        context.position = result

        context.side = result.side

        context.execution_price = result.avg_entry_price

        self.order_repository.persist_reversal(
            context=context,
            position=result,
        )

        self.recorder.position_reversed(
            context
        )

        self.snapshot_pipeline.refresh(
            context
        )

        context.status = "REVERSED"

        context.message = "Position reversed."

        return context

    # ==========================================================
    # Modify
    # ==========================================================

    def modify(
        self,
        context: ExecutionContext,
        *,
        stop_price=None,
        target_price=None,
    ) -> ExecutionContext:

        result = self.portfolio_engine.modify_position(

            position_id=context.position_id,

            stop_price=stop_price,

            target_price=target_price,

            raw=context.raw_request,

        )

        context.position = result

        self.order_repository.persist_modification(
            context=context,
            position=result,
        )

        self.recorder.position_modified(
            context
        )

        self.snapshot_pipeline.refresh(
            context
        )

        context.status = "MODIFIED"

        context.message = "Position modified."

        return context

    # ==========================================================
    # Stop Loss
    # ==========================================================

    def stop_loss_triggered(
        self,
        context: ExecutionContext,
        *,
        exit_price: float,
    ) -> ExecutionContext:

        context.execution_price = exit_price

        self.recorder.stop_loss(
            context
        )

        context.status = "STOP_LOSS"

        context.message = "Stop loss triggered."

        self.snapshot_pipeline.refresh(
            context
        )

        return context

    # ==========================================================
    # Take Profit
    # ==========================================================

    def take_profit_triggered(
        self,
        context: ExecutionContext,
        *,
        exit_price: float,
    ) -> ExecutionContext:

        context.execution_price = exit_price

        self.recorder.take_profit(
            context
        )

        context.status = "TAKE_PROFIT"

        context.message = "Take profit triggered."

        self.snapshot_pipeline.refresh(
            context
        )

        return context

    # ==========================================================
    # Flatten
    # ==========================================================

    def flatten_account(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        result = self.portfolio_engine.flatten_account(

            account_id=context.account_id,

            raw=context.raw_request,

        )

        self.order_repository.persist_flatten(
            context=context,
            result=result,
        )

        self.recorder.flatten_all(
            context
        )

        self.snapshot_pipeline.refresh(
            context
        )

        context.status = "FLATTENED"

        context.message = "All positions closed."

        context.mark_completed()

        return context

    # ==========================================================
    # Utility
    # ==========================================================

    def refresh(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        self.snapshot_pipeline.refresh(
            context
        )

        return context

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