"""
api/services/portfolio_optimization_api_service.py

Portfolio Optimization API Service

Backs GET /api/v1/portfolio/{portfolio_id}/optimization.

Wraps the two real portfolio-level weight engines already in
modules.portfolio: Black-Litterman (modules.portfolio.black_litterman)
and Risk Parity (modules.portfolio.risk_parity). Both are legitimate,
standard institutional weighting techniques -- this orchestrates the
engines that already exist rather than inventing a new one.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio, PortfolioPosition
from modules.market_data.service import get_price_history

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioOptimizationAPIService:
    """
    API service for portfolio optimization. Wraps the two real portfolio-
    level weight engines already in modules.portfolio: Black-Litterman
    (modules.portfolio.black_litterman) and Risk Parity
    (modules.portfolio.risk_parity). Both take the same price_cache/
    symbols shape, so both run off one shared price fetch.

    Both are legitimate, standard institutional weighting techniques --
    this doesn't invent a new optimizer, it just orchestrates the ones
    that already exist and compares them against current weights.
    """

    def __init__(self, db):
        self.db = db

    def get_optimization(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Current weights alongside Risk Parity and Black-Litterman
        suggested weights for the portfolio's currently-held symbols.

        Any symbol whose price history can't be fetched is left out of
        both optimizers and listed in symbols_without_history rather
        than estimated. Returns None if the portfolio doesn't exist or
        doesn't belong to tenant_id -- the router turns that into a 404.
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
                "current_weights": {},
                "risk_parity_weights": {},
                "black_litterman_weights": {},
                "note": "No open positions to optimize.",
            }

        symbols = sorted({p.symbol for p in positions})

        market_values = {
            p.symbol: float(p.qty or 0.0) * float(p.market_price or 0.0)
            for p in positions
        }
        total_value = sum(market_values.values())

        current_weights = (
            {s: round(v / total_value, 4) for s, v in market_values.items()}
            if total_value > 0
            else {}
        )

        price_cache: dict[str, Any] = {}
        history_failures: list[str] = []

        for symbol in symbols:
            try:
                history = get_price_history(
                    self.db, symbol, period="1y", interval="1d"
                )
                if history is not None and not history.empty:
                    price_cache[symbol] = history
                else:
                    history_failures.append(symbol)
            except Exception:
                logger.exception(
                    "Price history fetch failed for optimization | %s | %s",
                    portfolio_id,
                    symbol,
                )
                _safe_rollback(self.db)
                history_failures.append(symbol)

        usable_symbols = [s for s in symbols if s in price_cache]

        risk_parity_weights: dict[str, float] = {}
        black_litterman_weights: dict[str, float] = {}

        if usable_symbols:
            from modules.portfolio.risk_parity import risk_parity_weights as rp_fn
            from modules.portfolio.black_litterman import (
                black_litterman_weights as bl_fn,
            )

            try:
                rp_df = rp_fn(price_cache, usable_symbols)
                if rp_df is not None and not rp_df.empty:
                    risk_parity_weights = {
                        row["symbol"]: round(float(row["weight"]), 4)
                        for _, row in rp_df.iterrows()
                    }
            except Exception:
                logger.exception(
                    "Risk parity optimization failed | %s", portfolio_id
                )

            try:
                bl_df = bl_fn(price_cache, usable_symbols)
                if bl_df is not None and not bl_df.empty:
                    black_litterman_weights = {
                        row["symbol"]: round(float(row["weight"]), 4)
                        for _, row in bl_df.iterrows()
                    }
            except Exception:
                logger.exception(
                    "Black-Litterman optimization failed | %s", portfolio_id
                )

        return {
            "portfolio_id": str(portfolio_id),
            "current_weights": current_weights,
            "risk_parity_weights": risk_parity_weights,
            "black_litterman_weights": black_litterman_weights,
            "symbols_with_history": usable_symbols,
            "symbols_without_history": history_failures,
        }