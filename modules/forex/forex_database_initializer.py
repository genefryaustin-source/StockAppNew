"""
===============================================================================
Sprint 25 - Phase 2
Forex Database Initializer

File:
    modules/forex/forex_database_initializer.py

Purpose:
    Centralized database bootstrap and schema initialization for the Forex
    platform.

This replaces scattered ensure_tables() implementations throughout the Forex
module. Every dashboard, manager, and engine should simply call:

    get_forex_database_initializer(db).initialize()

The initializer is idempotent and only performs DDL once per process.

===============================================================================
"""

from __future__ import annotations

import threading
from typing import Optional

try:
    from sqlalchemy import text
except Exception:
    text = None


class ForexDatabaseInitializer:

    def __init__(self, db=None):
        self.db = db
        self._lock = threading.RLock()
        self._initialized = False

    # ---------------------------------------------------------------------
    # Public
    # ---------------------------------------------------------------------

    def initialize(self):

        if self.db is None:
            return

        if text is None:
            return

        if self._initialized:
            return

        with self._lock:

            if self._initialized:
                return

            try:

                self._create_tables()

                self._create_indexes()

                self.db.commit()

                self._initialized = True

                print("=" * 80)
                print("FOREX DATABASE INITIALIZED")
                print("=" * 80)

            except Exception:

                if self.db is not None:
                    self.db.rollback()

                raise

    # ---------------------------------------------------------------------
    # Tables
    # ---------------------------------------------------------------------

    def _create_tables(self):

        #
        # Portfolio
        #

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_positions (

            id SERIAL PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            account_id VARCHAR(100),

            pair VARCHAR(20),

            side VARCHAR(20),

            units DOUBLE PRECISION,

            avg_price DOUBLE PRECISION,

            market_price DOUBLE PRECISION,

            market_value DOUBLE PRECISION,

            notional_value DOUBLE PRECISION,

            unrealized_pnl DOUBLE PRECISION,

            realized_pnl DOUBLE PRECISION,

            stop_loss DOUBLE PRECISION,

            take_profit DOUBLE PRECISION,

            status VARCHAR(50),

            opened_at TIMESTAMP,

            closed_at TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_orders (

            id SERIAL PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            account_id VARCHAR(100),

            pair VARCHAR(20),

            side VARCHAR(20),

            order_type VARCHAR(30),

            units DOUBLE PRECISION,

            requested_price DOUBLE PRECISION,

            filled_price DOUBLE PRECISION,

            status VARCHAR(50),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            filled_at TIMESTAMP

        )

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_trade_orders (

            id SERIAL PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            account_id VARCHAR(100),

            broker VARCHAR(100),

            broker_order_id VARCHAR(100),

            position_id VARCHAR(100),

            pair VARCHAR(20),

            symbol VARCHAR(20),

            side VARCHAR(20),

            order_type VARCHAR(50),

            quantity DOUBLE PRECISION,

            units DOUBLE PRECISION,

            lots DOUBLE PRECISION,

            price DOUBLE PRECISION,

            limit_price DOUBLE PRECISION,

            stop_price DOUBLE PRECISION,

            target_price DOUBLE PRECISION,

            avg_fill_price DOUBLE PRECISION,

            filled_qty DOUBLE PRECISION,

            status VARCHAR(50),

            submitted_at TIMESTAMP,

            filled_at TIMESTAMP,

            cancelled_at TIMESTAMP,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            notes TEXT,

            raw_payload JSONB

        )

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_trade_journal (

            id SERIAL PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            trade_order_id VARCHAR(100),

            pair VARCHAR(20),

            side VARCHAR(20),

            setup VARCHAR(120),

            thesis TEXT,

            entry_price DOUBLE PRECISION,

            exit_price DOUBLE PRECISION,

            units DOUBLE PRECISION,

            pnl DOUBLE PRECISION,

            outcome VARCHAR(50),

            emotion VARCHAR(100),

            mistake_tags TEXT,

            lesson TEXT,

            screenshot_url TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_price_history (

            id UUID PRIMARY KEY,

            tenant_id VARCHAR(100),

            user_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            symbol VARCHAR(20),

            pair VARCHAR(20),

            base_currency VARCHAR(10),

            quote_currency VARCHAR(10),

            interval VARCHAR(20),

            asof TIMESTAMP,

            open DOUBLE PRECISION,

            high DOUBLE PRECISION,

            low DOUBLE PRECISION,

            close DOUBLE PRECISION,

            volume DOUBLE PRECISION,

            vwap DOUBLE PRECISION,

            provider VARCHAR(100),

            source VARCHAR(100),

            raw JSONB,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_history_refresh_log (

            id UUID PRIMARY KEY,

            tenant_id VARCHAR(100),

            portfolio_id VARCHAR(100),

            user_id VARCHAR(100),

            symbol VARCHAR(20),

            pair VARCHAR(20),

            interval VARCHAR(20),

            provider VARCHAR(100),

            requested_start TIMESTAMP,

            requested_end TIMESTAMP,

            rows_received INTEGER,

            rows_inserted INTEGER,

            status VARCHAR(50),

            message TEXT,

            started_at TIMESTAMP,

            completed_at TIMESTAMP,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

        """))

    # ---------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------

    def _create_indexes(self):

        statements = [

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_positions_status
            ON forex_positions(status)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_positions_portfolio
            ON forex_positions(portfolio_id,status)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_positions_user
            ON forex_positions(user_id,status)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_orders_status
            ON forex_orders(status)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_trade_orders_portfolio_status
            ON forex_trade_orders(portfolio_id,status)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_trade_orders_broker_order
            ON forex_trade_orders(broker_order_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_price_history_symbol
            ON forex_price_history(symbol,asof DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_price_history_provider
            ON forex_price_history(provider,asof DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_refresh_log_completed
            ON forex_history_refresh_log(completed_at DESC)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_journal_pair
            ON forex_trade_journal(pair)
            """,

            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_journal_user
            ON forex_trade_journal(user_id)
            """

        ]

        for sql in statements:
            self.db.execute(text(sql))


# =============================================================================
# Singleton
# =============================================================================

_INITIALIZER: Optional[ForexDatabaseInitializer] = None


def get_forex_database_initializer(db=None):

    global _INITIALIZER

    if (
        _INITIALIZER is None
        or (
            db is not None
            and getattr(_INITIALIZER, "db", None) is None
        )
    ):
        _INITIALIZER = ForexDatabaseInitializer(db=db)

    return _INITIALIZER


def initialize_forex_database(db=None):

    get_forex_database_initializer(
        db=db,
    ).initialize()