from __future__ import annotations

from datetime import datetime, timedelta, UTC

from models.trading import (
    Portfolio,
    PortfolioSnapshot,
)

# Standard chart period tokens -> lookback in days. "ytd" and "max"
# are handled specially (see get_history).
_PERIOD_DAYS = {
    "1d": 1,
    "5d": 5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 182,
    "1y": 365,
}


class PortfolioHistoryService:

    def __init__(self, db):
        self.db = db

    def get_history(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        period: str | None = None,
        limit: int = 250,
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

        query = (
            self.db.query(PortfolioSnapshot)
            .filter(
                PortfolioSnapshot.portfolio_id == portfolio_id,
            )
        )

        period_key = (period or "").lower().strip()

        if period_key == "ytd":
            cutoff = datetime(datetime.now(UTC).year, 1, 1, tzinfo=UTC)
            query = query.filter(PortfolioSnapshot.as_of >= cutoff)
        elif period_key in _PERIOD_DAYS:
            cutoff = datetime.now(UTC) - timedelta(days=_PERIOD_DAYS[period_key])
            query = query.filter(PortfolioSnapshot.as_of >= cutoff)
        # "max" (or no period given) -- no date filter, full history
        # up to `limit`.

        # Order descending and limit, then reverse for chronological
        # output -- ordering ascending-then-limit (the previous
        # behavior) returned the OLDEST records whenever history
        # exceeded the limit, silently dropping all recent data.
        snapshots = list(
            reversed(
                query
                .order_by(PortfolioSnapshot.as_of.desc())
                .limit(limit)
                .all()
            )
        )

        history = []

        for snapshot in snapshots:
            history.append({

                "as_of": (
                    snapshot.as_of.isoformat()
                    if snapshot.as_of
                    else None
                ),

                "cash_balance": float(
                    snapshot.cash or 0.0
                ),

                "market_value": float(
                    snapshot.market_value or 0.0
                ),

                "total_equity": float(
                    snapshot.equity or 0.0
                ),

                "realized_pnl": float(
                    snapshot.realized_pnl or 0.0
                ),

                "unrealized_pnl": float(
                    snapshot.unrealized_pnl or 0.0
                ),

                "net_pnl": float(
                    snapshot.net_pnl or 0.0
                ),

            })

        return history