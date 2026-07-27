"""
api/services/market_history_api_service.py

Market History API Service

Backs GET /api/v1/history/{symbol}.

Not tenant-scoped. Thin wrapper around
modules.market_data.service.get_price_history -- all provider
failover/caching logic stays there.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class MarketHistoryAPIService:
    """API service for historical OHLCV bars for a single symbol."""

    def __init__(self, db):
        # History isn't tenant-scoped, but the underlying market data
        # orchestrator still needs a working session for its own
        # provider-learning bookkeeping -- passing None here breaks
        # that internally and silently degrades every request to
        # "unavailable" instead of raising, so don't be tempted to skip
        # this the way an earlier version of this file did.
        self.db = db

    def get_history(
        self,
        *,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """
        Always returns a dict -- available=False with a reason if no
        history can be fetched, rather than raising.
        """

        symbol = symbol.upper().strip()

        # This service's db session is cached and reused across every
        # request to this endpoint for the life of the process (see
        # ModuleRegistry._load). If an earlier request left it in a
        # failed-transaction state (Postgres) and didn't roll back,
        # every query below would otherwise fail immediately. Rolling
        # back a clean session is a harmless no-op.
        _safe_rollback(self.db)

        from modules.market_data.service import get_price_history

        try:
            df = get_price_history(self.db, symbol, period=period, interval=interval)
        except Exception:
            logger.exception("History lookup failed | %s", symbol)
            _safe_rollback(self.db)
            df = None

        if df is None or df.empty:
            return {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "available": False,
                "reason": "No historical data available for this symbol/period.",
                "bars": [],
            }

        clean = df.copy()
        clean.index = clean.index.astype(str)
        clean = clean.reset_index().rename(columns={clean.reset_index().columns[0]: "date"})
        clean = clean.replace([np.inf, -np.inf], np.nan).where(pd.notnull(clean), None)

        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "available": True,
            "bar_count": len(clean),
            "bars": clean.to_dict(orient="records"),
        }