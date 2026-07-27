"""
api/services/portfolio_recommendations_command_center_api_service.py

Portfolio Recommendations Command Center API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations/command-center.

Thin wrapper around modules.trading_intelligence.recommendation_command_center.
RecommendationCommandCenter, which already composes lifecycle, targets,
stops, alerts, performance, attribution, and portfolio risk into one
snapshot -- this adapter validates tenant ownership and calls it, no
re-aggregation happens here.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._recommendations_shared import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationsCommandCenterAPIService:
    """
    API service for the full recommendation command-center snapshot:
    lifecycle, targets, stops, alerts, performance, attribution, and
    portfolio risk together, plus a derived health score. Wraps
    RecommendationCommandCenter -- the heaviest of the recommendations
    endpoints, since it touches every underlying engine.
    """

    def __init__(self, db):
        self.db = db

    def get_command_center(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Full command-center snapshot plus a derived 0-100 health score.

        Note: RecommendationCommandCenter.build_health_score() rebuilds
        the whole snapshot internally rather than accepting an
        already-built one, so this does the underlying aggregation
        work twice. Accepted here rather than reimplementing the score
        formula locally, which would drift out of sync with the real
        one over time -- this is already the heaviest endpoint in the
        set, so calling it twice doesn't change its performance
        category.

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
            from modules.trading_intelligence.recommendation_command_center import (
                RecommendationCommandCenter,
            )

            engine = RecommendationCommandCenter(self.db)

            snapshot = engine.build_command_snapshot(
                portfolio_id=portfolio_id,
                persist_alerts=False,
            )
            health = engine.build_health_score(portfolio_id=portfolio_id)

        except Exception:
            logger.exception(
                "Command center snapshot failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "snapshot": {},
                "health": {},
                "note": "Command center data unavailable.",
            }

        return {
            "portfolio_id": str(portfolio_id),
            "snapshot": snapshot,
            "health": health,
        }