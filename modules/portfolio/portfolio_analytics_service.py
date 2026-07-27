from __future__ import annotations

from models.trading import (
    Portfolio,
    PortfolioPosition,
    ClosedTrade,
    PortfolioCashLedger,
)


class PortfolioAnalyticsService:

    def __init__(self, db):
        self.db = db

    def get_analytics(
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

        closed = (
            self.db.query(ClosedTrade)
            .filter(
                ClosedTrade.portfolio_id == portfolio_id,
            )
            .all()
        )

        ledger = (
            self.db.query(PortfolioCashLedger)
            .filter(
                PortfolioCashLedger.portfolio_id == portfolio_id,
            )
            .all()
        )

        cash_balance = sum(
            float(entry.amount or 0.0)
            for entry in ledger
        )

        market_value = sum(
            float(position.market_value or 0.0)
            for position in positions
        )

        equity = cash_balance + market_value

        unrealized = sum(
            float(position.unrealized_pnl or 0.0)
            for position in positions
        )

        realized = sum(
            float(position.realized_pnl or 0.0)
            for position in positions
        )

        winners = sum(
            1
            for position in positions
            if (position.unrealized_pnl or 0.0) > 0
        )

        losers = sum(
            1
            for position in positions
            if (position.unrealized_pnl or 0.0) < 0
        )

        largest = max(
            (
                float(position.market_value or 0.0)
                for position in positions
            ),
            default=0.0,
        )

        concentration = (
            largest / market_value * 100
            if market_value > 0
            else 0.0
        )

        closed_trades = len(closed)

        winning_closed = sum(
            1
            for trade in closed
            if (trade.net_pnl or 0.0) > 0
        )

        losing_closed = sum(
            1
            for trade in closed
            if (trade.net_pnl or 0.0) < 0
        )

        total_closed_pnl = sum(
            float(trade.net_pnl or 0.0)
            for trade in closed
        )

        return {

            "overview": {

                "cash_balance": round(cash_balance, 2),

                "market_value": round(market_value, 2),

                "total_equity": round(equity, 2),

                "positions": len(positions),

            },

            "pnl": {

                "realized": round(realized, 2),

                "unrealized": round(unrealized, 2),

                "combined": round(
                    realized + unrealized,
                    2,
                ),

            },

            "portfolio": {

                "largest_position_pct": round(
                    concentration,
                    2,
                ),

                "winning_positions": winners,

                "losing_positions": losers,

            },

            "closed_trades": {

                "count": closed_trades,

                "winners": winning_closed,

                "losers": losing_closed,

                "net_pnl": round(
                    total_closed_pnl,
                    2,
                ),

                "win_rate": round(
                    (
                        winning_closed /
                        closed_trades * 100
                    )
                    if closed_trades
                    else 0.0,
                    2,
                ),

            },

        }