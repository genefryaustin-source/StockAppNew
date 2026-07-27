"""
modules/execution/execution_order_repository.py

Sprint 26 / Increment 36.1

Execution Order Repository

Owns mutable execution/order persistence for broker-facing order state.

This repository is intentionally separate from execution_repository.py.

Responsibilities:
- forex_trade_orders table creation
- market fill persistence
- pending order persistence
- order status updates
- basic order lookup/listing
- commit/rollback helpers

Non-responsibilities:
- immutable execution events
- portfolio position logic
- execution validation
- event replay
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from sqlalchemy import text, bindparam
import json

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def _json_payload(value: Any) -> Optional[str]:
    """
    Serialize dict/list payloads to a JSON string before binding as a SQL
    parameter. Passing a raw Python dict straight to sqlite3/psycopg2 fails
    (sqlite3.InterfaceError: unsupported type / psycopg2 can't adapt type
    'dict'); a JSON string works for both SQLite (TEXT column) and Postgres
    (implicit text->jsonb assignment cast on INSERT/UPDATE).
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


def _naive(value: Any) -> Any:
    if value is not None and hasattr(value, "replace"):
        try:
            return value.replace(tzinfo=None)
        except Exception:
            return value
    return value


def _dialect_name(db: Any) -> str:
    """Best-effort detection of the SQLAlchemy dialect (postgresql/sqlite/...)."""
    try:
        bind = getattr(db, "bind", None)
        if bind is None and hasattr(db, "get_bind"):
            bind = db.get_bind()
        if bind is not None:
            return bind.dialect.name
    except Exception:
        pass
    try:
        return db.dialect.name
    except Exception:
        pass
    return "unknown"



class ExecutionOrderRepository:
    """
    Mutable order-state repository.

    Current backing table:
        forex_trade_orders

    This keeps broker/order persistence separate from the immutable
    execution event store managed by ExecutionRepository.
    """

    TABLE_NAME = "forex_trade_orders"

    def __init__(self, db: Any):
        self.db = db
        self._tables_ready = False
        self._column_cache: Dict[str, Set[str]] = {}

        if self.db is not None:
            self.ensure_tables()

    # ==========================================================
    # Infrastructure
    # ==========================================================

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        if self._tables_ready:
            return

        dialect = _dialect_name(self.db)
        id_column = (
            "id INTEGER PRIMARY KEY AUTOINCREMENT"
            if dialect == "sqlite"
            else "id SERIAL PRIMARY KEY"
        )

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS forex_trade_orders (
                {id_column},
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(100),
                broker VARCHAR(80),
                broker_order_id VARCHAR(120),
                broker_trade_id VARCHAR(120),
                pair VARCHAR(20),
                symbol VARCHAR(30),
                side VARCHAR(20),
                order_type VARCHAR(40),
                status VARCHAR(40),
                quantity DOUBLE PRECISION,
                units DOUBLE PRECISION,
                lots DOUBLE PRECISION,
                requested_price DOUBLE PRECISION,
                limit_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                avg_fill_price DOUBLE PRECISION,
                filled_qty DOUBLE PRECISION,
                remaining_qty DOUBLE PRECISION,
                leverage DOUBLE PRECISION,
                estimated_commission DOUBLE PRECISION,
                estimated_slippage DOUBLE PRECISION,
                actual_commission DOUBLE PRECISION,
                actual_slippage DOUBLE PRECISION,
                notes TEXT,
                raw_payload JSONB,
                validation_payload JSONB,
                execution_id VARCHAR(120),
                correlation_id VARCHAR(120),
                position_id VARCHAR(120),
                submitted_at TIMESTAMP WITHOUT TIME ZONE,
                filled_at TIMESTAMP WITHOUT TIME ZONE,
                canceled_at TIMESTAMP WITHOUT TIME ZONE,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_forex_trade_orders_portfolio_status
            ON forex_trade_orders (portfolio_id, status)
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_forex_trade_orders_account_status
            ON forex_trade_orders (account_id, status)
        """))

        self.db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_forex_trade_orders_broker_order_id
            ON forex_trade_orders (broker_order_id)
        """))

        self.commit()
        self._tables_ready = True
        self._column_cache.pop(self.TABLE_NAME, None)

    def commit(self) -> None:
        if self.db is not None and hasattr(self.db, "commit"):
            self.db.commit()

    def rollback(self) -> None:
        if self.db is not None and hasattr(self.db, "rollback"):
            self.db.rollback()

    def _table_columns(self, table: str) -> Set[str]:
        if table in self._column_cache:
            return self._column_cache[table]

        if self.db is None:
            return set()

        dialect = _dialect_name(self.db)
        columns: Set[str] = set()

        try:
            if dialect == "sqlite":
                # information_schema doesn't exist on SQLite; PRAGMA table_info
                # works even against an empty table (unlike introspecting via
                # a SELECT * LIMIT 1, which returns nothing to introspect).
                rows = self.db.execute(text(f"PRAGMA table_info({table})")).fetchall()
                columns = {str(_row_to_dict(row).get("name")) for row in rows}
            else:
                rows = self.db.execute(
                    text("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = :table
                    """),
                    {"table": table},
                ).fetchall()
                columns = {str(_row_to_dict(row).get("column_name")) for row in rows}
        except Exception:
            columns = set()

        if not columns:
            # Last-resort fallback: introspect an actual row if one exists.
            try:
                row = self.db.execute(text(f"SELECT * FROM {table} LIMIT 1")).fetchone()
                if row is not None:
                    columns = set(_row_to_dict(row).keys())
            except Exception:
                pass

        self._column_cache[table] = columns
        return columns

    def _insert_row(
        self,
        *,
        table: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        columns = self._table_columns(table)
        data = {
            key: value
            for key, value in payload.items()
            if key in columns
        }

        if not data:
            return None

        names = list(data.keys())
        sql = text(
            f"""
            INSERT INTO {table} ({", ".join(names)})
            VALUES ({", ".join(":" + name for name in names)})
            RETURNING *
            """
        )

        row = self.db.execute(sql, data).fetchone()
        return _row_to_dict(row) if row is not None else None

    def _update_row(
        self,
        *,
        table: str,
        broker_order_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        columns = self._table_columns(table)
        data = {
            key: value
            for key, value in updates.items()
            if key in columns and key != "id"
        }

        if not data:
            return self.get_order(broker_order_id=broker_order_id)

        data["broker_order_id"] = broker_order_id

        assignments = [
            f"{name} = :{name}"
            for name in data.keys()
            if name != "broker_order_id"
        ]

        sql = text(
            f"""
            UPDATE {table}
            SET {", ".join(assignments)}
            WHERE broker_order_id = :broker_order_id
            RETURNING *
            """
        )

        row = self.db.execute(sql, data).fetchone()
        return _row_to_dict(row) if row is not None else None

    # ==========================================================
    # Market Fill
    # ==========================================================

    def insert_market_fill(
        self,
        *,
        context,
        position,
    ) -> Optional[Dict[str, Any]]:
        """
        Persist a filled market order into forex_trade_orders.

        This method intentionally does not create events. Events are handled by
        ExecutionEventRecorder.
        """

        self.ensure_tables()

        now = _utc_now_naive()

        avg_fill_price = (
            getattr(context, "average_fill_price", None)
            or getattr(context, "execution_price", None)
            or getattr(position, "avg_entry_price", None)
        )

        units = (
            getattr(context, "units", None)
            or getattr(context, "quantity", None)
            or getattr(position, "units", None)
        )

        pair = getattr(context, "pair", None) or getattr(position, "pair", None)
        symbol = getattr(context, "symbol", None) or _safe_str(pair).replace("/", "")

        payload = {
            "tenant_id": getattr(context, "tenant_id", None),
            "user_id": getattr(context, "user_id", None),
            "portfolio_id": getattr(context, "portfolio_id", None) or getattr(position, "portfolio_id", None),
            "account_id": getattr(context, "account_id", None) or getattr(position, "account_id", None),
            "broker": getattr(context, "broker", None) or "paper",
            "broker_order_id": getattr(context, "broker_order_id", None),
            "broker_trade_id": getattr(context, "broker_trade_id", None),
            "pair": pair,
            "symbol": symbol,
            "side": getattr(context, "side", None) or getattr(position, "side", None),
            "order_type": getattr(context, "order_type", None) or "MARKET",
            "status": "filled",
            "quantity": _safe_float(units),
            "units": _safe_float(units),
            "lots": _safe_float(getattr(context, "lots", 0.0)),
            "requested_price": getattr(context, "requested_price", None),
            "limit_price": getattr(context, "requested_price", None),
            "stop_price": getattr(context, "stop_price", None),
            "target_price": getattr(context, "target_price", None),
            "avg_fill_price": _safe_float(avg_fill_price),
            "filled_qty": _safe_float(units),
            "remaining_qty": 0.0,
            "leverage": getattr(context, "leverage", None) or getattr(position, "leverage", None),
            "raw_payload": _json_payload(getattr(context, "raw_request", None) or {}),
            "validation_payload": _json_payload(getattr(context, "validation", None) or {}),
            "execution_id": getattr(context, "execution_id", None),
            "correlation_id": getattr(context, "correlation_id", None),
            "position_id": getattr(context, "position_id", None) or getattr(position, "id", None),
            "submitted_at": _naive(getattr(context, "submitted_at", None)) or now,
            "filled_at": _naive(getattr(context, "filled_at", None)) or now,
            "created_at": now,
            "updated_at": now,
        }

        row = self._insert_row(
            table=self.TABLE_NAME,
            payload=payload,
        )

        self.commit()
        return row

    # ==========================================================
    # Pending Orders
    # ==========================================================

    def insert_pending_order(
        self,
        *,
        context,
    ) -> Optional[Dict[str, Any]]:
        self.ensure_tables()

        now = _utc_now_naive()

        pair = getattr(context, "pair", None)
        symbol = getattr(context, "symbol", None) or _safe_str(pair).replace("/", "")
        units = getattr(context, "units", None) or getattr(context, "quantity", None)

        payload = {
            "tenant_id": getattr(context, "tenant_id", None),
            "user_id": getattr(context, "user_id", None),
            "portfolio_id": getattr(context, "portfolio_id", None),
            "account_id": getattr(context, "account_id", None),
            "broker": getattr(context, "broker", None) or "paper",
            "broker_order_id": getattr(context, "broker_order_id", None),
            "broker_trade_id": getattr(context, "broker_trade_id", None),
            "pair": pair,
            "symbol": symbol,
            "side": getattr(context, "side", None),
            "order_type": getattr(context, "order_type", None) or "LIMIT",
            "status": "pending",
            "quantity": _safe_float(units),
            "units": _safe_float(units),
            "lots": _safe_float(getattr(context, "lots", 0.0)),
            "requested_price": getattr(context, "requested_price", None),
            "limit_price": getattr(context, "requested_price", None),
            "stop_price": getattr(context, "stop_price", None),
            "target_price": getattr(context, "target_price", None),
            "avg_fill_price": None,
            "filled_qty": 0.0,
            "remaining_qty": _safe_float(units),
            "leverage": getattr(context, "leverage", None),
            "raw_payload": _json_payload(getattr(context, "raw_request", None) or {}),
            "validation_payload": _json_payload(getattr(context, "validation", None) or {}),
            "execution_id": getattr(context, "execution_id", None),
            "correlation_id": getattr(context, "correlation_id", None),
            "position_id": getattr(context, "position_id", None),
            "submitted_at": _naive(getattr(context, "submitted_at", None)) or now,
            "created_at": now,
            "updated_at": now,
        }

        row = self._insert_row(
            table=self.TABLE_NAME,
            payload=payload,
        )

        self.commit()
        return row

    # ==========================================================
    # Updates
    # ==========================================================

    def update_order(
        self,
        *,
        broker_order_id: str,
        **updates: Any,
    ) -> Optional[Dict[str, Any]]:
        self.ensure_tables()

        updates.setdefault("updated_at", _utc_now_naive())

        row = self._update_row(
            table=self.TABLE_NAME,
            broker_order_id=broker_order_id,
            updates=updates,
        )

        self.commit()
        return row

    def mark_order_filled(
        self,
        *,
        broker_order_id: str,
        fill_price: float,
        filled_qty: Optional[float] = None,
        position_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        updates = {
            "status": "filled",
            "avg_fill_price": _safe_float(fill_price),
            "filled_at": _utc_now_naive(),
            "remaining_qty": 0.0,
        }

        if filled_qty is not None:
            updates["filled_qty"] = _safe_float(filled_qty)
            updates["quantity"] = _safe_float(filled_qty)
            updates["units"] = _safe_float(filled_qty)

        if position_id is not None:
            updates["position_id"] = position_id

        return self.update_order(
            broker_order_id=broker_order_id,
            **updates,
        )

    def cancel_pending_order(
        self,
        *,
        broker_order_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.update_order(
            broker_order_id=broker_order_id,
            status="cancelled",
            canceled_at=_utc_now_naive(),
        )

    def expire_pending_order(
        self,
        *,
        broker_order_id: str,
    ) -> Optional[Dict[str, Any]]:
        return self.update_order(
            broker_order_id=broker_order_id,
            status="expired",
        )

    def modify_pending_order(
        self,
        *,
        broker_order_id: str,
        limit_price=None,
        stop_price=None,
        target_price=None,
        quantity=None,
    ) -> Optional[Dict[str, Any]]:
        updates: Dict[str, Any] = {}

        if limit_price is not None:
            updates["requested_price"] = limit_price
            updates["limit_price"] = limit_price

        if stop_price is not None:
            updates["stop_price"] = stop_price

        if target_price is not None:
            updates["target_price"] = target_price

        if quantity is not None:
            updates["quantity"] = _safe_float(quantity)
            updates["units"] = _safe_float(quantity)
            updates["remaining_qty"] = _safe_float(quantity)

        if not updates:
            return self.get_order(broker_order_id=broker_order_id)

        return self.update_order(
            broker_order_id=broker_order_id,
            **updates,
        )

    # ==========================================================
    # Reads
    # ==========================================================

    def get_order(
        self,
        *,
        broker_order_id: str,
    ) -> Optional[Dict[str, Any]]:
        self.ensure_tables()

        row = self.db.execute(
            text("""
                SELECT *
                FROM forex_trade_orders
                WHERE broker_order_id = :broker_order_id
                LIMIT 1
            """),
            {
                "broker_order_id": broker_order_id,
            },
        ).fetchone()

        return _row_to_dict(row) if row is not None else None

    def load_pending_orders(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        """
        forex_pending_orders_dashboard.py calls repo.load_pending_orders()
        directly - that method never existed (only list_orders(), which
        needs an explicit statuses= filter), so the dashboard raised
        AttributeError on the very first render. Pending orders can sit in
        either PENDING (resting, not yet accepted) or ACCEPTED (accepted by
        the broker/pipeline but not yet filled) state.
        """
        return self.list_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
            statuses=["pending", "accepted"],
            limit=limit,
        )

    def list_orders(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        statuses: Optional[Sequence[str]] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        self.ensure_tables()

        params: Dict[str, Any] = {
            "limit": int(limit),
        }

        where_parts: List[str] = []

        if account_id:
            where_parts.append("account_id = :account_id")
            params["account_id"] = account_id

        if portfolio_id:
            where_parts.append("portfolio_id = :portfolio_id")
            params["portfolio_id"] = portfolio_id

        has_statuses = bool(statuses)

        if has_statuses:
            normalized = [str(status).lower() for status in statuses]
            where_parts.append("lower(status) IN :statuses")
            params["statuses"] = normalized

        where_sql = (
            "WHERE " + " AND ".join(where_parts)
            if where_parts
            else ""
        )

        stmt = text(f"""
            SELECT *
            FROM forex_trade_orders
            {where_sql}
            ORDER BY COALESCE(filled_at, submitted_at, created_at) DESC, id DESC
            LIMIT :limit
        """)

        if has_statuses:
            # `IN :statuses` + expanding=True is portable across Postgres and
            # SQLite (the old `= ANY(:statuses)` syntax is Postgres-only and
            # raises on SQLite).
            stmt = stmt.bindparams(bindparam("statuses", expanding=True))

        rows = self.db.execute(stmt, params).fetchall()

        return [_row_to_dict(row) for row in rows]

    def insert_execution_order(
            self,
            *,
            request,
            result,
    ) -> Optional[Dict[str, Any]]:
        """
        Persist an execution order coming from the legacy
        ForexTradeExecutionEngine.

        This is intentionally separate from insert_market_fill(),
        which accepts an ExecutionContext and Position.
        """

        self.ensure_tables()

        created = getattr(result, "created_at", None) or _utc_now_naive()
        filled_at = getattr(result, "filled_at", None)

        if isinstance(result, dict):
            created = result.get("created_at") or created
            filled_at = result.get("filled_at")

        payload = {
            "broker_order_id": result.get("broker_order_id"),
            "tenant_id": request.tenant_id,
            "portfolio_id": request.portfolio_id,
            "user_id": request.user_id,
            "pair": request.pair,
            "symbol": request.pair.replace("/", ""),
            "side": request.side,
            "order_type": request.order_type,
            "units": request.units,
            "quantity": request.units,
            "limit_price": request.limit_price,
            "stop_price": request.stop_price,
            "requested_price": result.get("requested_price"),
            "avg_fill_price": result.get("filled_price"),
            "filled_qty": result.get("filled_units"),
            "status": result.get("status"),
            "broker": result.get("broker"),
            "actual_commission": result.get("commission"),
            "actual_slippage": result.get("slippage"),
            "notes": result.get("notes"),
            "raw_payload": _json_payload(result),
            "created_at": created,
            "filled_at": filled_at,
            "updated_at": created,
        }

        row = self._insert_row(
            table=self.TABLE_NAME,
            payload=payload,
        )

        self.commit()

        return row

    def project_order(
            self,
            *,
            context,
    ) -> Optional[Dict[str, Any]]:
        """
        Projects the current ExecutionContext into the
        forex_trade_orders read model.

        Existing broker_order_id -> UPDATE

        New broker_order_id -> INSERT
        """

        broker_order_id = getattr(
            context,
            "broker_order_id",
            None,
        )

        if not broker_order_id:
            return None

        existing = self.get_order(
            broker_order_id=broker_order_id,
        )

        if existing:
            return self.update_order(

                broker_order_id=broker_order_id,

                status=getattr(context, "status", None),

                requested_price=getattr(
                    context,
                    "requested_price",
                    None,
                ),

                stop_price=getattr(
                    context,
                    "stop_price",
                    None,
                ),

                target_price=getattr(
                    context,
                    "target_price",
                    None,
                ),

                avg_fill_price=getattr(
                    context,
                    "average_fill_price",
                    None,
                ),

                filled_qty=getattr(
                    context,
                    "units",
                    None,
                ),

                position_id=getattr(
                    context,
                    "position_id",
                    None,
                ),

            )

        #
        # New order projection.
        #

        if (
                str(
                    getattr(
                        context,
                        "order_type",
                        "",
                    )
                ).upper()
                == "MARKET"
        ):
            return self.insert_market_fill(

                context=context,

                position=getattr(
                    context,
                    "position",
                    None,
                ),

            )

        return self.insert_pending_order(
            context=context,
        )

    def load_order_projection(
            self,
            *,
            broker_order_id: str,
    ) -> Optional[Dict[str, Any]]:

        return self.get_order(
            broker_order_id=broker_order_id,
        )

    def delete_projection(
            self,
            *,
            broker_order_id: str,
    ) -> None:

        self.ensure_tables()

        self.db.execute(
            text("""
            DELETE
            FROM forex_trade_orders
            WHERE broker_order_id=:broker_order_id
            """),
            {
                "broker_order_id": broker_order_id,
            },
        )

        self.commit()

    def rebuild_projection(
            self,
            *,
            context,
    ) -> Optional[Dict[str, Any]]:

        broker_order_id = getattr(
            context,
            "broker_order_id",
            None,
        )

        if broker_order_id:
            self.delete_projection(
                broker_order_id=broker_order_id,
            )

        return self.project_order(
            context=context,
        )



    # ------------------------------------------------------------------
    # Position-lifecycle audit hooks
    # ------------------------------------------------------------------
    #
    # ExecutionPositionPipeline (execution_position_pipeline.py) calls
    # these five after each position operation (close, partial close,
    # reverse, modify, flatten) actually completes against
    # portfolio_engine -- none of them existed on this class before,
    # so every one of those operations failed with AttributeError
    # after the real state change had already succeeded.
    #
    # These are deliberately minimal: the operation's real effect (the
    # position/account state change) has already happened by the time
    # these run, on the order/position tables that own that data.
    # These exist to log the event for observability, not to be the
    # source of truth for it -- never raising here means a logging
    # hiccup can't undo a position change that already succeeded.

    def persist_position_close(self, *, context, position=None) -> None:
        try:
            logger.info(
                "Forex position closed | position_id=%s tenant_id=%s pair=%s",
                getattr(context, "position_id", None),
                getattr(context, "tenant_id", None),
                getattr(context, "pair", None),
            )
        except Exception:
            logger.exception("persist_position_close logging failed")

    def persist_partial_close(self, *, context, position=None, quantity=None) -> None:
        try:
            logger.info(
                "Forex position partially closed | position_id=%s quantity=%s",
                getattr(context, "position_id", None),
                quantity,
            )
        except Exception:
            logger.exception("persist_partial_close logging failed")

    def persist_reversal(self, *, context, position=None) -> None:
        try:
            logger.info(
                "Forex position reversed | position_id=%s new_side=%s",
                getattr(context, "position_id", None),
                getattr(context, "side", None),
            )
        except Exception:
            logger.exception("persist_reversal logging failed")

    def persist_modification(self, *, context, position=None) -> None:
        try:
            logger.info(
                "Forex position modified | position_id=%s stop_price=%s target_price=%s",
                getattr(context, "position_id", None),
                getattr(context, "stop_price", None),
                getattr(context, "target_price", None),
            )
        except Exception:
            logger.exception("persist_modification logging failed")

    def persist_flatten(self, *, context, result=None) -> None:
        try:
            logger.info(
                "Forex account flattened | account_id=%s",
                getattr(context, "account_id", None),
            )
        except Exception:
            logger.exception("persist_flatten logging failed")