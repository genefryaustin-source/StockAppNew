"""
modules/execution/execution_event_explorer.py

Sprint 40.2

Institutional Execution Event Explorer

Searchable explorer for immutable execution events.

The explorer never reads projection tables.

It operates directly on execution_events and integrates with:

    • ExecutionEventReplayer
    • ExecutionEventTimeMachine
    • ExecutionAuditEngine
    • ExecutionComplianceEngine
    • ExecutionEventMetrics
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

from .execution_event_replayer import (
    ExecutionEventReplayer,
    get_execution_event_replayer,
)

from .execution_event_time_machine import (
    ExecutionEventTimeMachine,
    get_execution_event_time_machine,
)

from .execution_audit_engine import (
    ExecutionAuditEngine,
    get_execution_audit_engine,
)

from .execution_compliance_engine import (
    ExecutionComplianceEngine,
    get_execution_compliance_engine,
)

from .execution_event_metrics import (
    ExecutionEventMetrics,
    get_execution_event_metrics,
)


class ExecutionEventExplorer:

    def __init__(
        self,
        *,
        db,
        replayer: Optional[
            ExecutionEventReplayer
        ] = None,
        time_machine: Optional[
            ExecutionEventTimeMachine
        ] = None,
        audit: Optional[
            ExecutionAuditEngine
        ] = None,
        compliance: Optional[
            ExecutionComplianceEngine
        ] = None,
        metrics: Optional[
            ExecutionEventMetrics
        ] = None,
    ):

        self.db = db

        self.replayer = (
            replayer
            or get_execution_event_replayer(
                db=db,
            )
        )

        self.time_machine = (
            time_machine
            or get_execution_event_time_machine(
                db=db,
            )
        )

        self.audit = (
            audit
            or get_execution_audit_engine(
                db=db,
            )
        )

        self.compliance = (
            compliance
            or get_execution_compliance_engine(
                db=db,
            )
        )

        self.metrics = (
            metrics
            or get_execution_event_metrics(
                db=db,
            )
        )

    # ==========================================================
    # Search
    # ==========================================================

    def search(
        self,
        **filters,
    ) -> List[Dict[str, Any]]:

        events = self._load_events()

        return self._filter(
            events,
            **filters,
        )

    # ----------------------------------------------------------

    def search_execution(
        self,
        execution_id: str,
    ):

        return self.search(
            execution_id=execution_id,
        )

    # ----------------------------------------------------------

    def search_order(
        self,
        broker_order_id: str,
    ):

        return self.search(
            broker_order_id=broker_order_id,
        )

    # ----------------------------------------------------------

    def search_position(
        self,
        position_id: str,
    ):

        return self.search(
            position_id=position_id,
        )

    # ----------------------------------------------------------

    def search_account(
        self,
        account_id: str,
    ):

        return self.search(
            account_id=account_id,
        )

    # ----------------------------------------------------------

    def search_portfolio(
        self,
        portfolio_id: str,
    ):

        return self.search(
            portfolio_id=portfolio_id,
        )

    # ==========================================================
    # Timeline
    # ==========================================================

    def timeline(
        self,
        **filters,
    ) -> List[Dict[str, Any]]:

        events = self.search(
            **filters,
        )

        return self._build_timeline(
            events,
        )

    # ==========================================================
    # Details
    # ==========================================================

    def details(
        self,
        event_id: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        events = self._load_events()

        for event in events:

            if (
                event.get("event_id")
                == event_id
                or event.get("id")
                == event_id
            ):

                return {

                    "event_id":
                        event.get(
                            "event_id"
                        )
                        or event.get(
                            "id"
                        ),

                    "event_type":
                        event.get(
                            "event_type"
                        ),

                    "occurred_at":
                        event.get(
                            "occurred_at"
                        ),

                    "execution_id":
                        event.get(
                            "execution_id"
                        ),

                    "position_id":
                        event.get(
                            "position_id"
                        ),

                    "broker_order_id":
                        event.get(
                            "broker_order_id"
                        ),

                    "account_id":
                        event.get(
                            "account_id"
                        ),

                    "portfolio_id":
                        event.get(
                            "portfolio_id"
                        ),

                    "payload":
                        event,

                }

        return None

    # ==========================================================
    # Statistics
    # ==========================================================

    def statistics(
        self,
        **filters,
    ):

        events = self.search(
            **filters,
        )

        return self._build_statistics(
            events,
        )

    # ==========================================================
    # Replay
    # ==========================================================

    def replay_execution(
        self,
        execution_id: str,
        timestamp: datetime,
    ):

        return self.time_machine.execution_at(

            execution_id=execution_id,

            timestamp=timestamp,

        )

    def replay_position(
        self,
        position_id: str,
        timestamp: datetime,
    ):

        return self.time_machine.position_at(

            position_id=position_id,

            timestamp=timestamp,

        )

    def replay_order(
        self,
        broker_order_id: str,
        timestamp: datetime,
    ):

        return self.time_machine.order_at(

            broker_order_id=broker_order_id,

            timestamp=timestamp,

        )

    def replay_account(
        self,
        account_id: str,
        timestamp: datetime,
    ):

        return self.time_machine.account_at(

            account_id=account_id,

            timestamp=timestamp,

        )

    # ==========================================================
    # Audit
    # ==========================================================

    def audit_execution(
        self,
        execution_id,
    ):

        return self.audit.audit_execution(

            execution_id=execution_id,

        )

    def audit_order(
        self,
        broker_order_id,
    ):

        return self.audit.audit_order(

            broker_order_id=broker_order_id,

        )

    def audit_position(
        self,
        position_id,
    ):

        return self.audit.audit_position(

            position_id=position_id,

        )

    # ==========================================================
    # Compliance
    # ==========================================================

    def evaluate_execution(
        self,
        execution_id,
    ):

        return self.compliance.evaluate_execution(

            execution_id=execution_id,

        )

    def evaluate_order(
        self,
        broker_order_id,
    ):

        return self.compliance.evaluate_order(

            broker_order_id=broker_order_id,

        )

    def evaluate_position(
        self,
        position_id,
    ):

        return self.compliance.evaluate_position(

            position_id=position_id,

        )

    # ==========================================================
    # Metrics
    # ==========================================================

    def metrics_summary(self):

        return self.metrics.aggregate_metrics()

    # ==========================================================
    # Export
    # ==========================================================

    def export_json(
        self,
        **filters,
    ) -> str:

        return json.dumps(

            self.search(
                **filters,
            ),

            indent=4,

            default=str,

        )

    def export_csv(
        self,
        **filters,
    ) -> str:

        events = self.search(
            **filters,
        )

        if not events:
            return ""

        output = StringIO()

        writer = csv.DictWriter(

            output,

            fieldnames=sorted(

                events[0].keys()

            ),

        )

        writer.writeheader()

        writer.writerows(
            events,
        )

        return output.getvalue()

    # ==========================================================
    # Internal
    # ==========================================================

    def _load_events(self):

        return self.replayer.load_events()

    # ----------------------------------------------------------

    def _filter(
        self,
        events,
        **filters,
    ):

        result = []

        for event in events:

            include = True

            for key, value in filters.items():

                if value is None:
                    continue

                if key == "start":

                    ts = self._timestamp(
                        event
                    )

                    if (
                        ts is None
                        or ts < value
                    ):
                        include = False
                        break

                    continue

                if key == "end":

                    ts = self._timestamp(
                        event
                    )

                    if (
                        ts is None
                        or ts > value
                    ):
                        include = False
                        break

                    continue

                if (
                    str(
                        event.get(key)
                    )
                    != str(value)
                ):

                    include = False
                    break

            if include:

                result.append(
                    event
                )

        return self._sort(
            result,
        )

    # ----------------------------------------------------------

    def _sort(
        self,
        events,
    ):

        return sorted(

            events,

            key=lambda e:

            self._timestamp(e)

            or datetime.min,

        )

    # ----------------------------------------------------------

    def _build_timeline(
        self,
        events,
    ):

        timeline = []

        for i, event in enumerate(events):

            timeline.append({

                "sequence":

                    i + 1,

                "timestamp":

                    self._timestamp(
                        event
                    ),

                "event":

                    event.get(
                        "event_type"
                    ),

                "status":

                    event.get(
                        "status"
                    ),

                "execution":

                    event.get(
                        "execution_id"
                    ),

                "order":

                    event.get(
                        "broker_order_id"
                    ),

                "position":

                    event.get(
                        "position_id"
                    ),

            })

        return timeline

    # ----------------------------------------------------------

    def _build_statistics(
        self,
        events,
    ):

        executions = set()

        orders = set()

        positions = set()

        accounts = set()

        portfolios = set()

        dates = []

        for event in events:

            executions.add(
                event.get(
                    "execution_id"
                )
            )

            orders.add(
                event.get(
                    "broker_order_id"
                )
            )

            positions.add(
                event.get(
                    "position_id"
                )
            )

            accounts.add(
                event.get(
                    "account_id"
                )
            )

            portfolios.add(
                event.get(
                    "portfolio_id"
                )
            )

            ts = self._timestamp(
                event
            )

            if ts:

                dates.append(ts)

        return {

            "events":
                len(events),

            "executions":
                len(
                    executions
                    - {None}
                ),

            "orders":
                len(
                    orders
                    - {None}
                ),

            "positions":
                len(
                    positions
                    - {None}
                ),

            "accounts":
                len(
                    accounts
                    - {None}
                ),

            "portfolios":
                len(
                    portfolios
                    - {None}
                ),

            "start":
                min(
                    dates,
                    default=None,
                ),

            "end":
                max(
                    dates,
                    default=None,
                ),

        }

    # ----------------------------------------------------------

    @staticmethod
    def _timestamp(
        event,
    ):

        ts = (

            event.get(
                "occurred_at"
            )

            or

            event.get(
                "created_at"
            )

        )

        if isinstance(
            ts,
            str,
        ):

            try:

                ts = datetime.fromisoformat(
                    ts
                )

            except Exception:

                return None

        return ts


# ==========================================================
# Factory
# ==========================================================

_EXPLORER = None


def get_execution_event_explorer(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventExplorer:

    global _EXPLORER

    if (
        not cache
        or _EXPLORER is None
    ):

        _EXPLORER = (
            ExecutionEventExplorer(
                db=db,
            )
        )

    return _EXPLORER