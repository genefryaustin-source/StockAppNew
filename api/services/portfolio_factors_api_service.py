"""
api/services/portfolio_factors_api_service.py

Portfolio Factors API Service

Backs GET /api/v1/portfolio/{portfolio_id}/factors.

Computes real market beta (CAPM single-factor exposure) via linear
regression of each position's returns against the portfolio's
benchmark returns. Deliberately does not claim a multi-factor
(Fama-French style) model -- this platform has no size/value/momentum
factor return series to regress against, and fabricating one would be
worse than not offering it.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from models.trading import Portfolio, PortfolioPosition
from modules.market_data.service import get_price_history

from api.services._portfolio_symbol_returns import build_symbol_returns, _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioFactorsAPIService:
    """
    API service for factor exposure. This computes real market beta
    (CAPM single-factor exposure) via linear regression of each
    position's returns against the portfolio's benchmark returns --
    it does not claim to offer a multi-factor (Fama-French style) model,
    since this platform has no size/value/momentum factor return series
    to regress against. Beta is a real, standard, honestly-scoped
    factor exposure; anything more would be fabricated.
    """

    def __init__(self, db):
        self.db = db

    def get_factors(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Per-position beta against the portfolio's benchmark, plus a
        value-weighted portfolio-level beta.

        Requires at least 20 overlapping daily observations to compute;
        returns empty betas with a `note` explaining why otherwise.
        Returns None if the portfolio doesn't exist or doesn't belong to
        tenant_id -- the router turns that into a 404.
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
                "benchmark": portfolio.benchmark or "SPY",
                "position_betas": {},
                "portfolio_beta": None,
                "note": "No open positions.",
            }

        benchmark_symbol = (portfolio.benchmark or "SPY").upper()
        symbols = sorted({p.symbol for p in positions})

        returns_df, failures = build_symbol_returns(self.db, symbols)

        try:
            from modules.market_data.price_history_service import load_price_history

            bench_history = load_price_history(self.db, benchmark_symbol)

            if bench_history is None or bench_history.empty:
                bench_history = get_price_history(
                    self.db, benchmark_symbol, period="1y", interval="1d"
                )
        except Exception:
            logger.exception(
                "Benchmark history fetch failed for factors | %s", benchmark_symbol
            )
            _safe_rollback(self.db)
            bench_history = None

        if (
            returns_df.empty
            or bench_history is None
            or bench_history.empty
            or "Close" not in bench_history.columns
        ):
            return {
                "portfolio_id": str(portfolio_id),
                "benchmark": benchmark_symbol,
                "position_betas": {},
                "portfolio_beta": None,
                "symbols_without_history": failures,
                "note": "Not enough price history to compute beta.",
            }

        bench_prices = pd.to_numeric(bench_history["Close"], errors="coerce")

        if "Date" in bench_history.columns:
            bench_prices.index = pd.to_datetime(bench_history["Date"], errors="coerce")
        else:
            # "Date" is already the index (the fast, DB-cached path) --
            # just make sure it's real datetime values.
            bench_prices.index = pd.to_datetime(bench_history.index, errors="coerce")

        bench_returns = (
            bench_prices
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .pct_change()
            .dropna()
        )
        bench_returns.name = "__benchmark__"

        merged = pd.concat([returns_df, bench_returns], axis=1, join="inner").dropna()

        position_betas: dict[str, float] = {}

        if len(merged) >= 20:
            bench_var = float(merged["__benchmark__"].var())

            if bench_var > 0:
                for symbol in returns_df.columns:
                    if symbol not in merged.columns:
                        continue

                    covariance = float(
                        merged[symbol].cov(merged["__benchmark__"])
                    )
                    position_betas[symbol] = round(covariance / bench_var, 3)

        market_values = {
            p.symbol: float(p.qty or 0.0) * float(p.market_price or 0.0)
            for p in positions
        }
        total_value = sum(market_values.values())

        portfolio_beta = None
        if position_betas and total_value > 0:
            weighted = sum(
                position_betas.get(symbol, 0.0)
                * (market_values.get(symbol, 0.0) / total_value)
                for symbol in position_betas
            )
            portfolio_beta = round(weighted, 3)

        return {
            "portfolio_id": str(portfolio_id),
            "benchmark": benchmark_symbol,
            "position_betas": position_betas,
            "portfolio_beta": portfolio_beta,
            "symbols_without_history": failures,
            "observations_used": len(merged),
        }