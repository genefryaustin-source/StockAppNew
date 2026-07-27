"""
modules/forex/forex_walk_forward.py

Real walk-forward validation. Splits the same live historical price/score
series used by forex_strategy_backtester into sequential windows and runs
an independent backtest in each one, replacing the previous hardcoded
{"status": "READY", "windows": 6, "passed_windows": 4, "stability_score": 66.7}
stub that ignored the strategy and any real data entirely.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from modules.forex.forex_strategy_backtester import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_PAIR,
    _fetch_price_series,
    _rolling_factor_score,
    _summarize_run,
    run_single_backtest,
)

DEFAULT_WINDOWS = 6
MIN_BARS_PER_WINDOW = 10


class ForexWalkForward:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def run(
        self,
        strategy: Dict[str, Any],
        pair: Optional[str] = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        windows: int = DEFAULT_WINDOWS,
    ) -> Dict[str, Any]:
        name = strategy.get("name", "FX Strategy")
        pair = pair or strategy.get("pair") or DEFAULT_PAIR
        windows = int(windows) if windows else DEFAULT_WINDOWS

        try:
            closes = _fetch_price_series(pair, lookback_days)
        except Exception as exc:
            return {"status": "ERROR", "strategy": name, "pair": pair, "error": str(exc)}

        if closes is None or len(closes) < windows * MIN_BARS_PER_WINDOW:
            return {
                "status": "NO_DATA",
                "strategy": name,
                "pair": pair,
                "message": f"Not enough live historical data for a {windows}-window walk-forward yet.",
            }

        scores = _rolling_factor_score(closes)

        chunk_size = len(closes) // windows
        window_returns = []
        window_summaries = []

        for w in range(windows):
            start_i = w * chunk_size
            end_i = (w + 1) * chunk_size if w < windows - 1 else len(closes)
            window_closes = closes.iloc[start_i:end_i]
            window_scores = scores.iloc[start_i:end_i]
            if len(window_closes) < MIN_BARS_PER_WINDOW:
                continue

            run_result = run_single_backtest(strategy, window_closes, window_scores)
            summary = _summarize_run(run_result)
            window_summaries.append(summary)
            if summary["total_return_pct"] is not None:
                window_returns.append(summary["total_return_pct"])

        if not window_returns:
            return {
                "status": "NO_TRADES",
                "strategy": name,
                "pair": pair,
                "windows": len(window_summaries),
                "message": "No trades were generated in any window.",
            }

        passed_windows = sum(1 for r in window_returns if r > 0)
        mean_r = sum(window_returns) / len(window_returns)
        var_r = sum((r - mean_r) ** 2 for r in window_returns) / len(window_returns)
        std_r = var_r ** 0.5
        cv = (std_r / abs(mean_r)) if mean_r != 0 else (1.0 if std_r > 0 else 0.0)
        stability_score = round(max(0.0, min(100.0, 100.0 * (1.0 - min(cv, 1.0)))), 1)

        return {
            "status": "READY",
            "strategy": name,
            "pair": pair,
            "windows": len(window_summaries),
            "passed_windows": passed_windows,
            "window_returns_pct": window_returns,
            "window_summaries": window_summaries,
            "stability_score": stability_score,
            "methodology": (
                "Each window is an independent run of the same rule-based "
                "backtest (forex_strategy_backtester) on a sequential slice of "
                "live daily closes -- no parameter re-optimization between "
                "windows. stability_score = 100 * (1 - coefficient_of_variation "
                "of window returns), clipped to [0, 100]."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_WF = None


def get_forex_walk_forward(db: Optional[Any] = None) -> ForexWalkForward:
    global _WF
    if _WF is None or (db is not None and _WF.db is None):
        _WF = ForexWalkForward(db=db)
    return _WF