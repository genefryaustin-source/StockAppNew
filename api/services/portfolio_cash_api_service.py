"""
api/services/portfolio_cash_api_service.py

Portfolio Cash API Service

Backs GET /api/v1/portfolio/{portfolio_id}/cash.

Wraps modules.portfolio.accounting_service.AccountingService -- all
cash-balance math stays there; this validates tenant ownership of the
portfolio and shapes the response for the API layer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback


class PortfolioCashAPIService:
    """
    API service for portfolio cash balance and ledger activity.
    Wraps modules.portfolio.accounting_service.AccountingService --
    all cash math stays there, this just validates tenant ownership
    and shapes the response.
    """

    def __init__(self, db):
        self.db = db

    def get_cash(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        limit: int = 100,
    ) -> dict[str, Any] | None:
        """
        Current cash balance plus the most recent cash-ledger entries
        (trades, seed capital, and any other cash movement) for one
        portfolio.

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

        from modules.portfolio.accounting_service import AccountingService

        accounting = AccountingService(self.db)

        cash_balance = accounting.get_cash_balance(portfolio_id)

        rows = self.db.execute(
            text(
                """
                SELECT entry_type, amount, currency, trade_order_id, notes, created_at
                FROM portfolio_cash_ledger
                WHERE portfolio_id = :pid
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"pid": portfolio_id, "limit": limit},
        ).mappings().all()

        ledger = [dict(row) for row in rows]

        for row in ledger:
            if row.get("created_at") is not None:
                row["created_at"] = str(row["created_at"])

        return {
            "portfolio_id": str(portfolio_id),
            "cash_balance": float(cash_balance or 0.0),
            "currency": portfolio.base_currency,
            "starting_cash": float(portfolio.starting_cash or 0.0),
            "recent_ledger_entries": ledger,
        }