"""
execution_event_stream_validator.py

Sprint 38.3

Institutional Event Stream Validator

Validates immutable execution event streams for consistency,
ordering, identity integrity, and lifecycle correctness.

This validator NEVER reads projection tables.

It validates ONLY execution_events.

Execution Events
        ↓
ExecutionEventStreamValidator
        ↓
Validation Report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from .execution_event_replayer import (
    get_execution_event_replayer,
)
from .execution_models import ExecutionEventType

# ==============================================================================
# Allowed Event Transitions
# ==============================================================================

ALLOWED_TRANSITIONS = {

    #
    # Order Lifecycle
    #

    ExecutionEventType.NEW_ORDER: {

        ExecutionEventType.ORDER_VALIDATED,

        ExecutionEventType.ORDER_REJECTED,

        ExecutionEventType.ORDER_PENDING,

        ExecutionEventType.ORDER_ACCEPTED,

        ExecutionEventType.ORDER_CANCELLED,

    },

    ExecutionEventType.ORDER_VALIDATED: {

        ExecutionEventType.ORDER_ACCEPTED,

        ExecutionEventType.ORDER_PENDING,

        ExecutionEventType.ORDER_REJECTED,

    },

    ExecutionEventType.ORDER_PENDING: {

        ExecutionEventType.ORDER_ACCEPTED,

        ExecutionEventType.ORDER_FILLED,

        ExecutionEventType.ORDER_CANCELLED,

        ExecutionEventType.ORDER_EXPIRED,

        ExecutionEventType.ORDER_MODIFIED,

    },

    ExecutionEventType.ORDER_ACCEPTED: {

        ExecutionEventType.ORDER_FILLED,

        ExecutionEventType.ORDER_CANCELLED,

        ExecutionEventType.ORDER_MODIFIED,

    },

    ExecutionEventType.ORDER_PARTIALLY_FILLED: {

        ExecutionEventType.ORDER_PARTIALLY_FILLED,

        ExecutionEventType.ORDER_FILLED,

        ExecutionEventType.ORDER_CANCELLED,

    },

    ExecutionEventType.ORDER_FILLED: {

        ExecutionEventType.POSITION_OPENED,

    },

    #
    # Position Lifecycle
    #

    ExecutionEventType.POSITION_OPENED: {

        ExecutionEventType.POSITION_MODIFIED,

        ExecutionEventType.POSITION_SCALED_IN,

        ExecutionEventType.POSITION_SCALED_OUT,

        ExecutionEventType.POSITION_PARTIALLY_CLOSED,

        ExecutionEventType.POSITION_REVERSED,

        ExecutionEventType.POSITION_CLOSED,

        ExecutionEventType.STOP_LOSS_TRIGGERED,

        ExecutionEventType.TAKE_PROFIT_TRIGGERED,

        ExecutionEventType.TRAILING_STOP_TRIGGERED,

    },

    ExecutionEventType.POSITION_MODIFIED: {

        ExecutionEventType.POSITION_MODIFIED,

        ExecutionEventType.POSITION_SCALED_IN,

        ExecutionEventType.POSITION_SCALED_OUT,

        ExecutionEventType.POSITION_PARTIALLY_CLOSED,

        ExecutionEventType.POSITION_REVERSED,

        ExecutionEventType.POSITION_CLOSED,

    },

    ExecutionEventType.POSITION_SCALED_IN: {

        ExecutionEventType.POSITION_MODIFIED,

        ExecutionEventType.POSITION_SCALED_IN,

        ExecutionEventType.POSITION_SCALED_OUT,

        ExecutionEventType.POSITION_PARTIALLY_CLOSED,

        ExecutionEventType.POSITION_CLOSED,

    },

    ExecutionEventType.POSITION_SCALED_OUT: {

        ExecutionEventType.POSITION_MODIFIED,

        ExecutionEventType.POSITION_SCALED_IN,

        ExecutionEventType.POSITION_PARTIALLY_CLOSED,

        ExecutionEventType.POSITION_CLOSED,

    },

    ExecutionEventType.POSITION_PARTIALLY_CLOSED: {

        ExecutionEventType.POSITION_PARTIALLY_CLOSED,

        ExecutionEventType.POSITION_SCALED_IN,

        ExecutionEventType.POSITION_CLOSED,

    },

    ExecutionEventType.POSITION_REVERSED: {

        ExecutionEventType.POSITION_MODIFIED,

        ExecutionEventType.POSITION_CLOSED,

    },

    #
    # Terminal States
    #

    ExecutionEventType.POSITION_CLOSED: set(),

    ExecutionEventType.ORDER_CANCELLED: set(),

    ExecutionEventType.ORDER_REJECTED: set(),

    ExecutionEventType.ORDER_EXPIRED: set(),
}

# ==============================================================================
# Validation Result
# ==============================================================================


@dataclass
class EventStreamValidationResult:

    valid: bool = True

    errors: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)

    event_count: int = 0

    first_event: Optional[str] = None

    last_event: Optional[str] = None

    timeline_valid: bool = True

    identity_valid: bool = True

    sequence_valid: bool = True

    duplicate_valid: bool = True


# ==============================================================================
# Validator
# ==============================================================================


class ExecutionEventStreamValidator:

    def __init__(
        self,
        *,
        db,
    ):

        self.db = db

        self.replayer = get_execution_event_replayer(
            db=db,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_execution(
        self,
        execution_id: str,
    ) -> EventStreamValidationResult:

        events = self.replayer.load_events(
            execution_id=execution_id,
        )

        return self.validate_events(
            events,
        )

    # ------------------------------------------------------------------

    def validate_order(
        self,
        broker_order_id: str,
    ) -> EventStreamValidationResult:

        events = self.replayer.load_events(
            broker_order_id=broker_order_id,
        )

        return self.validate_events(
            events,
        )

    # ------------------------------------------------------------------

    def validate_position(
        self,
        position_id: str,
    ) -> EventStreamValidationResult:

        events = self.replayer.load_events(
            position_id=position_id,
        )

        return self.validate_events(
            events,
        )

    # ------------------------------------------------------------------

    def validate_account(
        self,
        account_id: str,
    ) -> EventStreamValidationResult:

        events = self.replayer.load_events(
            account_id=account_id,
        )

        return self.validate_events(
            events,
        )

    # ------------------------------------------------------------------

    def validate_portfolio(
        self,
        portfolio_id: str,
    ) -> EventStreamValidationResult:

        events = self.replayer.load_events(
            portfolio_id=portfolio_id,
        )

        return self.validate_events(
            events,
        )

    # ------------------------------------------------------------------

    def validate_event(
        self,
        event: Dict[str, Any],
    ) -> EventStreamValidationResult:

        return self.validate_events(
            [event],
        )

    # ------------------------------------------------------------------

    def validate_sequence(
        self,
        events: List[Dict[str, Any]],
    ) -> EventStreamValidationResult:

        return self.validate_events(
            events,
        )

    # ------------------------------------------------------------------

    def validate_events(
        self,
        events: List[Dict[str, Any]],
    ) -> EventStreamValidationResult:

        result = EventStreamValidationResult()

        result.event_count = len(events)

        if not events:
            result.valid = False
            result.errors.append(
                "No events supplied."
            )
            return result

        result.first_event = events[0].get(
            "event_type"
        )

        result.last_event = events[-1].get(
            "event_type"
        )

        self._validate_order_rules(
            events,
            result,
        )

        self._validate_position_rules(
            events,
            result,
        )

        self._validate_risk_rules(
            events,
            result,
        )

        self._validate_identity(
            events,
            result,
        )

        self._validate_timestamps(
            events,
            result,
        )

        self._validate_duplicates(
            events,
            result,
        )
        self._validate_transitions(
            events,
            result,
        )

        self._validate_terminal_states(
            events,
            result,
        )

        result.valid = (
            len(result.errors) == 0
        )

        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "event_count": self.event_count,
            "first_event": self.first_event,
            "last_event": self.last_event,
            "timeline_valid": self.timeline_valid,
            "identity_valid": self.identity_valid,
            "sequence_valid": self.sequence_valid,
            "duplicate_valid": self.duplicate_valid,
        }

    # ------------------------------------------------------------------
    # Order Rules
    # ------------------------------------------------------------------

    def _validate_order_rules(
        self,
        events,
        result,
    ):

        seen = []

        for event in events:

            t = event.get(
                "event_type"
            )

            if (
                t == ExecutionEventType.NEW_ORDER
                and ExecutionEventType.NEW_ORDER
                in seen
            ):

                result.errors.append(
                    "Duplicate NEW_ORDER."
                )

            if (
                t == ExecutionEventType.ORDER_ACCEPTED
                and ExecutionEventType.NEW_ORDER
                not in seen
            ):

                result.errors.append(
                    "ORDER_ACCEPTED before NEW_ORDER."
                )

            if (
                t == ExecutionEventType.ORDER_PENDING
                and ExecutionEventType.NEW_ORDER
                not in seen
            ):

                result.errors.append(
                    "ORDER_PENDING before NEW_ORDER."
                )

            if (
                t == ExecutionEventType.ORDER_FILLED
                and ExecutionEventType.NEW_ORDER
                not in seen
            ):

                result.errors.append(
                    "ORDER_FILLED before NEW_ORDER."
                )

            if (
                t
                in (
                    ExecutionEventType.ORDER_CANCELLED,
                    ExecutionEventType.ORDER_EXPIRED,
                    ExecutionEventType.ORDER_REJECTED,
                )
                and ExecutionEventType.ORDER_FILLED
                in seen
            ):

                result.errors.append(
                    f"{t} after ORDER_FILLED."
                )

            seen.append(t)

    # ------------------------------------------------------------------
    # Position Rules
    # ------------------------------------------------------------------

    def _validate_position_rules(
        self,
        events,
        result,
    ):

        opened = False

        closed = False

        for event in events:

            t = event.get(
                "event_type"
            )

            if (
                t
                == ExecutionEventType.POSITION_OPENED
            ):

                if opened:

                    result.errors.append(
                        "Duplicate POSITION_OPENED."
                    )

                opened = True

            elif (
                t
                == ExecutionEventType.POSITION_MODIFIED
            ):

                if not opened:

                    result.errors.append(
                        "POSITION_MODIFIED before POSITION_OPENED."
                    )

            elif (
                t
                == ExecutionEventType.POSITION_SCALED_IN
            ):

                if not opened:

                    result.errors.append(
                        "POSITION_SCALED_IN before POSITION_OPENED."
                    )

            elif (
                t
                == ExecutionEventType.POSITION_SCALED_OUT
            ):

                if not opened:

                    result.errors.append(
                        "POSITION_SCALED_OUT before POSITION_OPENED."
                    )

            elif (
                t
                == ExecutionEventType.POSITION_PARTIALLY_CLOSED
            ):

                if not opened:

                    result.errors.append(
                        "POSITION_PARTIALLY_CLOSED before POSITION_OPENED."
                    )

            elif (
                t
                == ExecutionEventType.POSITION_CLOSED
            ):

                if closed:

                    result.errors.append(
                        "Duplicate POSITION_CLOSED."
                    )

                closed = True

            elif (
                t
                == ExecutionEventType.POSITION_REVERSED
                and closed
            ):

                result.errors.append(
                    "POSITION_REVERSED after POSITION_CLOSED."
                )

    # ------------------------------------------------------------------
    # Risk Rules
    # ------------------------------------------------------------------

    def _validate_risk_rules(
        self,
        events,
        result,
    ):

        opened = any(
            e.get("event_type")
            == ExecutionEventType.POSITION_OPENED
            for e in events
        )

        for event in events:

            t = event.get(
                "event_type"
            )

            if (
                t
                in (
                    ExecutionEventType.STOP_LOSS_TRIGGERED,
                    ExecutionEventType.TAKE_PROFIT_TRIGGERED,
                    ExecutionEventType.TRAILING_STOP_TRIGGERED,
                )
                and not opened
            ):

                result.errors.append(
                    f"{t} before POSITION_OPENED."
                )

            if (
                t
                == ExecutionEventType.MARGIN_CALL
                and not opened
            ):

                result.warnings.append(
                    "MARGIN_CALL without open position."
                )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def _validate_identity(
        self,
        events,
        result,
    ):

        keys = (

            "execution_id",

            "correlation_id",

            "broker_order_id",

            "position_id",

            "account_id",

            "portfolio_id",

        )

        for key in keys:

            values = {

                e.get(key)

                for e in events

                if e.get(key)

            }

            if len(values) > 1:

                result.errors.append(
                    f"{key} changed during stream."
                )

                result.identity_valid = False

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def _validate_timestamps(
        self,
        events,
        result,
    ):

        previous = None

        for event in events:

            ts = (
                event.get("occurred_at")
                or event.get("created_at")
            )

            if (
                previous
                and isinstance(ts, datetime)
                and ts < previous
            ):

                result.errors.append(
                    "Event timestamps out of order."
                )

                result.timeline_valid = False

            if isinstance(ts, datetime):

                previous = ts

    # ------------------------------------------------------------------
    # Duplicate Detection
    # ------------------------------------------------------------------

    def _validate_duplicates(
        self,
        events,
        result,
    ):

        ids = set()

        for event in events:

            event_id = (
                event.get("id")
                or event.get("event_id")
            )

            if (
                event_id
                and event_id in ids
            ):

                result.errors.append(
                    f"Duplicate event id {event_id}."
                )

                result.duplicate_valid = False

            ids.add(
                event_id
            )

    def _validate_transitions(
            self,
            events,
            result,
    ):

        if len(events) < 2:
            return

        previous = events[0].get("event_type")

        for event in events[1:]:

            current = event.get("event_type")

            allowed = ALLOWED_TRANSITIONS.get(
                previous,
            )

            if (
                    allowed is not None
                    and current not in allowed
            ):
                result.errors.append(

                    f"Illegal transition: "
                    f"{previous} -> {current}"

                )

                result.sequence_valid = False

            previous = current


    # ------------------------------------------------------------------
    # Terminal States
    # ------------------------------------------------------------------

    def _validate_terminal_states(
        self,
        events,
        result,
    ):

        closed = False

        for event in events:

            t = event.get(
                "event_type"
            )

            if (
                t
                == ExecutionEventType.POSITION_CLOSED
            ):

                closed = True

            elif (
                closed
                and t
                in (
                    ExecutionEventType.POSITION_MODIFIED,
                    ExecutionEventType.POSITION_SCALED_IN,
                    ExecutionEventType.POSITION_SCALED_OUT,
                    ExecutionEventType.POSITION_PARTIALLY_CLOSED,
                )
            ):

                result.errors.append(
                    f"{t} after POSITION_CLOSED."
                )

                result.sequence_valid = False


# ==============================================================================
# Factory
# ==============================================================================

_VALIDATOR: Optional[
    ExecutionEventStreamValidator
] = None


def get_execution_event_stream_validator(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventStreamValidator:

    global _VALIDATOR

    if (
        not cache
        or _VALIDATOR is None
    ):

        _VALIDATOR = (
            ExecutionEventStreamValidator(
                db=db,
            )
        )

    return _VALIDATOR