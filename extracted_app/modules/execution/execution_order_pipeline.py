"""
modules/execution/execution_order_pipeline.py

Sprint 26

Institutional Execution Framework

Execution Order Pipeline

Responsible for:
- Context preparation
- Validation
- Rejection handling
- Broker order ID generation
- Correlation ID assignment
- NEW_ORDER recording
- Routing to market or pending execution pipelines
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable, Optional

from .execution_context import ExecutionContext
from .execution_event_recorder import ExecutionEventRecorder
from .execution_order_state_machine import ExecutionOrderState


class ExecutionOrderPipeline:
    def __init__(
            self,
            *,
            validator,
            recorder,
            order_state_machine,
            market_executor=None,
            pending_executor=None,
            fill_pipeline=None,
            pending_pipeline=None,
    ):
        self.validator = validator
        self.recorder = recorder
        self.order_state_machine = order_state_machine
        self.market_executor = market_executor
        self.pending_executor = pending_executor
        self.fill_pipeline = fill_pipeline
        self.pending_pipeline = pending_pipeline



    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def execute(self, context: ExecutionContext) -> ExecutionContext:
        context = self._prepare_context(context)
        validation = context.validation

        print("=" * 80)
        print("EXECUTION VALIDATION")
        print("VALID    :", validation.get("valid"))
        print("ERRORS   :", validation.get("errors"))
        print("WARNINGS :", validation.get("warnings"))
        print("MESSAGE  :", validation.get("message"))
        print("=" * 80)
        if not context.validation.get("valid", False):
            return self._reject(context)

        context = self._initialize_execution(context)

        return self._route(context)

    # ---------------------------------------------------------
    # Preparation / validation
    # ---------------------------------------------------------

    def _prepare_context(self, context: ExecutionContext) -> ExecutionContext:
        context.validation = self.validator.validate(context)

        if context.validation.get("valid"):
            context = self.order_state_machine.transition(

                context,

                ExecutionOrderState.VALIDATED,

            )
        return context

    def _reject(
            self,
            context: ExecutionContext,
    ) -> ExecutionContext:

        validation = context.validation or {}

        reason = validation.get(
            "message",
            "Order validation failed.",
        )

        context = self.order_state_machine.transition(

            context,

            ExecutionOrderState.REJECTED,

        )

        for error in validation.get("errors", []):
            context.add_error(error)

        for warning in validation.get("warnings", []):
            context.add_warning(warning)

        return context

    # ---------------------------------------------------------
    # Execution initialization
    # ---------------------------------------------------------

    def _initialize_execution(self, context: ExecutionContext) -> ExecutionContext:
        if not context.broker_order_id:
            context.broker_order_id = f"FXP-{uuid.uuid4().hex[:12].upper()}"

        if not context.correlation_id:
            context.correlation_id = context.broker_order_id

        #
        # Immutable NEW_ORDER
        #

        event = self.recorder.new_order(context)

        #
        # Accepted
        #

        context = self.order_state_machine.transition(

            context,

            ExecutionOrderState.ACCEPTED,

        )

        return context

    # ---------------------------------------------------------
    # Routing
    # ---------------------------------------------------------

    def _route(self, context: ExecutionContext) -> ExecutionContext:
        order_type = self._order_type(context)

        if order_type in {"MARKET", "MKT"}:
            return self._route_market(context)

        context = self.order_state_machine.transition(

            context,

            ExecutionOrderState.PENDING,

        )

        return self._route_pending(context)

    def _route_market(self, context: ExecutionContext) -> ExecutionContext:
        if self.market_executor is not None:
            return self.market_executor(context)

        if self.fill_pipeline is not None:
            return self.fill_pipeline.execute(context)

        raise RuntimeError("No market execution handler configured.")

    def _route_pending(self, context: ExecutionContext) -> ExecutionContext:
        if self.pending_executor is not None:
            return self.pending_executor(context)

        if self.pending_pipeline is not None:
            return self.pending_pipeline.create(context)

        raise RuntimeError("No pending execution handler configured.")

    @staticmethod
    def _order_type(context: ExecutionContext) -> str:
        return str(context.order_type or "MARKET").upper().strip()
