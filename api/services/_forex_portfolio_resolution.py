"""
api/services/_forex_portfolio_resolution.py

Shared helper for resolving which forex portfolio an operation applies
to. Used by forex_orders_api_service, forex_portfolios_api_service, and
forex_position_management_api_service.

A forex "portfolio" here (modules.forex.forex_portfolio_crud_engine.
ForexPortfolioCrudEngine, table forex_portfolios) is a distinct concept
from a trading "account" (modules.forex.forex_portfolio_engine.
ForexPortfolioEngine, table forex_accounts) -- a portfolio is a named
container a user creates; ForexPortfolioEngine.get_or_create_account()
auto-creates a separate trading account keyed by whatever portfolio_id
it's given, so each portfolio genuinely gets its own isolated account,
positions, and cash ledger. Every order/position endpoint accepts an
optional portfolio_id; when omitted, this resolves to the tenant's
(and user's) default portfolio, auto-creating one on first use so a
brand new tenant works immediately without first having to create a
portfolio explicitly.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_forex_portfolio_id(
    db,
    *,
    tenant_id: str,
    user_id: str | None,
    portfolio_id: str | None = None,
) -> str:
    """
    Returns portfolio_id unchanged if given. Otherwise resolves the
    caller's default portfolio, auto-creating one named "Default" if
    none exists yet. Never raises -- falls back to a deterministic
    per-tenant/user id if portfolio CRUD itself fails for any reason,
    so a database hiccup here degrades to "one portfolio" behavior
    rather than blocking every order/position call.

    user_id defaults to "default" when not supplied: ForexPortfolioCrudEngine
    filters by "user_id = :user" in raw SQL, and in SQL a NULL/None
    parameter never equals anything (not even another NULL), so passing
    None straight through would silently match zero rows on every
    lookup -- this is the same normalization ForexPortfolioManager
    already applies for the same reason.
    """

    effective_user_id = user_id or "default"

    try:
        from modules.forex.forex_portfolio_crud_engine import (
            get_forex_portfolio_crud_engine,
        )

        crud = get_forex_portfolio_crud_engine(db=db)

        if portfolio_id:
            existing = crud.get_portfolio(portfolio_id)
            if existing is not None and existing.get("tenant_id") == tenant_id:
                return portfolio_id
            # A portfolio_id was given but doesn't exist or belongs to
            # a different tenant -- fall through to default resolution
            # rather than silently trading against an unverified id.
            logger.warning(
                "forex portfolio_id %s not found for tenant %s; falling back to default",
                portfolio_id, tenant_id,
            )

        default = crud.get_default_portfolio(tenant_id=tenant_id, user_id=effective_user_id)
        if default is not None:
            return default["id"]

        existing_list = crud.list_portfolios(tenant_id=tenant_id, user_id=effective_user_id)
        if existing_list:
            return existing_list[0]["id"]

        return crud.create_portfolio(
            tenant_id=tenant_id,
            user_id=effective_user_id,
            name="Default",
            is_default=True,
        )

    except Exception:
        logger.exception(
            "Forex portfolio resolution failed | tenant_id=%s user_id=%s",
            tenant_id, effective_user_id,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return f"forex-{tenant_id}-{effective_user_id}"