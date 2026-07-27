"""
api/services/forex_portfolios_api_service.py

Forex Portfolios API Service

Backs the forex portfolio CRUD endpoints under /api/v1/forex/portfolios.
Wraps modules.forex.forex_portfolio_crud_engine.ForexPortfolioCrudEngine
-- no business logic lives here.

A "portfolio" here is a named container (table forex_portfolios);
ForexPortfolioEngine auto-creates a separate, genuinely isolated
trading account/position set for each distinct portfolio_id used in an
order. Creating a portfolio here doesn't itself create a trading
account -- that happens lazily, the first time an order references it.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ForexPortfoliosAPIService:
    """API service for forex portfolio CRUD."""

    def __init__(self, db):
        self.db = db

    def _crud(self):
        from modules.forex.forex_portfolio_crud_engine import (
            get_forex_portfolio_crud_engine,
        )

        return get_forex_portfolio_crud_engine(db=self.db)

    def create_portfolio(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        name: str,
        description: str = "",
        base_currency: str = "USD",
        starting_balance: float = 100000.0,
        is_default: bool = False,
    ) -> dict[str, Any] | None:
        try:
            crud = self._crud()

            portfolio_id = crud.create_portfolio(
                tenant_id=tenant_id,
                user_id=user_id or "default",
                name=name,
                description=description,
                base_currency=base_currency,
                starting_balance=starting_balance,
                is_default=is_default,
            )

            return crud.get_portfolio(portfolio_id)

        except Exception:
            logger.exception("Failed to create forex portfolio | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def list_portfolios(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        try:
            crud = self._crud()

            portfolios = crud.list_portfolios(
                tenant_id=tenant_id,
                user_id=user_id or "default",
                include_archived=include_archived,
            )

        except Exception:
            logger.exception("Failed to list forex portfolios | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {"tenant_id": tenant_id, "portfolio_count": 0, "portfolios": []}

        return {
            "tenant_id": tenant_id,
            "portfolio_count": len(portfolios),
            "portfolios": portfolios,
        }

    def get_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """Scoped to tenant_id -- ForexPortfolioCrudEngine.get_portfolio() itself doesn't filter by tenant."""

        try:
            crud = self._crud()
            portfolio = crud.get_portfolio(portfolio_id)

        except Exception:
            logger.exception("Failed to fetch forex portfolio | portfolio_id=%s", portfolio_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

        if portfolio is None or portfolio.get("tenant_id") != tenant_id:
            return None

        return portfolio

    def update_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        name: str,
        description: str = "",
        base_currency: str = "USD",
        status: str = "ACTIVE",
    ) -> dict[str, Any] | None:
        existing = self.get_portfolio(tenant_id=tenant_id, portfolio_id=portfolio_id)
        if existing is None:
            return None

        try:
            crud = self._crud()
            crud.update_portfolio(
                portfolio_id=portfolio_id,
                name=name,
                description=description,
                base_currency=base_currency,
                status=status,
            )
            return crud.get_portfolio(portfolio_id)

        except Exception:
            logger.exception("Failed to update forex portfolio | portfolio_id=%s", portfolio_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def delete_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> bool:
        existing = self.get_portfolio(tenant_id=tenant_id, portfolio_id=portfolio_id)
        if existing is None:
            return False

        try:
            self._crud().delete_portfolio(portfolio_id)
            return True

        except Exception:
            logger.exception("Failed to delete forex portfolio | portfolio_id=%s", portfolio_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return False

    def archive_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        existing = self.get_portfolio(tenant_id=tenant_id, portfolio_id=portfolio_id)
        if existing is None:
            return None

        try:
            crud = self._crud()
            crud.archive_portfolio(portfolio_id)
            return crud.get_portfolio(portfolio_id)

        except Exception:
            logger.exception("Failed to archive forex portfolio | portfolio_id=%s", portfolio_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def restore_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        existing = self.get_portfolio(tenant_id=tenant_id, portfolio_id=portfolio_id)
        if existing is None:
            return None

        try:
            crud = self._crud()
            crud.restore_portfolio(portfolio_id)
            return crud.get_portfolio(portfolio_id)

        except Exception:
            logger.exception("Failed to restore forex portfolio | portfolio_id=%s", portfolio_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def set_default_portfolio(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        existing = self.get_portfolio(tenant_id=tenant_id, portfolio_id=portfolio_id)
        if existing is None:
            return None

        try:
            crud = self._crud()
            crud.set_default_portfolio(
                tenant_id=tenant_id,
                user_id=user_id or "default",
                portfolio_id=portfolio_id,
            )
            return crud.get_portfolio(portfolio_id)

        except Exception:
            logger.exception("Failed to set default forex portfolio | portfolio_id=%s", portfolio_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def portfolio_statistics(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        try:
            return self._crud().portfolio_statistics(
                tenant_id=tenant_id,
                user_id=user_id or "default",
            )
        except Exception:
            logger.exception("Failed to compute forex portfolio statistics | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {"portfolio_count": 0, "default_portfolio": None, "combined_balance": 0.0, "combined_starting_balance": 0.0}