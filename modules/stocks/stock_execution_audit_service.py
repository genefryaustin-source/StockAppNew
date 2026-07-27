"""
modules/stocks/stock_execution_audit_service.py

Institutional Execution Audit Service

This service provides a complete immutable audit trail for every
trading action executed within the platform.

Responsibilities
----------------
• Regulatory Audit
• Compliance History
• Order Lifecycle
• Position Lifecycle
• Broker Communication
• User Activity
• Trade Replay
• Executive Reporting

This service NEVER executes trades.

It only consumes immutable execution events.
"""

from __future__ import annotations

import json
import logging

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ==========================================================
# Audit Record
# ==========================================================


@dataclass(slots=True)
class ExecutionAuditRecord:

    audit_id: Optional[int]

    event_id: str

    order_id: Optional[int]

    position_id: Optional[int]

    tenant_id: Optional[str]

    portfolio_id: Optional[str]

    user_id: Optional[str]

    symbol: str

    side: str

    event_type: str

    event_timestamp: datetime

    broker: Optional[str]

    broker_order_id: Optional[str]

    status: Optional[str]

    metadata: Dict[str, Any]

    created_at: datetime


# ==========================================================
# Audit Service
# ==========================================================


class StockExecutionAuditService:

    """
    Immutable execution audit service.
    """

    def __init__(
        self,
        db,
    ):

        self.db = db

        self._ensure_tables()

    # ======================================================
    # Bootstrap
    # ======================================================

    def _ensure_tables(self):

        if self.db is None:
            return

        try:

            self.db.execute(

                text(
                    """
                    CREATE TABLE IF NOT EXISTS stock_execution_audit (

                        audit_id BIGSERIAL PRIMARY KEY,

                        event_id VARCHAR(36) NOT NULL,

                        order_id BIGINT,

                        position_id BIGINT,

                        tenant_id VARCHAR(100),

                        portfolio_id VARCHAR(100),

                        user_id VARCHAR(100),

                        symbol VARCHAR(20),

                        side VARCHAR(10),

                        event_type VARCHAR(80),

                        event_timestamp TIMESTAMP,

                        broker VARCHAR(50),

                        broker_order_id VARCHAR(100),

                        status VARCHAR(50),

                        metadata TEXT,

                        created_at TIMESTAMP
                    )
                    """
                )

            )

            self.db.execute(

                text(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_stock_execution_audit_event
                    ON stock_execution_audit(event_id)
                    """
                )

            )

            self.db.execute(

                text(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_stock_execution_audit_order
                    ON stock_execution_audit(order_id)
                    """
                )

            )

            self.db.execute(

                text(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_stock_execution_audit_position
                    ON stock_execution_audit(position_id)
                    """
                )

            )

            self.db.commit()

        except SQLAlchemyError:

            logger.exception(
                "Unable to initialize audit tables."
            )

            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _serialize_metadata(
        metadata: Any,
    ) -> str:

        try:

            return json.dumps(
                metadata,
                default=str,
            )

        except Exception:

            return "{}"

    @staticmethod
    def _deserialize_metadata(
        value: Any,
    ) -> Dict[str, Any]:

        if not value:

            return {}

        try:

            return json.loads(value)

        except Exception:

            return {}

    # ======================================================
    # Public API
    # ======================================================

    def record_event(
        self,
        event: Any,
    ) -> ExecutionAuditRecord:
        """
        Persists an immutable execution audit record.

        Persistence implementation continues
        in Part 2.
        """

        return ExecutionAuditRecord(

            audit_id=None,

            event_id=getattr(
                event,
                "event_id",
                "",
            ),

            order_id=getattr(
                event,
                "order_id",
                None,
            ),

            position_id=getattr(
                event,
                "position_id",
                None,
            ),

            tenant_id=getattr(
                event,
                "tenant_id",
                None,
            ),

            portfolio_id=getattr(
                event,
                "portfolio_id",
                None,
            ),

            user_id=getattr(
                event,
                "user_id",
                None,
            ),

            symbol=getattr(
                event,
                "symbol",
                "",
            ),

            side=getattr(
                event,
                "side",
                "",
            ),

            event_type=getattr(
                event,
                "event_type",
                "",
            ),

            event_timestamp=getattr(
                event,
                "timestamp",
                datetime.now(UTC),
            ),

            broker=getattr(
                event,
                "broker",
                None,
            ),

            broker_order_id=getattr(
                event,
                "broker_order_id",
                None,
            ),

            status=getattr(
                event,
                "status",
                None,
            ),

            metadata=getattr(
                event,
                "metadata",
                {},
            ),

            created_at=datetime.now(
                UTC,
            ),
        )

    # ======================================================
    # Persistence
    # ======================================================

    def _persist_record(
            self,
            record: ExecutionAuditRecord,
    ) -> None:
        """
        Persist an immutable audit record.
        """

        if self.db is None:
            return

        try:

            self.db.execute(

                text(
                    """
                    INSERT INTO stock_execution_audit (

                        event_id,

                        order_id,
                        position_id,

                        tenant_id,
                        portfolio_id,
                        user_id,

                        symbol,
                        side,

                        event_type,
                        event_timestamp,

                        broker,
                        broker_order_id,

                        status,

                        metadata,

                        created_at

                    )
                    VALUES (

                        :event_id,

                        :order_id,
                        :position_id,

                        :tenant_id,
                        :portfolio_id,
                        :user_id,

                        :symbol,
                        :side,

                        :event_type,
                        :event_timestamp,

                        :broker,
                        :broker_order_id,

                        :status,

                        :metadata,

                        :created_at
                    )
                    """
                ),

                {

                    "event_id":
                        record.event_id,

                    "order_id":
                        record.order_id,

                    "position_id":
                        record.position_id,

                    "tenant_id":
                        record.tenant_id,

                    "portfolio_id":
                        record.portfolio_id,

                    "user_id":
                        record.user_id,

                    "symbol":
                        record.symbol,

                    "side":
                        record.side,

                    "event_type":
                        record.event_type,

                    "event_timestamp":
                        record.event_timestamp,

                    "broker":
                        record.broker,

                    "broker_order_id":
                        record.broker_order_id,

                    "status":
                        record.status,

                    "metadata":
                        self._serialize_metadata(
                            record.metadata,
                        ),

                    "created_at":
                        record.created_at,
                },

            )

            self.db.commit()

        except SQLAlchemyError:

            logger.exception(
                "Unable to persist execution audit record."
            )

            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Public API
    # ======================================================

    def record_event(
            self,
            event: Any,
    ) -> ExecutionAuditRecord:
        """
        Create and persist an immutable audit record.
        """

        record = ExecutionAuditRecord(

            audit_id=None,

            event_id=getattr(
                event,
                "event_id",
                "",
            ),

            order_id=getattr(
                event,
                "order_id",
                None,
            ),

            position_id=getattr(
                event,
                "position_id",
                None,
            ),

            tenant_id=getattr(
                event,
                "tenant_id",
                None,
            ),

            portfolio_id=getattr(
                event,
                "portfolio_id",
                None,
            ),

            user_id=getattr(
                event,
                "user_id",
                None,
            ),

            symbol=getattr(
                event,
                "symbol",
                "",
            ),

            side=getattr(
                event,
                "side",
                "",
            ),

            event_type=getattr(
                event,
                "event_type",
                "",
            ),

            event_timestamp=getattr(
                event,
                "timestamp",
                datetime.now(
                    UTC,
                ),
            ),

            broker=getattr(
                event,
                "broker",
                None,
            ),

            broker_order_id=getattr(
                event,
                "broker_order_id",
                None,
            ),

            status=getattr(
                event,
                "status",
                None,
            ),

            metadata=getattr(
                event,
                "metadata",
                {},
            ),

            created_at=datetime.now(
                UTC,
            ),
        )

        self._persist_record(
            record,
        )

        logger.info(

            "Execution Audit | %s | %s | %s",

            record.event_type,

            record.symbol,

            record.order_id,
        )

        return record

    # ======================================================
    # Query API
    # ======================================================

    def get_audit_records(
            self,
            *,
            order_id: Optional[int] = None,
            position_id: Optional[int] = None,
            symbol: Optional[str] = None,
            portfolio_id: Optional[str] = None,
            user_id: Optional[str] = None,
            event_type: Optional[str] = None,
            limit: int = 250,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM stock_execution_audit
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        if order_id is not None:
            sql += " AND order_id=:order_id"

            params["order_id"] = order_id

        if position_id is not None:
            sql += " AND position_id=:position_id"

            params["position_id"] = position_id

        if portfolio_id:
            sql += " AND portfolio_id=:portfolio_id"

            params["portfolio_id"] = portfolio_id

        if user_id:
            sql += " AND user_id=:user_id"

            params["user_id"] = user_id

        if symbol:
            sql += " AND UPPER(symbol)=:symbol"

            params["symbol"] = symbol.upper()

        if event_type:
            sql += " AND event_type=:event_type"

            params["event_type"] = event_type

        sql += """
            ORDER BY event_timestamp DESC
            LIMIT :limit
        """

        params["limit"] = limit

        try:

            rows = (

                self.db.execute(
                    text(sql),
                    params,
                )

                .mappings()

                .all()

            )

            results = []

            for row in rows:
                item = dict(row)

                item["metadata"] = (

                    self._deserialize_metadata(
                        item.get(
                            "metadata",
                        )
                    )

                )

                results.append(
                    item,
                )

            return results

        except SQLAlchemyError:

            logger.exception(
                "Unable to load execution audit records."
            )

            return []

    # ======================================================
    # Timeline / Replay API
    # ======================================================

    def get_order_timeline(
            self,
            *,
            order_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Returns the complete lifecycle for an order.

        Example:

            ORDER_CREATED
            ORDER_SUBMITTED
            ORDER_ACCEPTED
            ORDER_FILLED
            POSITION_OPENED
            POSITION_CLOSED
        """

        return self.get_audit_records(
            order_id=order_id,
            limit=1000,
        )

    def get_position_timeline(
            self,
            *,
            position_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Returns the complete lifecycle for a position.
        """

        return self.get_audit_records(
            position_id=position_id,
            limit=1000,
        )

    # ======================================================
    # Compliance Dashboard
    # ======================================================

    def compliance_summary(
            self,
    ) -> Dict[str, Any]:

        records = self.get_audit_records(
            limit=100000,
        )

        summary = {

            "events": len(records),

            "orders_created": 0,

            "orders_submitted": 0,

            "orders_filled": 0,

            "orders_cancelled": 0,

            "orders_rejected": 0,

            "positions_opened": 0,

            "positions_closed": 0,

            "position_reversals": 0,

            "stop_losses": 0,

            "take_profits": 0,

            "flatten_events": 0,
        }

        for row in records:

            event = row.get(
                "event_type",
            )

            if event == "ORDER_CREATED":

                summary["orders_created"] += 1

            elif event == "ORDER_SUBMITTED":

                summary["orders_submitted"] += 1

            elif event == "ORDER_FILLED":

                summary["orders_filled"] += 1

            elif event == "ORDER_CANCELLED":

                summary["orders_cancelled"] += 1

            elif event == "ORDER_REJECTED":

                summary["orders_rejected"] += 1

            elif event == "POSITION_OPENED":

                summary["positions_opened"] += 1

            elif event == "POSITION_CLOSED":

                summary["positions_closed"] += 1

            elif event == "POSITION_REVERSED":

                summary["position_reversals"] += 1

            elif event == "STOP_LOSS_TRIGGERED":

                summary["stop_losses"] += 1

            elif event == "TAKE_PROFIT_TRIGGERED":

                summary["take_profits"] += 1

            elif event == "FLATTEN_PORTFOLIO":

                summary["flatten_events"] += 1

        return summary

    # ======================================================
    # Trade Replay
    # ======================================================

    def build_trade_replay(
            self,
            *,
            order_id: Optional[int] = None,
            position_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Produces a replay package that can be consumed
        by future Trade Replay dashboards.
        """

        if order_id is not None:

            timeline = self.get_order_timeline(
                order_id=order_id,
            )

        elif position_id is not None:

            timeline = self.get_position_timeline(
                position_id=position_id,
            )

        else:

            timeline = []

        return {

            "event_count":
                len(timeline),

            "timeline":
                timeline,

            "first_event":
                timeline[0]
                if timeline
                else None,

            "last_event":
                timeline[-1]
                if timeline
                else None,
        }

# ==========================================================
# Factory
# ==========================================================

_audit_service = None

def get_stock_execution_audit_service(
        db,
) -> StockExecutionAuditService:

    global _audit_service

    if (

            _audit_service is None

            or _audit_service.db is not db

    ):
        _audit_service = (

            StockExecutionAuditService(
                db,
            )

        )

    return _audit_service