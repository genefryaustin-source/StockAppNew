"""
modules/analytics/backtest_engine.py

Strategy Backtesting Engine.

Simulates a strategy's historical performance by:
  1. Computing indicator signals daily from OHLCV history
  2. Entering positions when BUY conditions trigger
  3. Exiting on SELL conditions, stop-loss, take-profit, or hold-period
  4. Calculating per-trade P&L, portfolio curve, and full statistics

Supports two modes:
  A) Factor-based: rank universe by analytics scores, hold top N
  B) Indicator-based: use IndicatorFormula conditions as entry signals

All computations are pure pandas/numpy — no DB writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""
    strategy_name:      str   = "Custom Strategy"
    start_date:         str   = ""          # "2022-01-01" or ""
    end_date:           str   = ""          # "2024-12-31" or ""
    initial_capital:    float = 100_000.0
    position_size_pct:  float = 10.0        # % of capital per position
    max_positions:      int   = 10
    commission_pct:     float = 0.0         # 0 = paper/zero commission
    stop_loss_pct:      float = 0.0         # 0 = no stop loss
    take_profit_pct:    float = 0.0         # 0 = no take profit
    hold_days:          int   = 0           # 0 = hold until exit signal
    rebalance_freq:     str   = "monthly"   # daily / weekly / monthly
    benchmark_symbol:   str   = "SPY"


@dataclass
class Trade:
    symbol:         str
    entry_date:     str
    exit_date:      str
    entry_price:    float
    exit_price:     float
    qty:            float
    side:           str       = "long"
    pnl:            float     = 0.0
    pnl_pct:        float     = 0.0
    exit_reason:    str       = "signal"   # signal / stop_loss / take_profit / end


@dataclass
class BacktestResult:
    strategy_name:      str
    config:             BacktestConfig

    # Equity curve (DatetimeIndex → portfolio value)
    equity_curve:       pd.Series = field(default_factory=pd.Series)
    benchmark_curve:    pd.Series = field(default_factory=pd.Series)

    # Trade log
    trades:             list[Trade] = field(default_factory=list)

    # Summary statistics
    total_return_pct:   float = 0.0
    benchmark_return_pct: float = 0.0
    alpha_annualised:   float = 0.0
    sharpe_ratio:       float = 0.0
    sortino_ratio:      float = 0.0
    max_drawdown_pct:   float = 0.0
    win_rate_pct:       float = 0.0
    total_trades:       int   = 0
    avg_trade_pct:      float = 0.0
    avg_hold_days:      float = 0.0
    annualised_return:  float = 0.0
    calmar_ratio:       float = 0.0

    error:              Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Factor-based backtest (uses analytics scores)
# ─────────────────────────────────────────────────────────────

def run_factor_backtest(
    price_data: dict[str, pd.DataFrame],   # {symbol: OHLCV df}
    factor_scores: dict[str, dict],         # {symbol: {composite, momentum, quality...}}
    config: BacktestConfig,
    benchmark_data: Optional[pd.DataFrame] = None,
) -> BacktestResult:
    """
    Factor-based backtest: buy top-N stocks by composite score,
    rebalance at specified frequency.

    price_data : {symbol: DataFrame with Date + Close columns}
    factor_scores: {symbol: {"composite": float, "momentum": float, ...}}
    """
    result = BacktestResult(
        strategy_name=config.strategy_name,
        config=config,
    )

    # ── Build aligned price matrix ────────────────────────────
    closes = _build_price_matrix(price_data, config)
    if closes is None or closes.empty:
        result.error = "No valid price data for backtest."
        return result

    # ── Build rebalance schedule ──────────────────────────────
    rebalance_dates = _rebalance_schedule(closes.index, config.rebalance_freq)

    # ── Rank symbols by composite score ──────────────────────
    # Normalise all symbol keys to uppercase stripped — prevents AAPL vs AAPL.US mismatches
    def _norm(s):
        return str(s).upper().replace(".US", "").replace("-", ".").strip()

    closes.columns = [_norm(c) for c in closes.columns]
    factor_scores  = {_norm(k): v for k, v in factor_scores.items()}

    ranked = sorted(
        factor_scores.items(),
        key=lambda x: float(x[1].get("composite") or 0),
        reverse=True,
    )
    top_symbols = [s for s, _ in ranked[:config.max_positions] if s in closes.columns]

    if not top_symbols:
        # Debug info — show what keys exist on both sides
        price_keys  = sorted(closes.columns.tolist())[:10]
        factor_keys = sorted(factor_scores.keys())[:10]
        result.error = (
            f"No symbols with both price data and factor scores. "
            f"Price keys sample: {price_keys}. "
            f"Factor keys sample: {factor_keys}."
        )
        return result

    # ── Simulate equal-weight rebalanced portfolio ────────────
    # Only use symbols that have sufficient data
    valid_symbols = [s for s in top_symbols
                     if s in closes.columns
                     and closes[s].dropna().shape[0] >= 20]

    if not valid_symbols:
        result.error = "No symbols had sufficient price history."
        return result

    portfolio_closes = closes[valid_symbols].dropna(how="all")

    # Forward-fill gaps (weekend/holiday gaps) then compute returns
    portfolio_closes = portfolio_closes.ffill().dropna(how="all")
    daily_returns    = portfolio_closes.pct_change()

    # Equal weight portfolio return — only average across non-NaN columns per day
    port_return = daily_returns.mean(axis=1)

    # Equity curve — fill NaN at start, normalise so it begins at initial_capital
    port_return_filled = port_return.fillna(0)
    equity = (1 + port_return_filled).cumprod() * config.initial_capital
    equity.name = config.strategy_name

    # ── Benchmark curve ───────────────────────────────────────
    bench_curve = pd.Series(dtype=float)
    if benchmark_data is not None and not benchmark_data.empty:
        bench_closes = _extract_close_series(benchmark_data)
        if bench_closes is not None:
            bench_aligned = bench_closes.reindex(equity.index, method="ffill")
            bench_ret = bench_aligned.pct_change().fillna(0)
            bench_curve = (1 + bench_ret).cumprod() * config.initial_capital
            bench_curve = bench_curve.dropna()

    # ── Generate trade log ────────────────────────────────────
    trades = _generate_factor_trades(
        portfolio_closes, top_symbols, rebalance_dates, config
    )

    # ── Compute statistics ────────────────────────────────────
    _fill_stats(result, equity, bench_curve, trades, config)
    return result


# ─────────────────────────────────────────────────────────────
# Indicator-based backtest (uses IndicatorFormula entry signals)
# ─────────────────────────────────────────────────────────────

def run_indicator_backtest(
    price_data: dict[str, pd.DataFrame],
    formula,                                # IndicatorFormula instance
    config: BacktestConfig,
    benchmark_data: Optional[pd.DataFrame] = None,
) -> BacktestResult:
    """
    Indicator-based backtest: enter when IndicatorFormula fires on a symbol,
    exit after hold_days or on stop/take-profit.
    """
    from modules.indicators.indicator_engine import (
        normalise,
        compute_rsi,
        compute_sma,
        compute_ema,
        compute_macd,
        compute_bollinger,
        compute_volume_ratio,
        crossover_above,
        crossover_below,
    )

    result = BacktestResult(
        strategy_name=config.strategy_name,
        config=config,
    )

    closes  = _build_price_matrix(price_data, config)
    if closes is None or closes.empty:
        result.error = "No valid price data."
        return result

    # ── Build daily signal matrix for each symbol ─────────────
    # signal_matrix[date][symbol] = True if entry signal fires
    all_trades = []
    capital    = config.initial_capital
    equity_daily: dict = {}

    for sym in closes.columns:
        df_raw = price_data.get(sym)
        if df_raw is None or df_raw.empty:
            continue

        df = normalise(df_raw)
        if len(df) < 50:
            continue

        # Apply date filter
        if config.start_date:
            df = df[df["date"] >= config.start_date] if "date" in df.columns else df
        if config.end_date:
            df = df[df["date"] <= config.end_date] if "date" in df.columns else df
        if len(df) < 20:
            continue

        # Compute signals
        signals = _compute_entry_signals(df, formula)
        exit_signals = pd.Series(False, index=df.index)  # placeholder

        # Simulate trades
        sym_trades = _simulate_trades(
            df=df,
            entry_signals=signals,
            exit_signals=exit_signals,
            symbol=sym,
            config=config,
        )
        all_trades.extend(sym_trades)

    if not all_trades:
        result.error = "No trades generated. Try relaxing indicator conditions."
        return result

    # ── Build equity curve from trades ────────────────────────
    equity = _trades_to_equity_curve(all_trades, closes.index, config)

    # ── Benchmark ─────────────────────────────────────────────
    bench_curve = pd.Series(dtype=float)
    if benchmark_data is not None and not benchmark_data.empty:
        bench_closes = _extract_close_series(benchmark_data)
        if bench_closes is not None:
            bench_aligned = bench_closes.reindex(equity.index, method="ffill")
            bench_ret = bench_aligned.pct_change().fillna(0)
            bench_curve = (1 + bench_ret).cumprod() * config.initial_capital
            bench_curve = bench_curve.dropna()

    _fill_stats(result, equity, bench_curve, all_trades, config)
    return result


# ─────────────────────────────────────────────────────────────
# Signal computation from IndicatorFormula
# ─────────────────────────────────────────────────────────────

def _compute_entry_signals(df: pd.DataFrame, formula) -> pd.Series:
    """
    Returns boolean Series — True on days when all formula conditions are met.
    Reuses indicator_engine functions for consistency.
    """
    from modules.indicators.indicator_engine import (
        compute_rsi, compute_sma, compute_ema,
        compute_macd, compute_bollinger,
        compute_volume_ratio, crossover_above, crossover_below,
    )

    closes  = df["close"]
    signals = pd.Series(True, index=df.index)  # start all True, AND each condition

    def _and(cond: pd.Series):
        nonlocal signals
        signals = signals & cond.reindex(signals.index).fillna(False)

    if formula.rsi_cross_above is not None:
        rsi   = compute_rsi(closes, formula.rsi_cross_above_period)
        level = pd.Series(formula.rsi_cross_above, index=rsi.index)
        cross = crossover_above(rsi, level)
        # Persist the signal for N days
        cross = cross.rolling(formula.rsi_cross_above_days, min_periods=1).max().astype(bool)
        _and(cross)

    if formula.rsi_cross_below is not None:
        rsi   = compute_rsi(closes, formula.rsi_cross_below_period)
        level = pd.Series(formula.rsi_cross_below, index=rsi.index)
        cross = crossover_below(rsi, level)
        cross = cross.rolling(formula.rsi_cross_below_days, min_periods=1).max().astype(bool)
        _and(cross)

    if formula.rsi_above is not None:
        _and(compute_rsi(closes, 14) > formula.rsi_above)

    if formula.rsi_below is not None:
        _and(compute_rsi(closes, 14) < formula.rsi_below)

    if formula.price_above_sma is not None:
        _and(closes > compute_sma(closes, formula.price_above_sma))

    if formula.price_below_sma is not None:
        _and(closes < compute_sma(closes, formula.price_below_sma))

    if formula.price_above_ema is not None:
        _and(closes > compute_ema(closes, formula.price_above_ema))

    if formula.price_below_ema is not None:
        _and(closes < compute_ema(closes, formula.price_below_ema))

    if formula.sma_cross_above_fast and formula.sma_cross_above_slow:
        fast  = compute_sma(closes, formula.sma_cross_above_fast)
        slow  = compute_sma(closes, formula.sma_cross_above_slow)
        cross = crossover_above(fast, slow)
        cross = cross.rolling(formula.sma_cross_above_days, min_periods=1).max().astype(bool)
        _and(cross)

    if formula.macd_cross_above:
        macd  = compute_macd(closes)
        cross = crossover_above(macd["macd"], macd["macd_signal"])
        cross = cross.rolling(formula.macd_cross_above_days, min_periods=1).max().astype(bool)
        _and(cross)

    if formula.volume_spike is not None and "volume" in df.columns:
        ratio = compute_volume_ratio(df["volume"], formula.volume_spike_period)
        _and(ratio >= formula.volume_spike)

    if formula.high_52w_breakout:
        high_252 = closes.rolling(252, min_periods=50).max()
        _and(closes >= high_252.shift(1))

    if formula.bb_squeeze:
        bb    = compute_bollinger(closes)
        _and(bb["bb_width"] <= formula.bb_squeeze_threshold)

    return signals


# ─────────────────────────────────────────────────────────────
# Trade simulation
# ─────────────────────────────────────────────────────────────

def _simulate_trades(
    df: pd.DataFrame,
    entry_signals: pd.Series,
    exit_signals: pd.Series,
    symbol: str,
    config: BacktestConfig,
) -> list[Trade]:
    trades = []
    closes = df["close"].tolist()
    dates  = df["date"].tolist() if "date" in df.columns else list(range(len(df)))

    in_position    = False
    entry_idx      = None
    entry_price_   = None

    for i in range(len(df)):
        price = closes[i]

        if in_position:
            entry_p = entry_price_
            # Stop loss
            if config.stop_loss_pct > 0 and price <= entry_p * (1 - config.stop_loss_pct / 100):
                _close_trade(trades, symbol, dates, entry_idx, i, entry_p, price, config, "stop_loss")
                in_position = False
                continue
            # Take profit
            if config.take_profit_pct > 0 and price >= entry_p * (1 + config.take_profit_pct / 100):
                _close_trade(trades, symbol, dates, entry_idx, i, entry_p, price, config, "take_profit")
                in_position = False
                continue
            # Hold period
            if config.hold_days > 0 and (i - entry_idx) >= config.hold_days:
                _close_trade(trades, symbol, dates, entry_idx, i, entry_p, price, config, "hold_period")
                in_position = False
                continue
            # Exit signal
            if bool(exit_signals.iloc[i]):
                _close_trade(trades, symbol, dates, entry_idx, i, entry_p, price, config, "signal")
                in_position = False
                continue

        else:
            if bool(entry_signals.iloc[i]):
                in_position  = True
                entry_idx    = i
                entry_price_ = price

    # Close open position at end
    if in_position and entry_idx is not None:
        _close_trade(trades, symbol, dates, entry_idx, len(df) - 1,
                     entry_price_, closes[-1], config, "end")

    return trades


def _close_trade(trades, symbol, dates, entry_idx, exit_idx, entry_price, exit_price, config, reason):
    qty    = (config.initial_capital * config.position_size_pct / 100) / entry_price
    comm   = config.commission_pct / 100
    pnl    = qty * (exit_price - entry_price) * (1 - comm)
    pnl_pct= (exit_price - entry_price) / entry_price * 100 if entry_price else 0

    def _fmt_date(d):
        if isinstance(d, (datetime, pd.Timestamp)):
            return str(d)[:10]
        return str(d)

    trades.append(Trade(
        symbol=symbol,
        entry_date=_fmt_date(dates[entry_idx]),
        exit_date=_fmt_date(dates[min(exit_idx, len(dates)-1)]),
        entry_price=round(entry_price, 2),
        exit_price=round(exit_price, 2),
        qty=round(qty, 4),
        pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2),
        exit_reason=reason,
    ))


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _build_price_matrix(
    price_data: dict,
    config: BacktestConfig,
) -> Optional[pd.DataFrame]:
    frames = {}
    for sym, df in price_data.items():
        if df is None or df.empty:
            continue
        col = "Close" if "Close" in df.columns else "close" if "close" in df.columns else None
        if col is None:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if "Date" in df.columns:
            s.index = pd.to_datetime(df["Date"], errors="coerce")
        elif "date" in df.columns:
            s.index = pd.to_datetime(df["date"], errors="coerce")
        s = s[~s.index.isna()]
        if config.start_date:
            s = s[s.index >= pd.to_datetime(config.start_date)]
        if config.end_date:
            s = s[s.index <= pd.to_datetime(config.end_date)]
        if len(s) >= 20:
            frames[sym] = s

    if not frames:
        return None
    return pd.DataFrame(frames).sort_index()


def _extract_close_series(df: pd.DataFrame) -> Optional[pd.Series]:
    col = "Close" if "Close" in df.columns else "close" if "close" in df.columns else None
    if col is None:
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    idx_col = "Date" if "Date" in df.columns else "date" if "date" in df.columns else None
    if idx_col:
        s.index = pd.to_datetime(df[idx_col], errors="coerce")
        s = s[~s.index.isna()]
    return s


def _rebalance_schedule(index: pd.DatetimeIndex, freq: str) -> list:
    if freq == "daily":
        return list(index)
    elif freq == "weekly":
        return [d for d in index if d.dayofweek == 0]
    else:  # monthly
        return [d for d in index if d == index[index.month == d.month][0]]


def _generate_factor_trades(
    closes: pd.DataFrame,
    symbols: list[str],
    rebalance_dates: list,
    config: BacktestConfig,
) -> list[Trade]:
    """Generate simplified buy-and-hold trades for factor portfolio."""
    trades = []
    if closes.empty or not symbols:
        return trades

    entry_date = str(closes.index[0])[:10]
    exit_date  = str(closes.index[-1])[:10]

    for sym in symbols:
        if sym not in closes.columns:
            continue
        s = closes[sym].dropna()
        if len(s) < 2:
            continue
        entry_p = float(s.iloc[0])
        exit_p  = float(s.iloc[-1])
        qty = (config.initial_capital / len(symbols)) / entry_p if entry_p else 0
        pnl = qty * (exit_p - entry_p)
        pnl_pct = (exit_p - entry_p) / entry_p * 100 if entry_p else 0
        trades.append(Trade(
            symbol=sym,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=round(entry_p, 2),
            exit_price=round(exit_p, 2),
            qty=round(qty, 4),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            exit_reason="end",
        ))
    return trades


def _trades_to_equity_curve(
    trades: list[Trade],
    date_index: pd.DatetimeIndex,
    config: BacktestConfig,
) -> pd.Series:
    """Convert trade list to daily equity curve."""
    capital = config.initial_capital
    daily_pnl = pd.Series(0.0, index=date_index)

    for t in trades:
        try:
            exit_dt = pd.to_datetime(t.exit_date)
            if exit_dt in daily_pnl.index:
                daily_pnl[exit_dt] += t.pnl
        except Exception:
            pass

    equity = (capital + daily_pnl.cumsum())
    return equity


def _fill_stats(
    result: BacktestResult,
    equity: pd.Series,
    bench_curve: pd.Series,
    trades: list[Trade],
    config: BacktestConfig,
):
    """Compute all summary statistics and populate result."""
    result.equity_curve    = equity
    result.benchmark_curve = bench_curve
    result.trades          = trades
    result.total_trades    = len(trades)

    if equity.empty or len(equity) < 2:
        return

    # Returns
    equity_clean = equity.dropna()
    if equity_clean.empty:
        result.error = "Equity curve is all NaN — check price data."
        return
    start_val = float(equity_clean.iloc[0])
    end_val   = float(equity_clean.iloc[-1])
    result.total_return_pct = round((end_val - start_val) / start_val * 100, 2) if start_val else 0.0

    # Annualised return
    n_years = max(len(equity_clean) / 252, 0.01)
    if n_years > 0 and start_val > 0:
        result.annualised_return = round(
            ((end_val / start_val) ** (1 / n_years) - 1) * 100, 2
        )

    # Daily returns
    daily_ret = equity_clean.pct_change().dropna()

    # Sharpe
    if daily_ret.std() > 0:
        result.sharpe_ratio = round(
            float(daily_ret.mean() / daily_ret.std() * np.sqrt(252)), 2
        )

    # Sortino
    downside = daily_ret[daily_ret < 0]
    if len(downside) > 0 and downside.std() > 0:
        result.sortino_ratio = round(
            float(daily_ret.mean() / downside.std() * np.sqrt(252)), 2
        )

    # Max drawdown
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    result.max_drawdown_pct = round(float(drawdown.min()) * 100, 2)

    # Calmar
    if result.max_drawdown_pct < 0 and abs(result.max_drawdown_pct) > 0.001:
        result.calmar_ratio = round(
            result.annualised_return / abs(result.max_drawdown_pct), 2
        )

    # Benchmark stats
    if not bench_curve.empty and len(bench_curve) >= 2:
        b_start = float(bench_curve.iloc[0])
        b_end   = float(bench_curve.iloc[-1])
        result.benchmark_return_pct = round((b_end - b_start) / b_start * 100, 2)

        bench_ret = bench_curve.pct_change().dropna()
        aligned = daily_ret.reindex(bench_ret.index)
        if not aligned.empty and not bench_ret.empty:
            excess = aligned - bench_ret.reindex(aligned.index).fillna(0)
            result.alpha_annualised = round(float(excess.mean() * 252 * 100), 2)

    # Trade stats
    if trades:
        winning = [t for t in trades if t.pnl > 0]
        result.win_rate_pct  = round(len(winning) / len(trades) * 100, 1)
        result.avg_trade_pct = round(
            sum(t.pnl_pct for t in trades) / len(trades), 2
        )
        # Avg hold days
        hold_days_list = []
        for t in trades:
            try:
                entry = pd.to_datetime(t.entry_date)
                exit_ = pd.to_datetime(t.exit_date)
                hold_days_list.append((exit_ - entry).days)
            except Exception:
                pass
        if hold_days_list:
            result.avg_hold_days = round(sum(hold_days_list) / len(hold_days_list), 1)