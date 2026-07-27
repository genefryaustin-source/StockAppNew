"""
api/services/forex_orders_api_service.py

Forex Orders API Service

Backs POST /api/v1/forex/orders, GET /api/v1/forex/orders/{id},
POST /api/v1/forex/orders/{id}/cancel, and GET /api/v1/forex/positions.

Wraps modules.forex.forex_terminal_execution_service.
ForexTerminalExecutionService (submit_order, cancel_order) and
modules.forex.forex_portfolio_engine.ForexPortfolioEngine.list_positions
-- all real trading logic stays there.

Fixed a real, pre-existing bug found while building this: forex_accounts
(and forex_positions/forex_cash_ledger/forex_portfolio_snapshots) could
be permanently missing, because ForexPortfolioEngine.__init__
unconditionally set self._tables_ready = True on every instantiation --
based on an assumption that a separate "Forex bootstrap" step had
already created them, which isn't guaranteed and wasn't true in
testing. That silently broke order submission: create_account() builds
a valid-looking account object in memory regardless of whether
persistence actually succeeded, so validation would pass against an
account that was never saved, and execution would then fail with a
confusing "Forex account not found." Fixed in
modules/forex/forex_portfolio_engine.py (the actual root cause); this
adapter also explicitly calls ensure_tables() before any operation as a
second layer of safety, since nothing in the normal order-submission
path calls it automatically (every internal call site is commented
out) -- CREATE TABLE IF NOT EXISTS is idempotent and cheap, so calling
it on every request has no real cost once tables exist.

Deliberately calls ForexPortfolioEngine.ensure_tables() (the legacy,
self-managed version), not modules.execution.execution_account_
repository.ExecutionAccountRepository's newer one, even though forex is
in the middle of migrating onto the shared execution framework and that
newer repository exists specifically to replace this. That migration
isn't finished: ExecutionAccountRepository.ensure_tables() creates a
forex_accounts table with a genuinely different, incompatible schema
(base_currency/cash/used_margin/free_margin, no leverage column) than
ForexPortfolioEngine's version (account_currency/cash_balance/
margin_used/margin_available/leverage) -- same table name, two
different column sets. Nothing in the actual order-submission flow
calls the new repository yet; ForexPortfolioEngine.open_position() (what
genuinely runs today) still queries using the legacy column names. Using
the new repository's ensure_tables() here would create the wrong schema
and break the code path that's actually live. Whoever finishes wiring
the execution framework's account/position repositories into
ForexPortfolioEngine will also need to reconcile (or migrate) this
schema difference -- it isn't just a matter of switching which
ensure_tables() gets called.

One tenant/user can have multiple forex portfolios -- see
api.services._forex_portfolio_resolution.resolve_forex_portfolio_id.
Every method here accepts an optional portfolio_id; when omitted, it
resolves to the caller's default portfolio (auto-created on first use,
so a brand new tenant works immediately without first creating one
explicitly). This replaced an earlier, simpler design that used one
fixed portfolio_id per tenant ("forex-{tenant_id}") and didn't expose
portfolio selection at all.
"""

from __future__ import annotations

import logging
from typing import Any

from api.services._portfolio_symbol_returns import _safe_rollback
from api.services._forex_portfolio_resolution import resolve_forex_portfolio_id

logger = logging.getLogger(__name__)


class ForexOrdersAPIService:
    """API service for forex order lifecycle and positions."""

    def __init__(self, db):
        self.db = db

    def _ensure_tables(self, tenant_id: str, portfolio_id: str) -> None:
        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

            engine = get_forex_portfolio_engine(
                tenant_id=tenant_id,
                user_id=None,
                portfolio_id=portfolio_id,
                db=self.db,
            )
            engine.ensure_tables()
            self.db.commit()
        except Exception:
            logger.exception("Forex ensure_tables failed | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_order(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        pair: str,
        side: str,
        units: float | None = None,
        lots: float | None = None,
        order_type: str = "MARKET",
        limit_price: float | None = None,
        stop_price: float | None = None,
        target_price: float | None = None,
        leverage: float | None = None,
        broker: str = "paper",
        portfolio_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Submit a new forex order via ForexTerminalExecutionService.
        portfolio_id is optional -- omit it to use the caller's default
        portfolio (auto-created on first use). Always returns a dict --
        check its "status" field (e.g. "FILLED", "PENDING", "REJECTED",
        "ERROR") for the outcome, not the HTTP status; a rejected or
        errored order is still a normal response, since a valid request
        was processed and produced a real outcome.
        """

        _safe_rollback(self.db)

        resolved_portfolio_id = resolve_forex_portfolio_id(
            self.db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        self._ensure_tables(tenant_id, resolved_portfolio_id)

        from modules.forex.forex_terminal_execution_service import (
            ForexTerminalExecutionService,
        )

        service = ForexTerminalExecutionService(
            self.db, tenant_id=tenant_id, user_id=user_id, portfolio_id=resolved_portfolio_id,
        )

        return service.submit_order(
            pair=pair,
            side=side,
            units=units,
            lots=lots,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            target_price=target_price,
            leverage=leverage,
            broker=broker,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=resolved_portfolio_id,
        )

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    def get_order(
        self,
        *,
        tenant_id: str,
        order_id: str,
    ) -> dict[str, Any] | None:
        """
        Single forex order by broker_order_id. Scoped to tenant_id --
        ExecutionOrderRepository.get_order() itself doesn't filter by
        tenant, so ownership is checked here, after the fetch, treating
        a mismatch the same as not found rather than leaking whether
        an order belonging to a different tenant exists.
        """

        _safe_rollback(self.db)

        try:
            from modules.execution.execution_order_repository import (
                ExecutionOrderRepository,
            )

            repo = ExecutionOrderRepository(self.db)
            order = repo.get_order(broker_order_id=order_id)

        except Exception:
            logger.exception("Failed to fetch forex order | order_id=%s", order_id)
            _safe_rollback(self.db)
            return None

        if order is None or order.get("tenant_id") != tenant_id:
            return None

        return self._json_safe(order)

    def get_positions(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        status: str = "OPEN",
        portfolio_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Forex positions for a portfolio. portfolio_id is optional --
        omit it to use the caller's default portfolio (auto-created on
        first use).
        """

        _safe_rollback(self.db)

        resolved_portfolio_id = resolve_forex_portfolio_id(
            self.db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        self._ensure_tables(tenant_id, resolved_portfolio_id)

        try:
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

            engine = get_forex_portfolio_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=resolved_portfolio_id,
                db=self.db,
            )

            # Positions belong to an account, and an account is keyed
            # by portfolio_id -- resolving the account first and
            # filtering list_positions() by its id is what actually
            # isolates this portfolio's positions from every other
            # portfolio this tenant might have. list_positions() alone,
            # with no account_id filter, would return every open
            # position for the whole tenant across all portfolios.
            account = engine.get_or_create_account(portfolio_id=resolved_portfolio_id)
            positions = engine.list_positions(account_id=account.id, status=status)

        except Exception:
            logger.exception("Failed to list forex positions | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return {
                "tenant_id": tenant_id,
                "portfolio_id": resolved_portfolio_id,
                "position_count": 0,
                "positions": [],
            }

        return {
            "tenant_id": tenant_id,
            "portfolio_id": resolved_portfolio_id,
            "position_count": len(positions),
            "positions": [p.to_dict() for p in positions],
        }

    # ---------------------------------------------------------
    # Cancel
    # ---------------------------------------------------------

    def cancel_order(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        order_id: str,
        broker: str = "paper",
        portfolio_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Cancel a forex order. Ownership is verified via get_order()
        first (which enforces tenant_id, since cancel_order() itself
        doesn't) -- returns None if the order doesn't exist or doesn't
        belong to tenant_id, which the router turns into a 404.
        """

        existing = self.get_order(tenant_id=tenant_id, order_id=order_id)

        if existing is None:
            return None

        try:
            from modules.forex.forex_terminal_execution_service import (
                ForexTerminalExecutionService,
            )

            resolved_portfolio_id = portfolio_id or existing.get("portfolio_id") or resolve_forex_portfolio_id(
                self.db, tenant_id=tenant_id, user_id=user_id,
            )

            service = ForexTerminalExecutionService(
                self.db,
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=resolved_portfolio_id,
            )

            return service.cancel_order(order_id, broker=broker)

        except Exception:
            logger.exception("Failed to cancel forex order | order_id=%s", order_id)
            _safe_rollback(self.db)
            return {
                "status": "ERROR",
                "broker_order_id": order_id,
                "message": "Cancellation failed due to an internal error.",
            }

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    @staticmethod
    def _json_safe(value: dict) -> dict:
        result = {}
        for k, v in value.items():
            if hasattr(v, "isoformat"):
                result[k] = v.isoformat()
            else:
                result[k] = v
        return result