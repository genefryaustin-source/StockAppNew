"""
modules/stocks/stock_execution_intelligence_dashboard_service.py

Stock Execution Intelligence Dashboard Service

Aggregates data from:

    - Execution Quality
    - Broker Analytics
    - Transaction Cost Analysis

This service contains NO UI.

It prepares dashboard-ready data for:

    stock_execution_intelligence_dashboard.py

This is the analytics-intelligence counterpart to
stock_execution_dashboard_service.py, which covers the operational side
(events, attribution, AI review, compliance). Together they're meant to
be the complete picture: what happened, and how well it happened.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from modules.stocks.stock_execution_quality_service import (
    get_stock_execution_quality_service,
)
from modules.stocks.stock_broker_analytics_service import (
    get_stock_broker_analytics_service,
)
from modules.stocks.stock_transaction_cost_analysis_service import (
    get_stock_transaction_cost_analysis_service,
)

logger = logging.getLogger(__name__)


# ==========================================================
# Dashboard Service
# ==========================================================


class StockExecutionIntelligenceDashboardService:
    """
    Aggregates institutional execution intelligence: quality, broker
    comparison, and transaction cost analysis.
    """

    def __init__(self, db):
        self.db = db

        self.quality = get_stock_execution_quality_service(db)
        self.broker_analytics = get_stock_broker_analytics_service(db)
        self.tca = get_stock_transaction_cost_analysis_service(db)

    # ======================================================
    # Executive Dashboard
    # ======================================================

    def dashboard(self, *, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        quality_summary = self.quality.summary(portfolio_id=portfolio_id)
        broker_summary = self.broker_analytics.summary(portfolio_id=portfolio_id)
        cost_summary = self.tca.summary(portfolio_id=portfolio_id)

        broker_records = [
            asdict(r)
            for r in self.broker_analytics.analyze_all_brokers(portfolio_id=portfolio_id)
        ]

        cost_detail = asdict(self.tca.analyze_costs(portfolio_id=portfolio_id))

        return {
            "cards": self._cards(quality_summary, broker_summary, cost_summary),

            "quality_summary": quality_summary,
            "recent_quality_records": self.quality.get_quality_records(
                portfolio_id=portfolio_id,
                limit=50,
            ),

            "broker_summary": broker_summary,
            "broker_records": broker_records,

            "cost_summary": cost_summary,
            "cost_detail": cost_detail,
            "cost_trend": self.tca.cost_trend(
                portfolio_id=portfolio_id,
                limit_periods=30,
            ),
        }

    # ======================================================
    # KPI Cards
    # ======================================================

    def _cards(
        self,
        quality: Dict[str, Any],
        broker: Dict[str, Any],
        cost: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        return [
            {
                "title": "Orders Analyzed",
                "value": quality.get("order_count", 0),
                "delta": None,
                "format": "int",
            },
            {
                "title": "Avg Quality Score",
                "value": quality.get("average_quality_score", 0),
                "delta": None,
                "format": "score",
            },
            {
                "title": "Avg Fill Rate",
                "value": quality.get("average_fill_rate", 0),
                "delta": None,
                "format": "percent",
            },
            {
                "title": "Best Broker",
                "value": broker.get("best_broker") or "N/A",
                "delta": None,
                "format": "text",
            },
            {
                "title": "Blended Cost",
                "value": cost.get("blended_total_cost_bps", 0),
                "delta": None,
                "format": "bps",
            },
            {
                "title": "Total Cost",
                "value": cost.get("total_cost", 0),
                "delta": None,
                "format": "currency",
            },
            {
                "title": "Cost % of Equity",
                "value": cost.get("cost_as_pct_of_equity") or 0,
                "delta": None,
                "format": "percent",
            },
        ]


# ==========================================================
# Factory
# ==========================================================

_intelligence_dashboard_service = None


def get_stock_execution_intelligence_dashboard_service(
    db,
) -> StockExecutionIntelligenceDashboardService:

    global _intelligence_dashboard_service

    if (
        _intelligence_dashboard_service is None
        or _intelligence_dashboard_service.db is not db
    ):
        _intelligence_dashboard_service = StockExecutionIntelligenceDashboardService(db)

    return _intelligence_dashboard_service