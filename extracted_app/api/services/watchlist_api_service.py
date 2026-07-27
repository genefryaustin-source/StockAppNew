"""
api/services/watchlist_api_service.py

Watchlist API Service

Backs GET /api/v1/watchlists.

Two things were wrong with module_registry's original "watchlists"
entry, both fixed here:

1. It pointed at modules.watchlists.watchlist_service.WatchlistService,
   which doesn't exist -- the real file is modules.watchlists.service,
   a handful of bare functions, not a class with a db-only constructor.

2. Less obviously: modules.watchlists.models.Watchlist/WatchlistItem
   (what those bare functions are built against) is NOT the schema
   actually in the database. modules/db/core.py's init_database() never
   imports modules.watchlists.models at all -- it imports
   modules.institutional.models, which independently defines its own
   Watchlist/WatchlistItem mapped to the same "watchlists" /
   "watchlist_items" table names, and that's the definition that
   actually wins table registration. The two aren't even compatible:
   modules.institutional.models.WatchlistItem has a required tenant_id
   column modules.watchlists.models.WatchlistItem doesn't define at
   all. This adapter uses modules.institutional.models, the one that
   matches the real schema.
"""

from __future__ import annotations

import logging
from typing import Any

from modules.institutional.models import Watchlist, WatchlistItem

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class WatchlistAPIService:
    """API service for a tenant's watchlists and their symbols."""

    def __init__(self, db):
        self.db = db

    def list_watchlists(self, *, tenant_id: str) -> dict[str, Any]:
        """
        Every watchlist for a tenant, each with its symbol list.
        Returns an empty list (not an exception) on a database error.
        """

        # This service's db session is cached and reused across every
        # request to this endpoint for the life of the process (see
        # ModuleRegistry._load). If an earlier request left it in a
        # failed-transaction state (Postgres) and didn't roll back,
        # every query below -- including this very first one -- would
        # otherwise fail immediately. Rolling back a clean session is a
        # harmless no-op.
        _safe_rollback(self.db)

        try:
            watchlists = (
                self.db.query(Watchlist)
                .filter(Watchlist.tenant_id == tenant_id)
                .order_by(Watchlist.created_at.asc())
                .all()
            )

            result = []
            for wl in watchlists:
                symbols = (
                    self.db.query(WatchlistItem.symbol)
                    .filter(
                        WatchlistItem.watchlist_id == wl.id,
                        WatchlistItem.tenant_id == tenant_id,
                    )
                    .all()
                )
                result.append({
                    "id": wl.id,
                    "name": wl.name,
                    "created_at": wl.created_at.isoformat() if wl.created_at else None,
                    "symbols": [s[0] for s in symbols],
                })

        except Exception:
            logger.exception("Failed to list watchlists | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return {
                "tenant_id": tenant_id,
                "watchlist_count": 0,
                "watchlists": [],
            }

        return {
            "tenant_id": tenant_id,
            "watchlist_count": len(result),
            "watchlists": result,
        }