"""
api/services/portfolio_recommendations_alerts_api_service.py

Portfolio Recommendations Alerts API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations/alerts.

Thin wrapper around modules.trading_intelligence.recommendation_alert_center.
RecommendationAlertCenter -- already a cross-cutting aggregator that
pulls from the target, stop, trade-management, portfolio-risk, and
lifecycle engines into one deduplicated, severity-ranked alert feed.
This adapter doesn't re-aggregate anything itself.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._recommendations_shared import df_to_records, _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationsAlertsAPIService:
    """
    API service for the unified recommendation alert feed. Wraps
    RecommendationAlertCenter, which already aggregates target, stop,
    trade-management, portfolio-risk, and lifecycle alerts into one
    deduplicated, severity-ranked list.
    """

    def __init__(self, db):
        self.db = db

    def get_alerts(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        persist: bool = False,
    ) -> dict[str, Any] | None:
        """
        Active alerts (target, stop, trade-management, portfolio-risk,
        and lifecycle combined), deduplicated and sorted by severity,
        plus alert counts by severity/type.

        persist=True also writes new alerts to the recommendation_alerts
        table (RecommendationAlertCenter.persist_alerts) -- off by
        default since this is a read endpoint.

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
            from modules.trading_intelligence.recommendation_alert_center import (
                RecommendationAlertCenter,
            )

            engine = RecommendationAlertCenter(self.db)
            engine.ensure_schema()

            active = df_to_records(
                engine.get_active_alerts(portfolio_id=portfolio_id, persist=persist)
            )
            counts = engine.get_alert_counts(portfolio_id)

        except Exception:
            logger.exception(
                "Alert aggregation failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "alerts": [],
                "counts": {},
                "note": "Alert data unavailable.",
            }

        return {
            "portfolio_id": str(portfolio_id),
            "alerts": active,
            "counts": counts,
        }