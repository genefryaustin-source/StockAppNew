"""
modules/backtesting/vectorbt_engine.py

Vectorized backtesting via vectorbt. See package docstring for the
license note (fair-code, not plain MIT/BSD).
"""

from __future__ import annotations

from typing import Optional
import pandas as pd

MIN_BARS_FOR_BACKTEST = 60


def vectorbt_available() -> bool:
    try:
        import vectorbt  # noqa: F401
        return True
    except Exception:
        return False


def _stats_to_dict(pf) -> dict:
    """Converts vectorbt's pf.stats() Series (which has Timedelta values
    for some fields) into a JSON/Streamlit-friendly plain dict."""
    stats = pf.stats()
    out = {}
    for key, value in stats.items():
        if isinstance(value, pd.Timedelta):
            out[key] = str(value)
        elif pd.isna(value):
            out[key] = None
        else:
            try:
                out[key] = float(value)
            except (TypeError, ValueError):
                out[key] = str(value)
    return out


def backtest_signals(
    price: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    init_cash: float = 100_000.0,
    fees: float = 0.001,
) -> dict:
    """
    Generic entries/exits backtest -- price indexed by date, entries/exits
    boolean Series aligned to the same index. Returns stats + equity curve.
    """
    if not vectorbt_available():
        return {"available": False, "reason": "vectorbt isn't installed."}
    if len(price) < MIN_BARS_FOR_BACKTEST:
        return {"available": False,
                "reason": f"Need at least {MIN_BARS_FOR_BACKTEST} bars (have {len(price)})."}

    try:
        import vectorbt as vbt
        pf = vbt.Portfolio.from_signals(price, entries, exits, init_cash=init_cash, fees=fees)
        equity_curve = pf.value()
        return {
            "available": True,
            "stats": _stats_to_dict(pf),
            "total_return": float(pf.total_return()),
            "sharpe_ratio": float(pf.sharpe_ratio()) if pd.notna(pf.sharpe_ratio()) else None,
            "sortino_ratio": float(pf.sortino_ratio()) if pd.notna(pf.sortino_ratio()) else None,
            "max_drawdown": float(pf.max_drawdown()),
            "num_trades": int(pf.trades.count()),
            "win_rate": float(pf.trades.win_rate()) if pf.trades.count() > 0 else None,
            "equity_curve": equity_curve,
            "benchmark_return": float((price.iloc[-1] / price.iloc[0]) - 1.0),
        }
    except Exception as e:
        return {"available": False, "reason": f"Backtest failed: {e}"}


def backtest_signal_suite_strategy(
    db,
    symbol: str,
    period: str = "2y",
    interval: str = "1d",
    init_cash: float = 100_000.0,
    fees: float = 0.001,
    **signal_kwargs,
) -> dict:
    """
    Backtests the exact same buy/sell logic used app-wide for the chart
    overlay (modules.indicators.signal_suite.compute_signals) -- turns the
    "🎯 Buy/Sell/TP" arrows shown on every candlestick chart into an actual
    historical performance number, using the same EMA/RSI/ATR rules, not a
    separate reimplementation.
    """
    try:
        from modules.market_data.service import get_price_history
        from modules.indicators.signal_suite import compute_signals
    except Exception as e:
        return {"available": False, "reason": f"Could not load dependencies: {e}"}

    try:
        px = get_price_history(db, symbol, period=period, interval=interval)
    except Exception as e:
        return {"available": False, "reason": f"Could not fetch price history: {e}"}

    if px is None or len(px) < MIN_BARS_FOR_BACKTEST:
        return {"available": False,
                "reason": f"Not enough price history for {symbol} "
                          f"(need {MIN_BARS_FOR_BACKTEST}+ bars)."}

    sig_df = compute_signals(px, **signal_kwargs)
    price = pd.Series(sig_df["close"].values, index=pd.to_datetime(sig_df["x"].values))
    entries = pd.Series((sig_df["signal"] == "buy").values, index=price.index)
    exits = pd.Series((sig_df["signal"] == "sell").values, index=price.index)

    result = backtest_signals(price, entries, exits, init_cash=init_cash, fees=fees)
    if result.get("available"):
        result["symbol"] = symbol
        result["strategy"] = "signal_suite (EMA9/21 crossover + RSI + ATR chop filter)"
        result["num_signals"] = int(entries.sum() + exits.sum())
    return result


def backtest_ma_crossover(
    db,
    symbol: str,
    fast: int = 10,
    slow: int = 30,
    period: str = "2y",
    interval: str = "1d",
    init_cash: float = 100_000.0,
    fees: float = 0.001,
) -> dict:
    """A simple, dependency-free baseline strategy for comparison against
    backtest_signal_suite_strategy -- classic fast/slow MA crossover."""
    if not vectorbt_available():
        return {"available": False, "reason": "vectorbt isn't installed."}

    try:
        from modules.market_data.service import get_price_history
        px = get_price_history(db, symbol, period=period, interval=interval)
    except Exception as e:
        return {"available": False, "reason": f"Could not fetch price history: {e}"}

    if px is None or len(px) < MIN_BARS_FOR_BACKTEST:
        return {"available": False,
                "reason": f"Not enough price history for {symbol} "
                          f"(need {MIN_BARS_FOR_BACKTEST}+ bars)."}

    close_col = "Close" if "Close" in px.columns else "close"
    date_col = "Date" if "Date" in px.columns else "date"
    price = pd.Series(px[close_col].values, index=pd.to_datetime(px[date_col].values))

    import vectorbt as vbt
    fast_ma = vbt.MA.run(price, fast)
    slow_ma = vbt.MA.run(price, slow)
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)

    result = backtest_signals(price, entries, exits, init_cash=init_cash, fees=fees)
    if result.get("available"):
        result["symbol"] = symbol
        result["strategy"] = f"MA crossover ({fast}/{slow})"
        result["num_signals"] = int(entries.sum() + exits.sum())
    return result
