"""
execution_order_state_machine.py

Institutional Order State Machine

Owns the complete order lifecycle.

Pipelines should NEVER directly modify order status.

Instead they request:

    transition(context, NEW_STATE)

which

    • validates the transition
    • updates context
    • persists repository
    • emits immutable event
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, Optional, Set

from .execution_context import ExecutionContext
from .execution_event_recorder import ExecutionEventRecorder
from .execution_order_repository import ExecutionOrderRepository


# ==============================================================================
# Order States
# ==============================================================================


class ExecutionOrderState(str, Enum):

    NEW = "NEW"

    VALIDATED = "VALIDATED"

    ACCEPTED = "ACCEPTED"

    PENDING = "PENDING"

    PARTIALLY_FILLED = "PARTIALLY_FILLED"

    FILLED = "FILLED"

    CANCELLED = "CANCELLED"

    EXPIRED = "EXPIRED"

    REJECTED = "REJECTED"


# ==============================================================================
# State Machine
# ==============================================================================


class ExecutionOrderStateMachine:

    def __init__(
        self,
        *,
        recorder: ExecutionEventRecorder,
        order_repository: Optional[ExecutionOrderRepository] = None,
    ):

        self.recorder = recorder
        self.order_repository = order_repository

        self._allowed: Dict[
            ExecutionOrderState,
            Set[ExecutionOrderState],
        ] = {

            ExecutionOrderState.NEW: {
                ExecutionOrderState.VALIDATED,
                ExecutionOrderState.REJECTED,
            },

            ExecutionOrderState.VALIDATED: {
                ExecutionOrderState.ACCEPTED,
                ExecutionOrderState.REJECTED,
            },

            ExecutionOrderState.ACCEPTED: {
                ExecutionOrderState.PENDING,
                ExecutionOrderState.FILLED,
                ExecutionOrderState.CANCELLED,
            },

            ExecutionOrderState.PENDING: {
                ExecutionOrderState.PARTIALLY_FILLED,
                ExecutionOrderState.FILLED,
                ExecutionOrderState.CANCELLED,
                ExecutionOrderState.EXPIRED,
            },

            ExecutionOrderState.PARTIALLY_FILLED: {
                ExecutionOrderState.PARTIALLY_FILLED,
                ExecutionOrderState.FILLED,
                ExecutionOrderState.CANCELLED,
            },

            ExecutionOrderState.FILLED: set(),

            ExecutionOrderState.CANCELLED: set(),

            ExecutionOrderState.EXPIRED: set(),

            ExecutionOrderState.REJECTED: set(),
        }

        self._events: Dict[
            ExecutionOrderState,
            Callable[[ExecutionContext], object],
        ] = {

            ExecutionOrderState.VALIDATED:
                recorder.order_validated,

            ExecutionOrderState.ACCEPTED:
                recorder.order_accepted,

            ExecutionOrderState.PENDING:
                recorder.order_pending,

            ExecutionOrderState.PARTIALLY_FILLED:
                recorder.order_partially_filled,

            ExecutionOrderState.FILLED:
                recorder.order_filled,

            ExecutionOrderState.CANCELLED:
                recorder.order_cancelled,

            ExecutionOrderState.EXPIRED:
                recorder.order_expired,

            ExecutionOrderState.REJECTED:
                recorder.order_rejected,
        }

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def transition(
        self,
        context: ExecutionContext,
        new_state: ExecutionOrderState,
    ) -> ExecutionContext:

        current = self.current_state(context)

        self.validate_transition(
            current,
            new_state,
        )

        self.apply_transition(
            context,
            new_state,
        )

        self.update_order(
            context,
            new_state,
        )

        self.emit_events(
            context,
            new_state,
        )

        self.update_context(
            context,
            new_state,
        )

        return context

    # ------------------------------------------------------------------

    def validate_transition(
        self,
        current: ExecutionOrderState,
        requested: ExecutionOrderState,
    ) -> None:

        allowed = self.allowed_transitions(current)

        if requested not in allowed:

            raise ValueError(
                f"Illegal order transition "
                f"{current.value} -> {requested.value}"
            )

    # ------------------------------------------------------------------

    def apply_transition(
        self,
        context: ExecutionContext,
        new_state: ExecutionOrderState,
    ) -> None:

        context.status = new_state.value

    # ------------------------------------------------------------------

    def emit_events(
        self,
        context: ExecutionContext,
        new_state: ExecutionOrderState,
    ) -> None:

        handler = self._events.get(new_state)

        if handler is None:
            return

        handler(context)

    # ------------------------------------------------------------------

    def update_context(
        self,
        context: ExecutionContext,
        new_state: ExecutionOrderState,
    ) -> None:

        context.status = new_state.value

        if hasattr(context, "advance_stage"):

            context.advance_stage(
                new_state.value,
            )

    # ------------------------------------------------------------------

    def update_order(
        self,
        context: ExecutionContext,
        new_state: ExecutionOrderState,
    ) -> None:

        if self.order_repository is None:
            return

        if not context.broker_order_id:
            return

        if hasattr(
            self.order_repository,
            "update_status",
        ):

            self.order_repository.update_status(

                broker_order_id=context.broker_order_id,

                status=new_state.value,
            )

    # ------------------------------------------------------------------

    def current_state(
        self,
        context: ExecutionContext,
    ) -> ExecutionOrderState:

        value = (
            context.status
            or ExecutionOrderState.NEW.value
        )

        return ExecutionOrderState(value)

    # ------------------------------------------------------------------

    def allowed_transitions(
        self,
        state: ExecutionOrderState,
    ) -> Set[ExecutionOrderState]:

        return self._allowed.get(
            state,
            set(),
        )

    # ------------------------------------------------------------------

    @staticmethod
    def is_terminal(
        state: ExecutionOrderState,
    ) -> bool:

        return state in {

            ExecutionOrderState.FILLED,

            ExecutionOrderState.CANCELLED,

            ExecutionOrderState.EXPIRED,

            ExecutionOrderState.REJECTED,
        }


# ==============================================================================
# Factory
# ==============================================================================

_STATE_MACHINE: Optional[
    ExecutionOrderStateMachine
] = None


def get_execution_order_state_machine(
    *,
    recorder: ExecutionEventRecorder,
    order_repository: Optional[
        ExecutionOrderRepository
    ] = None,
) -> ExecutionOrderStateMachine:

    global _STATE_MACHINE

    if _STATE_MACHINE is None:

        _STATE_MACHINE = ExecutionOrderStateMachine(

            recorder=recorder,

            order_repository=order_repository,
        )

    return _STATE_MACHINE