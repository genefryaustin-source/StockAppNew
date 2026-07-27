"""
modules/execution/execution_fill_pipeline.py

Sprint 26
Institutional Execution Framework

Execution Fill Pipeline

Responsible for

Market execution
Order persistence
ORDER_FILLED event
POSITION_OPENED event
Snapshot refresh
Execution verification
Response construction

This pipeline completely replaces the old
_execute_market_order() implementation.
"""

from __future__ import annotations

from .execution_context import ExecutionContext
from .execution_order_state_machine import ExecutionOrderState
from modules.execution.execution_position_state_machine import ExecutionPositionState


class ExecutionFillPipeline:
    """
    Executes market orders.

    This class owns the institutional execution lifecycle.

    NEW_ORDER
            ↓
    Broker Fill
            ↓
    Persist Order
            ↓
    ORDER_FILLED
            ↓
    POSITION_OPENED
            ↓
    Snapshot Refresh
            ↓
    Verification
            ↓
    Response
    """
    print("=" * 80)
    print("LOADED EXECUTION_FILL_PIPELINE")
    print(__file__)
    print("=" * 80)

    def __init__(
            self,
            *,
            portfolio_engine,
            order_repository,
            snapshot_pipeline,
            recorder,
            order_state_machine,
            position_state_machine,
    ):
        self.portfolio_engine = portfolio_engine
        self.order_repository = order_repository
        self.snapshot_pipeline = snapshot_pipeline
        self.recorder = recorder
        self.order_state_machine = order_state_machine
        self.position_state_machine = position_state_machine

    # ------------------------------------------------------------------

    def execute(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:
        print("=" * 80)
        print("ENTER EXECUTION_FILL_PIPELINE.EXECUTE")
        print(__file__)
        print("=" * 80)
        #
        # Execute position
        #
        try:
            position = self.portfolio_engine.open_position(
                account_id=context.account_id,
                pair=context.pair,
                side=context.side,
                units=context.units,
                entry_price=context.requested_price,
                stop_price=context.stop_price,
                target_price=context.target_price,
                leverage=context.leverage,
                raw={
                    "broker_order_id": context.broker_order_id,
                    "correlation_id": context.correlation_id,
                    "metadata": context.metadata,
                    "request": context.raw_request,
                },
            )
            print("=" * 80)
            print("RETURNED FROM OPEN_POSITION")
            print("position.id   :", position.id)
            print("pair          :", position.pair)
            print("status        :", position.status)
            print("entry_price   :", position.avg_entry_price)
            print("=" * 80)
        #except Exception as exc:

            #return self.rollback(
                #context,
                #exc,
            #)
        except Exception as exc:

            print("=" * 80)
            print("OPEN_POSITION EXCEPTION")
            print(type(exc).__name__)
            print(exc)
            import traceback
            traceback.print_exc()
            print("=" * 80)

            return self.rollback(
                context,
                exc,
            )

        context.set_position(position)

        context.mark_execution(
            execution_price=position.avg_entry_price,
        )

        #
        # Persist order
        #
        print("=" * 80)
        print("ABOUT TO CALL insert_market_fill")
        print("Repository Type :", type(self.order_repository))
        print("Repository Mod  :", self.order_repository.__class__.__module__)
        print("Repository Name :", self.order_repository.__class__.__name__)
        print("=" * 80)
        self.order_repository.insert_market_fill(
            context=context,
            position=position,
        )
        self.commit()
        #
        # Immutable Events
        #
        try:

            context = self.order_state_machine.transition(

                context,

                ExecutionOrderState.FILLED,

            )

            context = self.position_state_machine.transition(

                context,

                ExecutionPositionState.OPEN,

            )

        except Exception as exc:

            context.add_warning(
                f"State transition failed: {exc}"
            )
        #
        # Refresh snapshot
        #
        try:
            self.snapshot_pipeline.refresh(
                context
            )
        except Exception as exc:

            context.warnings.append(
                f"Snapshot refresh failed: {exc}"
            )

        #
        # Final response
        #

        context.status = ExecutionOrderState.FILLED.value

        if hasattr(context, "advance_stage"):
            context.advance_stage("FILLED")

        context.message = (
            "Market order filled."
        )

        context.mark_completed()

        context.verified = self.verify(context)

        return context

    # ------------------------------------------------------------------

    def execute_fill_only(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:
        """
        Used when an existing pending order
        receives a market fill.
        """
        try:
            position = self.portfolio_engine.open_position(
                account_id=context.account_id,
                pair=context.pair,
                side=context.side,
                units=context.units,
                entry_price=context.requested_price,
                stop_price=context.stop_price,
                target_price=context.target_price,
                leverage=context.leverage,
                raw=context.raw_request,
            )
        except Exception as exc:

            return self.rollback(
                context,
                exc,
            )

        context.set_position(position)

        context.mark_execution(
            execution_price=position.avg_entry_price,
        )

        context = self.order_state_machine.transition(

            context,

            ExecutionOrderState.FILLED,

        )

        context = self.position_state_machine.transition(

            context,

            ExecutionPositionState.OPEN,

        )

        context.mark_filled()

        return context

    # ------------------------------------------------------------------

    def rollback(
        self,
        context: ExecutionContext,
        exc: Exception,
    ) -> ExecutionContext:
        """
        Transaction rollback.

        Future implementation may support:

        SQLAlchemy SAVEPOINTS

        Distributed transactions

        Broker reconciliation

        Compensation events
        """
        print("=" * 80)
        print("ROLLBACK CALLED")
        print("context.status :", getattr(context, "status", None))
        print("exception      :", exc)
        print("=" * 80)
        try:

            self.order_repository.rollback()

        except Exception:

            pass

        context.status = "ERROR"

        if hasattr(context, "advance_stage"):
            context.advance_stage("ERROR")

        context.add_error(
            str(exc)
        )

        return context

    # ------------------------------------------------------------------

    def commit(
        self,
    ):

        if hasattr(
            self.order_repository,
            "commit",
        ):
            self.order_repository.commit()

    # ------------------------------------------------------------------

    def verify(
            self,
            context: ExecutionContext,
    ) -> bool:
        """
        Verify execution using the snapshot pipeline.

        Supports both the legacy verify() API and the newer
        verify_execution() API during the Sprint 26 migration.
        """

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