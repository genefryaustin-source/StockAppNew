from __future__ import annotations

from models.trading import (
    Portfolio,
    PortfolioPosition,
)


class PortfolioAllocationService:

    def __init__(self, db):
        self.db = db

    def get_allocation(
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
                PortfolioPosition.market_value.desc()
            )
            .all()
        )

        total_market_value = sum(
            float(position.market_value or 0.0)
            for position in positions
        )

        allocations = []

        for position in positions:

            market_value = float(position.market_value or 0.0)

            weight = (
                (market_value / total_market_value) * 100.0
                if total_market_value > 0
                else 0.0
            )

            allocations.append({

                "symbol": position.symbol,

                "qty": float(position.qty or 0.0),

                "avg_cost": float(position.avg_cost or 0.0),

                "market_price": float(position.market_price or 0.0),

                "market_value": market_value,

                "weight": round(weight, 2),

                "unrealized_pnl": float(position.unrealized_pnl or 0.0),

                "realized_pnl": float(position.realized_pnl or 0.0),

            })

        return {

            "total_market_value": total_market_value,

            "position_count": len(positions),

            "allocations": allocations,

        }