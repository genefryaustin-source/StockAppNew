"""
execution_event_projection.py

Sprint 38.2

Institutional Event Projection Engine

Projects immutable execution events into read models.

Event Store
        ↓
ExecutionEventProjection
        ↓
Orders
Positions
Accounts
Snapshots

This is the ONLY component responsible for updating
projection tables from immutable events.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .execution_event_replayer import (
    get_execution_event_replayer,
)
from .execution_models import ExecutionEventType
from .execution_order_repository import (
    ExecutionOrderRepository,
)
from .execution_position_repository import (
    ExecutionPositionRepository,
)

from .execution_account_repository import (
    ExecutionAccountRepository,
)

from .execution_snapshot_repository import (
    ExecutionSnapshotRepository,
)


class ExecutionEventProjection:

    def __init__(
        self,
        *,
        db,
        order_repository: Optional[
            ExecutionOrderRepository
        ] = None,
            position_repository: Optional[
                ExecutionPositionRepository
            ] = None,

            account_repository: Optional[
                ExecutionAccountRepository
            ] = None,

            snapshot_repository: Optional[
                ExecutionSnapshotRepository
            ] = None,
    ):

        self.db = db

        self.order_repository = (
            order_repository
            or ExecutionOrderRepository(
                db=db,
            )
        )

        self.position_repository = (
                position_repository
                or ExecutionPositionRepository(
            db=db,
        )
        )

        self.account_repository = (
                account_repository
                or ExecutionAccountRepository(
            db=db,
        )
        )

        self.snapshot_repository = (
                snapshot_repository
                or ExecutionSnapshotRepository(
            db=db,
        )
        )

        self.replayer = (
            get_execution_event_replayer(
                db=db,
            )
        )

        self.handlers = {

            #
            # Orders
            #

            ExecutionEventType.NEW_ORDER:
                self._project_new_order,

            ExecutionEventType.ORDER_VALIDATED:
                self._project_order,

            ExecutionEventType.ORDER_ACCEPTED:
                self._project_order,

            ExecutionEventType.ORDER_PENDING:
                self._project_order,

            ExecutionEventType.ORDER_MODIFIED:
                self._project_order,

            ExecutionEventType.ORDER_PARTIALLY_FILLED:
                self._project_order,

            ExecutionEventType.ORDER_FILLED:
                self._project_order,

            ExecutionEventType.ORDER_CANCELLED:
                self._project_order,

            ExecutionEventType.ORDER_EXPIRED:
                self._project_order,

            ExecutionEventType.ORDER_REJECTED:
                self._project_order,

            #
            # Positions
            #

            ExecutionEventType.POSITION_OPENED:
                self._project_position,

            ExecutionEventType.POSITION_MODIFIED:
                self._project_position,

            ExecutionEventType.POSITION_SCALED_IN:
                self._project_position,

            ExecutionEventType.POSITION_SCALED_OUT:
                self._project_position,

            ExecutionEventType.POSITION_PARTIALLY_CLOSED:
                self._project_position,

            ExecutionEventType.POSITION_REVERSED:
                self._project_position,

            ExecutionEventType.POSITION_CLOSED:
                self._project_position,

            #
            # Account
            #

            ExecutionEventType.MARGIN_CALL:
                self._project_account,

            ExecutionEventType.FLATTEN_ALL:
                self._project_account,

            ExecutionEventType.ACCOUNT_SYNCHRONIZED:
                self._project_account,

            #
            # Risk
            #

            ExecutionEventType.STOP_LOSS_TRIGGERED:
                self._project_position,

            ExecutionEventType.TAKE_PROFIT_TRIGGERED:
                self._project_position,

            ExecutionEventType.TRAILING_STOP_TRIGGERED:
                self._project_position,
        }

    # ==============================================================
    # Public API
    # ==============================================================

    def project_event(
        self,
        event: Dict[str, Any],
    ) -> None:

        handler = self.handlers.get(
            event.get("event_type")
        )

        if handler:
            handler(event)

        account_id = event.get("account_id")

        if account_id:
            account = self.replayer.replay_account(
                account_id=account_id,
            )

            self.snapshot_repository.project_snapshot(
                snapshot=account,
            )

    # --------------------------------------------------------------

    def project_order(
        self,
        broker_order_id: str,
    ) -> None:

        context = self.replayer.replay_order(
            broker_order_id=broker_order_id,
        )

        self.order_repository.project_order(
            context=context,
        )

    # --------------------------------------------------------------

    def project_position(
        self,
        position_id: str,
    ) -> None:

        context = self.replayer.replay_position(
            position_id=position_id,
        )

        if context.position is not None:
            self.position_repository.project_position(
                position=context.position,
            )

    # --------------------------------------------------------------

    def project_account(
        self,
        account_id: str,
    ) -> None:

        snapshot = self.replayer.replay_account(
            account_id=account_id,
        )

        self.account_repository.project_account(
            account=snapshot,
        )

    # --------------------------------------------------------------

    def project_snapshot(
            self,
            snapshot: Dict[str, Any],
    ) -> None:

        self.snapshot_repository.project_snapshot(
            snapshot=snapshot,
        )

    # ==============================================================
    # Full Rebuild
    # ==============================================================

    def rebuild_execution(
        self,
        execution_id: str,
    ) -> None:

        context = self.replayer.replay_execution(
            execution_id=execution_id,
        )

        self.order_repository.project_order(
            context=context,
        )

        if context.position is not None:
            self.position_repository.project_position(
                position=context.position,
            )



        if context.account_id:
            account = self.replayer.replay_account(
                account_id=context.account_id,
            )

            self.account_repository.project_account(
                account=account,
            )

            self.snapshot_repository.project_snapshot(
                snapshot=account,
            )

    # --------------------------------------------------------------

    def rebuild_orders(
        self,
        *,
        portfolio_id: Optional[str] = None,
    ) -> None:

        events = self.replayer.load_events(
            portfolio_id=portfolio_id,
        )

        seen = set()

        for event in events:

            broker_order_id = event.get(
                "broker_order_id"
            )

            if (
                not broker_order_id
                or broker_order_id in seen
            ):
                continue

            seen.add(
                broker_order_id
            )

            self.project_order(
                broker_order_id,
            )

    # --------------------------------------------------------------

    def rebuild_positions(
        self,
        *,
        portfolio_id: Optional[str] = None,
    ) -> None:

        events = self.replayer.load_events(
            portfolio_id=portfolio_id,
        )

        seen = set()

        for event in events:

            position_id = event.get(
                "position_id"
            )

            if (
                not position_id
                or position_id in seen
            ):
                continue

            seen.add(
                position_id
            )

            self.project_position(
                position_id,
            )

    # --------------------------------------------------------------

    def rebuild_accounts(self) -> None:

        rows = self.db.execute(
            """
            SELECT DISTINCT account_id
            FROM execution_events
            WHERE account_id IS NOT NULL
            """
        ).fetchall()

        for row in rows:

            self.project_account(
                row[0],
            )

    # --------------------------------------------------------------

    def rebuild_portfolio(
        self,
        portfolio_id: str,
    ) -> None:

        self.rebuild_orders(
            portfolio_id=portfolio_id,
        )

        self.rebuild_positions(
            portfolio_id=portfolio_id,
        )

        events = self.replayer.load_events(
            portfolio_id=portfolio_id,
        )

        processed = set()

        for event in events:

            account_id = event.get("account_id")

            if (
                    not account_id
                    or account_id in processed
            ):
                continue

            account = self.replayer.replay_account(
                account_id=account_id,
            )

            self.account_repository.project_account(
                account=account,
            )

            self.snapshot_repository.project_snapshot(
                snapshot=account,
            )

            processed.add(account_id)

    # --------------------------------------------------------------

    def rebuild_everything(
        self,
    ) -> None:

        self.rebuild_orders()

        self.rebuild_positions()



        events = self.replayer.load_events()

        processed = set()

        for event in events:

            account_id = event.get("account_id")

            if (
                    not account_id
                    or account_id in processed
            ):
                continue

            account = self.replayer.replay_account(
                account_id=account_id,
            )

            self.account_repository.project_account(
                account=account,
            )

            self.snapshot_repository.project_snapshot(
                snapshot=account,
            )

            processed.add(account_id)

    # ==============================================================
    # Internal Dispatchers
    # ==============================================================

    def _project_new_order(
        self,
        event: Dict[str, Any],
    ) -> None:

        broker_order_id = event.get(
            "broker_order_id"
        )

        if broker_order_id:

            self.project_order(
                broker_order_id,
            )

    # --------------------------------------------------------------

    def _project_order(
        self,
        event: Dict[str, Any],
    ) -> None:

        broker_order_id = event.get(
            "broker_order_id"
        )

        if broker_order_id:

            self.project_order(
                broker_order_id,
            )

    # --------------------------------------------------------------

    def _project_position(
        self,
        event: Dict[str, Any],
    ) -> None:

        position_id = event.get(
            "position_id"
        )

        if position_id:

            self.project_position(
                position_id,
            )

    # --------------------------------------------------------------

    def _project_account(
        self,
        event: Dict[str, Any],
    ) -> None:

        account_id = event.get(
            "account_id"
        )

        if account_id:

            self.project_account(
                account_id,
            )


# ======================================================================
# Factory
# ======================================================================

_PROJECTION: Optional[
    ExecutionEventProjection
] = None


def get_execution_event_projection(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventProjection:

    global _PROJECTION

    if (
        not cache
        or _PROJECTION is None
    ):

        _PROJECTION = (
            ExecutionEventProjection(
                db=db,
            )
        )

    return _PROJECTION