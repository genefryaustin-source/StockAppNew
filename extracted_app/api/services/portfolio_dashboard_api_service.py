"""
api/services/portfolio_dashboard_api_service.py

Portfolio Dashboard API Service

Backs GET /api/v1/portfolio/{portfolio_id}/dashboard.

Composite of performance, allocation, cash, and health into one payload
so an external client can render a portfolio overview screen with one
call instead of four. Each section is computed by the same service its
own dedicated endpoint uses, just combined here -- a failing section
reports why rather than taking the rest of the dashboard down with it.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioDashboardAPIService:
    """
    API service for a single composite dashboard payload: performance,
    allocation, cash, and a health check together. Exists so an external
    client can render a portfolio overview screen with one call instead
    of four -- each section is computed by the same services their own
    dedicated endpoints use, just combined here.

    Any individual section failing does not fail the whole response --
    each is independently wrapped, and a failed section reports why
    rather than taking the rest of the dashboard down with it.
    """

    def __init__(self, db):
        self.db = db

    def get_dashboard(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Combined {portfolio, performance, allocation, cash, health}
        payload for one portfolio.

        Returns None if the portfolio doesn't exist or doesn't belong
        to tenant_id -- the router turns that into a 404. Individual
        sections that fail return {"available": False, "reason": ...}
        in their place rather than failing the whole call.
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

        sections: dict[str, Any] = {
            "portfolio": {
                "id": portfolio.id,
                "name": portfolio.name,
                "description": portfolio.description,
                "benchmark": portfolio.benchmark,
                "base_currency": portfolio.base_currency,
                "is_active": bool(portfolio.is_active),
            }
        }

        sections["performance"] = self._section(
            "performance", tenant_id, portfolio_id,
            "modules.portfolio.portfolio_performance_service",
            "PortfolioPerformanceService",
            "get_performance",
        )

        sections["allocation"] = self._section(
            "allocation", tenant_id, portfolio_id,
            "modules.portfolio.portfolio_allocation_service",
            "PortfolioAllocationService",
            "get_allocation",
        )

        sections["cash"] = self._section(
            "cash", tenant_id, portfolio_id,
            "api.services.portfolio_cash_api_service",
            "PortfolioCashAPIService",
            "get_cash",
        )

        sections["health"] = self._section(
            "health", tenant_id, portfolio_id,
            "api.services.portfolio_health_api_service",
            "PortfolioHealthAPIService",
            "get_health",
        )

        return sections

    def _section(
        self,
        name: str,
        tenant_id: str,
        portfolio_id: str,
        module_path: str,
        class_name: str,
        method_name: str,
    ) -> Any:
        try:
            import importlib

            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            instance = cls(self.db)
            method = getattr(instance, method_name)

            return method(tenant_id=tenant_id, portfolio_id=portfolio_id)

        except Exception:
            logger.exception(
                "Dashboard section '%s' failed | portfolio_id=%s",
                name,
                portfolio_id,
            )
            # Without this, a failure in this section would leave
            # self.db in a failed-transaction state on Postgres, and
            # every section called after this one in the same request
            # (they all share self.db) would fail too -- not just this
            # one section.
            _safe_rollback(self.db)
            return {"available": False, "reason": f"{name} section unavailable."}