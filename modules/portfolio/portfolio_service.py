from __future__ import annotations

from datetime import datetime
import uuid
from sqlalchemy import text

from models.trading import Portfolio


class PortfolioService:
    def __init__(self, db_session):
        self.db = db_session

    def list_portfolios(self, active_only: bool = True):
        q = self.db.query(Portfolio)
        if active_only:
            q = q.filter(Portfolio.is_active == True)  # noqa: E712
        return q.order_by(Portfolio.created_at.asc()).all()

    def get_portfolio(self, portfolio_id):
        p = (
            self.db.query(Portfolio)
            .filter(Portfolio.id == portfolio_id)
            .one_or_none()
        )

        if p is None:
            print("⚠️ PORTFOLIO NOT FOUND:", portfolio_id)

        return p

    def create_portfolio(
        self,
        tenant_id,
        name,
        description=None,
        benchmark="SPY",
        base_currency="USD",
        starting_cash=100000.0,
    ):
        try:
            portfolio = Portfolio(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=name,
                description=description,
                benchmark=benchmark,
                base_currency=base_currency,
                starting_cash=starting_cash,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
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

    def ensure_default_portfolio(self):
        existing = self.list_portfolios(active_only=True)
        if existing:
            return existing[0]

        return self.create_portfolio(
            tenant_id="default",  # safe fallback
            name="Core Portfolio",
            description="Default system portfolio",
            benchmark="SPY",
            starting_cash=100000.0,
            base_currency="USD",
        )

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