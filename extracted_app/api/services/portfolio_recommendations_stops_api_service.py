"""
api/services/portfolio_recommendations_stops_api_service.py

Portfolio Recommendations Stops API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations/stops.

Thin wrapper around modules.trading_intelligence.
recommendation_stop_loss_monitor.RecommendationStopLossMonitor --
distance-to-stop, risk-remaining, and drawdown math all stay there.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._recommendations_shared import df_to_records, _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationsStopsAPIService:
    """
    API service for stop-loss monitoring on open recommendation-driven
    positions: distance to stop, risk dollars remaining, drawdown.
    Wraps RecommendationStopLossMonitor.
    """

    def __init__(self, db):
        self.db = db

    def get_stops(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Stop-monitoring summary plus per-position detail (distance to
        stop, risk remaining, drawdown, status), active stop alerts,
        and stop breaches.

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
            from modules.trading_intelligence.recommendation_stop_loss_monitor import (
                RecommendationStopLossMonitor,
            )

            engine = RecommendationStopLossMonitor(self.db)

            summary = engine.generate_stop_summary(portfolio_id)
            monitor = df_to_records(engine.generate_monitor_view(portfolio_id))
            alerts = engine.get_stop_alerts(portfolio_id)
            breaches = df_to_records(engine.get_stop_breaches(portfolio_id))

        except Exception:
            logger.exception(
                "Stop monitoring failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "summary": {},
                "positions": [],
                "alerts": [],
                "stop_breaches": [],
                "note": "Stop monitoring data unavailable.",
            }

        return {
            "portfolio_id": str(portfolio_id),
            "summary": summary,
            "positions": monitor,
            "alerts": alerts,
            "stop_breaches": breaches,
        }