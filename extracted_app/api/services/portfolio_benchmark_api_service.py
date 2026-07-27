"""
api/services/portfolio_benchmark_api_service.py

Portfolio Benchmark API Service

Backs GET /api/v1/portfolio/{portfolio_id}/benchmark.

Wraps modules.portfolio.nav_service.NavService.compute_nav_vs_benchmark
-- all NAV/benchmark series construction stays there. Includes a
minimal, defensive market_data shim so NavService's rarely-hit sector-
lookup path can't raise AttributeError the way app.py's own ad-hoc
adapter can.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class _MarketDataShim:
    """
    Minimal, defensive market_data adapter for NavService. NavService
    only actually needs get_security_metadata() on rarely-hit paths
    (sector lookups) -- this returns an empty dict rather than raising,
    unlike the ad-hoc adapter app.py builds for the Streamlit UI, which
    doesn't define that method at all.
    """

    def get_security_metadata(self, symbol: str) -> dict:
        """Sector/metadata lookup NavService calls defensively; always
        safe to return nothing rather than raise."""
        return {}

    def get_quote(self, symbol: str):
        """Not used on the benchmark-comparison path; present only so
        this shim satisfies the same shape app.py's adapter offers."""
        return None


class PortfolioBenchmarkAPIService:
    """
    API service for portfolio-vs-benchmark performance comparison. Wraps
    modules.portfolio.nav_service.NavService.compute_nav_vs_benchmark --
    all NAV/benchmark series construction stays there.
    """

    def __init__(self, db):
        self.db = db

    def get_benchmark(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        benchmark: str | None = None,
        period: str = "6mo",
    ) -> dict[str, Any] | None:
        """
        Cumulative portfolio return vs. a benchmark's return over the
        requested period (defaults to the portfolio's own configured
        benchmark, falling back to SPY).

        available=False (not an error) if there isn't enough overlapping
        NAV/benchmark history yet. Returns None if the portfolio doesn't
        exist or doesn't belong to tenant_id -- the router turns that
        into a 404.
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

        benchmark_symbol = (benchmark or portfolio.benchmark or "SPY").upper()

        from modules.portfolio.nav_service import NavService

        nav_service = NavService(self.db, _MarketDataShim())

        try:
            result = nav_service.compute_nav_vs_benchmark(
                portfolio_id,
                benchmark=benchmark_symbol,
                period=period,
            )
        except Exception:
            logger.exception(
                "Benchmark comparison failed | %s | %s",
                portfolio_id,
                benchmark_symbol,
            )
            _safe_rollback(self.db)
            result = None

        if result is None:
            return {
                "portfolio_id": str(portfolio_id),
                "benchmark": benchmark_symbol,
                "period": period,
                "available": False,
                "reason": (
                    "Not enough overlapping NAV and benchmark history yet "
                    "(needs at least 5 matched trading days)."
                ),
                "comparison": [],
            }

        comparison_df = result["comparison_df"]

        portfolio_return_pct = (
            float(comparison_df["cum_p"].iloc[-1]) * 100.0
            if not comparison_df.empty
            else 0.0
        )
        benchmark_return_pct = (
            float(comparison_df["cum_b"].iloc[-1]) * 100.0
            if not comparison_df.empty
            else 0.0
        )

        clean = comparison_df.replace([np.inf, -np.inf], np.nan).where(
            pd.notnull(comparison_df), None
        )
        clean = clean.copy()
        clean["Date"] = clean["Date"].astype(str)

        return {
            "portfolio_id": str(portfolio_id),
            "benchmark": benchmark_symbol,
            "period": period,
            "available": True,
            "portfolio_return_pct": round(portfolio_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "excess_return_pct": round(
                portfolio_return_pct - benchmark_return_pct, 2
            ),
            "comparison": clean.to_dict(orient="records"),
        }