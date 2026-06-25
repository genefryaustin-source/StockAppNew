
"""
modules/forex/forex_refresh_engine.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from modules.forex.forex_price_service import get_forex_price_service

logger = logging.getLogger(__name__)

DEFAULT_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "NZD/USD",
    "USD/CAD",
    "EUR/GBP",
    "EUR/JPY",
    "GBP/JPY",
    "AUD/JPY",
    "CAD/JPY",
]


class ForexRefreshEngine:

    def __init__(self):
        self.price_service = get_forex_price_service()

    def refresh_pair(
        self,
        pair: str,
    ) -> dict:
        quote = self.price_service.get_quote(
            pair,
            force_refresh=True,
        )

        quote["refreshed_at"] = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
        )

        return quote

    def refresh_pairs(
        self,
        pairs: Iterable[str],
    ) -> dict[str, dict]:

        results = {}

        for pair in pairs:
            try:
                results[pair] = self.refresh_pair(pair)
            except Exception as exc:
                logger.exception(
                    "Forex refresh failed for %s",
                    pair,
                )
                results[pair] = {
                    "pair": pair,
                    "error": str(exc),
                }

        return results

    def refresh_default_universe(self) -> dict[str, dict]:
        return self.refresh_pairs(DEFAULT_PAIRS)

    def health_check(self) -> dict:
        results = self.refresh_pairs(
            DEFAULT_PAIRS[:5]
        )

        success = sum(
            1
            for r in results.values()
            if not r.get("error")
        )

        return {
            "pairs_tested": len(results),
            "successful": success,
            "failed": len(results) - success,
            "success_rate": round(
                success / max(len(results), 1) * 100,
                2,
            ),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }


_ENGINE = None


def get_forex_refresh_engine():
    global _ENGINE

    if _ENGINE is None:
        _ENGINE = ForexRefreshEngine()

    return _ENGINE
