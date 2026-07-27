from __future__ import annotations

import logging
import uuid

from datetime import datetime
from typing import List, Optional

from sqlalchemy import text

from modules.forex.forex_watchlist_models import (
    ForexWatchlist,
    ForexWatchlistItem,
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Repository initialization state
#
# Tables are created once during application bootstrap.
# -----------------------------------------------------------------------------

_INITIALIZED = False
class ForexWatchlistRepository:

    def __init__(
        self,
        *,
        db,
        tenant_id: str,
        user_id: str,
    ):

        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

        # ensure_tables() is correctly written (module-level _INITIALIZED
        # guard, safe to call repeatedly) but was never actually invoked
        # anywhere -- every call site below was commented out on the
        # same "tables are created during bootstrap" assumption found
        # (and fixed) elsewhere in this module. Confirmed directly:
        # forex_trading_desk_dashboard.py crashed with "no such table:
        # forex_watchlists" on a fresh database.
        self.ensure_tables()

    # ======================================================
    # Tables
    # ======================================================

    def ensure_tables(self):

        global _INITIALIZED

        if _INITIALIZED:
            return

        #
        # Existing CREATE TABLE statements remain unchanged below
        #

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_watchlists (

            id VARCHAR(36) PRIMARY KEY,

            tenant_id VARCHAR(100) NOT NULL,

            user_id VARCHAR(100) NOT NULL,

            portfolio_id VARCHAR(36),

            watchlist_name VARCHAR(100) NOT NULL,

            is_default BOOLEAN DEFAULT FALSE,

            created_at TIMESTAMP,

            updated_at TIMESTAMP

        )

        """))

        self.db.execute(text("""

        CREATE TABLE IF NOT EXISTS forex_watchlist_items (

            id VARCHAR(36) PRIMARY KEY,

            watchlist_id VARCHAR(36) NOT NULL,

            pair VARCHAR(20) NOT NULL,

            display_order INTEGER DEFAULT 0,

            ai_enabled BOOLEAN DEFAULT TRUE,

            alerts_enabled BOOLEAN DEFAULT TRUE,

            auto_trade_enabled BOOLEAN DEFAULT FALSE,

            notes TEXT,

            created_at TIMESTAMP,

            updated_at TIMESTAMP

        )

        """))

        self.db.commit()

        _INITIALIZED = True

    # ======================================================
    # Create Default Watchlist
    # ======================================================

    def create_default_watchlist(
        self,
        *,
        portfolio_id: Optional[str],
    ) -> str:

        #self.ensure_tables()

        watchlist_id = str(uuid.uuid4())

        now = datetime.utcnow()

        self.db.execute(

            text("""

            INSERT INTO forex_watchlists (

                id,
                tenant_id,
                user_id,
                portfolio_id,
                watchlist_name,
                is_default,
                created_at,
                updated_at

            )

            VALUES (

                :id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :watchlist_name,
                TRUE,
                :created_at,
                :updated_at

            )

            """),

            {

                "id": watchlist_id,

                "tenant_id": self.tenant_id,

                "user_id": self.user_id,

                "portfolio_id": portfolio_id,

                "watchlist_name": "Default",

                "created_at": now,

                "updated_at": now,

            },

        )

        self.db.commit()

        return watchlist_id

    # ======================================================
    # Default Watchlist Lookup
    # ======================================================

    def get_default_watchlist_id(
        self,
        *,
        portfolio_id: Optional[str],
    ) -> Optional[str]:

        #self.ensure_tables()

        row = self.db.execute(

            text("""

            SELECT id

            FROM forex_watchlists

            WHERE

                tenant_id=:tenant_id

            AND user_id=:user_id

            AND

            (

                portfolio_id=:portfolio_id

                OR

                portfolio_id IS NULL

            )

            AND is_default=TRUE

            LIMIT 1

            """),

            {

                "tenant_id": self.tenant_id,

                "user_id": self.user_id,

                "portfolio_id": portfolio_id,

            },

        ).fetchone()

        if row:

            return row[0]

        return None

    # ======================================================
    # Load
    # ======================================================

    def load_watchlist(
        self,
        *,
        watchlist_id: str,
    ) -> Optional[ForexWatchlist]:

        #self.ensure_tables()

        row = self.db.execute(

            text("""

            SELECT *

            FROM forex_watchlists

            WHERE id=:id

            """),

            {

                "id": watchlist_id,

            },

        ).fetchone()

        if row is None:

            return None

        items = self.list_items(

            watchlist_id=watchlist_id

        )

        return ForexWatchlist(

            id=row.id,

            tenant_id=row.tenant_id,

            user_id=row.user_id,

            portfolio_id=row.portfolio_id,

            watchlist_name=row.watchlist_name,

            is_default=row.is_default,

            created_at=row.created_at,

            updated_at=row.updated_at,

            items=items,

        )

    # ======================================================
    # Items
    # ======================================================

    def list_items(
        self,
        *,
        watchlist_id: str,
    ) -> List[ForexWatchlistItem]:

        rows = self.db.execute(

            text("""

            SELECT *

            FROM forex_watchlist_items

            WHERE watchlist_id=:id

            ORDER BY display_order,pair

            """),

            {

                "id": watchlist_id,

            },

        ).fetchall()

        results = []

        for row in rows:

            results.append(

                ForexWatchlistItem(

                    id=row.id,

                    watchlist_id=row.watchlist_id,

                    pair=row.pair,

                    display_order=row.display_order,

                    ai_enabled=row.ai_enabled,

                    alerts_enabled=row.alerts_enabled,

                    auto_trade_enabled=row.auto_trade_enabled,

                    notes=row.notes or "",

                    created_at=row.created_at,

                    updated_at=row.updated_at,

                )

            )

        return results