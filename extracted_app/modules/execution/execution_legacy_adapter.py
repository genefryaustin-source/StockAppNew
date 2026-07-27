"""
modules/execution/execution_legacy_adapter.py

Sprint 26
Institutional Execution Framework

Legacy Execution Adapter

Bridges the new execution pipeline framework with the
existing ForexTerminalExecutionService implementation.

This adapter allows incremental migration by converting
ExecutionContext objects into the legacy method signatures.
"""

from __future__ import annotations

from typing import Any, Callable

from .execution_context import ExecutionContext


class ExecutionLegacyAdapter:
    """
    Adapter between ExecutionContext and the legacy
    ForexTerminalExecutionService methods.
    """

    def __init__(
        self,
        *,
        market_executor: Callable[..., dict],
        pending_executor: Callable[..., dict],
        verify_executor: Callable[..., dict] | None = None,
        cancel_executor: Callable[..., dict] | None = None,
    ):
        self.market_executor = market_executor
        self.pending_executor = pending_executor
        self.verify_executor = verify_executor
        self.cancel_executor = cancel_executor

    # ==========================================================
    # Market Order
    # ==========================================================

    def execute_market(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        result = self.market_executor(

            engine=context.metadata["engine"],

            account=context.account,

            broker_order_id=context.broker_order_id,

            pair=context.pair,

            side=context.side,

            units=context.units,

            requested_price=context.requested_price,

            stop_price=context.stop_price,

            target_price=context.target_price,

            leverage=context.leverage,

            broker=context.broker,

            raw=context.raw_request,

            validation=context.validation,

        )

        self._merge(context, result)

        return context

    # ==========================================================
    # Pending Order
    # ==========================================================

    def execute_pending(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        result = self.pending_executor(

            engine=context.metadata["engine"],

            account=context.account,

            broker_order_id=context.broker_order_id,

            pair=context.pair,

            side=context.side,

            units=context.units,

            order_type=context.order_type,

            limit_price=context.requested_price,

            stop_price=context.stop_price,

            target_price=context.target_price,

            risk_pct=context.metadata.get("risk_pct"),

            broker=context.broker,

            raw=context.raw_request,

            validation=context.validation,

        )

        self._merge(context, result)

        return context

    # ==========================================================
    # Verification
    # ==========================================================

    def verify(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        if self.verify_executor is None:
            return context

        context.metadata["verification"] = self.verify_executor(

            broker_order_id=context.broker_order_id,

            position_id=context.position_id,

            account_id=context.account_id,

            portfolio_id=context.portfolio_id,

        )

        return context

    # ==========================================================
    # Cancel
    # ==========================================================

    def cancel(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        if self.cancel_executor is None:
            return context

        result = self.cancel_executor(

            broker_order_id=context.broker_order_id,

            broker=context.broker,

        )

        self._merge(context, result)

        return context

    # ==========================================================
    # Merge Legacy Result
    # ==========================================================

    def _merge(
        self,
        context: ExecutionContext,
        result: dict,
    ) -> None:

        if not isinstance(result, dict):
            return

        context.status = result.get(
            "status",
            context.status,
        )

        context.message = result.get(
            "message",
            context.message,
        )

        context.position_id = result.get(
            "position_id",
            context.position_id,
        )

        context.account_id = result.get(
            "account_id",
            context.account_id,
        )

        context.portfolio_id = result.get(
            "portfolio_id",
            context.portfolio_id,
        )

        context.execution_price = result.get(
            "avg_fill_price",
            context.execution_price,
        )

        context.average_fill_price = result.get(
            "avg_fill_price",
            context.average_fill_price,
        )

        context.snapshot = result.get(
            "snapshot",
            context.snapshot,
        )

        context.validation = result.get(
            "validation",
            context.validation,
        )

        context.metadata["verification"] = result.get(
            "verification",
        )

        context.metadata["legacy_result"] = result

        if "position" in result:
            context.position = result["position"]

        if "execution_event_id" in result:
            context.event_ids["NEW_ORDER"] = result[
                "execution_event_id"
            ]

        if "order_filled_event_id" in result:
            context.event_ids["ORDER_FILLED"] = result[
                "order_filled_event_id"
            ]

        if "position_opened_event_id" in result:
            context.event_ids["POSITION_OPENED"] = result[
                "position_opened_event_id"
            ]

        errors = result.get("errors")

        if errors:

            if isinstance(errors, list):
                context.errors.extend(errors)
            else:
                context.add_error(str(errors))

        warnings = result.get("warnings")

        if warnings:

            if isinstance(warnings, list):
                context.warnings.extend(warnings)
            else:
                context.add_warning(str(warnings))