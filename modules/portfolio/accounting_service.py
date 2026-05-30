from __future__ import annotations

from datetime import datetime, UTC
from sqlalchemy import func

from models.trading import (
    Portfolio,
    PortfolioCashLedger,
    PortfolioPosition,
    PortfolioSnapshot,
)

from sqlalchemy import text
class AccountingService:
    def __init__(self, db_session):
        self.db = db_session

    def ensure_seed_cash(self, portfolio_id: int, starting_cash: float | None = None) -> None:
        existing = (
            self.db.query(PortfolioCashLedger)
            .filter(PortfolioCashLedger.portfolio_id == portfolio_id)
            .first()
        )
        if existing is not None:
            return

        if starting_cash is None:
            portfolio = (
                self.db.query(Portfolio)
                .filter(Portfolio.id == portfolio_id)
                .one_or_none()
            )
            starting_cash = float(getattr(portfolio, "starting_cash", 100000.0) or 100000.0)

        self.db.add(
            PortfolioCashLedger(
                portfolio_id=portfolio_id,
                entry_type="seed",
                amount=float(starting_cash),
                currency="USD",
                notes="Initial capital",
            )
        )

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def cash_balance(self, portfolio_id: int) -> float:
        value = (
            self.db.query(func.coalesce(func.sum(PortfolioCashLedger.amount), 0.0))
            .filter(PortfolioCashLedger.portfolio_id == portfolio_id)
            .scalar()
        )
        return float(value or 0.0)

    def record_cash_entry(
        self,
        portfolio_id: int,
        entry_type: str,
        amount: float,
        trade_order_id: int | None = None,
        notes: str | None = None,
        currency: str = "USD",
    ) -> None:
        self.db.add(
            PortfolioCashLedger(
                portfolio_id=portfolio_id,
                entry_type=entry_type,
                amount=float(amount),
                trade_order_id=trade_order_id,
                notes=notes,
                currency=currency,
            )
        )

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def portfolio_totals(self, portfolio_id: int) -> dict:
        positions = (
            self.db.query(PortfolioPosition)
            .filter(PortfolioPosition.portfolio_id == portfolio_id)
            .all()
        )

        cash = self.cash_balance(portfolio_id)
        market_value = float(sum(float(p.market_value or 0.0) for p in positions))
        realized_pnl = float(sum(float(p.realized_pnl or 0.0) for p in positions))
        unrealized_pnl = float(sum(float(p.unrealized_pnl or 0.0) for p in positions))
        equity = cash + market_value
        net_pnl = realized_pnl + unrealized_pnl

        return {
            "cash": cash,
            "market_value": market_value,
            "equity": equity,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
        }

    def record_snapshot(self, portfolio_id: int) -> dict:
        totals = self.portfolio_totals(portfolio_id)

        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio_id,
            as_of=datetime.now(UTC),
            cash=totals["cash"],
            market_value=totals["market_value"],
            equity=totals["equity"],
            realized_pnl=totals["realized_pnl"],
            unrealized_pnl=totals["unrealized_pnl"],
            net_pnl=totals["net_pnl"],
        )

        self.db.add(snapshot)

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

        return totals



    def get_cash_balance(self, portfolio_id: str) -> float:
        try:
            result = self.db.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM portfolio_cash_ledger
                    WHERE portfolio_id = :pid
                """),
                {"pid": portfolio_id},
            ).fetchone()

            if result and result[0] is not None:
                return float(result[0])

        except Exception as e:
            print("⚠️ CASH BALANCE ERROR:", e)

        return 0.0