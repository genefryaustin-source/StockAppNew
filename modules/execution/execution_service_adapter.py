"""
modules/execution/execution_service_adapter.py

Sprint 26

Institutional Execution Framework

Adapter between the legacy execution service and the
new execution pipeline framework.

Purpose

Allows ForexTerminalExecutionService to migrate
incrementally instead of a full rewrite.
"""

from __future__ import annotations

from .execution_context import ExecutionContext
from .execution_pipeline_factory import (
    build_execution_pipeline,
)


class ExecutionServiceAdapter:

    """
    Thin adapter used by every execution service.

    Forex

    Equities

    Options

    Crypto

    all use this class.
    """

    def __init__(
        self,
        *,
        db,
        portfolio_engine,
        actor=None,
        source=None,
    ):

        self.pipeline = build_execution_pipeline(

            db=db,

            portfolio_engine=portfolio_engine,

            actor=actor,

            source=source,

        )

    # ----------------------------------------------------------
    # New Order
    # ----------------------------------------------------------

    def submit_order(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.order_pipeline.execute(
            context
        )

    # ----------------------------------------------------------
    # Pending Orders
    # ----------------------------------------------------------

    def submit_pending(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.pending_pipeline.create(
            context
        )

    # ----------------------------------------------------------
    # Position
    # ----------------------------------------------------------

    def close_position(
        self,
        context: ExecutionContext,
        *,
        quantity=None,
        exit_price=None,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.close(

            context,

            quantity=quantity,

            exit_price=exit_price,

        )

    def partial_close(
        self,
        context: ExecutionContext,
        *,
        quantity,
        exit_price=None,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.partial_close(

            context,

            quantity=quantity,

            exit_price=exit_price,

        )

    def reverse_position(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.reverse(
            context
        )

    def modify_position(
        self,
        context: ExecutionContext,
        *,
        stop_price=None,
        target_price=None,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.modify(

            context,

            stop_price=stop_price,

            target_price=target_price,

        )

    def flatten_account(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.flatten_account(
            context
        )

    # ----------------------------------------------------------
    # Snapshot
    # ----------------------------------------------------------

    def refresh(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.snapshot_pipeline.refresh(
            context
        )

    def verify(
        self,
        context: ExecutionContext,
    ):

        return self.pipeline.snapshot_pipeline.verify_execution(
            context
        )