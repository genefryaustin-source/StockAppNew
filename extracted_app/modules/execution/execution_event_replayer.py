"""
execution_event_replayer.py

Sprint 38.1

Institutional Event Replay Engine

Reconstructs execution state exclusively from immutable
execution_events.

No portfolio tables are required.

Execution Events
        ↓
Replay
        ↓
ExecutionContext
        ↓
Order
        ↓
Position
        ↓
Account
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from .execution_context import ExecutionContext
from .execution_models import ExecutionEventType


class ExecutionEventReplayer:

    def __init__(
        self,
        *,
        db,
    ):
        self.db = db
        # load_events() below queries execution_events directly, bypassing
        # ExecutionRepository's constructor (which is what normally calls
        # ExecutionSchema(db).ensure() first). On a fresh database with no
        # orders ever submitted, every audit/explorer dashboard that uses
        # this replayer crashed with "no such table: execution_events"
        # instead of showing an empty result.
        if self.db is not None:
            try:
                from modules.execution.execution_schema import ExecutionSchema
                ExecutionSchema(self.db).ensure()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Event Loading
    # ------------------------------------------------------------------

    def load_events(
        self,
        *,
        execution_id: Optional[str] = None,
        broker_order_id: Optional[str] = None,
        position_id: Optional[str] = None,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        where = []
        params: Dict[str, Any] = {}

        if execution_id:
            where.append("execution_id=:execution_id")
            params["execution_id"] = execution_id

        if broker_order_id:
            where.append("broker_order_id=:broker_order_id")
            params["broker_order_id"] = broker_order_id

        if position_id:
            where.append("position_id=:position_id")
            params["position_id"] = position_id

        if account_id:
            where.append("account_id=:account_id")
            params["account_id"] = account_id

        if portfolio_id:
            where.append("portfolio_id=:portfolio_id")
            params["portfolio_id"] = portfolio_id

        if tenant_id:
            where.append("tenant_id=:tenant_id")
            params["tenant_id"] = tenant_id

        sql = """
        SELECT *
        FROM execution_events
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += """
        ORDER BY
            occurred_at,
            created_at,
            id
        """

        rows = self.db.execute(
            text(sql),
            params,
        ).mappings().all()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Replay Context
    # ------------------------------------------------------------------

    def replay_execution(
        self,
        *,
        execution_id: str,
    ) -> ExecutionContext:

        context = ExecutionContext()

        events = self.load_events(
            execution_id=execution_id,
        )

        for event in events:
            self.apply_event(
                context,
                event,
            )

        return context

    # ------------------------------------------------------------------
    # Replay Order
    # ------------------------------------------------------------------

    def replay_order(
        self,
        *,
        broker_order_id: str,
    ) -> ExecutionContext:

        context = ExecutionContext()

        events = self.load_events(
            broker_order_id=broker_order_id,
        )

        for event in events:
            self.apply_event(
                context,
                event,
            )

        return context

    # ------------------------------------------------------------------
    # Replay Position
    # ------------------------------------------------------------------

    def replay_position(
        self,
        *,
        position_id: str,
    ) -> ExecutionContext:

        context = ExecutionContext()

        events = self.load_events(
            position_id=position_id,
        )

        for event in events:
            self.apply_event(
                context,
                event,
            )

        return context

    # ------------------------------------------------------------------
    # Replay Account
    # ------------------------------------------------------------------

    def replay_account(
        self,
        *,
        account_id: str,
    ) -> Dict[str, Any]:

        events = self.load_events(
            account_id=account_id,
        )

        positions = {}

        order_count = 0

        fills = 0

        pnl = 0.0

        for event in events:

            event_type = str(
                event.get("event_type")
            )

            if event_type == ExecutionEventType.NEW_ORDER:
                order_count += 1

            elif event_type == ExecutionEventType.ORDER_FILLED:
                fills += 1

            elif event_type == ExecutionEventType.POSITION_OPENED:

                positions[
                    event.get("position_id")
                ] = "OPEN"

            elif event_type == ExecutionEventType.POSITION_CLOSED:

                positions[
                    event.get("position_id")
                ] = "CLOSED"

            pnl += float(
                event.get("realized_pnl") or 0
            )

        return {

            "orders": order_count,

            "fills": fills,

            "positions": positions,

            "realized_pnl": pnl,

            "events": len(events),
        }

    # ------------------------------------------------------------------
    # Replay Portfolio
    # ------------------------------------------------------------------

    def replay_portfolio(
        self,
        *,
        portfolio_id: str,
    ) -> Dict[str, Any]:

        events = self.load_events(
            portfolio_id=portfolio_id,
        )

        grouped = defaultdict(list)

        for e in events:
            grouped[
                e.get("position_id")
            ].append(e)

        return {

            "positions": len(grouped),

            "events": len(events),

            "position_events": grouped,
        }

    # ------------------------------------------------------------------
    # Replay Between
    # ------------------------------------------------------------------

    def replay_between(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:

        rows = self.db.execute(text("""
            SELECT *
            FROM execution_events
            WHERE occurred_at BETWEEN :start AND :end
            ORDER BY occurred_at,id
        """), {

            "start": start,

            "end": end,

        }).mappings().all()

        return [
            dict(r)
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Replay Until
    # ------------------------------------------------------------------

    def replay_until(
        self,
        *,
        timestamp: datetime,
        account_id: Optional[str] = None,
    ) -> ExecutionContext:

        context = ExecutionContext()

        sql = """
        SELECT *
        FROM execution_events
        WHERE occurred_at<=:ts
        """

        params = {

            "ts": timestamp,
        }

        if account_id:

            sql += """
            AND account_id=:account_id
            """

            params["account_id"] = account_id

        sql += """
        ORDER BY occurred_at,id
        """

        rows = self.db.execute(
            text(sql),
            params,
        ).mappings().all()

        for row in rows:

            self.apply_event(
                context,
                dict(row),
            )

        return context

    # ------------------------------------------------------------------
    # Single Event
    # ------------------------------------------------------------------

    def replay_event(
        self,
        context: ExecutionContext,
        event: Dict[str, Any],
    ) -> ExecutionContext:

        self.apply_event(
            context,
            event,
        )

        return context

    # ------------------------------------------------------------------
    # Apply Event
    # ------------------------------------------------------------------

    def apply_event(
        self,
        context: ExecutionContext,
        event: Dict[str, Any],
    ) -> None:

        event_type = str(
            event.get("event_type")
        )

        context.execution_id = (
            event.get("execution_id")
            or context.execution_id
        )

        context.correlation_id = (
            event.get("correlation_id")
            or context.correlation_id
        )

        context.account_id = (
            event.get("account_id")
            or context.account_id
        )

        context.position_id = (
            event.get("position_id")
            or context.position_id
        )

        context.broker_order_id = (
            event.get("broker_order_id")
            or context.broker_order_id
        )

        context.side = (
            event.get("side")
            or context.side
        )

        context.symbol = (
            event.get("symbol")
            or context.symbol
        )

        context.pair = (
            event.get("pair")
            or context.pair
        )

        context.units = float(
            event.get("units")
            or context.units
            or 0
        )

        context.execution_price = (
            event.get("execution_price")
            or context.execution_price
        )

        context.status = event_type

        if hasattr(
            context,
            "events",
        ):
            context.events.append(event)

    # ------------------------------------------------------------------
    # Event Stream Validation
    # ------------------------------------------------------------------

    def verify_event_stream(
        self,
        *,
        execution_id: Optional[str] = None,
        broker_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        events = self.load_events(
            execution_id=execution_id,
            broker_order_id=broker_order_id,
        )

        seen = set()

        errors = []

        for event in events:

            event_type = event.get(
                "event_type"
            )

            if (
                event_type
                == ExecutionEventType.ORDER_FILLED
                and ExecutionEventType.NEW_ORDER
                not in seen
            ):

                errors.append(
                    "ORDER_FILLED before NEW_ORDER"
                )

            if (
                event_type
                == ExecutionEventType.POSITION_OPENED
                and ExecutionEventType.ORDER_FILLED
                not in seen
            ):

                errors.append(
                    "POSITION_OPENED before ORDER_FILLED"
                )

            if (
                event_type
                == ExecutionEventType.POSITION_CLOSED
                and ExecutionEventType.POSITION_OPENED
                not in seen
            ):

                errors.append(
                    "POSITION_CLOSED before POSITION_OPENED"
                )

            seen.add(event_type)

        return {

            "valid": len(errors) == 0,

            "errors": errors,

            "events": len(events),
        }


# ==============================================================================
# Factory
# ==============================================================================

_REPLAYER: Optional[
    ExecutionEventReplayer
] = None


def get_execution_event_replayer(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventReplayer:

    global _REPLAYER

    if (
        not cache
        or _REPLAYER is None
    ):

        _REPLAYER = ExecutionEventReplayer(
            db=db,
        )

    return _REPLAYER