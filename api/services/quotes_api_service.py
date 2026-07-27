"""
api/services/quotes_api_service.py

Quotes API Service

Backs GET /api/v1/quotes/{symbol}.

Not tenant-scoped -- market data isn't a per-tenant resource. Wraps
modules.market_data.service.get_latest_price (which already fails over
across multiple real providers) for the current price, and the most
recent two bars of get_price_history for day-over-day change -- both
real data sources, not derived/estimated figures.
"""

from __future__ import annotations

import logging
from typing import Any

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class QuotesAPIService:
    """
    API service for a single-symbol quote: latest price plus
    day-over-day change, both from real market data providers.
    """

    def __init__(self, db):
        # Quotes aren't tenant-scoped, but the underlying market data
        # orchestrator still needs a working session for its own
        # provider-learning bookkeeping -- passing None here breaks
        # that internally and silently degrades every quote to
        # "unavailable" instead of raising, so don't be tempted to skip
        # this the way an earlier version of this file did.
        self.db = db

    def get_quote(self, *, symbol: str) -> dict[str, Any]:
        """
        Always returns a dict (there's no "portfolio not found" concept
        here) -- available=False with a reason if no live price can be
        fetched, rather than raising.
        """

        symbol = symbol.upper().strip()

        # This service's db session is cached and reused across every
        # request to this endpoint for the life of the process (see
        # ModuleRegistry._load). If an earlier request left it in a
        # failed-transaction state (Postgres) and didn't roll back,
        # every query below would otherwise fail immediately. Rolling
        # back a clean session is a harmless no-op.
        _safe_rollback(self.db)

        from modules.market_data.service import get_latest_price, get_price_history

        try:
            price = get_latest_price(symbol, db=self.db)
        except Exception:
            logger.exception("Quote lookup failed | %s", symbol)
            _safe_rollback(self.db)
            price = None

        if price is None:
            return {
                "symbol": symbol,
                "available": False,
                "reason": "No live price available for this symbol.",
            }

        previous_close = None
        change = None
        change_pct = None

        try:
            history = get_price_history(self.db, symbol, period="5d", interval="1d")
            if history is not None and len(history) >= 2:
                close_col = "Close" if "Close" in history.columns else "close"
                if close_col in history.columns:
                    previous_close = float(history[close_col].iloc[-2])
                    if previous_close > 0:
                        change = round(price - previous_close, 4)
                        change_pct = round((change / previous_close) * 100.0, 4)
        except Exception:
            logger.exception("Previous-close lookup failed | %s", symbol)
            _safe_rollback(self.db)

        return {
            "symbol": symbol,
            "available": True,
            "price": price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
        }