"""
api/services/portfolio_correlation_api_service.py

Portfolio Correlation API Service

Backs GET /api/v1/portfolio/{portfolio_id}/correlation.

Real pairwise correlation matrix (pandas .corr()) over real per-symbol
daily return series, built via api.services._portfolio_symbol_returns --
no fabricated or placeholder values.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from models.trading import Portfolio, PortfolioPosition

from api.services._portfolio_symbol_returns import build_symbol_returns, _safe_rollback


class PortfolioCorrelationAPIService:
    """
    API service for pairwise correlation between currently-held symbols.
    Real correlation math (pandas .corr()) over real per-symbol daily
    return series -- no fabricated or placeholder values.
    """

    def __init__(self, db):
        self.db = db

    def get_correlation(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Pairwise correlation matrix across currently-held symbols with
        at least a year of overlapping daily price history.

        Returns an empty matrix (not an error) with a `note` explaining
        why if there are fewer than 2 positions or not enough
        overlapping history. Returns None if the portfolio doesn't exist
        or doesn't belong to tenant_id -- the router turns that into a
        404.
        """

        # This service's db session is cached and reused across every
        # request to this endpoint for the life of the process (see
        # ModuleRegistry._load). If an earlier request left it in a
        # failed-transaction state (Postgres) and didn't roll back,
        # every query below -- including this very first one -- would
        # otherwise fail immediately. Rolling back a clean session is a
        # harmless no-op.
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

        symbols = sorted({p.symbol for p in positions})

        if len(symbols) < 2:
            return {
                "portfolio_id": str(portfolio_id),
                "symbols": symbols,
                "matrix": {},
                "note": "Need at least 2 open positions to compute correlation.",
            }

        returns_df, failures = build_symbol_returns(self.db, symbols)

        if returns_df.empty or returns_df.shape[1] < 2:
            return {
                "portfolio_id": str(portfolio_id),
                "symbols": symbols,
                "matrix": {},
                "symbols_without_history": failures,
                "note": "Not enough overlapping price history to compute correlation.",
            }

        corr = returns_df.corr()
        corr = corr.replace([np.inf, -np.inf], np.nan)

        matrix = {
            row_symbol: {
                col_symbol: (
                    round(float(value), 4) if pd.notnull(value) else None
                )
                for col_symbol, value in corr[row_symbol].items()
            }
            for row_symbol in corr.columns
        }

        return {
            "portfolio_id": str(portfolio_id),
            "symbols": list(corr.columns),
            "matrix": matrix,
            "symbols_without_history": failures,
        }