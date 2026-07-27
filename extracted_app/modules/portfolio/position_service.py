
from models.trading import Portfolio, PortfolioPosition

class PositionService:

    def __init__(self, db):
        self.db = db

    def list_positions(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ):

        #
        # Verify portfolio belongs to tenant
        #
        portfolio = (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

        if portfolio is None:
            return []

        return (
            self.db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.portfolio_id == portfolio_id,
            )
            .order_by(
                PortfolioPosition.symbol.asc(),
            )
            .all()
        )

