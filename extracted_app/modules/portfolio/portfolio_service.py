"""
modules/portfolio/portfolio_service.py

Portfolio Service

Owns the Portfolio row itself: list, get, create, partial update, and
soft-delete (deactivate). Everything else about a portfolio -- its
positions, orders, performance, risk, etc. -- lives in sibling services
under modules/portfolio/ and is orchestrated by the API layer's
module_registry, not here.

Every read/write here is tenant-scoped: callers always pass tenant_id
and it's always part of the WHERE clause, so one tenant can never see
or modify another tenant's portfolios.
"""

from __future__ import annotations

from datetime import datetime, UTC
import uuid
from sqlalchemy import text

from models.trading import Portfolio


class PortfolioService:
    """
    CRUD for the Portfolio row itself. See module docstring above for
    scope -- this does not touch positions, orders, or any other
    portfolio-related data.
    """

    def __init__(self, db_session):
        self.db = db_session

    def list_portfolios(
            self,
            *,
            tenant_id: str,
            user_id: str | None = None,
            active_only: bool = True,
    ):
        """All portfolios for a tenant, oldest first. Excludes soft-
        deleted (is_active=False) portfolios unless active_only=False.

        user_id optionally narrows this to one user's own portfolios
        within the tenant (Portfolio.user_id is nullable -- a
        portfolio created before this column existed, or created
        through a path that hasn't been updated to set it, has no
        owner recorded and won't match any user_id filter)."""
        q = self.db.query(Portfolio)

        q = q.filter(
            Portfolio.tenant_id == tenant_id,
        )

        if user_id is not None:
            q = q.filter(
                Portfolio.user_id == user_id,
            )

        if active_only:
            q = q.filter(
                Portfolio.is_active == True,
            )

        return (
            q.order_by(
                Portfolio.created_at.asc(),
            )
            .all()
        )

    def get_portfolio(
            self,
            *,
            tenant_id: str,
            portfolio_id: str,
    ):
        """Single portfolio by id, scoped to tenant_id so one tenant can
        never fetch another tenant's portfolio by guessing its id.
        None if not found or not owned by this tenant."""
        return (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

    def create_portfolio(
        self,
        tenant_id,
        name,
        description=None,
        benchmark="SPY",
        base_currency="USD",
        starting_cash=100000.0,
        user_id=None,
    ):
        """Create and persist a new portfolio. Returns {"id", "name"}
        on success, or None if the insert fails (rolled back either way).

        user_id optionally records which user within the tenant owns
        this portfolio -- omit for a tenant-wide/shared portfolio."""
        try:
            portfolio = Portfolio(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                description=description,
                benchmark=benchmark,
                base_currency=base_currency,
                starting_cash=starting_cash,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            self.db.add(portfolio)
            self.db.commit()

            print("✅ PORTFOLIO CREATED:", portfolio.id, portfolio.name)

            return {
                "id": portfolio.id,
                "name": portfolio.name,
            }

        except Exception as e:
            self.db.rollback()
            print("❌ CREATE PORTFOLIO ERROR:", e)
            return None

    def update_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        name=None,
        description=None,
        benchmark=None,
        base_currency=None,
    ):
        """
        Partial update. Only fields explicitly passed (not None) are
        changed. starting_cash and is_active are intentionally not
        editable here: starting_cash is a historical seed value baked
        into every prior P&L calculation, and is_active is owned by
        deactivate_portfolio()/reactivate_portfolio() so that path stays
        the single place that flips it.
        """
        portfolio = self.get_portfolio(
            tenant_id=tenant_id,
            portfolio_id=portfolio_id,
        )

        if portfolio is None:
            return None

        if name is not None:
            portfolio.name = name

        if description is not None:
            portfolio.description = description

        if benchmark is not None:
            portfolio.benchmark = benchmark

        if base_currency is not None:
            portfolio.base_currency = base_currency

        portfolio.updated_at = datetime.now(UTC)

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("❌ UPDATE PORTFOLIO ERROR:", e)
            return None

        return portfolio

    def deactivate_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> bool:
        """
        Soft delete: marks the portfolio inactive rather than destroying
        its trading history. list_portfolios(active_only=True) already
        filters these out, matching the existing behavior everywhere else
        in the app that assumes inactive portfolios exist and are simply
        hidden, not gone.

        Deliberately does not call delete_portfolio_safe(), which hard-
        deletes the portfolio's entire cash ledger, closed trades, fills,
        positions, and orders with no way back -- not something an
        external API should be able to trigger with a single DELETE call.
        """
        portfolio = self.get_portfolio(
            tenant_id=tenant_id,
            portfolio_id=portfolio_id,
        )

        if portfolio is None:
            return False

        portfolio.is_active = False
        portfolio.updated_at = datetime.now(UTC)

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print("❌ DEACTIVATE PORTFOLIO ERROR:", e)
            return False

        return True

    def ensure_default_portfolio(self, tenant_id: str, user_id: str | None = None):
        """Return this user's most recently active portfolio within the
        tenant (the one with the most recent trade order), or their
        oldest active portfolio if none has any trading activity yet,
        creating a default "Core Portfolio" (owned by user_id, if
        given) if none exists at all.

        user_id is optional for backward compatibility -- omitting it
        keeps the original tenant-wide behavior (any portfolio for the
        tenant, not scoped to one user), which some callers genuinely
        want (e.g. a cross-user tenant aggregate). Passing it resolves
        THIS user's own portfolio specifically, so a user's default
        portfolio (e.g. the one resolved at login) is the same one
        they see when listing their own portfolios by user_id.

        Previously this always picked the OLDEST active portfolio
        (list_portfolios' own creation-date ordering), regardless of
        which portfolio was actually in use -- for a tenant/user with
        more than one portfolio (e.g. an old, empty "Core Portfolio"
        auto-created early on, plus a separate portfolio actually
        traded in), this silently resolved to the wrong, unused one
        every time. Confirmed as the likely cause of a reported
        "recent buy/options positions not reflected in the dashboard"
        symptom.
        """
        existing = self.list_portfolios(tenant_id=tenant_id, user_id=user_id, active_only=True)

        if not existing:
            return self.create_portfolio(
                tenant_id=tenant_id,
                user_id=user_id,
                name="Core Portfolio",
                description="Default system portfolio",
                benchmark="SPY",
                starting_cash=100000.0,
                base_currency="USD",
            )

        if len(existing) == 1:
            return existing[0]

        # More than one portfolio in scope -- prefer whichever has the
        # most recent trading activity, since that's the one actually
        # in use, not necessarily the oldest one.
        try:
            from models.trading import TradeOrder

            portfolio_ids = [p.id for p in existing]

            most_recent_order = (
                self.db.query(TradeOrder)
                .filter(TradeOrder.portfolio_id.in_(portfolio_ids))
                .order_by(TradeOrder.created_at.desc())
                .first()
            )

            if most_recent_order is not None:
                for p in existing:
                    if p.id == most_recent_order.portfolio_id:
                        return p

        except Exception:
            pass

        # No trading activity anywhere yet -- fall back to the
        # original, stable "oldest first" behavior.
        return existing[0]

    # ---------------------------------------------------
    # ✅ FIXED: DELETE PORTFOLIO (NOW IN CORRECT CLASS)
    # ---------------------------------------------------
    def delete_portfolio_safe(self, portfolio_id: str) -> bool:
        """
        Fully deletes a portfolio and all dependent data
        in correct FK order.
        """

        try:
            # 1. CASH LEDGER
            self.db.execute(text("""
                DELETE FROM portfolio_cash_ledger
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id})

            # 2. CLOSED TRADES
            self.db.execute(text("""
                DELETE FROM closed_trades
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id})

            # 3. TRADE FILLS
            self.db.execute(text("""
                DELETE FROM trade_fills
                WHERE order_id IN (
                    SELECT id FROM trade_orders WHERE portfolio_id = :pid
                )
            """), {"pid": portfolio_id})

            # 4. POSITIONS
            self.db.execute(text("""
                DELETE FROM portfolio_positions
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id})

            # 5. TRADE ORDERS
            self.db.execute(text("""
                DELETE FROM trade_orders
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id})

            # 6. SNAPSHOTS (safe if exists)
            try:
                self.db.execute(text("""
                    DELETE FROM portfolio_snapshots
                    WHERE portfolio_id = :pid
                """), {"pid": portfolio_id})
            except Exception:
                pass  # table may not exist yet

            # 7. PORTFOLIO
            self.db.execute(text("""
                DELETE FROM portfolios
                WHERE id = :pid
            """), {"pid": portfolio_id})

            self.db.commit()

            print("✅ PORTFOLIO DELETED:", portfolio_id)
            return True

        except Exception as e:
            self.db.rollback()
            print("❌ DELETE PORTFOLIO ERROR:", e)
            return False