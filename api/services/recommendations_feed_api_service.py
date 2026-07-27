"""
api/services/recommendations_feed_api_service.py

Recommendations Feed API Service

Backs GET /api/v1/recommendations (tenant-wide, not portfolio-scoped --
for the portfolio-scoped version see
api.services.portfolio_recommendation_api_service).

Deliberately does NOT call
modules.trading_intelligence.recommendation_lifecycle_engine.
RecommendationLifecycleEngine.get_all_recommendations(portfolio_id=None)
for this: that method filters by portfolio_id when given one, but has
no tenant_id filtering at all -- calling it with portfolio_id=None
would return every tenant's recommendations, not just this one's. This
queries trade_recommendations directly with an explicit tenant_id
filter instead.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


class RecommendationsFeedAPIService:
    """API service for a tenant-wide recommendation feed."""

    def __init__(self, db):
        self.db = db

    def get_recommendations(
        self,
        *,
        tenant_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:

        try:
            from modules.trading_intelligence.recommendation_engine import (
                TradeRecommendationEngine,
            )
            TradeRecommendationEngine(self.db, tenant_id).ensure_schema()
        except Exception:
            logger.exception("Unable to ensure trade_recommendations schema.")
            try:
                self.db.rollback()
            except Exception:
                pass

        sql = "SELECT * FROM trade_recommendations WHERE tenant_id = :tenant_id"
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}

        if status:
            sql += " AND status = :status"
            params["status"] = status

        sql += " ORDER BY created_at DESC LIMIT :limit"

        try:
            rows = self.db.execute(text(sql), params).mappings().all()
        except Exception:
            logger.exception("Recommendations feed query failed | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {"tenant_id": tenant_id, "result_count": 0, "recommendations": []}

        recommendations = []
        for row in rows:
            r = dict(row)
            if r.get("created_at") is not None:
                r["created_at"] = str(r["created_at"])
            if r.get("executed_at") is not None:
                r["executed_at"] = str(r["executed_at"])
            recommendations.append(r)

        return {
            "tenant_id": tenant_id,
            "result_count": len(recommendations),
            "recommendations": recommendations,
        }