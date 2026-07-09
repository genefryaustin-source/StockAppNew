"""
execution_snapshot_repository.py

Sprint 38.2A.3

Execution Snapshot Projection Repository

Maintains portfolio/account snapshot projections generated
from immutable execution events.

Execution Events
        ↓
ExecutionEventProjection
        ↓
ExecutionSnapshotRepository
        ↓
portfolio_snapshots
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text


# ==============================================================================
# Helpers
# ==============================================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _json(value: Any) -> str:
    try:
        return json.dumps(value or {})
    except Exception:
        return "{}"


# ==============================================================================
# Repository
# ==============================================================================


class ExecutionSnapshotRepository:

    def __init__(
        self,
        *,
        db,
    ):
        self.db = db

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def ensure_tables(self) -> None:

        if self.db is None:
            return

        self.db.execute(text("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (

            id VARCHAR(64) PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            account_id VARCHAR(100),

            snapshot_time TIMESTAMP,

            balance DOUBLE PRECISION,

            cash DOUBLE PRECISION,

            equity DOUBLE PRECISION,

            market_value DOUBLE PRECISION,

            realized_pnl DOUBLE PRECISION,

            unrealized_pnl DOUBLE PRECISION,

            margin_used DOUBLE PRECISION,

            margin_available DOUBLE PRECISION,

            open_positions INTEGER,

            open_orders INTEGER,

            net_liquidation DOUBLE PRECISION,

            raw_payload JSONB,

            created_at TIMESTAMP,

            updated_at TIMESTAMP
        )
        """))

        self.db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        idx_portfolio_snapshots_portfolio_time

        ON portfolio_snapshots(
            portfolio_id,
            snapshot_time DESC
        )
        """))

        self.db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        idx_portfolio_snapshots_account_time

        ON portfolio_snapshots(
            account_id,
            snapshot_time DESC
        )
        """))

        self.db.commit()

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    def project_snapshot(
        self,
        *,
        snapshot: Dict[str, Any],
    ) -> None:

        self.ensure_tables()

        now = _utc_now().replace(tzinfo=None)

        snapshot_id = (
            snapshot.get("id")
            or snapshot.get("snapshot_id")
            or f"{snapshot.get('portfolio_id','')}_{int(now.timestamp())}"
        )

        snapshot_time = (
            snapshot.get("snapshot_time")
            or snapshot.get("asof")
            or now
        )

        if (
            isinstance(snapshot_time, datetime)
            and snapshot_time.tzinfo is not None
        ):
            snapshot_time = snapshot_time.replace(
                tzinfo=None
            )

        self.db.execute(text("""
        INSERT INTO portfolio_snapshots (

            id,

            tenant_id,

            user_id,

            portfolio_id,

            account_id,

            snapshot_time,

            balance,

            cash,

            equity,

            market_value,

            realized_pnl,

            unrealized_pnl,

            margin_used,

            margin_available,

            open_positions,

            open_orders,

            net_liquidation,

            raw_payload,

            created_at,

            updated_at

        )

        VALUES (

            :id,

            :tenant_id,

            :user_id,

            :portfolio_id,

            :account_id,

            :snapshot_time,

            :balance,

            :cash,

            :equity,

            :market_value,

            :realized_pnl,

            :unrealized_pnl,

            :margin_used,

            :margin_available,

            :open_positions,

            :open_orders,

            :net_liquidation,

            CAST(:raw_payload AS JSONB),

            :created_at,

            :updated_at

        )

        ON CONFLICT(id)

        DO UPDATE SET

            snapshot_time = EXCLUDED.snapshot_time,

            balance = EXCLUDED.balance,

            cash = EXCLUDED.cash,

            equity = EXCLUDED.equity,

            market_value = EXCLUDED.market_value,

            realized_pnl = EXCLUDED.realized_pnl,

            unrealized_pnl = EXCLUDED.unrealized_pnl,

            margin_used = EXCLUDED.margin_used,

            margin_available = EXCLUDED.margin_available,

            open_positions = EXCLUDED.open_positions,

            open_orders = EXCLUDED.open_orders,

            net_liquidation = EXCLUDED.net_liquidation,

            raw_payload = EXCLUDED.raw_payload,

            updated_at = EXCLUDED.updated_at
        """), {

            "id": snapshot_id,

            "tenant_id": snapshot.get("tenant_id"),

            "user_id": snapshot.get("user_id"),

            "portfolio_id": snapshot.get("portfolio_id"),

            "account_id": snapshot.get("account_id"),

            "snapshot_time": snapshot_time,

            "balance": _safe_float(snapshot.get("balance")),

            "cash": _safe_float(snapshot.get("cash")),

            "equity": _safe_float(snapshot.get("equity")),

            "market_value": _safe_float(snapshot.get("market_value")),

            "realized_pnl": _safe_float(snapshot.get("realized_pnl")),

            "unrealized_pnl": _safe_float(snapshot.get("unrealized_pnl")),

            "margin_used": _safe_float(snapshot.get("margin_used")),

            "margin_available": _safe_float(snapshot.get("margin_available")),

            "open_positions": _safe_int(snapshot.get("open_positions")),

            "open_orders": _safe_int(snapshot.get("open_orders")),

            "net_liquidation": _safe_float(snapshot.get("net_liquidation")),

            "raw_payload": _json(snapshot),

            "created_at": snapshot.get(
                "created_at",
                now,
            ),

            "updated_at": now,

        })

        self.db.commit()

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> Optional[Dict[str, Any]]:

        row = self.db.execute(text("""
        SELECT *

        FROM portfolio_snapshots

        WHERE id=:id
        """), {

            "id": snapshot_id,

        }).mappings().first()

        if row is None:
            return None

        return dict(row)

    # ------------------------------------------------------------------

    def load_latest_snapshot(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:

        where = []
        params = {}

        if account_id:
            where.append("account_id=:account_id")
            params["account_id"] = account_id

        if portfolio_id:
            where.append("portfolio_id=:portfolio_id")
            params["portfolio_id"] = portfolio_id

        sql = """
        SELECT *

        FROM portfolio_snapshots
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += """

        ORDER BY

            snapshot_time DESC,

            updated_at DESC

        LIMIT 1

        """

        row = self.db.execute(
            text(sql),
            params,
        ).mappings().first()

        if row is None:
            return None

        return dict(row)

    # ------------------------------------------------------------------

    def load_snapshots(
        self,
        *,
        tenant_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        account_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:

        where = []
        params = {}

        if tenant_id:
            where.append("tenant_id=:tenant_id")
            params["tenant_id"] = tenant_id

        if portfolio_id:
            where.append("portfolio_id=:portfolio_id")
            params["portfolio_id"] = portfolio_id

        if account_id:
            where.append("account_id=:account_id")
            params["account_id"] = account_id

        if start:
            where.append("snapshot_time>=:start")
            params["start"] = start.replace(tzinfo=None)

        if end:
            where.append("snapshot_time<=:end")
            params["end"] = end.replace(tzinfo=None)

        sql = """
        SELECT *

        FROM portfolio_snapshots
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += """

        ORDER BY

            snapshot_time DESC

        """

        rows = self.db.execute(
            text(sql),
            params,
        ).mappings().all()

        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def delete_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> None:

        self.db.execute(text("""
        DELETE

        FROM portfolio_snapshots

        WHERE id=:id
        """), {

            "id": snapshot_id,

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def rebuild_snapshot(
        self,
        *,
        snapshot: Dict[str, Any],
    ) -> None:

        self.project_snapshot(
            snapshot=snapshot,
        )


# ==============================================================================
# Factory
# ==============================================================================

_SNAPSHOT_REPOSITORY = None


def get_execution_snapshot_repository(
    *,
    db,
    cache: bool = True,
) -> ExecutionSnapshotRepository:

    global _SNAPSHOT_REPOSITORY

    if (
        not cache
        or _SNAPSHOT_REPOSITORY is None
    ):

        _SNAPSHOT_REPOSITORY = (
            ExecutionSnapshotRepository(
                db=db,
            )
        )

    return _SNAPSHOT_REPOSITORY