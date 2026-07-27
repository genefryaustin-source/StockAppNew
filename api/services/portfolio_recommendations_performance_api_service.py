"""
api/services/portfolio_recommendations_performance_api_service.py

Portfolio Recommendations Performance API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations/performance.

Thin wrapper around modules.trading_intelligence.recommendation_performance_engine.
RecommendationPerformanceEngine -- win rate, execution rate, and P&L
math all stay there.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._recommendations_shared import df_to_records, _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationsPerformanceAPIService:
    """
    API service for recommendation performance: win rate, execution
    rate, and realized P&L from closed trades that originated as
    recommendations. Wraps RecommendationPerformanceEngine.
    """

    def __init__(self, db):
        self.db = db

    def get_performance(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Headline performance summary (win rate, execution rate, average
        return, total net P&L) plus breakdowns by recommendation type,
        conviction band, signal, and sector.

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
            from modules.trading_intelligence.recommendation_performance_engine import (
                RecommendationPerformanceEngine,
            )

            engine = RecommendationPerformanceEngine(self.db)

            summary = engine.build_summary(portfolio_id).to_dict()
            breakdown = df_to_records(engine.recommendation_breakdown(portfolio_id))
            conviction = df_to_records(engine.conviction_analysis(portfolio_id))
            signal_effectiveness = df_to_records(engine.signal_effectiveness(portfolio_id))
            sector = df_to_records(engine.sector_analysis(portfolio_id))

        except Exception:
            logger.exception(
                "Performance computation failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "summary": {},
                "by_recommendation_type": [],
                "by_conviction": [],
                "by_signal": [],
                "by_sector": [],
                "note": "Performance data unavailable.",
            }

        return {
            "portfolio_id": str(portfolio_id),
            "summary": summary,
            "by_recommendation_type": breakdown,
            "by_conviction": conviction,
            "by_signal": signal_effectiveness,
            "by_sector": sector,
        }