
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import json, uuid, hashlib

SCHEMA_VERSION=1

class AssetClass(str,Enum):
    FOREX="FOREX";EQUITIES="EQUITIES";OPTIONS="OPTIONS";CRYPTO="CRYPTO";FUTURES="FUTURES";UNKNOWN="UNKNOWN"
class ExecutionEventType(str, Enum):

    # ------------------------------------------------------------------
    # Order Lifecycle
    # ------------------------------------------------------------------

    NEW_ORDER = "NEW_ORDER"

    ORDER_VALIDATED = "ORDER_VALIDATED"

    ORDER_REJECTED = "ORDER_REJECTED"

    ORDER_PENDING = "ORDER_PENDING"

    ORDER_ACCEPTED = "ORDER_ACCEPTED"

    ORDER_MODIFIED = "ORDER_MODIFIED"

    ORDER_CANCELLED = "ORDER_CANCELLED"

    ORDER_EXPIRED = "ORDER_EXPIRED"

    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"

    ORDER_FILLED = "ORDER_FILLED"

    # ------------------------------------------------------------------
    # Position Lifecycle
    # ------------------------------------------------------------------

    POSITION_OPENED = "POSITION_OPENED"

    POSITION_MODIFIED = "POSITION_MODIFIED"

    POSITION_SCALED_IN = "POSITION_SCALED_IN"

    POSITION_SCALED_OUT = "POSITION_SCALED_OUT"

    POSITION_PARTIALLY_CLOSED = "POSITION_PARTIALLY_CLOSED"

    POSITION_CLOSED = "POSITION_CLOSED"

    POSITION_REVERSED = "POSITION_REVERSED"

    # ------------------------------------------------------------------
    # Risk
    # ------------------------------------------------------------------

    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"

    TAKE_PROFIT_TRIGGERED = "TAKE_PROFIT_TRIGGERED"

    TRAILING_STOP_TRIGGERED = "TRAILING_STOP_TRIGGERED"

    MARGIN_CALL = "MARGIN_CALL"

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    FLATTEN_ALL = "FLATTEN_ALL"

    ACCOUNT_SYNCHRONIZED = "ACCOUNT_SYNCHRONIZED"
class ExecutionActor(str,Enum):
    USER="USER";AI="AI";SYSTEM="SYSTEM";BROKER="BROKER"
class ExecutionSource(str,Enum):
    UI="UI";API="API";QUEUE="QUEUE";SCHEDULER="SCHEDULER"

def utc_now(): return datetime.now(timezone.utc)

@dataclass(frozen=True)
class ExecutionContext:
    actor:ExecutionActor=ExecutionActor.SYSTEM
    source:ExecutionSource=ExecutionSource.UI
    strategy:Optional[str]=None

@dataclass(frozen=True)
class ExecutionEvent:
    event_id:str=field(default_factory=lambda:str(uuid.uuid4()))
    schema_version:int=SCHEMA_VERSION
    event_type:ExecutionEventType=ExecutionEventType.NEW_ORDER
    occurred_at:datetime=field(default_factory=utc_now)
    asset_class:AssetClass=AssetClass.UNKNOWN
    account_id:Optional[str]=None
    portfolio_id:Optional[str]=None
    symbol:Optional[str]=None
    position_id:Optional[str]=None
    order_id:Optional[str]=None
    execution_id:Optional[str]=None
    correlation_id:Optional[str]=None
    causation_id:Optional[str]=None
    quantity:Optional[float]=None
    price:Optional[float]=None
    payload:Dict[str,Any]=field(default_factory=dict)
    metadata:Dict[str,Any]=field(default_factory=dict)
    context:ExecutionContext=field(default_factory=ExecutionContext)
    def to_dict(self):
        d=asdict(self);d["occurred_at"]=self.occurred_at.isoformat()
        for k in("event_type","asset_class"): d[k]=d[k].value
        d["context"]["actor"] = (
            self.context.actor.value
            if self.context.actor is not None
            else None
        )

        d["context"]["source"] = (
            self.context.source.value
            if self.context.source is not None
            else None
        )
        return d
    def checksum(self):
        return hashlib.sha256(json.dumps(self.to_dict(),sort_keys=True).encode()).hexdigest()
