"""
api/services/_portfolio_symbol_returns.py

Shared per-symbol return-series builder for the Portfolio API layer.

Used by portfolio_correlation_api_service.py and
portfolio_factors_api_service.py, both of which need one return series
per held symbol (to correlate or regress symbols against each other),
unlike modules.risk_layer.positions.get_returns_df, which returns a
single portfolio-level aggregated equity-curve series -- useful for
VaR/stress testing, useless for comparing individual holdings.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from modules.market_data.service import get_price_history

logger = logging.getLogger(__name__)


def _safe_rollback(db) -> None:
    """
    Roll back a session after a caught DB-touching exception.

    On Postgres (unlike SQLite), one failed query leaves the whole
    transaction "aborted" -- every subsequent command on that same
    connection is refused until a rollback happens, not just the one
    that failed. The Portfolio API's module registry caches one
    session per service for the life of the process, so skipping this
    doesn't just break the current request -- it breaks every request
    to that endpoint until the process restarts. Never raises.
    """
    try:
        db.rollback()
    except Exception:
        logger.exception("Rollback itself failed -- session may be unusable.")


def build_symbol_returns(
    db,
    symbols: list[str],
    *,
    period: str = "1y",
    interval: str = "1d",
) -> tuple[pd.DataFrame, list[str]]:
    """
    Per-symbol daily return series for a set of symbols, as one
    DataFrame (one column per symbol, inner-joined on date).

    This is deliberately separate from
    modules.risk_layer.positions.get_returns_df, which returns a single
    portfolio-level aggregated equity-curve return series -- useful for
    VaR/stress testing, useless for correlating individual holdings
    against each other, which needs each symbol's own return series as
    its own column.

    Returns (returns_df, symbols_without_history). Never raises -- a
    symbol whose history can't be fetched is just left out and reported
    in the second element, not estimated or defaulted to zero.
    """

    series_list: list[pd.Series] = []
    failures: list[str] = []

    # Batch fetch: every symbol's closes in ONE query, instead of one
    # live get_price_history() call per symbol. Falls back to the live
    # per-symbol fetch only for symbols with no stored history at all.
    try:
        from modules.market_data.price_history_service import load_close_matrix

        matrix = load_close_matrix(db, symbols)
    except Exception:
        logger.exception("Batched close-matrix fetch failed, falling back to per-symbol live fetches.")
        _safe_rollback(db)
        matrix = None

    matrix_symbols = set(matrix.columns) if matrix is not None and not matrix.empty else set()

    for symbol in symbols:
        if symbol in matrix_symbols:
            closes = matrix[symbol].dropna()

            if closes.empty:
                failures.append(symbol)
                continue

            returns = (
                pd.to_numeric(closes, errors="coerce")
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
                .pct_change()
                .dropna()
            )

            if returns.empty:
                failures.append(symbol)
                continue

            returns.name = symbol
            series_list.append(returns)
            continue

        try:
            history = get_price_history(db, symbol, period=period, interval=interval)
        except Exception:
            logger.exception("Price history fetch failed | %s", symbol)
            _safe_rollback(db)
            failures.append(symbol)
            continue

        if history is None or history.empty:
            failures.append(symbol)
            continue

        close_col = None
        for candidate in ("Close", "close", "Adj Close", "adj_close"):
            if candidate in history.columns:
                close_col = candidate
                break

        if close_col is None:
            failures.append(symbol)
            continue

        # Index by date to match the fast path's date-indexed series
        # (from load_close_matrix) -- pd.concat's inner join below
        # needs every series to share the same kind of index, or dates
        # from one symbol won't align with another's at all.
        date_col = "Date" if "Date" in history.columns else None
        prices = pd.to_numeric(history[close_col], errors="coerce")
        if date_col is not None:
            prices.index = pd.to_datetime(history[date_col], errors="coerce")

        returns = (
            prices
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .pct_change()
            .dropna()
        )

        if returns.empty:
            failures.append(symbol)
            continue

        returns.name = symbol
        series_list.append(returns)

    if not series_list:
        return pd.DataFrame(), failures

    returns_df = pd.concat(series_list, axis=1, join="inner")
    returns_df = returns_df.replace([np.inf, -np.inf], np.nan).dropna(how="all")

    return returns_df, failures