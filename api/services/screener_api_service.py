"""
api/services/screener_api_service.py

Screener API Service

Backs GET /api/v1/screener.

Thin wrapper around modules.analytics.screener.run_screener, which
filters the most recent AnalyticsSnapshot per symbol for a tenant --
the same composite/quality/growth/value/momentum/risk scores the
portfolio Intelligence workspace uses. All filtering logic stays there.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

logger = logging.getLogger(__name__)


class ScreenerAPIService:
    """API service for screening symbols by their latest analytics scores."""

    def __init__(self, db):
        self.db = db

    def run_screen(
        self,
        *,
        tenant_id: str,
        sector: str | None = None,
        min_composite: float | None = None,
        min_confidence: float | None = None,
        rating_in: list[str] | None = None,
        min_quality: float | None = None,
        min_growth: float | None = None,
        min_value: float | None = None,
        min_momentum: float | None = None,
        max_risk: float | None = None,
    ) -> dict[str, Any]:

        from modules.analytics.screener import run_screener

        try:
            rows = run_screener(
                self.db,
                tenant_id,
                sector=sector,
                min_composite=min_composite,
                min_confidence=min_confidence,
                rating_in=rating_in,
                min_quality=min_quality,
                min_growth=min_growth,
                min_value=min_value,
                min_momentum=min_momentum,
                max_risk=max_risk,
            )
        except Exception:
            logger.exception("Screener run failed | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "result_count": 0,
                "results": [],
                "note": "Screener data unavailable.",
            }

        return {
            "result_count": len(rows),
            "results": [asdict(r) for r in rows],
        }