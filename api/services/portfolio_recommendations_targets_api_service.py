"""
api/services/portfolio_recommendations_targets_api_service.py

Portfolio Recommendations Targets API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations/targets.

Thin wrapper around modules.trading_intelligence.
recommendation_target_tracking_engine.RecommendationTargetTrackingEngine
-- progress-to-target, distance, and reward-remaining math all stay
there.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._recommendations_shared import df_to_records, _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationsTargetsAPIService:
    """
    API service for target-price tracking on open recommendation-driven
    positions: progress to target, distance remaining, reward
    remaining. Wraps RecommendationTargetTrackingEngine.
    """

    def __init__(self, db):
        self.db = db

    def get_targets(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Target-tracking summary plus per-position detail (progress to
        target, distance remaining, reward remaining, status), active
        target alerts, and target hits.

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
            from modules.trading_intelligence.recommendation_target_tracking_engine import (
                RecommendationTargetTrackingEngine,
            )

            engine = RecommendationTargetTrackingEngine(self.db)

            summary = engine.generate_target_summary(portfolio_id)
            tracking = df_to_records(engine.generate_tracking_view(portfolio_id))
            alerts = engine.get_target_alerts(portfolio_id)
            hits = df_to_records(engine.get_target_hits(portfolio_id))

        except Exception:
            logger.exception(
                "Target tracking failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "summary": {},
                "positions": [],
                "alerts": [],
                "target_hits": [],
                "note": "Target tracking data unavailable.",
            }

        return {
            "portfolio_id": str(portfolio_id),
            "summary": summary,
            "positions": tracking,
            "alerts": alerts,
            "target_hits": hits,
        }