"""
execution_event_metrics.py

Sprint 39.5

Institutional Execution Event Metrics

Produces execution analytics directly from immutable
execution events.

No projection tables are used.

Execution Events
        ↓
ExecutionEventMetrics
        ↓
Operational KPIs
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Optional

from .execution_event_replayer import (
    ExecutionEventReplayer,
    get_execution_event_replayer,
)
from .execution_models import ExecutionEventType


class ExecutionEventMetrics:

    def __init__(
        self,
        *,
        db,
        replayer: Optional[ExecutionEventReplayer] = None,
    ):
        self.db = db
        self.replayer = (
            replayer
            or get_execution_event_replayer(db=db)
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def execution_metrics(self) -> Dict[str, Any]:

        events = self._load_events()

        executions = self._group_by_execution(events)

        durations = []

        successful = 0

        failed = 0

        total_events = 0

        for execution_events in executions.values():

            total_events += len(execution_events)

            event_types = {
                e.get("event_type")
                for e in execution_events
            }

            if (
                ExecutionEventType.ORDER_FILLED
                in event_types
            ):
                successful += 1

            if (
                ExecutionEventType.ORDER_REJECTED
                in event_types
            ):
                failed += 1

            duration = self._calculate_duration(
                execution_events
            )

            if duration is not None:
                durations.append(duration)

        return {

            "total_executions":
                len(executions),

            "successful":
                successful,

            "failed":
                failed,

            "average_events":
                (
                    total_events /
                    max(len(executions), 1)
                ),

            "average_duration":
                mean(durations)
                if durations else 0,

            "max_duration":
                max(durations)
                if durations else 0,
        }

    # ----------------------------------------------------------

    def order_metrics(self):

        events = self._load_events()

        groups = self._group_by_order(
            events
        )

        submitted = 0
        filled = 0
        cancelled = 0
        rejected = 0

        fill_times = []

        for order_events in groups.values():

            submitted += 1

            event_types = {
                e["event_type"]
                for e in order_events
            }

            if (
                ExecutionEventType.ORDER_FILLED
                in event_types
            ):
                filled += 1

            if (
                ExecutionEventType.ORDER_CANCELLED
                in event_types
            ):
                cancelled += 1

            if (
                ExecutionEventType.ORDER_REJECTED
                in event_types
            ):
                rejected += 1

            latency = self._calculate_latency(

                order_events,

                ExecutionEventType.NEW_ORDER,

                ExecutionEventType.ORDER_FILLED,

            )

            if latency is not None:
                fill_times.append(latency)

        return {

            "orders":
                submitted,

            "filled":
                filled,

            "cancelled":
                cancelled,

            "rejected":
                rejected,

            "fill_rate":
                filled /
                max(submitted, 1),

            "cancel_rate":
                cancelled /
                max(submitted, 1),

            "average_fill_time":
                mean(fill_times)
                if fill_times else 0,

            "median_fill_time":
                median(fill_times)
                if fill_times else 0,

        }

    # ----------------------------------------------------------

    def position_metrics(self):

        events = self._load_events()

        groups = self._group_by_position(
            events
        )

        opened = 0
        closed = 0

        holding = []

        scale_in = 0
        scale_out = 0

        for position_events in groups.values():

            event_types = [
                e["event_type"]
                for e in position_events
            ]

            if (
                ExecutionEventType.POSITION_OPENED
                in event_types
            ):
                opened += 1

            if (
                ExecutionEventType.POSITION_CLOSED
                in event_types
            ):
                closed += 1

            scale_in += event_types.count(
                ExecutionEventType.POSITION_SCALED_IN
            )

            scale_out += event_types.count(
                ExecutionEventType.POSITION_SCALED_OUT
            )

            duration = self._calculate_latency(

                position_events,

                ExecutionEventType.POSITION_OPENED,

                ExecutionEventType.POSITION_CLOSED,

            )

            if duration is not None:
                holding.append(duration)

        return {

            "opened":
                opened,

            "closed":
                closed,

            "average_hold_time":
                mean(holding)
                if holding else 0,

            "average_scale_in":
                scale_in /
                max(opened, 1),

            "average_scale_out":
                scale_out /
                max(opened, 1),

        }

    # ----------------------------------------------------------

    def latency_metrics(self):

        events = self._load_events()

        groups = self._group_by_execution(
            events
        )

        values = []

        for execution_events in groups.values():

            latency = self._calculate_latency(

                execution_events,

                ExecutionEventType.NEW_ORDER,

                ExecutionEventType.ORDER_FILLED,

            )

            if latency is not None:

                values.append(latency)

        return {

            "average":
                mean(values)
                if values else 0,

            "median":
                median(values)
                if values else 0,

            "minimum":
                min(values)
                if values else 0,

            "maximum":
                max(values)
                if values else 0,

            "p95":
                self._percentile(
                    values,
                    95,
                ),

        }

    # ----------------------------------------------------------

    def throughput_metrics(self):

        events = self._load_events()

        per_minute = defaultdict(int)
        per_hour = defaultdict(int)

        for event in events:

            ts = self._timestamp(event)

            if ts is None:
                continue

            minute = ts.replace(
                second=0,
                microsecond=0,
            )

            hour = ts.replace(
                minute=0,
                second=0,
                microsecond=0,
            )

            per_minute[minute] += 1
            per_hour[hour] += 1

        return {

            "events_per_minute":

                mean(
                    per_minute.values()
                )
                if per_minute else 0,

            "events_per_hour":

                mean(
                    per_hour.values()
                )
                if per_hour else 0,

            "peak_minute":

                max(
                    per_minute.values(),
                    default=0,
                ),

            "peak_hour":

                max(
                    per_hour.values(),
                    default=0,
                ),

        }

    # ----------------------------------------------------------

    def quality_metrics(self):

        events = self._load_events()

        commissions = []

        slippage = []

        spreads = []

        for event in events:

            if event.get(
                "commission"
            ) is not None:

                commissions.append(
                    float(
                        event["commission"]
                    )
                )

            if event.get(
                "slippage"
            ) is not None:

                slippage.append(
                    float(
                        event["slippage"]
                    )
                )

            if event.get(
                "spread"
            ) is not None:

                spreads.append(
                    float(
                        event["spread"]
                    )
                )

        return {

            "average_commission":

                mean(commissions)
                if commissions else 0,

            "average_slippage":

                mean(slippage)
                if slippage else 0,

            "average_spread":

                mean(spreads)
                if spreads else 0,

        }

    # ----------------------------------------------------------

    def account_metrics(self):

        events = self._load_events()

        accounts = defaultdict(list)

        for event in events:

            account = event.get(
                "account_id"
            )

            if account:

                accounts[
                    account
                ].append(event)

        return {

            "accounts":

                len(accounts),

            "average_events":

                mean(
                    len(v)
                    for v in accounts.values()
                )
                if accounts else 0,

        }

    # ----------------------------------------------------------

    def portfolio_metrics(self):

        events = self._load_events()

        portfolios = defaultdict(list)

        for event in events:

            portfolio = event.get(
                "portfolio_id"
            )

            if portfolio:

                portfolios[
                    portfolio
                ].append(event)

        return {

            "portfolios":

                len(portfolios),

            "average_events":

                mean(
                    len(v)
                    for v in portfolios.values()
                )
                if portfolios else 0,

        }

    # ----------------------------------------------------------

    def aggregate_metrics(self):

        return {

            "execution_metrics":
                self.execution_metrics(),

            "order_metrics":
                self.order_metrics(),

            "position_metrics":
                self.position_metrics(),

            "latency_metrics":
                self.latency_metrics(),

            "throughput_metrics":
                self.throughput_metrics(),

            "quality_metrics":
                self.quality_metrics(),

            "account_metrics":
                self.account_metrics(),

            "portfolio_metrics":
                self.portfolio_metrics(),

            "generated_at":
                datetime.utcnow().isoformat(),

        }

    # ==========================================================
    # Internal
    # ==========================================================

    def _load_events(self):

        return self.replayer.load_events()

    def _group_by_execution(self, events):

        groups = defaultdict(list)

        for e in events:

            key = e.get(
                "execution_id"
            )

            if key:
                groups[key].append(e)

        return groups

    def _group_by_order(self, events):

        groups = defaultdict(list)

        for e in events:

            key = e.get(
                "broker_order_id"
            )

            if key:
                groups[key].append(e)

        return groups

    def _group_by_position(self, events):

        groups = defaultdict(list)

        for e in events:

            key = e.get(
                "position_id"
            )

            if key:
                groups[key].append(e)

        return groups

    def _timestamp(self, event):

        ts = (
            event.get("occurred_at")
            or event.get("created_at")
        )

        if isinstance(ts, str):

            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                return None

        return ts

    def _calculate_latency(

        self,

        events,

        start_event,

        end_event,

    ):

        start = None
        end = None

        for event in events:

            if (
                event["event_type"]
                == start_event
            ):
                start = self._timestamp(
                    event
                )

            elif (
                event["event_type"]
                == end_event
            ):
                end = self._timestamp(
                    event
                )

        if (
            start is None
            or end is None
        ):
            return None

        return (
            end - start
        ).total_seconds()

    def _calculate_duration(
        self,
        events,
    ):

        if len(events) < 2:
            return None

        first = self._timestamp(
            events[0]
        )

        last = self._timestamp(
            events[-1]
        )

        if (
            first is None
            or last is None
        ):
            return None

        return (
            last - first
        ).total_seconds()

    def _percentile(
        self,
        values,
        pct,
    ):

        if not values:
            return 0

        values = sorted(values)

        index = int(
            (pct / 100)
            * (len(values) - 1)
        )

        return values[index]


# ==========================================================
# Factory
# ==========================================================

_METRICS = None


def get_execution_event_metrics(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventMetrics:

    global _METRICS

    if (
        not cache
        or _METRICS is None
    ):

        _METRICS = (
            ExecutionEventMetrics(
                db=db,
            )
        )

    return _METRICS