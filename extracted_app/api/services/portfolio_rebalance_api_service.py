"""
api/services/portfolio_rebalance_api_service.py

Portfolio Rebalance API Service

Backs GET /api/v1/portfolio/{portfolio_id}/rebalance.

Wraps modules.portfolio.rebalance_engine.compute_rebalance() -- all
trade-sizing math stays there. Defaults to an equal-weight target across
currently-held symbols since there's no stored "target allocation" on a
Portfolio to read instead; see the class docstring for why.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from models.trading import Portfolio, PortfolioPosition

from api.services._portfolio_symbol_returns import _safe_rollback


class PortfolioRebalanceAPIService:
    """
    API service for rebalance suggestions. Wraps
    modules.portfolio.rebalance_engine.compute_rebalance() -- all trade-
    sizing math stays there.

    There's no stored "target allocation" concept on a Portfolio today,
    so a GET endpoint (no request body to supply one) needs a sensible
    default: equal-weight across currently-held symbols. That's a
    standard, honest default rebalance strategy, not a personalized
    target -- the response says so explicitly.
    """

    def __init__(self, db):
        self.db = db

    def get_rebalance(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Trades needed to move current holdings to an equal weight
        across currently-held symbols.

        Returns None if the portfolio doesn't exist or doesn't belong
        to tenant_id -- the router turns that into a 404.
        """

        # See portfolio_correlation_api_service.py for why this matters:
        # this service's session is cached and reused for the life of
        # the process, so a prior request's unrolled-back failure would
        # otherwise break every query below, including this first one.
        _safe_rollback(self.db)

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
                PortfolioPosition.qty != 0,
            )
            .all()
        )

        if not positions:
            return {
                "portfolio_id": str(portfolio_id),
                "strategy": "equal_weight",
                "trades": [],
                "note": "No open positions to rebalance.",
            }

        current_positions = {p.symbol: float(p.qty or 0.0) for p in positions}
        price_map = {
            p.symbol: float(p.market_price or 0.0)
            for p in positions
            if float(p.market_price or 0.0) > 0
        }

        portfolio_value = sum(
            float(p.qty or 0.0) * float(p.market_price or 0.0) for p in positions
        )

        symbols = [s for s in current_positions if s in price_map]

        if not symbols or portfolio_value <= 0:
            return {
                "portfolio_id": str(portfolio_id),
                "strategy": "equal_weight",
                "trades": [],
                "note": "No usable market prices available for rebalancing.",
            }

        equal_weight = 1.0 / len(symbols)
        target_weights = pd.DataFrame(
            {"symbol": symbols, "weight": [equal_weight] * len(symbols)}
        )

        from modules.portfolio.rebalance_engine import compute_rebalance

        trades_df = compute_rebalance(
            current_positions=current_positions,
            target_weights=target_weights,
            portfolio_value=portfolio_value,
            price_map=price_map,
        )

        trades = (
            trades_df.to_dict(orient="records") if not trades_df.empty else []
        )

        return {
            "portfolio_id": str(portfolio_id),
            "strategy": "equal_weight",
            "portfolio_value": round(portfolio_value, 2),
            "symbols_considered": symbols,
            "trades": trades,
            "note": (
                "Trades shown are what it would take to move to an equal "
                "weight across currently-held symbols -- not a "
                "personalized target allocation, since none is configured "
                "for this portfolio."
            ),
        }