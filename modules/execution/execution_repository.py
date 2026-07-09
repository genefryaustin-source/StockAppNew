
"""
execution_repository.py

Production repository (core implementation)
"""

from __future__ import annotations

import json
from typing import Iterable, List, Optional

from sqlalchemy import text

from .execution_models import ExecutionEvent
from .execution_schema import ExecutionSchema
from .execution_event_validator import ExecutionEventValidator


class ExecutionRepository:
    """Append-only repository for execution events."""

    def __init__(self, db, validator: Optional[ExecutionEventValidator] = None):
        self.db = db
        self.validator = validator or ExecutionEventValidator()
        if self.db is not None:
            ExecutionSchema(self.db).ensure()

    def _serialize(self, event: ExecutionEvent) -> dict:
        d = event.to_dict()
        d["payload"] = json.dumps(d.get("payload", {}), default=str)
        d["metadata"] = json.dumps(d.get("metadata", {}), default=str)
        return d

    @staticmethod
    def _deserialize(row) -> ExecutionEvent:
        data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
        data["payload"] = json.loads(data.get("payload") or "{}")
        data["metadata"] = json.loads(data.get("metadata") or "{}")
        return ExecutionEvent(**{k: v for k, v in data.items() if k in ExecutionEvent.__dataclass_fields__})

    def exists(self, event_id: str) -> bool:
        sql = text("SELECT 1 FROM execution_events WHERE event_id=:id LIMIT 1")
        return self.db.execute(sql, {"id": event_id}).first() is not None

    def append(self, event: ExecutionEvent) -> ExecutionEvent:
        self.validator.validate(event)
        if self.exists(event.event_id):
            raise ValueError(f"Duplicate event_id: {event.event_id}")

        e = self._serialize(event)

        sql = text("""
        INSERT INTO execution_events(
            event_id,schema_version,event_type,occurred_at,
            account_id,portfolio_id,asset_class,symbol,
            position_id,order_id,execution_id,
            correlation_id,causation_id,
            quantity,price,payload,metadata)
        VALUES(
            :event_id,:schema_version,:event_type,:occurred_at,
            :account_id,:portfolio_id,:asset_class,:symbol,
            :position_id,:order_id,:execution_id,
            :correlation_id,:causation_id,
            :quantity,:price,:payload,:metadata)
        """)

        self.db.execute(sql, e)
        self.db.commit()
        return event

    def append_if_new(self, event: ExecutionEvent) -> bool:
        if self.exists(event.event_id):
            return False
        self.append(event)
        return True

    def append_many(self, events: Iterable[ExecutionEvent]) -> int:
        count = 0
        try:
            for event in events:
                self.validator.validate(event)
                if not self.exists(event.event_id):
                    self.db.execute(text("""
                    INSERT INTO execution_events(
                        event_id,schema_version,event_type,occurred_at,
                        account_id,portfolio_id,asset_class,symbol,
                        position_id,order_id,execution_id,
                        correlation_id,causation_id,
                        quantity,price,payload,metadata)
                    VALUES(
                        :event_id,:schema_version,:event_type,:occurred_at,
                        :account_id,:portfolio_id,:asset_class,:symbol,
                        :position_id,:order_id,:execution_id,
                        :correlation_id,:causation_id,
                        :quantity,:price,:payload,:metadata)
                    """), self._serialize(event))
                    count += 1
            self.db.commit()
            return count
        except Exception:
            self.db.rollback()
            raise

    def get_event(self, event_id: str) -> Optional[ExecutionEvent]:
        row = self.db.execute(
            text("SELECT * FROM execution_events WHERE event_id=:id"),
            {"id": event_id},
        ).first()
        return None if row is None else self._deserialize(row)

    def get_recent(self, limit: int = 100) -> List[ExecutionEvent]:
        rows = self.db.execute(
            text("SELECT * FROM execution_events ORDER BY occurred_at DESC LIMIT :n"),
            {"n": int(limit)},
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def get_by_portfolio(self, portfolio_id: str) -> List[ExecutionEvent]:
        rows = self.db.execute(
            text("""SELECT * FROM execution_events
                    WHERE portfolio_id=:p
                    ORDER BY occurred_at"""),
            {"p": portfolio_id},
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def get_by_position(self, position_id: str) -> List[ExecutionEvent]:
        rows = self.db.execute(
            text("""SELECT * FROM execution_events
                    WHERE position_id=:p
                    ORDER BY occurred_at"""),
            {"p": position_id},
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def get_by_order(self, order_id: str) -> List[ExecutionEvent]:
        rows = self.db.execute(
            text("SELECT * FROM execution_events WHERE order_id=:o ORDER BY occurred_at"),
            {"o": order_id},
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def get_by_execution(self, execution_id: str) -> List[ExecutionEvent]:
        rows = self.db.execute(
            text("SELECT * FROM execution_events WHERE execution_id=:e ORDER BY occurred_at"),
            {"e": execution_id},
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def get_by_symbol(self, symbol: str) -> List[ExecutionEvent]:
        rows = self.db.execute(
            text("SELECT * FROM execution_events WHERE symbol=:s ORDER BY occurred_at DESC"),
            {"s": symbol},
        ).fetchall()
        return [self._deserialize(r) for r in rows]
