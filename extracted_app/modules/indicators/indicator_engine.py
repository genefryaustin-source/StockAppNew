"""
modules/indicators/indicator_engine.py

Technical indicator computation library.

Computes indicators from raw OHLCV DataFrames:
  - RSI (any period)
  - SMA / EMA (any period)
  - MACD (standard + custom)
  - Bollinger Bands
  - ATR
  - Volume ratio vs N-day average
  - Crossover detection (within N days)
  - Price vs indicator comparisons
  - Lookback window conditions ("in the last N days")

All functions are pure — they take a DataFrame, return values/Series.
No DB access. No Streamlit. Composable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional


# ─────────────────────────────────────────────────────────────
# DataFrame normaliser
# ─────────────────────────────────────────────────────────────

def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, ensure numeric types, sort by date."""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
    return df.dropna(subset=["close"])


# ─────────────────────────────────────────────────────────────
# Core indicators
# ─────────────────────────────────────────────────────────────

def compute_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta  = closes.diff()
    gain   = delta.clip(lower=0)
    loss   = (-delta).clip(lower=0)
    avg_g  = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_l  = loss.ewm(com=period - 1, min_periods=period).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).rename(f"rsi_{period}")


def compute_sma(closes: pd.Series, period: int) -> pd.Series:
    return closes.rolling(period, min_periods=max(1, period // 2)).mean().rename(f"sma_{period}")


def compute_ema(closes: pd.Series, period: int) -> pd.Series:
    return closes.ewm(span=period, adjust=False).mean().rename(f"ema_{period}")


def compute_macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    ema_fast   = compute_ema(closes, fast)
    ema_slow   = compute_ema(closes, slow)
    macd_line  = ema_fast - ema_slow
    signal_line= macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histogram,
    })


def compute_bollinger(
    closes: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    mid  = compute_sma(closes, period)
    std  = closes.rolling(period, min_periods=period // 2).std()
    return pd.DataFrame({
        "bb_upper": mid + std_dev * std,
        "bb_mid":   mid,
        "bb_lower": mid - std_dev * std,
        "bb_width": (2 * std_dev * std) / mid.replace(0, np.nan),
    })


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h = df["high"]
    l = df["low"]
    c = df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean().rename(f"atr_{period}")


def compute_volume_ratio(volumes: pd.Series, period: int = 20) -> pd.Series:
    avg = volumes.rolling(period, min_periods=max(1, period // 2)).mean()
    return (volumes / avg.replace(0, np.nan)).rename(f"vol_ratio_{period}")


def compute_stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
) -> pd.DataFrame:
    low_min  = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    denom    = (high_max - low_min).replace(0, np.nan)
    k = 100 * (df["close"] - low_min) / denom
    d = k.rolling(d_period).mean()
    return pd.DataFrame({"stoch_k": k, "stoch_d": d})


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Intraday VWAP — cumulative. For daily bars gives cumulative VWAP."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vol     = df["volume"].replace(0, np.nan)
    cum_pv  = (typical * vol).cumsum()
    cum_v   = vol.cumsum()
    return (cum_pv / cum_v).rename("vwap")


# ─────────────────────────────────────────────────────────────
# Crossover detection
# ─────────────────────────────────────────────────────────────

def crossover_above(
    series_a: pd.Series,
    series_b: pd.Series,
) -> pd.Series:
    """
    Returns boolean Series: True on bars where A crossed above B.
    (A[i-1] <= B[i-1]) and (A[i] > B[i])
    """
    prev_a = series_a.shift(1)
    prev_b = series_b.shift(1)
    return ((prev_a <= prev_b) & (series_a > series_b)).rename("cross_above")


def crossover_below(
    series_a: pd.Series,
    series_b: pd.Series,
) -> pd.Series:
    """True on bars where A crossed below B."""
    prev_a = series_a.shift(1)
    prev_b = series_b.shift(1)
    return ((prev_a >= prev_b) & (series_a < series_b)).rename("cross_below")


def crossed_within(
    cross_series: pd.Series,
    lookback_days: int,
) -> bool:
    """
    Returns True if a crossover occurred in the last N bars.
    cross_series is a boolean Series from crossover_above/below.
    """
    if cross_series.empty:
        return False
    recent = cross_series.tail(lookback_days)
    return bool(recent.any())


# ─────────────────────────────────────────────────────────────
# High-level condition evaluators
# ─────────────────────────────────────────────────────────────

def eval_rsi_cross_above(
    df: pd.DataFrame,
    level: float,
    rsi_period: int = 14,
    lookback_days: int = 3,
) -> tuple[bool, str]:
    """RSI crossed above `level` within `lookback_days`."""
    rsi    = compute_rsi(df["close"], rsi_period)
    level_s= pd.Series(level, index=rsi.index)
    cross  = crossover_above(rsi, level_s)
    fired  = crossed_within(cross, lookback_days)
    last   = rsi.iloc[-1] if not rsi.empty else None
    reason = (
        f"RSI({rsi_period}) crossed above {level} in last {lookback_days}d "
        f"(current RSI={last:.1f})"
        if fired else
        f"RSI({rsi_period})={last:.1f if last else 'N/A'}, no cross above {level} in last {lookback_days}d"
    )
    return fired, reason


def eval_rsi_cross_below(
    df: pd.DataFrame,
    level: float,
    rsi_period: int = 14,
    lookback_days: int = 3,
) -> tuple[bool, str]:
    """RSI crossed below `level` within `lookback_days`."""
    rsi    = compute_rsi(df["close"], rsi_period)
    level_s= pd.Series(level, index=rsi.index)
    cross  = crossover_below(rsi, level_s)
    fired  = crossed_within(cross, lookback_days)
    last   = rsi.iloc[-1] if not rsi.empty else None
    reason = (
        f"RSI({rsi_period}) crossed below {level} in last {lookback_days}d "
        f"(current={last:.1f})"
        if fired else
        f"RSI({rsi_period})={last:.1f if last else 'N/A'}, no cross below {level} in last {lookback_days}d"
    )
    return fired, reason


def eval_price_above_sma(
    df: pd.DataFrame,
    sma_period: int,
) -> tuple[bool, str]:
    """Price is currently above SMA(period)."""
    sma  = compute_sma(df["close"], sma_period)
    last = df["close"].iloc[-1]
    sma_v= sma.iloc[-1]
    fired= last > sma_v if pd.notna(sma_v) else False
    return fired, f"Price ${last:.2f} {'>' if fired else '<='} SMA{sma_period} ${sma_v:.2f}"


def eval_price_below_sma(
    df: pd.DataFrame,
    sma_period: int,
) -> tuple[bool, str]:
    sma  = compute_sma(df["close"], sma_period)
    last = df["close"].iloc[-1]
    sma_v= sma.iloc[-1]
    fired= last < sma_v if pd.notna(sma_v) else False
    return fired, f"Price ${last:.2f} {'<' if fired else '>='} SMA{sma_period} ${sma_v:.2f}"


def eval_sma_cross_above(
    df: pd.DataFrame,
    fast_period: int,
    slow_period: int,
    lookback_days: int = 5,
) -> tuple[bool, str]:
    """Fast SMA crossed above slow SMA within lookback_days (golden cross)."""
    fast  = compute_sma(df["close"], fast_period)
    slow  = compute_sma(df["close"], slow_period)
    cross = crossover_above(fast, slow)
    fired = crossed_within(cross, lookback_days)
    return fired, (
        f"SMA{fast_period} crossed above SMA{slow_period} in last {lookback_days}d"
        if fired else
        f"No SMA{fast_period}/SMA{slow_period} golden cross in last {lookback_days}d"
    )


def eval_macd_cross_above(
    df: pd.DataFrame,
    lookback_days: int = 3,
) -> tuple[bool, str]:
    """MACD line crossed above signal line within lookback_days."""
    macd  = compute_macd(df["close"])
    cross = crossover_above(macd["macd"], macd["macd_signal"])
    fired = crossed_within(cross, lookback_days)
    last_hist = macd["macd_hist"].iloc[-1]
    return fired, (
        f"MACD crossed above signal in last {lookback_days}d (hist={last_hist:.3f})"
        if fired else
        f"No MACD bullish cross in last {lookback_days}d (hist={last_hist:.3f})"
    )


def eval_price_near_support(
    df: pd.DataFrame,
    support: float,
    tolerance_pct: float = 2.0,
) -> tuple[bool, str]:
    last   = df["close"].iloc[-1]
    pct    = abs(last - support) / support * 100
    fired  = pct <= tolerance_pct
    return fired, f"Price ${last:.2f} within {pct:.1f}% of support ${support:.2f}"


def eval_volume_spike(
    df: pd.DataFrame,
    multiplier: float = 2.0,
    avg_period: int = 20,
) -> tuple[bool, str]:
    if "volume" not in df.columns:
        return False, "No volume data"
    ratio = compute_volume_ratio(df["volume"], avg_period)
    last  = ratio.iloc[-1]
    fired = last >= multiplier if pd.notna(last) else False
    return fired, f"Volume {last:.1f}x {avg_period}d avg {'✓' if fired else '✗'} (need {multiplier:.1f}x)"


def eval_bb_squeeze(
    df: pd.DataFrame,
    width_threshold: float = 0.05,
) -> tuple[bool, str]:
    """Bollinger Band width below threshold — squeeze condition."""
    bb    = compute_bollinger(df["close"])
    width = bb["bb_width"].iloc[-1]
    fired = width <= width_threshold if pd.notna(width) else False
    return fired, f"BB width {width:.3f} {'<=' if fired else '>'} {width_threshold:.3f}"


def eval_price_above_bb_upper(df: pd.DataFrame) -> tuple[bool, str]:
    bb   = compute_bollinger(df["close"])
    last = df["close"].iloc[-1]
    ub   = bb["bb_upper"].iloc[-1]
    fired= last > ub if pd.notna(ub) else False
    return fired, f"Price ${last:.2f} {'above' if fired else 'below'} BB upper ${ub:.2f}"


def eval_52w_high_breakout(
    df: pd.DataFrame,
    lookback_days: int = 3,
) -> tuple[bool, str]:
    """Price made a new 52-week high within lookback_days."""
    closes   = df["close"]
    high_252 = closes.rolling(252, min_periods=50).max()
    new_high = closes >= high_252
    fired    = bool(new_high.tail(lookback_days).any())
    last     = closes.iloc[-1]
    h52      = high_252.iloc[-1]
    return fired, (
        f"New 52w high ${last:.2f} (prev high ${h52:.2f}) in last {lookback_days}d"
        if fired else
        f"No 52w high breakout in last {lookback_days}d (current ${last:.2f}, 52w high ${h52:.2f})"
    )


def eval_higher_highs(
    df: pd.DataFrame,
    lookback_days: int = 5,
    count: int = 3,
) -> tuple[bool, str]:
    """N consecutive higher highs within lookback_days."""
    highs  = df["high"].tail(lookback_days + count)
    consec = 0
    for i in range(1, len(highs)):
        if highs.iloc[i] > highs.iloc[i - 1]:
            consec += 1
        else:
            consec = 0
    fired = consec >= count
    return fired, f"{consec} consecutive higher highs (need {count})"