"""
api/services/portfolio_scenarios_api_service.py

Portfolio Scenarios API Service

Backs GET /api/v1/portfolio/{portfolio_id}/scenarios.

Wraps modules.portfolio.risk_analytics_service.RiskAnalyticsService.
stress_test -- the same method the /risk endpoint already uses with a
brief 3-scenario default -- with a wider, dedicated scenario set for a
standalone deep-dive view. Reuses modules.risk_layer.positions'
cross-asset positions/returns builders rather than duplicating the
per-symbol fetch PortfolioRiskAPIService does privately.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioScenariosAPIService:
    """
    API service for portfolio stress-test scenarios. Wraps
    modules.portfolio.risk_analytics_service.RiskAnalyticsService.stress_test
    -- the same method the /risk endpoint already uses with a default
    3-scenario set -- with a wider, dedicated scenario set for a standalone
    deep-dive view.

    Uses modules.risk_layer.positions.get_positions_df/get_returns_df
    (the cross-asset aggregation layer) rather than duplicating the
    per-symbol fetch PortfolioRiskAPIService does privately, so this
    naturally covers non-equity positions bridged into that layer too.
    """

    def __init__(self, db):
        self.db = db

    def get_scenarios(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Estimated P&L impact of 7 uniform market-shock scenarios
        (-20% to +15%) applied to total portfolio market value.

        Returns None if the portfolio doesn't exist or doesn't belong
        to tenant_id -- the router turns that into a 404.
        """

        # See portfolio_correlation_api_service.py for why this matters:
        # this service's session is cached and reused for the life of
        # the process, so a prior request's unrolled-back failure would
        # otherwise break every query below, including this first one.
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

        from modules.risk_layer.positions import get_positions_df, get_returns_df
        from modules.portfolio.risk_analytics_service import RiskAnalyticsService

        try:
            positions_df = get_positions_df(
                self.db, tenant_id=tenant_id, portfolio_id=portfolio_id
            )
            returns_df = get_returns_df(
                self.db, tenant_id=tenant_id, portfolio_id=portfolio_id
            )
        except Exception:
            logger.exception(
                "Failed to build positions/returns for scenarios | %s",
                portfolio_id,
            )
            _safe_rollback(self.db)
            positions_df, returns_df = None, None

        if positions_df is None or positions_df.empty:
            return {
                "portfolio_id": str(portfolio_id),
                "scenarios": [],
                "note": "No positions available to stress test.",
            }

        analytics = RiskAnalyticsService(
            returns_df=returns_df, positions_df=positions_df
        )

        scenarios = {
            "Market Down 20%": -0.20,
            "Market Down 15%": -0.15,
            "Market Down 10%": -0.10,
            "Market Down 5%": -0.05,
            "Market Up 5%": 0.05,
            "Market Up 10%": 0.10,
            "Market Up 15%": 0.15,
        }

        result_df = analytics.stress_test(scenarios=scenarios)

        rows = (
            result_df.to_dict(orient="records") if not result_df.empty else []
        )

        return {
            "portfolio_id": str(portfolio_id),
            "portfolio_value": round(
                float(positions_df["Market Value"].fillna(0.0).sum()), 2
            ),
            "scenarios": rows,
            "methodology": (
                "Uniform shock applied to total portfolio market value -- "
                "not per-position beta-adjusted, and not a full Monte "
                "Carlo simulation. Same methodology the /risk endpoint's "
                "brief stress-test summary already uses."
            ),
        }