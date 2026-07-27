"""
modules/forex/forex_portfolio_crud_engine.py

Sprint 33 Phase 1
Forex Portfolio CRUD Engine

Author: OpenAI
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text = None


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ForexPortfolioCrudEngine:

    def __init__(self, db=None):
        self.db = db

        # NOT "already bootstrapped" -- this used to be hardcoded True
        # here unconditionally, on the same false assumption found (and
        # fixed) in ForexPortfolioEngine and ForexPortfolioManager: that
        # a separate "Forex bootstrap" step already created this table.
        # It doesn't reliably happen, so every method below had its own
        # ensure_tables() call commented out on the same assumption,
        # meaning forex_portfolios could be permanently missing --
        # confirmed directly: active_portfolio()/portfolio_list() threw
        # "no such table: forex_portfolios" on a fresh database.
        self._tables_ready = False
        self.ensure_tables()

    # ---------------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------------

    def ensure_tables(self):

        if self.db is None or text is None:
            return

        if self._tables_ready:
            return

        self.db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_portfolios (

            id VARCHAR(36) PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            name VARCHAR(150) NOT NULL,

            description TEXT,

            base_currency VARCHAR(10),

            starting_balance DOUBLE PRECISION DEFAULT 100000,

            current_balance DOUBLE PRECISION DEFAULT 100000,

            status VARCHAR(30) DEFAULT 'ACTIVE',

            is_default BOOLEAN DEFAULT FALSE,

            created_at TIMESTAMP,

            updated_at TIMESTAMP

        )
        """))

        self.db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_fx_portfolio_tenant
        ON forex_portfolios(tenant_id)
        """))

        self.db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_fx_portfolio_user
        ON forex_portfolios(user_id)
        """))

        self.db.commit()

        self._tables_ready = True

    # ---------------------------------------------------------------------
    # Create
    # ---------------------------------------------------------------------

    def create_portfolio(
        self,
        *,
        tenant_id,
        user_id,
        name,
        description="",
        base_currency="USD",
        starting_balance=100000.0,
        is_default=False,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        if is_default:

            self.db.execute(text("""
            UPDATE forex_portfolios
            SET is_default=FALSE
            WHERE tenant_id=:tenant
            """), {
                "tenant": tenant_id,
            })

        portfolio_id = str(uuid.uuid4())

        now = utc_now()

        self.db.execute(text("""
        INSERT INTO forex_portfolios(

            id,
            tenant_id,
            user_id,
            name,
            description,
            base_currency,
            starting_balance,
            current_balance,
            status,
            is_default,
            created_at,
            updated_at

        )
        VALUES(

            :id,
            :tenant,
            :user,
            :name,
            :description,
            :currency,
            :starting,
            :current,
            'ACTIVE',
            :default,
            :created,
            :updated

        )
        """), {

            "id": portfolio_id,
            "tenant": tenant_id,
            "user": user_id,
            "name": name,
            "description": description,
            "currency": base_currency,
            "starting": starting_balance,
            "current": starting_balance,
            "default": is_default,
            "created": now,
            "updated": now,

        })

        self.db.commit()

        return portfolio_id

    # ---------------------------------------------------------------------
    # Read
    # ---------------------------------------------------------------------

    def list_portfolios(
            self,
            *,
            tenant_id,
            user_id,
            include_archived=False,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_portfolios
        WHERE tenant_id=:tenant
          AND user_id=:user
        """

        if not include_archived:

            sql += """
            AND status='ACTIVE'
            """

        sql += """
        ORDER BY
            is_default DESC,
            created_at
        """

        rows = self.db.execute(
            text(sql),
            {
                "tenant": tenant_id,
                "user": user_id,
            },
        ).fetchall()

        return [
            dict(r._mapping)
            for r in rows
        ]

    def get_portfolio(
        self,
        portfolio_id,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        row = self.db.execute(text("""
        SELECT *
        FROM forex_portfolios
        WHERE id=:id
        """), {
            "id": portfolio_id,
        }).fetchone()

        if row is None:
            return None

        return dict(row._mapping)

    def get_default_portfolio(
        self,
        *,
        tenant_id,
        user_id,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        row = self.db.execute(text("""
        SELECT *
        FROM forex_portfolios

        WHERE tenant_id=:tenant
          AND user_id=:user
          AND is_default=TRUE

        LIMIT 1
        """), {

            "tenant": tenant_id,
            "user": user_id,

        }).fetchone()

        if row is None:
            return None

        return dict(row._mapping)

    # ---------------------------------------------------------------------
    # Update
    # ---------------------------------------------------------------------

    def update_portfolio(
        self,
        *,
        portfolio_id,
        name,
        description,
        base_currency,
        status,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        self.db.execute(text("""
        UPDATE forex_portfolios

        SET

            name=:name,

            description=:description,

            base_currency=:currency,

            status=:status,

            updated_at=:updated

        WHERE id=:id
        """), {

            "id": portfolio_id,
            "name": name,
            "description": description,
            "currency": base_currency,
            "status": status,
            "updated": utc_now(),

        })

        self.db.commit()

    # ---------------------------------------------------------------------
    # Delete
    # ---------------------------------------------------------------------

    def delete_portfolio(
        self,
        portfolio_id,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        self.db.execute(text("""
        DELETE
        FROM forex_portfolios
        WHERE id=:id
        """), {

            "id": portfolio_id,

        })

        self.db.commit()

    # ---------------------------------------------------------------------
    # Archive
    # ---------------------------------------------------------------------

    def archive_portfolio(
        self,
        portfolio_id,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        self.db.execute(text("""
        UPDATE forex_portfolios

        SET

            status='ARCHIVED',

            updated_at=:updated

        WHERE id=:id
        """), {

            "id": portfolio_id,
            "updated": utc_now(),

        })

        self.db.commit()

    def restore_portfolio(
        self,
        portfolio_id,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        self.db.execute(text("""
        UPDATE forex_portfolios

        SET

            status='ACTIVE',

            updated_at=:updated

        WHERE id=:id
        """), {

            "id": portfolio_id,
            "updated": utc_now(),

        })

        self.db.commit()

    # ---------------------------------------------------------------------
    # Default Portfolio
    # ---------------------------------------------------------------------

    def set_default_portfolio(
        self,
        *,
        tenant_id,
        user_id,
        portfolio_id,
    ):

        #
        # Tables initialized during
        # Forex bootstrap.
        #
        # self.ensure_tables()

        self.db.execute(text("""
        UPDATE forex_portfolios

        SET is_default=FALSE

        WHERE tenant_id=:tenant
          AND user_id=:user
        """), {

            "tenant": tenant_id,
            "user": user_id,

        })

        self.db.execute(text("""
        UPDATE forex_portfolios

        SET

            is_default=TRUE,

            updated_at=:updated

        WHERE id=:id
        """), {

            "id": portfolio_id,
            "updated": utc_now(),

        })

        self.db.commit()

    # ---------------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------------

    def portfolio_statistics(
        self,
        *,
        tenant_id,
        user_id,
    ):

        portfolios = self.list_portfolios(
            tenant_id=tenant_id,
            user_id=user_id,
            include_archived=False,
        )

        return {

            "portfolio_count": len(portfolios),

            "default_portfolio": next(
                (
                    p["name"]
                    for p in portfolios
                    if p["is_default"]
                ),
                None,
            ),

            "combined_balance": sum(
                p["current_balance"]
                for p in portfolios
            ),

            "combined_starting_balance": sum(
                p["starting_balance"]
                for p in portfolios
            ),

        }


_ENGINE = None


def get_forex_portfolio_crud_engine(db=None):

    global _ENGINE

    # Previously this just swapped `_ENGINE.db = db` on the same cached
    # instance, leaving `_ENGINE._tables_ready` stuck at True from
    # whichever db session first triggered ensure_tables(). Any later call
    # with a *different* db session (a fresh request-scoped session, a
    # fresh test database, a reconnect, ...) then silently skipped
    # ensure_tables() against a database that had never actually had the
    # forex_portfolios table created in it - "no such table:
    # forex_portfolios" on every read. Rebuilding the instance when the db
    # session actually changes resets _tables_ready along with it, so it
    # gets created for real once per distinct session.
    #
    # That fix then caused a DIFFERENT real problem: comparing session
    # objects by identity (db is not db) means EVERY distinct session
    # instance -- even one pointed at the exact same database -- looks
    # "different" and triggers a full rebuild. Confirmed directly via
    # production console logs: Streamlit hands each render a fresh
    # session object, so this was rebuilding the engine (and re-running
    # every "CREATE TABLE IF NOT EXISTS" / "CREATE INDEX" statement in
    # ensure_tables()) on every single rerun -- a consistent ~450-600ms
    # DB round-trip cost on every render, not just the first one.
    #
    # Comparing the underlying engine (db.bind) instead of the session
    # object fixes both cases at once: different sessions against the
    # SAME database share the same .bind and correctly reuse the cached
    # engine (no more per-rerun rebuild), while a genuinely different
    # database -- a real reconnect, a different test DB, a different
    # Neon branch -- has a different .bind and still correctly triggers
    # a rebuild, preserving the original fix's intent.
    current_bind = getattr(db, "bind", None) if db is not None else None
    cached_bind = getattr(_ENGINE.db, "bind", None) if _ENGINE is not None and _ENGINE.db is not None else None

    if _ENGINE is None or (db is not None and current_bind is not cached_bind):
        _ENGINE = ForexPortfolioCrudEngine(db=db)

    return _ENGINE