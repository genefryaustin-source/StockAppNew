from __future__ import annotations

from models.trading import (
    Portfolio,
    PortfolioPosition,
)


class PortfolioHoldingsService:

    def __init__(self, db):
        self.db = db

    def get_holdings(
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
            .order_by(
                PortfolioPosition.symbol.asc(),
            )
            .all()
        )

        total_market_value = sum(
            float(p.market_value or 0.0)
            for p in positions
        )

        holdings = []

        for position in positions:

            qty = float(position.qty or 0.0)
            avg_cost = float(position.avg_cost or 0.0)
            market_price = float(position.market_price or 0.0)
            market_value = float(position.market_value or 0.0)

            cost_basis = qty * avg_cost

            unrealized = float(position.unrealized_pnl or 0.0)
            realized = float(position.realized_pnl or 0.0)

            allocation = (
                (market_value / total_market_value) * 100.0
                if total_market_value > 0
                else 0.0
            )

            unrealized_pct = (
                (unrealized / cost_basis) * 100.0
                if cost_basis > 0
                else 0.0
            )

            holdings.append({

                "symbol": position.symbol,

                "quantity": qty,

                "average_cost": avg_cost,

                "cost_basis": round(cost_basis, 2),

                "market_price": market_price,

                "market_value": round(market_value, 2),

                "allocation_pct": round(allocation, 2),

                "unrealized_pnl": round(unrealized, 2),

                "unrealized_pnl_pct": round(unrealized_pct, 2),

                "realized_pnl": round(realized, 2),

                "last_updated": (
                    position.updated_at.isoformat()
                    if position.updated_at
                    else None
                ),

            })

        return {

            "portfolio_id": portfolio_id,

            "holding_count": len(holdings),

            "total_market_value": round(
                total_market_value,
                2,
            ),

            "holdings": holdings,

        }