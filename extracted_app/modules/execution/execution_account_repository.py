"""
execution_account_repository.py

Sprint 38.2A.2

Execution Account Projection Repository

Maintains the account projection generated from immutable
execution events.

Execution Events
        ↓
ExecutionEventProjection
        ↓
ExecutionAccountRepository
        ↓
forex_accounts
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


class ExecutionAccountRepository:

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
        CREATE TABLE IF NOT EXISTS forex_accounts (

            id VARCHAR(100) PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            base_currency VARCHAR(10),

            balance DOUBLE PRECISION,

            equity DOUBLE PRECISION,

            cash DOUBLE PRECISION,

            used_margin DOUBLE PRECISION,

            free_margin DOUBLE PRECISION,

            margin_level DOUBLE PRECISION,

            unrealized_pnl DOUBLE PRECISION,

            realized_pnl DOUBLE PRECISION,

            open_positions INTEGER,

            open_orders INTEGER,

            total_exposure DOUBLE PRECISION,

            status VARCHAR(40),

            raw_payload JSONB,

            created_at TIMESTAMP,

            updated_at TIMESTAMP

        )
        """))

        self.db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        idx_forex_accounts_portfolio

        ON forex_accounts(portfolio_id)
        """))

        self.db.commit()

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    def project_account(
        self,
        *,
        account: Dict[str, Any],
    ) -> None:

        self.ensure_tables()

        now = _utc_now().replace(
            tzinfo=None,
        )

        self.db.execute(text("""
        INSERT INTO forex_accounts (

            id,

            tenant_id,

            user_id,

            portfolio_id,

            base_currency,

            balance,

            equity,

            cash,

            used_margin,

            free_margin,

            margin_level,

            unrealized_pnl,

            realized_pnl,

            open_positions,

            open_orders,

            total_exposure,

            status,

            raw_payload,

            created_at,

            updated_at

        )

        VALUES (

            :id,

            :tenant_id,

            :user_id,

            :portfolio_id,

            :base_currency,

            :balance,

            :equity,

            :cash,

            :used_margin,

            :free_margin,

            :margin_level,

            :unrealized_pnl,

            :realized_pnl,

            :open_positions,

            :open_orders,

            :total_exposure,

            :status,

            CAST(:raw_payload AS JSONB),

            :created_at,

            :updated_at

        )

        ON CONFLICT(id)

        DO UPDATE SET

            balance = EXCLUDED.balance,

            equity = EXCLUDED.equity,

            cash = EXCLUDED.cash,

            used_margin = EXCLUDED.used_margin,

            free_margin = EXCLUDED.free_margin,

            margin_level = EXCLUDED.margin_level,

            unrealized_pnl = EXCLUDED.unrealized_pnl,

            realized_pnl = EXCLUDED.realized_pnl,

            open_positions = EXCLUDED.open_positions,

            open_orders = EXCLUDED.open_orders,

            total_exposure = EXCLUDED.total_exposure,

            status = EXCLUDED.status,

            raw_payload = EXCLUDED.raw_payload,

            updated_at = EXCLUDED.updated_at
        """), {

            "id": account.get("account_id"),

            "tenant_id": account.get("tenant_id"),

            "user_id": account.get("user_id"),

            "portfolio_id": account.get("portfolio_id"),

            "base_currency": account.get(
                "base_currency",
                "USD",
            ),

            "balance": _safe_float(
                account.get("balance"),
            ),

            "equity": _safe_float(
                account.get("equity"),
            ),

            "cash": _safe_float(
                account.get("cash"),
            ),

            "used_margin": _safe_float(
                account.get("used_margin"),
            ),

            "free_margin": _safe_float(
                account.get("free_margin"),
            ),

            "margin_level": _safe_float(
                account.get("margin_level"),
            ),

            "unrealized_pnl": _safe_float(
                account.get("unrealized_pnl"),
            ),

            "realized_pnl": _safe_float(
                account.get("realized_pnl"),
            ),

            "open_positions": _safe_int(
                account.get("open_positions"),
            ),

            "open_orders": _safe_int(
                account.get("open_orders"),
            ),

            "total_exposure": _safe_float(
                account.get("total_exposure"),
            ),

            "status": account.get(
                "status",
                "ACTIVE",
            ),

            "raw_payload": _json(account),

            "created_at": account.get(
                "created_at",
                now,
            ),

            "updated_at": now,

        })

        self.db.commit()

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_account(
        self,
        *,
        account_id: str,
    ) -> Optional[Dict[str, Any]]:

        row = self.db.execute(text("""
        SELECT *

        FROM forex_accounts

        WHERE id=:id
        """), {

            "id": account_id,

        }).mappings().first()

        if row is None:
            return None

        return dict(row)

    # ------------------------------------------------------------------

    def load_accounts(
        self,
        *,
        tenant_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        where = []

        params = {}

        if tenant_id:

            where.append(
                "tenant_id=:tenant_id"
            )

            params["tenant_id"] = tenant_id

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

        FROM forex_accounts
        """

        if where:

            sql += " WHERE "

            sql += " AND ".join(where)

        sql += """

        ORDER BY

            updated_at DESC

        """

        rows = self.db.execute(
            text(sql),
            params,
        ).mappings().all()

        return [

            dict(r)

            for r in rows

        ]

    # ------------------------------------------------------------------
    # Incremental Updates
    # ------------------------------------------------------------------

    def update_balance(
        self,
        *,
        account_id: str,
        balance: float,
        equity: Optional[float] = None,
        cash: Optional[float] = None,
    ) -> None:

        self.db.execute(text("""
        UPDATE forex_accounts

        SET

            balance=:balance,

            equity=COALESCE(:equity,equity),

            cash=COALESCE(:cash,cash),

            updated_at=:updated_at

        WHERE id=:id
        """), {

            "id": account_id,

            "balance": balance,

            "equity": equity,

            "cash": cash,

            "updated_at": _utc_now().replace(
                tzinfo=None,
            ),

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def update_margin(
        self,
        *,
        account_id: str,
        used_margin: float,
        free_margin: float,
        margin_level: float,
    ) -> None:

        self.db.execute(text("""
        UPDATE forex_accounts

        SET

            used_margin=:used_margin,

            free_margin=:free_margin,

            margin_level=:margin_level,

            updated_at=:updated_at

        WHERE id=:id
        """), {

            "id": account_id,

            "used_margin": used_margin,

            "free_margin": free_margin,

            "margin_level": margin_level,

            "updated_at": _utc_now().replace(
                tzinfo=None,
            ),

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def update_exposure(
        self,
        *,
        account_id: str,
        exposure: float,
        open_positions: int,
        open_orders: int,
    ) -> None:

        self.db.execute(text("""
        UPDATE forex_accounts

        SET

            total_exposure=:exposure,

            open_positions=:positions,

            open_orders=:orders,

            updated_at=:updated_at

        WHERE id=:id
        """), {

            "id": account_id,

            "exposure": exposure,

            "positions": open_positions,

            "orders": open_orders,

            "updated_at": _utc_now().replace(
                tzinfo=None,
            ),

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def delete_projection(
        self,
        *,
        account_id: str,
    ) -> None:

        self.db.execute(text("""
        DELETE

        FROM forex_accounts

        WHERE id=:id
        """), {

            "id": account_id,

        })

        self.db.commit()

    # ------------------------------------------------------------------

    def rebuild_projection(
        self,
        *,
        account: Dict[str, Any],
    ) -> None:

        self.project_account(
            account=account,
        )


# ==============================================================================
# Factory
# ==============================================================================

_ACCOUNT_REPOSITORY = None


def get_execution_account_repository(
    *,
    db,
    cache: bool = True,
) -> ExecutionAccountRepository:

    global _ACCOUNT_REPOSITORY

    if (
        not cache
        or _ACCOUNT_REPOSITORY is None
    ):

        _ACCOUNT_REPOSITORY = (
            ExecutionAccountRepository(
                db=db,
            )
        )

    return _ACCOUNT_REPOSITORY