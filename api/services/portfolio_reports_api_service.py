"""
api/services/portfolio_reports_api_service.py

Portfolio Reports API Service

Backs GET /api/v1/portfolio/{portfolio_id}/reports/pdf.

Wraps modules.portfolio.pdf_reporting_service.PDFReportingService.
generate_portfolio_report -- cover page, NAV chart, and an executive
summary table (total/annualized return, equity, unrealized P&L), all
built from real portfolio data (NavService + portfolio_positions).

That method had a real bug fixed as part of building this: it called
self._nav_chart(nav_df), a method that was never actually defined on
the class (a comment said to "keep your chart methods... as they are",
but they'd been dropped) -- calling generate_portfolio_report would
always crash with AttributeError. Fixed there, not here; this adapter
just calls the now-working method.
"""

from __future__ import annotations

import io
import logging

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioReportsAPIService:
    """API service for generating a portfolio PDF report."""

    def __init__(self, db):
        self.db = db

    def generate_pdf(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> bytes | None:
        """
        Returns the generated PDF as bytes, or None if the portfolio
        doesn't exist/doesn't belong to tenant_id, or generation failed
        for any other reason -- the router distinguishes these cases by
        checking portfolio ownership itself before calling this.
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
            from modules.portfolio.nav_service import NavService
            from modules.portfolio.pdf_reporting_service import PDFReportingService
            from modules.market_data import service as market_data_service

            nav_service = NavService(self.db, market_data_service)

            report_service = PDFReportingService(
                self.db,
                nav_service,
                accounting_service=None,
                reporting_service=None,
            )

            buffer = io.BytesIO()
            report_service.generate_portfolio_report(portfolio_id, buffer)

            return buffer.getvalue()

        except Exception:
            logger.exception(
                "PDF report generation failed | portfolio_id=%s", portfolio_id
            )
            _safe_rollback(self.db)
            return None