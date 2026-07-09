"""
execution_event_time_machine.py

Sprint 39.1

Institutional Event Time Machine

Reconstructs execution, order, position, account, or portfolio state
as it existed at any historical timestamp.

This module reads only immutable execution events through the
ExecutionEventReplayer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .execution_context import ExecutionContext
from .execution_event_replayer import (
    ExecutionEventReplayer,
    get_execution_event_replayer,
)


class ExecutionEventTimeMachine:
    def __init__(
        self,
        *,
        db,
        replayer: Optional[ExecutionEventReplayer] = None,
    ):
        self.db = db
        self.replayer = replayer or get_execution_event_replayer(db=db)

    # ------------------------------------------------------------------
    # Point-in-time replay
    # ------------------------------------------------------------------

    def execution_at(
        self,
        *,
        execution_id: str,
        timestamp: datetime,
    ) -> ExecutionContext:
        events = self.replayer.load_events(execution_id=execution_id)
        return self._replay(events, timestamp=timestamp)

    def order_at(
        self,
        *,
        broker_order_id: str,
        timestamp: datetime,
    ) -> ExecutionContext:
        events = self.replayer.load_events(broker_order_id=broker_order_id)
        return self._replay(events, timestamp=timestamp)

    def position_at(
        self,
        *,
        position_id: str,
        timestamp: datetime,
    ) -> ExecutionContext:
        events = self.replayer.load_events(position_id=position_id)
        return self._replay(events, timestamp=timestamp)

    def account_at(
        self,
        *,
        account_id: str,
        timestamp: datetime,
    ) -> ExecutionContext:
        events = self.replayer.load_events(account_id=account_id)
        return self._replay(events, timestamp=timestamp)

    def portfolio_at(
        self,
        *,
        portfolio_id: str,
        timestamp: datetime,
    ) -> Dict[str, Any]:
        events = self.replayer.load_events(portfolio_id=portfolio_id)
        filtered = self._filter_events(events, end=timestamp)

        context = ExecutionContext()

        positions: Dict[str, ExecutionContext] = {}
        orders: Dict[str, ExecutionContext] = {}

        for event in filtered:
            self.replayer.apply_event(context, event)

            position_id = event.get("position_id")
            broker_order_id = event.get("broker_order_id")

            if position_id:
                position_context = positions.get(position_id) or ExecutionContext()
                self.replayer.apply_event(position_context, event)
                positions[position_id] = position_context

            if broker_order_id:
                order_context = orders.get(broker_order_id) or ExecutionContext()
                self.replayer.apply_event(order_context, event)
                orders[broker_order_id] = order_context

        return {
            "portfolio_id": portfolio_id,
            "asof": timestamp,
            "context": context,
            "positions": positions,
            "orders": orders,
            "event_count": len(filtered),
        }

    # ------------------------------------------------------------------
    # Generic replay windows
    # ------------------------------------------------------------------

    def replay_until(
        self,
        *,
        timestamp: datetime,
        execution_id: Optional[str] = None,
        broker_order_id: Optional[str] = None,
        position_id: Optional[str] = None,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> ExecutionContext:
        events = self.replayer.load_events(
            execution_id=execution_id,
            broker_order_id=broker_order_id,
            position_id=position_id,
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        return self._replay(events, timestamp=timestamp)

    def replay_range(
        self,
        *,
        start: datetime,
        end: datetime,
        execution_id: Optional[str] = None,
        broker_order_id: Optional[str] = None,
        position_id: Optional[str] = None,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        events = self.replayer.load_events(
            execution_id=execution_id,
            broker_order_id=broker_order_id,
            position_id=position_id,
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        filtered = self._filter_events(events, start=start, end=end)
        contexts: List[ExecutionContext] = []

        context = ExecutionContext()

        for event in filtered:
            self.replayer.apply_event(context, event)
            contexts.append(context)

        return {
            "start": start,
            "end": end,
            "events": filtered,
            "contexts": contexts,
            "event_count": len(filtered),
        }

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(
        self,
        *,
        execution_id: str,
        timestamp_a: datetime,
        timestamp_b: datetime,
    ) -> Dict[str, Any]:
        a = self.execution_at(
            execution_id=execution_id,
            timestamp=timestamp_a,
        )

        b = self.execution_at(
            execution_id=execution_id,
            timestamp=timestamp_b,
        )

        return {
            "execution_id": execution_id,
            "timestamp_a": timestamp_a,
            "timestamp_b": timestamp_b,
            "status": {
                "a": getattr(a, "status", None),
                "b": getattr(b, "status", None),
            },
            "price": {
                "a": getattr(a, "execution_price", None),
                "b": getattr(b, "execution_price", None),
            },
            "quantity": {
                "a": getattr(a, "units", None),
                "b": getattr(b, "units", None),
            },
            "position_id": {
                "a": getattr(a, "position_id", None),
                "b": getattr(b, "position_id", None),
            },
            "broker_order_id": {
                "a": getattr(a, "broker_order_id", None),
                "b": getattr(b, "broker_order_id", None),
            },
            "event_count": {
                "a": len(getattr(a, "events", []) or []),
                "b": len(getattr(b, "events", []) or []),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _replay(
        self,
        events: List[Dict[str, Any]],
        *,
        timestamp: datetime,
    ) -> ExecutionContext:
        context = ExecutionContext()

        filtered = self._filter_events(
            events,
            end=timestamp,
        )

        for event in filtered:
            self.replayer.apply_event(
                context,
                event,
            )

        return context

    def _filter_events(
        self,
        events: List[Dict[str, Any]],
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []

        for event in events:
            ts = (
                event.get("occurred_at")
                or event.get("created_at")
                or event.get("timestamp")
            )

            if ts is None:
                continue

            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except Exception:
                    continue

            if start is not None and ts < start:
                continue

            if end is not None and ts > end:
                continue

            filtered.append(event)

        return filtered


# ==============================================================================
# Factory
# ==============================================================================

_TIME_MACHINE: Optional[ExecutionEventTimeMachine] = None


def get_execution_event_time_machine(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventTimeMachine:
    global _TIME_MACHINE

    if not cache or _TIME_MACHINE is None:
        _TIME_MACHINE = ExecutionEventTimeMachine(db=db)

    return _TIME_MACHINE