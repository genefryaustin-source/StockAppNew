"""
execution_audit_engine.py

Sprint 39.2

Institutional Execution Audit Engine

Builds audit reports directly from the immutable execution event
stream.

The audit engine NEVER reads projection tables.

Everything is reconstructed from execution_events.

Execution Events
        ↓
ExecutionEventReplayer
        ↓
ExecutionEventTimeMachine
        ↓
ExecutionEventStreamValidator
        ↓
ExecutionAuditEngine
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .execution_event_replayer import (
    ExecutionEventReplayer,
    get_execution_event_replayer,
)
from .execution_event_stream_validator import (
    ExecutionEventStreamValidator,
    get_execution_event_stream_validator,
)
from .execution_event_time_machine import (
    ExecutionEventTimeMachine,
    get_execution_event_time_machine,
)


class ExecutionAuditEngine:

    def __init__(
        self,
        *,
        db,
        replayer: Optional[ExecutionEventReplayer] = None,
        validator: Optional[
            ExecutionEventStreamValidator
        ] = None,
        time_machine: Optional[
            ExecutionEventTimeMachine
        ] = None,
    ):

        self.db = db

        self.replayer = (
            replayer
            or get_execution_event_replayer(
                db=db,
            )
        )

        self.validator = (
            validator
            or get_execution_event_stream_validator(
                db=db,
            )
        )

        self.time_machine = (
            time_machine
            or get_execution_event_time_machine(
                db=db,
            )
        )

    # ==============================================================
    # Public API
    # ==============================================================

    def audit_execution(
        self,
        *,
        execution_id: str,
    ) -> Dict[str, Any]:

        events = self.replayer.load_events(
            execution_id=execution_id,
        )

        validation = (
            self.validator.validate_events(
                events,
            )
        )

        return self._build_report(

            entity_type="execution",

            entity_id=execution_id,

            events=events,

            validation=validation,

        )

    # --------------------------------------------------------------

    def audit_order(
        self,
        *,
        broker_order_id: str,
    ) -> Dict[str, Any]:

        events = self.replayer.load_events(
            broker_order_id=broker_order_id,
        )

        validation = (
            self.validator.validate_events(
                events,
            )
        )

        return self._build_report(

            entity_type="order",

            entity_id=broker_order_id,

            events=events,

            validation=validation,

        )

    # --------------------------------------------------------------

    def audit_position(
        self,
        *,
        position_id: str,
    ) -> Dict[str, Any]:

        events = self.replayer.load_events(
            position_id=position_id,
        )

        validation = (
            self.validator.validate_events(
                events,
            )
        )

        return self._build_report(

            entity_type="position",

            entity_id=position_id,

            events=events,

            validation=validation,

        )

    # --------------------------------------------------------------

    def audit_account(
        self,
        *,
        account_id: str,
    ) -> Dict[str, Any]:

        events = self.replayer.load_events(
            account_id=account_id,
        )

        validation = (
            self.validator.validate_events(
                events,
            )
        )

        return self._build_report(

            entity_type="account",

            entity_id=account_id,

            events=events,

            validation=validation,

        )

    # --------------------------------------------------------------

    def audit_portfolio(
        self,
        *,
        portfolio_id: str,
    ) -> Dict[str, Any]:

        events = self.replayer.load_events(
            portfolio_id=portfolio_id,
        )

        validation = (
            self.validator.validate_events(
                events,
            )
        )

        return self._build_report(

            entity_type="portfolio",

            entity_id=portfolio_id,

            events=events,

            validation=validation,

        )

    # ==============================================================
    # Timeline
    # ==============================================================

    def build_timeline(
        self,
        *,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        timeline = []

        for index, event in enumerate(events):

            timeline.append(

                {

                    "sequence": index + 1,

                    "event_type": event.get(
                        "event_type"
                    ),

                    "timestamp": (
                        event.get("occurred_at")
                        or event.get(
                            "created_at"
                        )
                    ),

                    "execution_id": event.get(
                        "execution_id"
                    ),

                    "position_id": event.get(
                        "position_id"
                    ),

                    "broker_order_id": event.get(
                        "broker_order_id"
                    ),

                    "status": event.get(
                        "status"
                    ),

                }

            )

        return timeline

    # ==============================================================
    # Summary
    # ==============================================================

    def summarize(
        self,
        *,
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not events:

            return {

                "event_count": 0,

            }

        return {

            "event_count": len(events),

            "first_event": events[0].get(
                "event_type"
            ),

            "last_event": events[-1].get(
                "event_type"
            ),

            "started": (
                events[0].get("occurred_at")
                or events[0].get(
                    "created_at"
                )
            ),

            "completed": (
                events[-1].get("occurred_at")
                or events[-1].get(
                    "created_at"
                )
            ),

        }

    # ==============================================================
    # Anomaly Detection
    # ==============================================================

    def detect_anomalies(
        self,
        *,
        events: List[Dict[str, Any]],
    ) -> List[str]:

        anomalies = []

        if not events:

            anomalies.append(
                "No events found."
            )

            return anomalies

        timestamps = []

        for event in events:

            ts = (
                event.get("occurred_at")
                or event.get(
                    "created_at"
                )
            )

            if ts:

                timestamps.append(
                    ts
                )

        if timestamps != sorted(
            timestamps
        ):

            anomalies.append(
                "Events out of chronological order."
            )

        event_types = {

            e.get("event_type")

            for e in events

        }

        if (
            "NEW_ORDER"
            not in event_types
        ):

            anomalies.append(
                "Missing NEW_ORDER."
            )

        if (
            "ORDER_FILLED"
            in event_types
            and "POSITION_OPENED"
            not in event_types
        ):

            anomalies.append(
                "Filled order without opened position."
            )

        return anomalies

    # ==============================================================
    # Time Machine
    # ==============================================================

    def snapshot_at(
        self,
        *,
        execution_id: str,
        timestamp: datetime,
    ):

        return self.time_machine.execution_at(

            execution_id=execution_id,

            timestamp=timestamp,

        )

    # ==============================================================
    # Report Builder
    # ==============================================================

    def export_audit_report(
        self,
        *,
        entity_type: str,
        entity_id: str,
    ) -> Dict[str, Any]:

        dispatch = {

            "execution": self.audit_execution,

            "order": self.audit_order,

            "position": self.audit_position,

            "account": self.audit_account,

            "portfolio": self.audit_portfolio,

        }

        if entity_type not in dispatch:

            raise ValueError(
                entity_type
            )

        keyword = {

            "execution": "execution_id",

            "order": "broker_order_id",

            "position": "position_id",

            "account": "account_id",

            "portfolio": "portfolio_id",

        }[entity_type]

        return dispatch[
            entity_type
        ](

            **{

                keyword: entity_id,

            }

        )

    # ==============================================================
    # Internal
    # ==============================================================

    def _build_report(
        self,
        *,
        entity_type: str,
        entity_id: str,
        events: List[Dict[str, Any]],
        validation,
    ) -> Dict[str, Any]:

        return {

            "entity_type": entity_type,

            "entity_id": entity_id,

            "valid": validation.valid,

            "validation": validation.to_dict(),

            "summary": self.summarize(
                events=events,
            ),

            "timeline": self.build_timeline(
                events=events,
            ),

            "anomalies": self.detect_anomalies(
                events=events,
            ),

            "event_count": len(
                events
            ),

        }


# ==============================================================
# Factory
# ==============================================================

_AUDIT_ENGINE: Optional[
    ExecutionAuditEngine
] = None


def get_execution_audit_engine(
    *,
    db,
    cache: bool = True,
) -> ExecutionAuditEngine:

    global _AUDIT_ENGINE

    if (
        not cache
        or _AUDIT_ENGINE is None
    ):

        _AUDIT_ENGINE = (
            ExecutionAuditEngine(
                db=db,
            )
        )

    return _AUDIT_ENGINE