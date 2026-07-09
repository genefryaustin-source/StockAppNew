"""
forex_position_management_engine.py

Sprint FX
Phase 1A

Forex Position Management Engine

Core responsibilities

    • Load live positions
    • Refresh positions
    • Build ExecutionContext objects
    • Verification helpers
    • Repository integration

Execution actions (modify, close, reverse, scale, flatten)
are implemented in subsequent parts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.execution.execution_context import (
    ExecutionContext,
)

from modules.execution.execution_service import (
    ExecutionService,
    get_execution_service,
)

from modules.execution.execution_position_repository import (
    ExecutionPositionRepository,
)

from modules.execution.execution_snapshot_pipeline import (
    ExecutionSnapshotPipeline,
)

from modules.execution.execution_event_recorder import (
    ExecutionEventRecorder,
)


class ForexPositionManagementEngine:
    """
    Institutional Forex Position Manager.

    This class coordinates the execution framework and should
    never directly manipulate execution tables.

    All lifecycle changes flow through ExecutionService.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        *,
        db,
        portfolio_engine,
        actor: Optional[str] = None,
        source: str = "FOREX",
    ):

        self.db = db

        self.portfolio_engine = portfolio_engine

        self.actor = actor

        self.source = source

        self.execution_service: ExecutionService = (
            get_execution_service(
                db=db,
                portfolio_engine=portfolio_engine,
                actor=actor,
                source=source,
            )
        )

        self.repository = ExecutionPositionRepository(
            db=db,
        )

        self.snapshot_pipeline = (
            ExecutionSnapshotPipeline(
                db=db,
            )
        )

        self.recorder = (
            ExecutionEventRecorder(
                db=db,
                actor=actor,
                source=source,
            )
        )

    # ------------------------------------------------------------------
    # Position Loading
    # ------------------------------------------------------------------

    def load_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns every open position.
        """

        return self.repository.load_positions(

            account_id=account_id,

            portfolio_id=portfolio_id,

            tenant_id=tenant_id,

        )

    # ------------------------------------------------------------------

    def load_position(
        self,
        position_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Load a single position.
        """

        return self.repository.load_position(
            position_id,
        )

    # ------------------------------------------------------------------

    def load_symbol_positions(
        self,
        symbol: str,
        *,
        account_id=None,
    ) -> List[Dict[str, Any]]:

        rows = self.load_positions(
            account_id=account_id,
        )

        symbol = symbol.upper()

        return [

            row

            for row in rows

            if str(
                row.get(
                    "symbol",
                    "",
                )
            ).upper()
            == symbol

        ]

    # ------------------------------------------------------------------

    def refresh_positions(
        self,
        *,
        account_id=None,
        portfolio_id=None,
    ) -> List[Dict[str, Any]]:
        """
        Refresh position snapshots.

        Market pricing is handled elsewhere.
        """

        positions = self.load_positions(

            account_id=account_id,

            portfolio_id=portfolio_id,

        )

        for row in positions:

            try:

                context = self._build_context(
                    row,
                )

                self.snapshot_pipeline.refresh(
                    context,
                )

            except Exception:

                pass

        return self.load_positions(

            account_id=account_id,

            portfolio_id=portfolio_id,

        )

    # ------------------------------------------------------------------
    # Context Builder
    # ------------------------------------------------------------------

    def _build_context(
        self,
        position: Dict[str, Any],
    ) -> ExecutionContext:
        """
        Converts repository rows into ExecutionContext.
        """

        context = ExecutionContext()

        context.execution_id = position.get(
            "execution_id",
        )

        context.position_id = position.get(
            "position_id",
        )

        context.account_id = position.get(
            "account_id",
        )

        context.portfolio_id = position.get(
            "portfolio_id",
        )

        context.tenant_id = position.get(
            "tenant_id",
        )

        context.user_id = position.get(
            "user_id",
        )

        context.symbol = position.get(
            "symbol",
        )

        context.pair = position.get(
            "pair",
            position.get("symbol"),
        )

        context.side = position.get(
            "side",
        )

        context.quantity = position.get(
            "quantity",
            0,
        )

        context.units = context.quantity

        context.avg_price = position.get(
            "avg_price",
        )

        context.requested_price = position.get(
            "avg_price",
        )

        context.stop_price = position.get(
            "stop_price",
        )

        context.target_price = position.get(
            "target_price",
        )

        context.broker = position.get(
            "broker",
        )

        context.broker_order_id = position.get(
            "broker_order_id",
        )

        context.status = position.get(
            "status",
        )

        return context

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify(
        self,
        context: ExecutionContext,
    ) -> bool:
        """
        Delegates verification to the execution framework.
        """

        try:

            result = self.execution_service.verify_execution(
                context,
            )

            context.verified = bool(result)

            return bool(result)

        except Exception:

            context.verified = False

            return False

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def is_open(
        position: Dict[str, Any],
    ) -> bool:

        return str(

            position.get(
                "status",
                "",
            )

        ).upper() in {

            "OPEN",

            "ACTIVE",

            "LIVE",

        }

    @staticmethod
    def is_long(
        position: Dict[str, Any],
    ) -> bool:

        return str(

            position.get(
                "side",
                "",
            )

        ).upper() == "BUY"

    @staticmethod
    def is_short(
        position: Dict[str, Any],
    ) -> bool:

        return str(

            position.get(
                "side",
                "",
            )

        ).upper() == "SELL"

    # ------------------------------------------------------------------
    # Modify Position
    # ------------------------------------------------------------------

    def modify_position(
        self,
        position_id: str,
        *,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
    ) -> ExecutionContext:
        """
        Modify an existing Forex position.

        Only stop loss and take profit modifications are supported
        through this operation.
        """

        position = self.load_position(
            position_id,
        )

        if position is None:
            raise ValueError(
                f"Position '{position_id}' not found."
            )

        context = self._build_context(
            position,
        )

        result = self.execution_service.modify_position(

            context,

            stop_price=stop_price,

            target_price=target_price,

        )

        #
        # Refresh snapshot
        #

        try:

            self.snapshot_pipeline.refresh(
                result,
            )

        except Exception as exc:

            result.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        #
        # Verify
        #

        self.verify(
            result,
        )

        return result

    # ------------------------------------------------------------------
    # Close Position
    # ------------------------------------------------------------------

    def close_position(
        self,
        position_id: str,
        *,
        quantity: Optional[float] = None,
        requested_price: Optional[float] = None,
    ) -> ExecutionContext:
        """
        Close an existing position.

        If quantity is None the entire position is closed.

        Otherwise a partial close is performed.
        """

        position = self.load_position(
            position_id,
        )

        if position is None:

            raise ValueError(
                f"Position '{position_id}' not found."
            )

        context = self._build_context(
            position,
        )

        #
        # Full position quantity
        #

        if quantity is None:

            quantity = context.quantity

        result = self.execution_service.close_position(

            context,

            quantity=quantity,

            requested_price=requested_price,

        )

        #
        # Refresh snapshot
        #

        try:

            self.snapshot_pipeline.refresh(
                result,
            )

        except Exception as exc:

            result.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        #
        # Verify
        #

        self.verify(
            result,
        )

        return result

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def update_stop_loss(
        self,
        position_id: str,
        stop_price: float,
    ) -> ExecutionContext:

        return self.modify_position(

            position_id,

            stop_price=stop_price,

        )

    # ------------------------------------------------------------------

    def update_take_profit(
        self,
        position_id: str,
        target_price: float,
    ) -> ExecutionContext:

        return self.modify_position(

            position_id,

            target_price=target_price,

        )

    # ------------------------------------------------------------------

    def close_all_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[ExecutionContext]:
        """
        Close every open position.
        """

        results: List[
            ExecutionContext
        ] = []

        positions = self.load_positions(

            account_id=account_id,

            portfolio_id=portfolio_id,

        )

        for position in positions:

            if not self.is_open(
                position,
            ):
                continue

            try:

                result = self.close_position(

                    position[
                        "position_id"
                    ]

                )

                results.append(
                    result,
                )

            except Exception:
                #
                # Continue processing remaining positions.
                #
                continue

        return results
    # ------------------------------------------------------------------
    # Reverse Position
    # ------------------------------------------------------------------

    def reverse_position(
        self,
        position_id: str,
        *,
        requested_price: Optional[float] = None,
    ) -> ExecutionContext:
        """
        Reverse an existing Forex position.

        BUY  -> SELL
        SELL -> BUY

        The ExecutionService handles the complete lifecycle:

            POSITION_CLOSED
                    ↓
            POSITION_REVERSED
                    ↓
            POSITION_OPENED
        """

        position = self.load_position(
            position_id,
        )

        if position is None:

            raise ValueError(
                f"Position '{position_id}' not found."
            )

        context = self._build_context(
            position,
        )

        result = self.execution_service.reverse_position(

            context,

            requested_price=requested_price,

        )

        try:

            self.snapshot_pipeline.refresh(
                result,
            )

        except Exception as exc:

            result.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        self.verify(
            result,
        )

        return result

    # ------------------------------------------------------------------
    # Scale In
    # ------------------------------------------------------------------

    def scale_in(
        self,
        position_id: str,
        *,
        quantity: float,
        requested_price: Optional[float] = None,
    ) -> ExecutionContext:
        """
        Increase an existing position.

        The execution framework determines whether this becomes

            POSITION_SCALED_IN

        or

            POSITION_MODIFIED
        """

        if quantity <= 0:

            raise ValueError(
                "Scale quantity must be greater than zero."
            )

        position = self.load_position(
            position_id,
        )

        if position is None:

            raise ValueError(
                f"Position '{position_id}' not found."
            )

        context = self._build_context(
            position,
        )

        #
        # New total position size
        #

        new_quantity = (
            float(context.quantity)
            + float(quantity)
        )

        result = self.execution_service.modify_position(

            context,

            quantity=new_quantity,

            requested_price=requested_price,

        )

        #
        # Immutable Event
        #

        try:

            event = self.recorder.position_scaled_in(
                result,
            )

            if (
                event is not None
                and hasattr(result, "add_event")
            ):

                result.add_event(
                    event,
                )

        except Exception as exc:

            result.add_warning(
                f"Event recording failed: {exc}"
            )

        try:

            self.snapshot_pipeline.refresh(
                result,
            )

        except Exception as exc:

            result.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        self.verify(
            result,
        )

        return result

    # ------------------------------------------------------------------
    # Scale Out
    # ------------------------------------------------------------------

    def scale_out(
        self,
        position_id: str,
        *,
        quantity: float,
        requested_price: Optional[float] = None,
    ) -> ExecutionContext:
        """
        Reduce an existing position.

        If the requested quantity equals the current position
        size, this becomes a normal close_position().
        """

        if quantity <= 0:

            raise ValueError(
                "Scale quantity must be greater than zero."
            )

        position = self.load_position(
            position_id,
        )

        if position is None:

            raise ValueError(
                f"Position '{position_id}' not found."
            )

        context = self._build_context(
            position,
        )

        #
        # Entire position?
        #

        if quantity >= context.quantity:

            return self.close_position(

                position_id,

                quantity=context.quantity,

                requested_price=requested_price,

            )

        #
        # Remaining quantity
        #

        remaining = (
            float(context.quantity)
            - float(quantity)
        )

        result = self.execution_service.modify_position(

            context,

            quantity=remaining,

            requested_price=requested_price,

        )

        #
        # Immutable Event
        #

        try:

            event = self.recorder.position_scaled_out(
                result,
            )

            if (
                event is not None
                and hasattr(result, "add_event")
            ):

                result.add_event(
                    event,
                )

        except Exception as exc:

            result.add_warning(
                f"Event recording failed: {exc}"
            )

        try:

            self.snapshot_pipeline.refresh(
                result,
            )

        except Exception as exc:

            result.add_warning(
                f"Snapshot refresh failed: {exc}"
            )

        self.verify(
            result,
        )

        return result

    # ------------------------------------------------------------------
    # Convenience Helpers
    # ------------------------------------------------------------------

    def add_units(
        self,
        position_id: str,
        units: float,
    ) -> ExecutionContext:

        return self.scale_in(

            position_id,

            quantity=units,

        )

    # ------------------------------------------------------------------

    def reduce_units(
        self,
        position_id: str,
        units: float,
    ) -> ExecutionContext:

        return self.scale_out(

            position_id,

            quantity=units,

        )

        # ------------------------------------------------------------------
        # Flatten Account
        # ------------------------------------------------------------------

        def flatten_account(
                self,
                *,
                account_id: str,
        ) -> List[ExecutionContext]:
            """
            Close every open position for an account.
            """

            results: List[ExecutionContext] = []

            positions = self.load_positions(
                account_id=account_id,
            )

            for position in positions:

                if not self.is_open(position):
                    continue

                try:

                    result = self.close_position(
                        position["position_id"],
                    )

                    results.append(result)

                except Exception:
                    continue

            return results

        # ------------------------------------------------------------------
        # Flatten Portfolio
        # ------------------------------------------------------------------

        def flatten_portfolio(
                self,
                *,
                portfolio_id: str,
        ) -> List[ExecutionContext]:

            results: List[ExecutionContext] = []

            positions = self.load_positions(
                portfolio_id=portfolio_id,
            )

            for position in positions:

                if not self.is_open(position):
                    continue

                try:

                    results.append(

                        self.close_position(
                            position["position_id"],
                        )

                    )

                except Exception:
                    pass

            return results

        # ------------------------------------------------------------------
        # Flatten Symbol
        # ------------------------------------------------------------------

        def flatten_symbol(
                self,
                *,
                symbol: str,
                account_id: Optional[str] = None,
        ) -> List[ExecutionContext]:

            results: List[ExecutionContext] = []

            positions = self.load_symbol_positions(

                symbol,

                account_id=account_id,

            )

            for position in positions:

                if not self.is_open(position):
                    continue

                try:

                    results.append(

                        self.close_position(

                            position["position_id"]

                        )

                    )

                except Exception:
                    pass

            return results

        # ------------------------------------------------------------------
        # Refresh Snapshots
        # ------------------------------------------------------------------

        def refresh_all_snapshots(
                self,
                *,
                account_id=None,
                portfolio_id=None,
        ) -> int:

            refreshed = 0

            positions = self.load_positions(

                account_id=account_id,

                portfolio_id=portfolio_id,

            )

            for row in positions:

                try:

                    context = self._build_context(
                        row,
                    )

                    self.snapshot_pipeline.refresh(
                        context,
                    )

                    refreshed += 1

                except Exception:
                    pass

            return refreshed

        # ------------------------------------------------------------------
        # Verify All Positions
        # ------------------------------------------------------------------

        def verify_all_positions(
                self,
                *,
                account_id=None,
                portfolio_id=None,
        ) -> Dict[str, Any]:

            verified = 0

            failed = 0

            positions = self.load_positions(

                account_id=account_id,

                portfolio_id=portfolio_id,

            )

            for row in positions:

                context = self._build_context(
                    row,
                )

                if self.verify(context):

                    verified += 1

                else:

                    failed += 1

            return {

                "positions": len(positions),

                "verified": verified,

                "failed": failed,

            }

        # ------------------------------------------------------------------
        # Synchronize
        # ------------------------------------------------------------------

        def synchronize_positions(
                self,
                *,
                account_id=None,
                portfolio_id=None,
        ) -> Dict[str, Any]:
            """
            Refresh snapshots then verify every position.
            """

            refreshed = self.refresh_all_snapshots(

                account_id=account_id,

                portfolio_id=portfolio_id,

            )

            verification = self.verify_all_positions(

                account_id=account_id,

                portfolio_id=portfolio_id,

            )

            return {

                "snapshots_refreshed": refreshed,

                "verification": verification,

            }

        # ------------------------------------------------------------------
        # Health
        # ------------------------------------------------------------------

        def health(self) -> Dict[str, Any]:

            return {

                "healthy": True,

                "service": self.__class__.__name__,

                "version": "FX-1",

                "last_check": "OK",

                "capabilities": [

                    "load_positions",

                    "modify_position",

                    "close_position",

                    "reverse_position",

                    "scale_in",

                    "scale_out",

                    "flatten_account",

                    "flatten_portfolio",

                    "flatten_symbol",

                    "verify",

                    "snapshot_refresh",

                ],

            }

# ==============================================================================
# Singleton Factory
# ==============================================================================

_POSITION_MANAGER: Optional[
    ForexPositionManagementEngine
] = None

def get_forex_position_management_engine(
        *,
        db,
        portfolio_engine,
        actor=None,
        source="FOREX",
        cache: bool = True,
) -> ForexPositionManagementEngine:

    global _POSITION_MANAGER

    if (

            not cache

            or _POSITION_MANAGER is None

    ):
        _POSITION_MANAGER = ForexPositionManagementEngine(

            db=db,

            portfolio_engine=portfolio_engine,

            actor=actor,

            source=source,

        )

    return _POSITION_MANAGER