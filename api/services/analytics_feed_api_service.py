"""
api/services/analytics_feed_api_service.py

Analytics Feed API Service

Backs GET /api/v1/analytics (symbol-scoped, tenant-scoped -- for the
portfolio-scoped version see api.services.portfolio_analytics via
modules.portfolio.portfolio_analytics_service).

Reads the most recent modules.analytics.models.AnalyticsSnapshot for a
symbol -- the same composite/quality/growth/value/momentum/risk scores
the screener filters on and the portfolio Intelligence workspace shows.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnalyticsFeedAPIService:
    """API service for a single symbol's latest analytics snapshot."""

    def __init__(self, db):
        self.db = db

    def get_analytics(
        self,
        *,
        tenant_id: str,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Always returns a dict -- available=False with a reason if no
        snapshot exists for this symbol/tenant yet, rather than raising.
        """

        symbol = symbol.upper().strip()

        try:
            from modules.analytics.models import AnalyticsSnapshot

            snapshot = (
                self.db.query(AnalyticsSnapshot)
                .filter(
                    AnalyticsSnapshot.tenant_id == tenant_id,
                    AnalyticsSnapshot.symbol == symbol,
                )
                .order_by(AnalyticsSnapshot.asof.desc())
                .first()
            )
        except Exception:
            logger.exception("Analytics lookup failed | %s", symbol)
            try:
                self.db.rollback()
            except Exception:
                pass
            snapshot = None

        if snapshot is None:
            return {
                "symbol": symbol,
                "available": False,
                "reason": "No analytics snapshot available for this symbol yet.",
            }

        data = {
            column.name: getattr(snapshot, column.name)
            for column in snapshot.__table__.columns
        }

        if data.get("asof") is not None:
            data["asof"] = data["asof"].isoformat()

        data["available"] = True

        return data