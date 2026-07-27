"""
api/services/crypto_market_data_api_service.py

Crypto Market Data API Service

Backs GET /api/v1/crypto/coins, /coins/{id}, /global, /trending,
/fear-greed, /search. Wraps modules.crypto.data_service directly --
real CoinGecko/Alternative.me data, free, no API key required. No new
logic lives here.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """DataFrame -> list of records, NaN -> None, so this is always valid JSON."""
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return []
        clean = value.replace([math.inf, -math.inf], None).where(pd.notnull(value), None)
        return clean.to_dict(orient="records")

    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    if isinstance(value, float) and value != value:  # NaN
        return None

    return value


class CryptoMarketDataAPIService:
    """API service for crypto market data."""

    def __init__(self, db=None):
        # Not used for queries (this is pure external market data), but
        # module_registry._load() always instantiates services as
        # cls(db) -- accepting it here keeps this class consistent
        # with every other registered service rather than needing a
        # special case in the registry.
        self.db = db

    def get_top_coins(self, *, limit: int = 100, category: str | None = None) -> dict[str, Any]:
        try:
            from modules.crypto.data_service import get_top_coins

            df = get_top_coins(limit=limit, category=category)
            coins = _json_safe(df)
            return {"coin_count": len(coins), "coins": coins}

        except Exception:
            logger.exception("Failed to load top coins.")
            return {"available": False, "reason": "This section failed to load."}

    def get_coin_detail(self, *, coin_id: str) -> dict[str, Any]:
        try:
            from modules.crypto.data_service import get_coin_detail

            detail = get_coin_detail(coin_id)

            if not detail:
                return {"available": False, "reason": f"No data found for coin id '{coin_id}'."}

            return _json_safe(detail)

        except Exception:
            logger.exception("Failed to load coin detail | coin_id=%s", coin_id)
            return {"available": False, "reason": "This section failed to load."}

    def get_global_stats(self) -> dict[str, Any]:
        try:
            from modules.crypto.data_service import get_global_stats

            return _json_safe(get_global_stats())

        except Exception:
            logger.exception("Failed to load global crypto stats.")
            return {"available": False, "reason": "This section failed to load."}

    def get_trending(self) -> dict[str, Any]:
        try:
            from modules.crypto.data_service import get_trending

            trending = _json_safe(get_trending())
            return {"coin_count": len(trending), "coins": trending}

        except Exception:
            logger.exception("Failed to load trending coins.")
            return {"available": False, "reason": "This section failed to load."}

    def get_fear_greed(self, *, limit: int = 30) -> dict[str, Any]:
        try:
            from modules.crypto.data_service import get_fear_greed

            df = get_fear_greed(limit=limit)
            records = _json_safe(df)
            return {"record_count": len(records), "history": records}

        except Exception:
            logger.exception("Failed to load fear/greed index.")
            return {"available": False, "reason": "This section failed to load."}

    def search_coin(self, *, query: str) -> dict[str, Any]:
        try:
            from modules.crypto.data_service import search_coin

            results = _json_safe(search_coin(query))
            return {"result_count": len(results), "results": results}

        except Exception:
            logger.exception("Failed to search coins | query=%s", query)
            return {"available": False, "reason": "This section failed to load."}