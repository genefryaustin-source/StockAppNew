"""
modules/analytics/market_regime_inputs.py

Market Regime Inputs

Computes the four real, data-driven statistics
modules.analytics.adaptive_factor_engine.detect_market_regime() needs
(market_return_30d, market_return_90d, volatility_30d, drawdown_90d)
from stored price history for a broad market benchmark.

detect_market_regime()'s own classification logic is genuinely
real -- honest threshold-based rules over these four numbers, not
fabricated. The problem was upstream: its one confirmed-live caller
(modules.analytics.ranking_ui.render_ai_rankings) fed it hardcoded
literal constants (0.06, 0.11, 0.19, -0.04) instead of anything
computed, so it always returned the same regime regardless of actual
market conditions. This module is what makes those inputs real.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# S&P 500 ETF -- the same symbol already used as this platform's
# default portfolio benchmark elsewhere (models.trading.Portfolio.
# benchmark defaults to "SPY"), so this is consistent with what "the
# market" already means throughout the rest of this app, not a new,
# separate convention.
DEFAULT_BENCHMARK_SYMBOL = "SPY"

# Below this many stored trading days, don't attempt any of the
# rolling-window statistics -- a short, noisy history would produce a
# real-looking-but-unreliable number rather than an honest "not enough
# data yet".
MIN_TRADING_DAYS = 95


def compute_market_regime_inputs(
    db,
    *,
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL,
) -> Optional[dict]:
    """
    Returns {"market_return_30d", "market_return_90d",
    "volatility_30d", "drawdown_90d"} computed from real, stored
    daily closes for benchmark_symbol, or None if there isn't enough
    price history yet to compute them honestly. Callers should treat
    None as "unknown" (e.g. fall back to a neutral/default regime
    rather than passing zeros through, which would themselves look
    like a real, computed "flat market" reading).

    volatility_30d is annualized realized volatility (daily return
    std * sqrt(252)), matching the units detect_market_regime()'s own
    thresholds (0.15/0.25/0.35) are written against -- those are
    clearly annualized-vol-style cutoffs, not raw daily-return-std
    magnitudes.
    """

    from modules.market_data.price_history_service import load_price_history

    try:
        df = load_price_history(db, benchmark_symbol)
    except Exception:
        logger.exception(
            "Failed to load price history for market regime inputs | symbol=%s",
            benchmark_symbol,
        )
        return None

    if df is None or df.empty:
        logger.info(
            "No stored price history for market regime benchmark | symbol=%s",
            benchmark_symbol,
        )
        return None

    closes = df["Close"].dropna()

    if len(closes) < MIN_TRADING_DAYS:
        logger.info(
            "Not enough price history for market regime inputs | symbol=%s days=%d needed=%d",
            benchmark_symbol, len(closes), MIN_TRADING_DAYS,
        )
        return None

    def _pct_return(n_days: int) -> float:
        # Return from n_days of trading sessions ago to the most
        # recent close -- guarded above by MIN_TRADING_DAYS, but
        # checked again here defensively.
        if len(closes) <= n_days:
            return 0.0
        start = closes.iloc[-(n_days + 1)]
        end = closes.iloc[-1]
        if start == 0:
            return 0.0
        return float((end / start) - 1.0)

    market_return_30d = _pct_return(30)
    market_return_90d = _pct_return(90)

    daily_returns_30d = closes.iloc[-31:].pct_change().dropna()
    volatility_30d = float(daily_returns_30d.std() * (252 ** 0.5)) if len(daily_returns_30d) > 1 else 0.0

    window_90d = closes.iloc[-90:]
    running_max = window_90d.cummax()
    drawdown_series = (window_90d - running_max) / running_max.replace(0, float("nan"))
    drawdown_90d = float(drawdown_series.min()) if not drawdown_series.empty else 0.0

    return {
        "market_return_30d": market_return_30d,
        "market_return_90d": market_return_90d,
        "volatility_30d": volatility_30d,
        "drawdown_90d": drawdown_90d,
        "benchmark_symbol": benchmark_symbol,
        "trading_days_available": int(len(closes)),
    }