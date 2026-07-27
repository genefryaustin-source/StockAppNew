"""
modules/smc/smc_engine.py

Smart Money Concepts (SMC) analysis engine.
Computes all signals from raw OHLCV price data — no external API needed.

Signals computed:
  - Order Blocks (OB)      : Institutional supply/demand zones
  - Fair Value Gaps (FVG)  : Price imbalance zones
  - BOS / CHoCH            : Break of Structure / Change of Character
  - Trend                  : HTF bias (Bullish / Bearish / Ranging)
  - Momentum               : Oscillator value + signal

Usage:
    from modules.smc.smc_engine import analyse
    result = analyse(ohlcv_df)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────

@dataclass
class OrderBlock:
    index: int          # bar index
    date: str
    top: float
    bottom: float
    kind: Literal["bullish", "bearish"]
    mitigated: bool = False
    strength: float = 1.0   # 0–1 relative volume score


@dataclass
class FairValueGap:
    index: int
    date: str
    top: float
    bottom: float
    kind: Literal["bullish", "bearish"]
    filled: bool = False


@dataclass
class StructurePoint:
    index: int
    date: str
    price: float
    kind: Literal["BOS_bull", "BOS_bear", "CHoCH_bull", "CHoCH_bear"]


@dataclass
class SMCResult:
    order_blocks: list[OrderBlock]
    fvgs: list[FairValueGap]
    structure: list[StructurePoint]
    trend: Literal["Bullish", "Bearish", "Ranging"]
    trend_strength: float           # 0–1
    momentum: list[float]           # one value per bar
    momentum_signal: list[float]    # smoothed signal line
    swing_highs: list[tuple]        # (index, price)
    swing_lows: list[tuple]         # (index, price)
    dashboard: dict                 # summary for the dashboard panel


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────

def analyse(
    df: pd.DataFrame,
    ob_lookback: int = 10,
    swing_length: int = 5,
    fvg_min_gap_pct: float = 0.001,
) -> SMCResult:
    """
    Run full SMC analysis on an OHLCV DataFrame.

    Expected columns (case-insensitive): open, high, low, close, volume
    Returns an SMCResult with all computed signals.
    """
    df = _normalise(df)
    if len(df) < 20:
        return _empty_result()

    opens  = df["open"].values.astype(float)
    highs  = df["high"].values.astype(float)
    lows   = df["low"].values.astype(float)
    closes = df["close"].values.astype(float)
    vols   = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(df))
    dates  = [str(d)[:10] for d in df["date"]] if "date" in df.columns else [str(i) for i in range(len(df))]

    swing_highs, swing_lows = _find_swings(highs, lows, swing_length)
    structure               = _find_structure(swing_highs, swing_lows, highs, lows, dates)
    trend, trend_strength   = _determine_trend(swing_highs, swing_lows, closes)
    order_blocks            = _find_order_blocks(opens, highs, lows, closes, vols, dates, ob_lookback, closes[-1])
    fvgs                    = _find_fvgs(opens, highs, lows, closes, dates, fvg_min_gap_pct, closes[-1])
    momentum, mom_signal    = _compute_momentum(closes)

    dashboard = _build_dashboard(
        order_blocks, fvgs, structure, trend, trend_strength,
        momentum, swing_highs, swing_lows, closes[-1]
    )

    return SMCResult(
        order_blocks=order_blocks,
        fvgs=fvgs,
        structure=structure,
        trend=trend,
        trend_strength=trend_strength,
        momentum=momentum.tolist(),
        momentum_signal=mom_signal.tolist(),
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        dashboard=dashboard,
    )


# ─────────────────────────────────────────────────────────────
# Swing detection
# ─────────────────────────────────────────────────────────────

def _find_swings(highs, lows, length=5):
    swing_highs, swing_lows = [], []
    n = len(highs)
    for i in range(length, n - length):
        if all(highs[i] >= highs[i-j] for j in range(1, length+1)) and \
           all(highs[i] >= highs[i+j] for j in range(1, length+1)):
            swing_highs.append((i, highs[i]))
        if all(lows[i] <= lows[i-j] for j in range(1, length+1)) and \
           all(lows[i] <= lows[i+j] for j in range(1, length+1)):
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


# ─────────────────────────────────────────────────────────────
# Structure: BOS / CHoCH
# ─────────────────────────────────────────────────────────────

def _find_structure(swing_highs, swing_lows, highs, lows, dates):
    points = []
    sh = swing_highs[-6:] if len(swing_highs) >= 6 else swing_highs
    sl = swing_lows[-6:]  if len(swing_lows)  >= 6 else swing_lows

    # BOS Bullish: price breaks above previous swing high
    for k in range(1, len(sh)):
        prev_idx, prev_hi = sh[k-1]
        curr_idx, curr_hi = sh[k]
        if curr_hi > prev_hi:
            points.append(StructurePoint(
                index=curr_idx, date=dates[curr_idx],
                price=curr_hi, kind="BOS_bull"
            ))
        elif curr_hi < prev_hi:
            points.append(StructurePoint(
                index=curr_idx, date=dates[curr_idx],
                price=curr_hi, kind="CHoCH_bear"
            ))

    # BOS Bearish: price breaks below previous swing low
    for k in range(1, len(sl)):
        prev_idx, prev_lo = sl[k-1]
        curr_idx, curr_lo = sl[k]
        if curr_lo < prev_lo:
            points.append(StructurePoint(
                index=curr_idx, date=dates[curr_idx],
                price=curr_lo, kind="BOS_bear"
            ))
        elif curr_lo > prev_lo:
            points.append(StructurePoint(
                index=curr_idx, date=dates[curr_idx],
                price=curr_lo, kind="CHoCH_bull"
            ))

    return sorted(points, key=lambda p: p.index)


# ─────────────────────────────────────────────────────────────
# Trend determination
# ─────────────────────────────────────────────────────────────

def _determine_trend(swing_highs, swing_lows, closes):
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "Ranging", 0.3

    # Higher highs + higher lows = bullish
    hh = swing_highs[-1][1] > swing_highs[-2][1]
    hl = swing_lows[-1][1]  > swing_lows[-2][1]
    lh = swing_highs[-1][1] < swing_highs[-2][1]
    ll = swing_lows[-1][1]  < swing_lows[-2][1]

    # EMA trend confirmation
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    ema_bull = ema20[-1] > ema50[-1]

    if hh and hl and ema_bull:
        strength = min(1.0, 0.6 + 0.2 * (hh + hl))
        return "Bullish", round(strength, 2)
    elif lh and ll and not ema_bull:
        strength = min(1.0, 0.6 + 0.2 * (lh + ll))
        return "Bearish", round(strength, 2)
    else:
        return "Ranging", 0.35


# ─────────────────────────────────────────────────────────────
# Order Blocks
# ─────────────────────────────────────────────────────────────

def _find_order_blocks(opens, highs, lows, closes, vols, dates, lookback, last_price):
    obs = []
    n = len(closes)
    avg_vol = np.mean(vols) if vols.sum() > 0 else 1.0

    for i in range(lookback, n - 3):
        # Bullish OB: bearish candle followed by strong bullish move
        if closes[i] < opens[i]:  # bearish candle
            # Check if next candles move up strongly
            future_high = max(highs[i+1:min(i+4, n)])
            if future_high > highs[i] * 1.005:
                top    = max(opens[i], closes[i])
                bottom = min(opens[i], closes[i])
                mitigated = last_price < bottom or last_price > top * 1.02
                strength = min(1.0, vols[i] / avg_vol * 0.5)
                obs.append(OrderBlock(
                    index=i, date=dates[i],
                    top=round(top, 2), bottom=round(bottom, 2),
                    kind="bullish", mitigated=mitigated, strength=round(strength, 2)
                ))

        # Bearish OB: bullish candle followed by strong bearish move
        if closes[i] > opens[i]:  # bullish candle
            future_low = min(lows[i+1:min(i+4, n)])
            if future_low < lows[i] * 0.995:
                top    = max(opens[i], closes[i])
                bottom = min(opens[i], closes[i])
                mitigated = last_price > top or last_price < bottom * 0.98
                strength = min(1.0, vols[i] / avg_vol * 0.5)
                obs.append(OrderBlock(
                    index=i, date=dates[i],
                    top=round(top, 2), bottom=round(bottom, 2),
                    kind="bearish", mitigated=mitigated, strength=round(strength, 2)
                ))

    # Keep most recent, strongest, unmitigated ones
    active = [o for o in obs if not o.mitigated]
    active.sort(key=lambda o: o.index, reverse=True)
    return active[:8]


# ─────────────────────────────────────────────────────────────
# Fair Value Gaps
# ─────────────────────────────────────────────────────────────

def _find_fvgs(opens, highs, lows, closes, dates, min_gap_pct, last_price):
    fvgs = []
    n = len(closes)
    for i in range(1, n - 1):
        # Bullish FVG: gap between candle[i-1] high and candle[i+1] low
        if lows[i+1] > highs[i-1]:
            gap_pct = (lows[i+1] - highs[i-1]) / highs[i-1]
            if gap_pct >= min_gap_pct:
                top    = lows[i+1]
                bottom = highs[i-1]
                filled = last_price <= bottom
                fvgs.append(FairValueGap(
                    index=i, date=dates[i],
                    top=round(top, 2), bottom=round(bottom, 2),
                    kind="bullish", filled=filled
                ))

        # Bearish FVG: gap between candle[i-1] low and candle[i+1] high
        if highs[i+1] < lows[i-1]:
            gap_pct = (lows[i-1] - highs[i+1]) / lows[i-1]
            if gap_pct >= min_gap_pct:
                top    = lows[i-1]
                bottom = highs[i+1]
                filled = last_price >= top
                fvgs.append(FairValueGap(
                    index=i, date=dates[i],
                    top=round(top, 2), bottom=round(bottom, 2),
                    kind="bearish", filled=filled
                ))

    active = [f for f in fvgs if not f.filled]
    active.sort(key=lambda f: f.index, reverse=True)
    return active[:6]


# ─────────────────────────────────────────────────────────────
# Momentum oscillator (custom — similar to RSI + MACD hybrid)
# ─────────────────────────────────────────────────────────────

def _compute_momentum(closes):
    n = len(closes)
    # RSI component
    rsi = _rsi(closes, 14)
    # Normalise RSI to -1..+1
    norm_rsi = (rsi - 50) / 50

    # Rate of change component (10-period)
    roc = np.zeros(n)
    for i in range(10, n):
        roc[i] = (closes[i] - closes[i-10]) / closes[i-10]

    # Combine
    momentum = (norm_rsi * 0.6 + np.clip(roc * 5, -1, 1) * 0.4)
    signal   = _ema(momentum, 9)
    return momentum, signal


# ─────────────────────────────────────────────────────────────
# Dashboard summary
# ─────────────────────────────────────────────────────────────

def _build_dashboard(obs, fvgs, structure, trend, trend_strength, momentum, sh, sl, last_price):
    active_obs  = [o for o in obs if not o.mitigated]
    active_fvgs = [f for f in fvgs if not f.filled]

    # Nearest OB above and below price
    ob_above = [o for o in active_obs if o.bottom > last_price]
    ob_below = [o for o in active_obs if o.top < last_price]
    nearest_resistance = min(ob_above, key=lambda o: o.bottom).bottom if ob_above else None
    nearest_support    = max(ob_below, key=lambda o: o.top).top       if ob_below else None

    # Last structure event
    last_struct = structure[-1].kind if structure else "None"

    # Momentum reading
    mom_val = float(momentum[-1]) if len(momentum) else 0.0
    mom_label = "Overbought" if mom_val > 0.6 else "Oversold" if mom_val < -0.6 else \
                "Bullish"    if mom_val > 0.1 else "Bearish"  if mom_val < -0.1 else "Neutral"

    # Sweep detection (price swept a recent swing)
    swept = False
    if sh and last_price > sh[-1][1] * 1.001:
        swept = True
    if sl and last_price < sl[-1][1] * 0.999:
        swept = True

    return {
        "trend":             trend,
        "trend_strength":    trend_strength,
        "active_obs":        len(active_obs),
        "active_fvgs":       len(active_fvgs),
        "last_structure":    last_struct,
        "nearest_support":   nearest_support,
        "nearest_resistance": nearest_resistance,
        "momentum_value":    round(mom_val, 3),
        "momentum_label":    mom_label,
        "liquidity_swept":   swept,
    }


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {}
    for col in df.columns:
        lc = col.lower()
        if lc in ("open","high","low","close","volume","date"):
            rename[col] = lc
    df = df.rename(columns=rename)
    for col in ("open","high","low","close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df.reset_index(drop=True)
    return df


def _ema(arr, period):
    arr = np.asarray(arr, dtype=float)
    k = 2 / (period + 1)
    ema = np.zeros_like(arr)
    ema[0] = arr[0]
    for i in range(1, len(arr)):
        ema[i] = arr[i] * k + ema[i-1] * (1 - k)
    return ema


def _rsi(closes, period=14):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    rsi = np.full(n, 50.0)
    gains = np.maximum(np.diff(closes), 0)
    losses = np.abs(np.minimum(np.diff(closes), 0))
    if len(gains) < period:
        return rsi
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi[i + 1] = 100 - (100 / (1 + rs))
    return rsi


def _empty_result():
    return SMCResult(
        order_blocks=[], fvgs=[], structure=[],
        trend="Ranging", trend_strength=0.0,
        momentum=[], momentum_signal=[],
        swing_highs=[], swing_lows=[],
        dashboard={
            "trend": "Ranging", "trend_strength": 0.0,
            "active_obs": 0, "active_fvgs": 0,
            "last_structure": "None",
            "nearest_support": None, "nearest_resistance": None,
            "momentum_value": 0.0, "momentum_label": "Neutral",
            "liquidity_swept": False,
        }
    )
