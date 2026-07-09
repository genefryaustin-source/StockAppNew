"""
execution_position_repository.py

Sprint 38.2A.1

Execution Position Projection Repository

Owns the position projection read model.

This repository is responsible ONLY for maintaining the
forex_positions projection generated from immutable execution
events.

Execution Events
        ↓
ExecutionEventProjection
        ↓
ExecutionPositionRepository
        ↓
forex_positions
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


def _json(value: Any) -> str:
    try:
        return json.dumps(value or {})
    except Exception:
        return "{}"


# ==============================================================================
# Repository
# ==============================================================================


class ExecutionPositionRepository:

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
        CREATE TABLE IF NOT EXISTS forex_positions (
            id VARCHAR(64) PRIMARY KEY,

            tenant_id VARCHAR(100),
            user_id VARCHAR(100),
            portfolio_id VARCHAR(100),
            account_id VARCHAR(100),

            pair VARCHAR(20),
            base_currency VARCHAR(10),
            quote_currency VARCHAR(10),

            side VARCHAR(20),

            units DOUBLE PRECISION,

            avg_entry_price DOUBLE PRECISION,
            current_price DOUBLE PRECISION,

            notional_value DOUBLE PRECISION,
            market_value DOUBLE PRECISION,

            unrealized_pnl DOUBLE PRECISION,
            realized_pnl DOUBLE PRECISION,

            stop_price DOUBLE PRECISION,
            target_price DOUBLE PRECISION,

            margin_required DOUBLE PRECISION,
            leverage DOUBLE PRECISION,

            status VARCHAR(40),

            raw_payload JSONB,

            opened_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """))

        self.db.commit()

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    def project_position(
        self,
        *,
        position: Dict[str, Any],
    ) -> None:

        self.ensure_tables()

        self.db.execute(text("""
        INSERT INTO forex_positions (

            id,
            tenant_id,
            user_id,
            portfolio_id,
            account_id,

            pair,
            base_currency,
            quote_currency,

            side,
            units,

            avg_entry_price,
            current_price,

            notional_value,
            market_value,

            unrealized_pnl,
            realized_pnl,

            stop_price,
            target_price,

            margin_required,
            leverage,

            status,

            raw_payload,

            opened_at,
            updated_at

        )
        VALUES (

            :id,
            :tenant_id,
            :user_id,
            :portfolio_id,
            :account_id,

            :pair,
            :base_currency,
            :quote_currency,

            :side,
            :units,

            :avg_entry_price,
            :current_price,

            :notional_value,
            :market_value,

            :unrealized_pnl,
            :realized_pnl,

            :stop_price,
            :target_price,

            :margin_required,
            :leverage,

            :status,

            CAST(:raw_payload AS JSONB),

            :opened_at,
            :updated_at

        )

        ON CONFLICT (id)

        DO UPDATE SET

            units = EXCLUDED.units,

            current_price = EXCLUDED.current_price,

            notional_value = EXCLUDED.notional_value,

            market_value = EXCLUDED.market_value,

            unrealized_pnl = EXCLUDED.unrealized_pnl,

            realized_pnl = EXCLUDED.realized_pnl,

            stop_price = EXCLUDED.stop_price,

            target_price = EXCLUDED.target_price,

            margin_required = EXCLUDED.margin_required,

            leverage = EXCLUDED.leverage,

            status = EXCLUDED.status,

            raw_payload = EXCLUDED.raw_payload,

            updated_at = EXCLUDED.updated_at
        """), {

            "id": position.id,

            "tenant_id": position.tenant_id,
            "user_id": position.user_id,
            "portfolio_id": position.portfolio_id,
            "account_id": position.account_id,

            "pair": position.pair,
            "base_currency": position.base_currency,
            "quote_currency": position.quote_currency,

            "side": position.side,

            "units": position.units,

            "avg_entry_price": position.avg_entry_price,
            "current_price": position.current_price,

            "notional_value": position.notional_value,
            "market_value": position.market_value,

            "unrealized_pnl": position.unrealized_pnl,
            "realized_pnl": position.realized_pnl,

            "stop_price": position.stop_price,
            "target_price": position.target_price,

            "margin_required": position.margin_required,
            "leverage": position.leverage,

            "status": position.status,

            "raw_payload": _json(
                position.raw
                if position.raw is not None
                else position.to_dict()
            ),

            "opened_at": position.opened_at.replace(
                tzinfo=None
            ),

            "updated_at": position.updated_at.replace(
                tzinfo=None
            ),
        })

        self.db.commit()

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_position(
            self,
            position_id: str,
    ) -> Optional[Dict[str, Any]]:

        row = self.db.execute(text("""
        SELECT *
        FROM forex_positions
        WHERE id=:id
        """), {

            "id": position_id,

        }).mappings().first()

        if row is None:
            return None

        return self._from_row(row)

    # ------------------------------------------------------------------

    def load_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        where = []

        params = {}

        if account_id:

            where.append(
                "account_id=:account_id"
            )

            params["account_id"] = account_id

        if portfolio_id:

            where.append(
                "portfolio_id=:portfolio_id"
            )

            params["portfolio_id"] = portfolio_id

        if status:

            where.append(
                "status=:status"
            )

            params["status"] = status

        sql = """
        SELECT *
        FROM forex_positions
        """

        if where:

            sql += " WHERE "

            sql += " AND ".join(where)

        sql += """

        ORDER BY

            updated_at DESC,
            opened_at DESC

        """

        rows = self.db.execute(
            text(sql),
            params,
        ).mappings().all()

        return [

            self._from_row(r)

            for r in rows

        ]

    # ------------------------------------------------------------------
    # Projection Updates
    # ------------------------------------------------------------------

    def close_position_projection(
        self,
        *,
        position_id: str,
    ) -> None:

        self.db.execute(text("""
        UPDATE forex_positions
        SET

            status='CLOSED',

            units=0,

            updated_at=:updated_at

        WHERE id=:id
        """), {

            "id": position_id,

            "updated_at": _utc_now().replace(
                tzinfo=None
            ),

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def delete_projection(
        self,
        *,
        position_id: str,
    ) -> None:

        self.db.execute(text("""
        DELETE
        FROM forex_positions
        WHERE id=:id
        """), {

            "id": position_id,

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def rebuild_projection(
        self,
        *,
        position: Dict[str, Any],
    ) -> None:

        self.project_position(
            position=position,
        )

    # ------------------------------------------------------------------
    # Row Conversion
    # ------------------------------------------------------------------

    def _from_row(
        self,
        row,
    ) -> Dict[str, Any]:

        opened = row["opened_at"] or _utc_now()
        updated = row["updated_at"] or _utc_now()

        if opened.tzinfo is None:
            opened = opened.replace(
                tzinfo=timezone.utc
            )

        if updated.tzinfo is None:
            updated = updated.replace(
                tzinfo=timezone.utc
            )

        return {

            "id": row["id"],

            "tenant_id": row["tenant_id"],

            "user_id": row["user_id"],

            "portfolio_id": row["portfolio_id"],

            "account_id": row["account_id"],

            "pair": row["pair"],

            "base_currency": row["base_currency"],

            "quote_currency": row["quote_currency"],

            "side": row["side"],

            "units": _safe_float(row["units"]),

            "avg_entry_price": _safe_float(row["avg_entry_price"]),

            "current_price": _safe_float(row["current_price"]),

            "notional_value": _safe_float(row["notional_value"]),

            "market_value": _safe_float(row["market_value"]),

            "unrealized_pnl": _safe_float(row["unrealized_pnl"]),

            "realized_pnl": _safe_float(row["realized_pnl"]),

            "stop_price": row["stop_price"],

            "target_price": row["target_price"],

            "margin_required": _safe_float(row["margin_required"]),

            "leverage": _safe_float(row["leverage"], 1.0),

            "status": row["status"],

            "opened_at": opened,

            "updated_at": updated,

            "raw_payload": row["raw_payload"],

        }


# ==============================================================================
# Factory
# ==============================================================================

_POSITION_REPOSITORY = None


def get_execution_position_repository(
    *,
    db,
    cache: bool = True,
) -> ExecutionPositionRepository:

    global _POSITION_REPOSITORY

    if (
        not cache
        or _POSITION_REPOSITORY is None
    ):

        _POSITION_REPOSITORY = (
            ExecutionPositionRepository(
                db=db,
            )
        )

    return _POSITION_REPOSITORY