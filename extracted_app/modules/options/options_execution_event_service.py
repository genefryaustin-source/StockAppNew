"""
modules/options/options_execution_event_service.py

Options Execution Event Service

Immutable, append-only record of what happened to every options order:
submitted, filled, partially filled, cancelled, rejected. Serves as both
the event stream and the audit trail for options execution -- unlike the
stock module (which has separate events/audit/attribution/AI-review
services built up over several sprints), options only needs the core
execution record for now. This can be split apart later if options grows
its own attribution/AI-review layer, the same way stocks did.

Never mutates or deletes a row once written.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class OptionsExecutionEventType(str, Enum):
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"


@dataclass(slots=True)
class OptionsExecutionEvent:
    event_id: str
    event_type: str
    timestamp: datetime

    tenant_id: Optional[str]
    user_id: Optional[str]

    order_id: Optional[str]
    broker_order_id: Optional[str]

    option_symbol: str
    underlying: Optional[str]
    side: Optional[str]

    qty: float
    filled_qty: float
    fill_price: Optional[float]

    status: Optional[str]
    metadata: Dict[str, Any]


class OptionsExecutionEventService:

    def __init__(self, db):
        self.db = db
        self._ensure_tables()

    # ======================================================
    # Bootstrap
    # ======================================================

    def _ensure_tables(self) -> None:
        if self.db is None:
            return

        try:
            self.db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS options_execution_events (

                        id BIGSERIAL PRIMARY KEY,

                        event_id VARCHAR(36) UNIQUE,
                        event_type VARCHAR(30),
                        event_timestamp TIMESTAMP,

                        tenant_id VARCHAR(100),
                        user_id VARCHAR(100),

                        order_id VARCHAR(36),
                        broker_order_id VARCHAR(100),

                        option_symbol VARCHAR(40),
                        underlying VARCHAR(20),
                        side VARCHAR(10),

                        qty DOUBLE PRECISION,
                        filled_qty DOUBLE PRECISION,
                        fill_price DOUBLE PRECISION,

                        status VARCHAR(30),
                        metadata TEXT
                    )
                    """
                )
            )
            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to initialize options_execution_events table.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Recording
    # ======================================================

    def record(
        self,
        *,
        event_type: OptionsExecutionEventType,
        tenant_id: Optional[str],
        user_id: Optional[str],
        order_id: Optional[str],
        broker_order_id: Optional[str],
        option_symbol: str,
        underlying: Optional[str] = None,
        side: Optional[str] = None,
        qty: float = 0.0,
        filled_qty: float = 0.0,
        fill_price: Optional[float] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OptionsExecutionEvent:

        event = OptionsExecutionEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type.value,
            timestamp=datetime.now(UTC),
            tenant_id=tenant_id,
            user_id=user_id,
            order_id=order_id,
            broker_order_id=broker_order_id,
            option_symbol=option_symbol,
            underlying=underlying,
            side=side,
            qty=float(qty or 0.0),
            filled_qty=float(filled_qty or 0.0),
            fill_price=float(fill_price) if fill_price is not None else None,
            status=status,
            metadata=metadata or {},
        )

        self._persist_event(event)

        logger.info(
            "Options Execution Event | %s | %s | %s",
            event.event_type,
            event.option_symbol,
            event.order_id,
        )

        return event

    def _persist_event(self, event: OptionsExecutionEvent) -> None:
        if self.db is None:
            return

        try:
            import json

            self.db.execute(
                text(
                    """
                    INSERT INTO options_execution_events (

                        event_id,
                        event_type,
                        event_timestamp,

                        tenant_id,
                        user_id,

                        order_id,
                        broker_order_id,

                        option_symbol,
                        underlying,
                        side,

                        qty,
                        filled_qty,
                        fill_price,

                        status,
                        metadata

                    )
                    VALUES (

                        :event_id,
                        :event_type,
                        :event_timestamp,

                        :tenant_id,
                        :user_id,

                        :order_id,
                        :broker_order_id,

                        :option_symbol,
                        :underlying,
                        :side,

                        :qty,
                        :filled_qty,
                        :fill_price,

                        :status,
                        :metadata
                    )
                    """
                ),
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "event_timestamp": event.timestamp,
                    "tenant_id": event.tenant_id,
                    "user_id": event.user_id,
                    "order_id": event.order_id,
                    "broker_order_id": event.broker_order_id,
                    "option_symbol": event.option_symbol,
                    "underlying": event.underlying,
                    "side": event.side,
                    "qty": event.qty,
                    "filled_qty": event.filled_qty,
                    "fill_price": event.fill_price,
                    "status": event.status,
                    "metadata": json.dumps(event.metadata, default=str),
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to persist options execution event.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Query API
    # ======================================================

    def get_events(
        self,
        *,
        tenant_id: Optional[str] = None,
        order_id: Optional[str] = None,
        option_symbol: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM options_execution_events
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        if tenant_id:
            sql += " AND tenant_id=:tenant_id"
            params["tenant_id"] = tenant_id

        if order_id:
            sql += " AND order_id=:order_id"
            params["order_id"] = order_id

        if option_symbol:
            sql += " AND option_symbol=:option_symbol"
            params["option_symbol"] = option_symbol

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
                self.db.execute(text(sql), params)
                .mappings()
                .all()
            )

            return [dict(row) for row in rows]

        except SQLAlchemyError:
            logger.exception("Unable to load options execution events.")
            return []

    def summary(self, *, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        records = self.get_events(tenant_id=tenant_id, limit=100000)

        counts: Dict[str, int] = {}
        for row in records:
            event_type = row["event_type"]
            counts[event_type] = counts.get(event_type, 0) + 1

        return {
            "event_count": len(records),
            "by_type": counts,
        }


_options_execution_event_service = None


def get_options_execution_event_service(db) -> OptionsExecutionEventService:
    global _options_execution_event_service

    if (
        _options_execution_event_service is None
        or _options_execution_event_service.db is not db
    ):
        _options_execution_event_service = OptionsExecutionEventService(db)

    return _options_execution_event_service