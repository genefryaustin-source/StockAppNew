from __future__ import annotations

from sqlalchemy import func

from models.trading import (
    Portfolio,
    PortfolioPosition,
    PortfolioCashLedger,
)


class PortfolioPerformanceService:

    def __init__(self, db):
        self.db = db

    def get_performance(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ):

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

        positions = (
            self.db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.portfolio_id == portfolio_id,
            )
            .all()
        )

        ledger = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        PortfolioCashLedger.amount
                    ),
                    0.0,
                )
            )
            .filter(
                PortfolioCashLedger.portfolio_id == portfolio_id,
            )
            .scalar()
        )

        cash_balance = float(ledger or 0.0)

        market_value = sum(
            float(p.market_value or 0.0)
            for p in positions
        )

        cost_basis = sum(
            float(p.qty or 0.0)
            * float(p.avg_cost or 0.0)
            for p in positions
        )

        unrealized_pnl = sum(
            float(p.unrealized_pnl or 0.0)
            for p in positions
        )

        realized_pnl = sum(
            float(p.realized_pnl or 0.0)
            for p in positions
        )

        equity = cash_balance + market_value

        total_return = realized_pnl + unrealized_pnl

        invested = cost_basis

        total_return_pct = (
            (total_return / invested) * 100.0
            if invested > 0
            else 0.0
        )

        winners = sum(
            1
            for p in positions
            if float(p.unrealized_pnl or 0.0) > 0
        )

        losers = sum(
            1
            for p in positions
            if float(p.unrealized_pnl or 0.0) < 0
        )

        return {

            "cash_balance": cash_balance,

            "market_value": market_value,

            "total_equity": equity,

            "cost_basis": cost_basis,

            "unrealized_pnl": unrealized_pnl,

            "realized_pnl": realized_pnl,

            "total_return": total_return,

            "total_return_pct": total_return_pct,

            "positions": len(positions),

            "winning_positions": winners,

            "losing_positions": losers,

        }