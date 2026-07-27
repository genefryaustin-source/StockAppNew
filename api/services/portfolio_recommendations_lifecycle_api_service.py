"""
api/services/portfolio_recommendations_lifecycle_api_service.py

Portfolio Recommendations Lifecycle API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations/lifecycle.

Thin wrapper around modules.trading_intelligence.recommendation_lifecycle_engine.
RecommendationLifecycleEngine -- all lifecycle-state logic (OPEN,
EXECUTED, TARGET_APPROACHING, TARGET_HIT, STOP_APPROACHING, STOP_HIT,
CLOSED_WIN, CLOSED_LOSS, EXPIRED) stays there.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._recommendations_shared import df_to_records, _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationsLifecycleAPIService:
    """
    API service for recommendation lifecycle state. Wraps
    RecommendationLifecycleEngine -- state derivation (OPEN through
    CLOSED_WIN/CLOSED_LOSS/EXPIRED) stays entirely in that engine.
    """

    def __init__(self, db):
        self.db = db

    def get_lifecycle(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Lifecycle summary and funnel metrics (counts at each stage from
        OPEN through closed/expired) plus the full per-recommendation
        lifecycle detail list.

        Returns None if the portfolio doesn't exist or doesn't belong
        to tenant_id -- the router turns that into a 404.
        """

        _safe_rollback(self.db)

        portfolio = (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

        if portfolio is None:
            return None

        try:
            from modules.trading_intelligence.recommendation_lifecycle_engine import (
                RecommendationLifecycleEngine,
            )

            engine = RecommendationLifecycleEngine(self.db)

            summary = engine.generate_lifecycle_summary(portfolio_id)
            funnel = engine.recommendation_funnel_metrics(portfolio_id)
            detail = df_to_records(engine.generate_lifecycle_view(portfolio_id))

        except Exception:
            logger.exception(
                "Lifecycle computation failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "summary": {},
                "funnel": {},
                "recommendations": [],
                "note": "Lifecycle data unavailable.",
            }

        return {
            "portfolio_id": str(portfolio_id),
            "summary": summary,
            "funnel": funnel,
            "recommendations": detail,
        }