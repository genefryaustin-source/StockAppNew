"""
modules/indicators/signal_suite.py

App-wide "AI Buy / Sell / Take-Profit" signal overlay for candlestick charts.

Context: you asked to pull in the signal style shown on optitrade.shop (an
AI trend ribbon + buy/sell arrows + multi-level take-profit/stop-loss).
OptiTrade is a paid, closed-source TradingView Pine Script (their own site
calls out "10,000+ lines" of un-published proprietary code) — there's no
public algorithm to read or port, so nothing was copied from them. What's
below is an original, transparent composite indicator built for this app
that produces the *same category* of output (trend ribbon, buy/sell arrows,
TP1-TP4 + SL levels, a "chop filter" that suppresses signals in sideways
markets) using auditable rules instead of a black box:

  1. Trend:      EMA(9) vs EMA(21), filtered by EMA(50) slope
  2. Momentum:   RSI(14) confirmation
  3. Chop filter: current ATR(14) vs its 50-bar average — signals are
                  suppressed when volatility is contracting (sideways/choppy)
  4. Entries:    EMA(9)/EMA(21) crossover, in the direction of the EMA(50)
                  trend, only while the chop filter is open
  5. Exits:      ATR-based multi-level take-profit (TP1-TP4) and a stop-loss,
                  set from price/ATR at the moment each signal fires

None of this is investment advice — it's a rules-based visual overlay.

Public API
----------
compute_signals(df) -> pd.DataFrame        # adds signal columns to OHLCV data
add_signal_overlay(fig, sig_df, row=1, col=1, show_ribbon=True) -> None
signal_toggle(key_prefix) -> bool          # a standard Streamlit checkbox
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

GREEN = "#1D9E75"
RED = "#E24B4A"
TP_COLOR = "#2ECC71"
SL_COLOR = "#FF5555"


# ─────────────────────────────────────────────────────────────
# Column normalization — accept whatever case/naming the caller has
# ─────────────────────────────────────────────────────────────

def _pick(df: pd.DataFrame, *names: str):
    for n in names:
        if n in df.columns:
            return df[n]
    return None


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["x"] = _pick(df, "Date", "date", "timestamps", "Datetime", "datetime")
    out["open"] = _pick(df, "Open", "open")
    out["high"] = _pick(df, "High", "high")
    out["low"] = _pick(df, "Low", "low")
    out["close"] = _pick(df, "Close", "close")
    if out["x"] is None:
        out["x"] = df.index
    if out["open"] is None:
        out["open"] = out["close"]
    if out["high"] is None:
        out["high"] = out["close"]
    if out["low"] is None:
        out["low"] = out["close"]
    return out.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# Indicator math
# ─────────────────────────────────────────────────────────────

def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, min_periods=length).mean()


def compute_signals(
    df: pd.DataFrame,
    fast: int = 9,
    slow: int = 21,
    trend_len: int = 50,
    rsi_len: int = 14,
    atr_len: int = 14,
    tp_atr_multiples: tuple = (1.0, 2.0, 3.0, 4.0),
    sl_atr_multiple: float = 1.5,
    chop_threshold: float = 0.85,
) -> pd.DataFrame:
    """
    Returns a normalized OHLC dataframe (columns x/open/high/low/close) plus:
      ema_fast, ema_slow, ema_trend, rsi, atr, trend ("bull"/"bear"),
      signal ("buy"/"sell"/None), tp1..tp4, sl (levels valid from that bar
      until the next opposite signal).
    """
    n = _normalize(df)
    close = n["close"].astype(float)

    n["ema_fast"] = close.ewm(span=fast, adjust=False).mean()
    n["ema_slow"] = close.ewm(span=slow, adjust=False).mean()
    n["ema_trend"] = close.ewm(span=trend_len, adjust=False).mean()
    n["rsi"] = _rsi(close, rsi_len)
    n["atr"] = _atr(n["high"].astype(float), n["low"].astype(float), close, atr_len)

    atr_avg = n["atr"].rolling(50, min_periods=10).mean()
    chop_open = n["atr"] >= (atr_avg * chop_threshold)

    trend_bull = (n["ema_fast"] > n["ema_slow"]) & (close > n["ema_trend"])
    trend_bear = (n["ema_fast"] < n["ema_slow"]) & (close < n["ema_trend"])
    n["trend"] = np.where(trend_bull, "bull", np.where(trend_bear, "bear", "flat"))

    cross_up = (n["ema_fast"] > n["ema_slow"]) & (n["ema_fast"].shift(1) <= n["ema_slow"].shift(1))
    cross_dn = (n["ema_fast"] < n["ema_slow"]) & (n["ema_fast"].shift(1) >= n["ema_slow"].shift(1))

    buy = cross_up & trend_bull & chop_open & (n["rsi"] > 50)
    sell = cross_dn & trend_bear & chop_open & (n["rsi"] < 50)

    n["signal"] = np.where(buy, "buy", np.where(sell, "sell", None))

    tp_cols = [f"tp{i+1}" for i in range(len(tp_atr_multiples))]
    for c in tp_cols + ["sl"]:
        n[c] = np.nan

    buy_idx = close.loc[buy].index
    n.loc[buy_idx, [f"tp{i+1}" for i in range(len(tp_atr_multiples))]] = np.array([
        close[buy_idx] + m * n.loc[buy_idx, "atr"] for m in tp_atr_multiples
    ]).T
    n.loc[buy_idx, "sl"] = close[buy_idx] - sl_atr_multiple * n.loc[buy_idx, "atr"]

    sell_idx = close.loc[sell].index
    n.loc[sell_idx, [f"tp{i+1}" for i in range(len(tp_atr_multiples))]] = np.array([
        close[sell_idx] - m * n.loc[sell_idx, "atr"] for m in tp_atr_multiples
    ]).T
    n.loc[sell_idx, "sl"] = close[sell_idx] + sl_atr_multiple * n.loc[sell_idx, "atr"]

    return n


# ─────────────────────────────────────────────────────────────
# Plotly overlay
# ─────────────────────────────────────────────────────────────

def add_signal_overlay(fig: go.Figure, sig_df: pd.DataFrame, row: int = 1, col: int = 1, show_ribbon: bool = True) -> None:
    """Adds trend ribbon (EMA fast/slow), buy/sell arrows, and the most
    recent active TP1-TP4/SL levels to an existing candlestick figure."""
    if sig_df is None or sig_df.empty:
        return

    kwargs = dict(row=row, col=col) if (row and col) else {}

    if show_ribbon:
        fig.add_trace(go.Scatter(
            x=sig_df["x"], y=sig_df["ema_fast"],
            line=dict(color="#42A5F5", width=1.1), name="Trend fast (EMA9)",
            hoverinfo="skip",
        ), **kwargs)
        fig.add_trace(go.Scatter(
            x=sig_df["x"], y=sig_df["ema_slow"],
            line=dict(color="#AB47BC", width=1.1), name="Trend slow (EMA21)",
            hoverinfo="skip",
        ), **kwargs)

    buys = sig_df[sig_df["signal"] == "buy"]
    sells = sig_df[sig_df["signal"] == "sell"]

    if not buys.empty:
        fig.add_trace(go.Scatter(
            x=buys["x"], y=buys["low"] * 0.995,
            mode="markers", marker=dict(symbol="triangle-up", size=13, color=GREEN,
                                         line=dict(width=1, color="white")),
            name="BUY",
        ), **kwargs)

    if not sells.empty:
        fig.add_trace(go.Scatter(
            x=sells["x"], y=sells["high"] * 1.005,
            mode="markers", marker=dict(symbol="triangle-down", size=13, color=RED,
                                         line=dict(width=1, color="white")),
            name="SELL",
        ), **kwargs)

    # Most recent active signal's TP/SL levels, drawn across the visible range.
    active = sig_df[sig_df["signal"].notna()]
    if not active.empty:
        last = active.iloc[-1]
        x0, x1 = sig_df["x"].iloc[0], sig_df["x"].iloc[-1]
        for i in range(1, 5):
            level = last.get(f"tp{i}")
            if pd.notna(level):
                fig.add_trace(go.Scatter(
                    x=[x0, x1], y=[level, level],
                    mode="lines", line=dict(color=TP_COLOR, width=1, dash="dot"),
                    name=f"TP{i}: {level:.2f}", hoverinfo="skip",
                ), **kwargs)
        if pd.notna(last.get("sl")):
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[last["sl"], last["sl"]],
                mode="lines", line=dict(color=SL_COLOR, width=1.3, dash="dash"),
                name=f"SL: {last['sl']:.2f}", hoverinfo="skip",
            ), **kwargs)


def signal_toggle(key_prefix: str, default: bool = True) -> bool:
    """Standard checkbox used on every chart page to turn the overlay on/off."""
    return st.checkbox(
        "🎯 Show AI Buy/Sell/TP Signals", value=default, key=f"{key_prefix}_signal_toggle"
    )


def latest_signal_summary(sig_df: pd.DataFrame) -> dict | None:
    """Small helper for a metrics strip: latest signal type, entry, TP1, SL."""
    if sig_df is None or sig_df.empty:
        return None
    active = sig_df[sig_df["signal"].notna()]
    if active.empty:
        return None
    last = active.iloc[-1]
    return {
        "type": last["signal"],
        "entry": float(last["close"]),
        "tp1": float(last["tp1"]) if pd.notna(last["tp1"]) else None,
        "tp4": float(last["tp4"]) if pd.notna(last["tp4"]) else None,
        "sl": float(last["sl"]) if pd.notna(last["sl"]) else None,
        "trend": last["trend"],
    }
