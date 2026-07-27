"""
api/services/forex_market_data_api_service.py

Forex Market Data API Service

Backs GET /api/v1/forex/quotes/{pair} and GET /api/v1/forex/pairs.

Wraps modules.forex.forex_service.ForexService -- already registered in
module_registry as registry.forex(), never routed until now.

Worth knowing: ForexService.get_quote() has a three-tier fallback --
real aggregator, then a real provider router, then (only if both of
those produce nothing) a hardcoded, static "synthetic_fallback" quote
(fixed values like EUR/USD always exactly 1.0800, never actually
updating). Unlike some other fabricated-data patterns found elsewhere
in this codebase, this fallback DOES honestly self-label via its
"source" and "provider" fields rather than silently pretending to be
real -- this adapter deliberately never strips or hides those fields,
so a caller can always tell whether they got a live quote or the
static fallback.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ForexMarketDataAPIService:
    """API service for forex quotes and supported pairs. Not tenant-scoped -- market data isn't a per-tenant resource."""

    def __init__(self, db):
        # Not used for anything DB-specific here, but ForexService's
        # own quote aggregator can optionally use a db session for
        # caching, so it's passed through rather than dropped.
        self.db = db

    def get_quote(self, *, pair: str) -> dict[str, Any]:
        """
        Current quote for a pair. Always includes "source" and
        "provider" -- check these: "synthetic_fallback" means this is
        a static placeholder value, not a live market quote (see
        module docstring).
        """

        try:
            from modules.forex.forex_service import ForexService

            service = ForexService(self.db)
            quote = service.get_quote(pair)

            return quote.to_dict()

        except Exception:
            logger.exception("Forex quote lookup failed | %s", pair)
            return {
                "pair": pair,
                "available": False,
                "reason": "Quote lookup failed.",
            }

    def get_pairs(self) -> dict[str, Any]:
        """Every currency pair this platform supports quoting/trading for."""

        try:
            from modules.forex.forex_service import ForexService

            service = ForexService(self.db)
            pairs = service.supported_pairs()

        except Exception:
            logger.exception("Failed to list supported forex pairs.")
            pairs = []

        return {
            "pair_count": len(pairs),
            "pairs": pairs,
        }