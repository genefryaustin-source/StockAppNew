"""
execution_position_state_machine.py

Institutional Position State Machine

Owns the complete lifecycle of an execution position.

Pipelines should NEVER directly modify position state.

Instead they request

    transition(context, NEW_STATE)

which

    • validates transition
    • updates context
    • updates portfolio position
    • emits immutable event
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, Optional, Set

from .execution_context import ExecutionContext
from .execution_event_recorder import ExecutionEventRecorder


# ==============================================================================
# Position States
# ==============================================================================


class ExecutionPositionState(str, Enum):

    NEW = "NEW"

    OPEN = "OPEN"

    MODIFIED = "MODIFIED"

    SCALED_IN = "SCALED_IN"

    SCALED_OUT = "SCALED_OUT"

    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"

    REVERSED = "REVERSED"

    CLOSED = "CLOSED"


# ==============================================================================
# Position State Machine
# ==============================================================================


class ExecutionPositionStateMachine:

    def __init__(
        self,
        *,
        recorder: ExecutionEventRecorder,
        portfolio_engine=None,
    ):

        self.recorder = recorder
        self.portfolio_engine = portfolio_engine

        self._allowed: Dict[
            ExecutionPositionState,
            Set[ExecutionPositionState],
        ] = {

            ExecutionPositionState.NEW: {

                ExecutionPositionState.OPEN,

            },

            ExecutionPositionState.OPEN: {

                ExecutionPositionState.MODIFIED,

                ExecutionPositionState.SCALED_IN,

                ExecutionPositionState.SCALED_OUT,

                ExecutionPositionState.PARTIALLY_CLOSED,

                ExecutionPositionState.REVERSED,

                ExecutionPositionState.CLOSED,

            },

            ExecutionPositionState.MODIFIED: {

                ExecutionPositionState.MODIFIED,

                ExecutionPositionState.SCALED_IN,

                ExecutionPositionState.SCALED_OUT,

                ExecutionPositionState.PARTIALLY_CLOSED,

                ExecutionPositionState.REVERSED,

                ExecutionPositionState.CLOSED,

            },

            ExecutionPositionState.SCALED_IN: {

                ExecutionPositionState.MODIFIED,

                ExecutionPositionState.SCALED_IN,

                ExecutionPositionState.SCALED_OUT,

                ExecutionPositionState.PARTIALLY_CLOSED,

                ExecutionPositionState.REVERSED,

                ExecutionPositionState.CLOSED,

            },

            ExecutionPositionState.SCALED_OUT: {

                ExecutionPositionState.MODIFIED,

                ExecutionPositionState.SCALED_IN,

                ExecutionPositionState.SCALED_OUT,

                ExecutionPositionState.PARTIALLY_CLOSED,

                ExecutionPositionState.REVERSED,

                ExecutionPositionState.CLOSED,

            },

            ExecutionPositionState.PARTIALLY_CLOSED: {

                ExecutionPositionState.MODIFIED,

                ExecutionPositionState.SCALED_IN,

                ExecutionPositionState.SCALED_OUT,

                ExecutionPositionState.PARTIALLY_CLOSED,

                ExecutionPositionState.CLOSED,

            },

            ExecutionPositionState.REVERSED: {

                ExecutionPositionState.MODIFIED,

                ExecutionPositionState.SCALED_IN,

                ExecutionPositionState.SCALED_OUT,

                ExecutionPositionState.PARTIALLY_CLOSED,

                ExecutionPositionState.CLOSED,

            },

            ExecutionPositionState.CLOSED: set(),
        }

        self._events: Dict[
            ExecutionPositionState,
            Callable[[ExecutionContext], object],
        ] = {

            ExecutionPositionState.OPEN:
                recorder.position_opened,

            ExecutionPositionState.MODIFIED:
                recorder.position_modified,

            ExecutionPositionState.SCALED_IN:
                recorder.position_scaled_in,

            ExecutionPositionState.SCALED_OUT:
                recorder.position_scaled_out,

            ExecutionPositionState.PARTIALLY_CLOSED:
                recorder.position_partially_closed,

            ExecutionPositionState.REVERSED:
                recorder.position_reversed,

            ExecutionPositionState.CLOSED:
                recorder.position_closed,
        }

    # ------------------------------------------------------------------

    def transition(
        self,
        context: ExecutionContext,
        new_state: ExecutionPositionState,
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

        self.update_position(
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
        current: ExecutionPositionState,
        requested: ExecutionPositionState,
    ) -> None:

        allowed = self.allowed_transitions(current)

        if requested not in allowed:

            raise ValueError(
                f"Illegal position transition "
                f"{current.value} -> {requested.value}"
            )

    # ------------------------------------------------------------------

    def apply_transition(
        self,
        context: ExecutionContext,
        new_state: ExecutionPositionState,
    ) -> None:

        context.status = new_state.value

        if context.position is not None:

            if hasattr(context.position, "status"):

                context.position.status = new_state.value

    # ------------------------------------------------------------------

    def emit_events(
        self,
        context: ExecutionContext,
        new_state: ExecutionPositionState,
    ) -> None:

        handler = self._events.get(new_state)

        if handler is None:
            return

        handler(context)

    # ------------------------------------------------------------------

    def update_context(
        self,
        context: ExecutionContext,
        new_state: ExecutionPositionState,
    ) -> None:

        context.status = new_state.value

        if hasattr(context, "advance_stage"):

            context.advance_stage(
                new_state.value,
            )

    # ------------------------------------------------------------------

    def update_position(
        self,
        context: ExecutionContext,
        new_state: ExecutionPositionState,
    ) -> None:

        if self.portfolio_engine is None:
            return

        position = context.position

        if position is None:
            return

        #
        # Preferred institutional API
        #

        if hasattr(
            self.portfolio_engine,
            "update_position_status",
        ):

            self.portfolio_engine.update_position_status(

                position_id=position.id,

                status=new_state.value,
            )

            return

        #
        # Current StockApp compatibility
        #

        if hasattr(
            self.portfolio_engine,
            "_persist_position",
        ):

            position.status = new_state.value

            position.updated_at = context.completed_at

            self.portfolio_engine._persist_position(
                position
            )

    # ------------------------------------------------------------------

    def current_state(
        self,
        context: ExecutionContext,
    ) -> ExecutionPositionState:

        #
        # Prefer actual position state
        #

        if (
            context.position is not None
            and hasattr(context.position, "status")
            and context.position.status
        ):

            return ExecutionPositionState(
                context.position.status
            )

        #
        # Fall back to execution context
        #

        value = (
            context.status
            or ExecutionPositionState.NEW.value
        )

        return ExecutionPositionState(value)

    # ------------------------------------------------------------------

    def allowed_transitions(
        self,
        state: ExecutionPositionState,
    ) -> Set[ExecutionPositionState]:

        return self._allowed.get(
            state,
            set(),
        )

    # ------------------------------------------------------------------

    @staticmethod
    def is_terminal(
        state: ExecutionPositionState,
    ) -> bool:

        return state == ExecutionPositionState.CLOSED


# ==============================================================================
# Factory
# ==============================================================================

_POSITION_STATE_MACHINE: Optional[
    ExecutionPositionStateMachine
] = None


def get_execution_position_state_machine(
    *,
    recorder: ExecutionEventRecorder,
    portfolio_engine=None,
) -> ExecutionPositionStateMachine:

    global _POSITION_STATE_MACHINE

    if _POSITION_STATE_MACHINE is None:

        _POSITION_STATE_MACHINE = ExecutionPositionStateMachine(

            recorder=recorder,

            portfolio_engine=portfolio_engine,
        )

    return _POSITION_STATE_MACHINE