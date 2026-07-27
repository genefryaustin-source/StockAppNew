"""
modules/execution/execution_context.py

Sprint 26
Institutional Execution Framework

Immutable execution context passed through every execution pipeline.

The context represents the complete state of a single execution request
from validation through settlement.

Forex
Equities
Options
Crypto

all share this object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat()


@dataclass(slots=True)
class ExecutionContext:
    """
    Immutable execution context.

    Pipelines should modify fields directly only when progressing
    through execution stages.

    Every execution pipeline receives the SAME context object.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # Tenant
    # ------------------------------------------------------------------

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    account_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Asset
    # ------------------------------------------------------------------

    asset_class: str = "FOREX"

    symbol: Optional[str] = None
    pair: Optional[str] = None

    side: Optional[str] = None

    quantity: float = 0.0
    units: float = 0.0
    lots: float = 0.0

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    requested_price: Optional[float] = None
    execution_price: Optional[float] = None

    stop_price: Optional[float] = None
    target_price: Optional[float] = None

    average_fill_price: Optional[float] = None

    filled_quantity: float = 0.0

    remaining_quantity: float = 0.0

    fill_count: int = 0

    commission: float = 0.0

    slippage: float = 0.0

    # ------------------------------------------------------------------
    # Broker
    # ------------------------------------------------------------------

    broker: str = "paper"

    broker_order_id: Optional[str] = None
    broker_trade_id: Optional[str] = None

    parent_order_id: Optional[str] = None

    child_order_id: Optional[str] = None

    replacement_order_id: Optional[str] = None

    order_type: str = "MARKET"

    leverage: Optional[float] = None

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    position_id: Optional[str] = None

    parent_position_id: Optional[str] = None

    child_position_id: Optional[str] = None

    position_version: int = 1

    position: Optional[Any] = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    validation: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    event_ids: Dict[str, str] = field(default_factory=dict)

    events: List[Any] = field(default_factory=list)

    #
    # Event Tracking
    #

    last_event_id: Optional[str] = None

    last_event_type: Optional[str] = None

    event_count: int = 0

    event_stream_complete: bool = False

    replay_version: int = 1

    # ------------------------------------------------------------------
    # Runtime Objects
    # ------------------------------------------------------------------

    account: Optional[Any] = None

    snapshot: Optional[Any] = None

    repository: Optional[Any] = None

    current_stage: str = "NEW"

    pipeline_name: str = ""

    pipeline_version: str = "2.0"

    pipeline_history: List[str] = field(default_factory=list)

    execution_engine: Optional[Any] = None

    event_recorder: Optional[Any] = None

    # ------------------------------------------------------------------
    # Raw Request
    # ------------------------------------------------------------------

    raw_request: Dict[str, Any] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    status: str = "NEW"

    message: str = ""

    errors: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    verified: bool = False

    verification: Dict[str, Any] = field(default_factory=dict)

    risk_score: Optional[float] = None

    margin_required: Optional[float] = None

    margin_used: Optional[float] = None

    buying_power_before: Optional[float] = None

    buying_power_after: Optional[float] = None

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    created_at: datetime = field(default_factory=utc_now)

    validated_at: Optional[datetime] = None

    submitted_at: Optional[datetime] = None

    filled_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None

    snapshot_refreshed_at: Optional[datetime] = None

    synchronized_at: Optional[datetime] = None
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def successful(self) -> bool:
        return self.status.upper() in {
            "FILLED",
            "OPEN",
            "COMPLETED",
            "SUCCESS",
        }

    @property
    def failed(self) -> bool:
        return len(self.errors) > 0

    @property
    def rejected(self) -> bool:
        return self.status.upper() == "REJECTED"

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_error(self, message: str) -> None:
        self.errors.append(str(message))

    def add_warning(self, message: str) -> None:
        self.warnings.append(str(message))

    def add_event(self, event: Any) -> None:
        self.events.append(event)

        event_id = getattr(event, "event_id", None)

        event_type = getattr(event, "event_type", None)

        if event_type is not None and event_id is not None:
            key = getattr(event_type, "value", str(event_type))
            self.event_ids[key] = event_id

    def set_status(self, status: str) -> None:
        self.status = status.upper()

    def mark_validated(self) -> None:
        self.validated_at = utc_now()

    def mark_submitted(self) -> None:
        self.submitted_at = utc_now()

    def mark_filled(self) -> None:
        self.status = "FILLED"
        self.filled_at = utc_now()
        self.completed_at = self.filled_at

    def mark_completed(self) -> None:
        self.completed_at = utc_now()

    def mark_snapshot_refreshed(self) -> None:
        self.snapshot_refreshed_at = utc_now()

    def mark_synchronized(self) -> None:
        self.synchronized_at = utc_now()

    # ==========================================================
    # Lifecycle Helpers
    # ==========================================================

    def mark_pending(self) -> None:
        self.status = "PENDING"
        self.completed_at = utc_now()

    def mark_filled(self) -> None:
        self.status = "FILLED"
        self.filled_at = utc_now()
        self.completed_at = self.filled_at

    def mark_rejected(
            self,
            reason: str,
            *,
            errors=None,
            warnings=None,
    ) -> None:

        self.status = "REJECTED"
        self.message = reason
        self.completed_at = utc_now()

        self.add_error(reason)

        for error in errors or []:
            self.add_error(error)

        for warning in warnings or []:
            self.add_warning(warning)

    def mark_cancelled(self) -> None:
        self.status = "CANCELLED"
        self.completed_at = utc_now()

    def mark_expired(self) -> None:
        self.status = "EXPIRED"
        self.completed_at = utc_now()

    def set_position(self, position: Any) -> None:
        self.position = position

        self.position_id = getattr(
            position,
            "id",
            None,
        )

    def set_snapshot(
            self,
            snapshot: Any,
    ) -> None:
        self.snapshot = snapshot

        self.mark_snapshot_refreshed()

    def mark_execution(
            self,
            *,
            execution_price: float,
    ) -> None:
        self.execution_price = execution_price
        self.average_fill_price = execution_price
        self.mark_filled()

    def set_verification(
            self,
            verification: Dict[str, Any],
    ) -> None:
        self.verification = verification

        self.verified = verification.get(
            "verified",
            False,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "portfolio_id": self.portfolio_id,
            "account_id": self.account_id,
            "asset_class": self.asset_class,
            "symbol": self.symbol,
            "pair": self.pair,
            "side": self.side,
            "quantity": self.quantity,
            "units": self.units,
            "lots": self.lots,
            "requested_price": self.requested_price,
            "execution_price": self.execution_price,
            "average_fill_price": self.average_fill_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "broker": self.broker,
            "broker_order_id": self.broker_order_id,
            "broker_trade_id": self.broker_trade_id,
            "order_type": self.order_type,
            "position_id": self.position_id,
            "status": self.status,
            "message": self.message,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "event_ids": dict(self.event_ids),
            "created_at": self.created_at.isoformat(),
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "validated_at": (
                self.validated_at.isoformat()
                if self.validated_at
                else None
            ),
            "submitted_at": (
                self.submitted_at.isoformat()
                if self.submitted_at
                else None
            ),
            "filled_at": (
                self.filled_at.isoformat()
                if self.filled_at
                else None
            ),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),

            #
            # Sprint 26
            #

            "verified": self.verified,

            "verification": self.verification,

            "snapshot_refreshed_at": (
                self.snapshot_refreshed_at.isoformat()
                if self.snapshot_refreshed_at
                else None
            ),

            "synchronized_at": (
                self.synchronized_at.isoformat()
                if self.synchronized_at
                else None
            ),
        }


    def to_response(self) -> Dict[str, Any]:
        """
        Standard execution pipeline response.
        """
        response = self.to_dict()

        response.update(
            {
                "validation": self.validation,
                "event_ids": dict(self.event_ids),
                "snapshot": self.snapshot,
                "position": (
                    self.position.to_dict()
                    if hasattr(self.position, "to_dict")
                    else self.position
                ),
            }
        )

        return response

    def add_event(
            self,
            event,
    ):

        self.events.append(event)

        self.event_count += 1

        self.last_event_id = event.event_id

        self.last_event_type = event.event_type

    def advance_stage(
            self,
            stage: str,
    ):

        self.current_stage = stage

        self.pipeline_history.append(stage)

    def add_fill(
            self,
            quantity: float,
            price: float,
    ):

        self.filled_quantity += quantity

        self.remaining_quantity = max(
            0.0,
            self.quantity - self.filled_quantity,
        )

        self.average_fill_price = price

        self.fill_count += 1

    def mark_replayed(
            self,
    ):

        self.event_stream_complete = True

