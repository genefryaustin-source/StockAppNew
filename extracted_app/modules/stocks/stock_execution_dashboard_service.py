"""
modules/stocks/stock_execution_dashboard_service.py

Institutional Execution Dashboard Service

Aggregates data from:

    • Execution Events
    • Trade Attribution
    • AI Trade Review
    • Execution Audit

This service contains NO UI.

It prepares dashboard-ready data for:

    stock_execution_dashboard.py
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional

from modules.stocks.stock_execution_event_service import (
    get_stock_execution_event_service,
)

from modules.stocks.stock_trade_attribution_service import (
    get_stock_trade_attribution_service,
)

from modules.stocks.stock_ai_trade_review_service import (
    get_stock_ai_trade_review_service,
)

from modules.stocks.stock_execution_audit_service import (
    get_stock_execution_audit_service,
)

logger = logging.getLogger(__name__)


# ==========================================================
# Dashboard Service
# ==========================================================


class StockExecutionDashboardService:

    """
    Aggregates institutional execution analytics.
    """

    def __init__(
        self,
        db,
    ):

        self.db = db

        self.events = (
            get_stock_execution_event_service(
                db,
            )
        )

        self.attribution = (
            get_stock_trade_attribution_service(
                db,
            )
        )

        self.ai = (
            get_stock_ai_trade_review_service(
                db,
            )
        )

        self.audit = (
            get_stock_execution_audit_service(
                db,
            )
        )

    # ======================================================
    # Executive Dashboard
    # ======================================================

    def dashboard(
        self,
        *,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        event_summary = (
            self.events.get_statistics(
                portfolio_id=portfolio_id,
            )
        )

        attribution_summary = (
            self.attribution.summary()
        )

        ai_summary = (
            self.ai.summary()
        )

        compliance_summary = (
            self.audit.compliance_summary()
        )

        return {

            "cards": self._cards(

                event_summary,

                attribution_summary,

                ai_summary,

                compliance_summary,

            ),

            "event_summary":
                event_summary,

            "trade_attribution":
                attribution_summary,

            "ai_review":
                ai_summary,

            "compliance":
                compliance_summary,

            "recent_events":

                self.events.get_events(

                    portfolio_id=portfolio_id,

                    limit=50,

                ),

            "recent_reviews":

                self.ai.get_reviews(
                    limit=25,
                ),

            "recent_attribution":

                self.attribution.get_trade_attribution(
                    limit=25,
                ),

            "audit":

                self.audit.get_audit_records(
                    limit=50,
                ),
        }

    # ======================================================
    # KPI Cards
    # ======================================================

    def _cards(

        self,

        event_summary,

        attribution,

        ai,

        compliance,

    ) -> List[Dict[str, Any]]:

        return [

            {

                "title":

                    "Execution Events",

                "value":

                    event_summary.get(
                        "total_events",
                        0,
                    ),

                "delta": None,

                "format": "int",

            },

            {

                "title":

                    "Orders Filled",

                "value":

                    event_summary.get(
                        "orders_filled",
                        0,
                    ),

                "delta": None,

                "format": "int",

            },

            {

                "title":

                    "Average Trade Score",

                "value":

                    attribution.get(
                        "average_score",
                        0,
                    ),

                "delta": None,

                "format": "percent",

            },

            {

                "title":

                    "Average Return",

                "value":

                    attribution.get(
                        "average_return",
                        0,
                    ),

                "delta": None,

                "format": "percent",

            },

            {

                "title":

                    "AI Rating",

                "value":

                    ai.get(
                        "average_rating",
                        0,
                    ),

                "delta": None,

                "format": "percent",

            },

            {

                "title":

                    "AI Confidence",

                "value":

                    ai.get(
                        "average_confidence",
                        0,
                    ),

                "delta": None,

                "format": "percent",

            },

            {

                "title":

                    "Compliance Events",

                "value":

                    compliance.get(
                        "events",
                        0,
                    ),

                "delta": None,

                "format": "int",

            },

            {

                "title":

                    "Positions Closed",

                "value":

                    compliance.get(
                        "positions_closed",
                        0,
                    ),

                "delta": None,

                "format": "int",

            },

        ]


# ==========================================================
# Factory
# ==========================================================

_dashboard_service = None


def get_stock_execution_dashboard_service(
    db,
) -> StockExecutionDashboardService:

    global _dashboard_service

    if (

        _dashboard_service is None

        or _dashboard_service.db is not db

    ):

        _dashboard_service = (

            StockExecutionDashboardService(
                db,
            )

        )

    return _dashboard_service