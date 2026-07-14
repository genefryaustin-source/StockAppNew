from __future__ import annotations

import logging
import uuid

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text

from modules.forex.forex_watchlist_models import (
    ForexWatchlist,
    ForexWatchlistItem,
)
from modules.forex.forex_watchlist_repository import (
    ForexWatchlistRepository,
)

logger = logging.getLogger(__name__)


# ==========================================================
# Default Universes
# ==========================================================

MAJOR_PAIRS = [

    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "NZD/USD",
    "USD/CAD",

]

CROSS_PAIRS = [

    "EUR/GBP",
    "EUR/JPY",
    "EUR/CHF",
    "EUR/AUD",
    "EUR/CAD",
    "GBP/JPY",
    "GBP/CHF",
    "GBP/AUD",
    "AUD/JPY",
    "AUD/NZD",
    "CAD/JPY",
    "CHF/JPY",
    "NZD/JPY",

]


class ForexWatchlistService:

    def __init__(
        self,
        *,
        db,
        tenant_id: str,
        user_id: str,
        portfolio_id: Optional[str] = None,
    ):

        self.db = db

        self.tenant_id = tenant_id

        self.user_id = user_id

        self.portfolio_id = portfolio_id

        self.repository = ForexWatchlistRepository(

            db=db,

            tenant_id=tenant_id,

            user_id=user_id,

        )

    # ======================================================
    # Default Watchlist
    # ======================================================

    def get_or_create_default_watchlist(
        self,
    ) -> ForexWatchlist:

        watchlist_id = self.repository.get_default_watchlist_id(

            portfolio_id=self.portfolio_id,

        )

        if watchlist_id is None:

            watchlist_id = self.repository.create_default_watchlist(

                portfolio_id=self.portfolio_id,

            )

        watchlist = self.repository.load_watchlist(

            watchlist_id=watchlist_id,

        )

        if watchlist is None:

            raise RuntimeError(

                "Unable to create default watchlist."

            )

        return watchlist

    # ======================================================
    # Pair Exists
    # ======================================================

    def pair_exists(
        self,
        *,
        pair: str,
    ) -> bool:

        watchlist = self.get_or_create_default_watchlist()

        pair = pair.upper().strip()

        for item in watchlist.items:

            if item.pair.upper() == pair:

                return True

        return False

    # ======================================================
    # List Pairs
    # ======================================================

    def list_pairs(
        self,
    ) -> List[str]:

        watchlist = self.get_or_create_default_watchlist()

        return [

            item.pair

            for item in watchlist.items

        ]

    def pair_count(
            self,
    ) -> int:

        return len(
            self.list_pairs()
        )

    def is_empty(
            self,
    ) -> bool:

        return self.pair_count() == 0

    def validate_pair(
            self,
            pair: str,
    ) -> bool:

        return pair.upper() in self.list_pairs()



    # ======================================================
    # Add Pair
    # ======================================================

    def add_pair(
        self,
        *,
        pair: str,
        ai_enabled: bool = True,
        alerts_enabled: bool = True,
        auto_trade_enabled: bool = False,
        notes: str = "",
    ) -> bool:

        pair = pair.upper().strip()

        if self.pair_exists(pair=pair):

            return False

        watchlist = self.get_or_create_default_watchlist()

        now = datetime.utcnow()

        self.db.execute(

            text("""

            INSERT INTO forex_watchlist_items (

                id,

                watchlist_id,

                pair,

                display_order,

                ai_enabled,

                alerts_enabled,

                auto_trade_enabled,

                notes,

                created_at,

                updated_at

            )

            VALUES (

                :id,

                :watchlist_id,

                :pair,

                :display_order,

                :ai_enabled,

                :alerts_enabled,

                :auto_trade_enabled,

                :notes,

                :created_at,

                :updated_at

            )

            """),

            {

                "id": str(uuid.uuid4()),

                "watchlist_id": watchlist.id,

                "pair": pair,

                "display_order": len(watchlist.items),

                "ai_enabled": ai_enabled,

                "alerts_enabled": alerts_enabled,

                "auto_trade_enabled": auto_trade_enabled,

                "notes": notes,

                "created_at": now,

                "updated_at": now,

            },

        )

        self.db.commit()

        return True

    # ======================================================
    # Remove Pair
    # ======================================================

    def remove_pair(
        self,
        *,
        pair: str,
    ) -> bool:

        watchlist = self.get_or_create_default_watchlist()

        result = self.db.execute(

            text("""

            DELETE

            FROM forex_watchlist_items

            WHERE

                watchlist_id=:watchlist_id

            AND

                UPPER(pair)=:pair

            """),

            {

                "watchlist_id": watchlist.id,

                "pair": pair.upper(),

            },

        )

        self.db.commit()

        return result.rowcount > 0

    def get_pairs_for_ui(
            self,
    ) -> List[str]:

        pairs = sorted(

            {

                item.pair.upper()

                for item in self.load_watchlist().items

            }

        )

        return pairs

    def get_ai_enabled_pairs(self) -> List[str]:

        watchlist = self.load_watchlist()

        return [

            item.pair

            for item in watchlist.items

            if item.ai_enabled

        ]

    def get_alert_enabled_pairs(self) -> List[str]:

        watchlist = self.load_watchlist()

        return [

            item.pair

            for item in watchlist.items

            if item.alerts_enabled

        ]

    def get_auto_trade_pairs(self) -> List[str]:

        watchlist = self.load_watchlist()

        return [

            item.pair

            for item in watchlist.items

            if item.auto_trade_enabled

        ]

    def get_pair_records(self) -> List[ForexWatchlistItem]:

        return self.load_watchlist().items

    def refresh_default_watchlist(self) -> ForexWatchlist:

        return self.get_or_create_default_watchlist()



    # ======================================================
    # Seed Helpers
    # ======================================================

    def seed_pairs(
        self,
        *,
        pairs: List[str],
    ) -> int:

        count = 0

        for pair in pairs:

            if self.add_pair(pair=pair):

                count += 1

        return count

    def seed_major_pairs(
        self,
    ) -> int:

        return self.seed_pairs(

            pairs=MAJOR_PAIRS,

        )

    def seed_cross_pairs(
        self,
    ) -> int:

        return self.seed_pairs(

            pairs=CROSS_PAIRS,

        )

    def seed_all_pairs(
        self,
    ) -> int:

        return (

            self.seed_major_pairs()

            +

            self.seed_cross_pairs()

        )

    # ======================================================
    # Load
    # ======================================================

    def load_watchlist(
        self,
    ) -> ForexWatchlist:

        return self.get_or_create_default_watchlist()

    # ======================================================
    # Dictionary
    # ======================================================

    def to_dict(
        self,
    ) -> Dict:

        return self.load_watchlist().to_dict()