import pandas as pd
import numpy as np

def _rsi(series: pd.Series, period: int = 14) -> float | None:
    if series is None or series.empty or len(series) < period + 2:
        return None
    delta = series.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = (-delta.clip(upper=0)).rolling(period).mean()
    rs = up / down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else None

def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    if series is None or series.empty or len(series) < slow + signal + 5:
        return None, None, None
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return float(macd.iloc[-1]), float(sig.iloc[-1]), float(hist.iloc[-1])

def _support_resistance(close: pd.Series, bins: int = 30) -> dict:
    """
    Simple clustering of prices into zones using histogram bins.
    Returns top 2 support and resistance zones around current price.
    """
    if close is None or close.empty or len(close) < 60:
        return {"support": [], "resistance": []}

    cur = float(close.iloc[-1])
    prices = close.tail(252).values  # ~1y
    hist, edges = np.histogram(prices, bins=bins)

    # bin centers
    centers = (edges[:-1] + edges[1:]) / 2

    # Rank bins by frequency
    idx_sorted = np.argsort(hist)[::-1]
    zones = []
    for i in idx_sorted[:8]:
        zones.append((float(centers[i]), int(hist[i])))

    supports = sorted([z for z in zones if z[0] < cur], key=lambda x: abs(cur - x[0]))[:2]
    resist = sorted([z for z in zones if z[0] > cur], key=lambda x: abs(cur - x[0]))[:2]

    return {
        "support": [{"level": round(s[0], 2), "strength": s[1]} for s in supports],
        "resistance": [{"level": round(r[0], 2), "strength": r[1]} for r in resist],
    }

def technical_summary(px: pd.DataFrame) -> dict:
    if px is None or px.empty or "Close" not in px.columns:
        return {"error": "No price data"}

    close = px["Close"].dropna()
    cur = float(close.iloc[-1])

    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

    rsi14 = _rsi(close, 14)
    macd, macd_sig, macd_hist = _macd(close)

    trend = "Neutral"
    if ma50 and ma200:
        trend = "Bullish" if ma50 > ma200 else "Bearish"
    elif ma50:
        trend = "Bullish (short-term)" if cur > ma50 else "Bearish (short-term)"

    zones = _support_resistance(close)

    # Breakout / breakdown markers
    breakout = None
    breakdown = None
    if zones["resistance"]:
        breakout = zones["resistance"][0]["level"]
    if zones["support"]:
        breakdown = zones["support"][0]["level"]

    momentum = "Neutral"
    if rsi14 is not None:
        if rsi14 >= 60:
            momentum = "Bullish"
        elif rsi14 <= 40:
            momentum = "Bearish"

    return {
        "current_price": round(cur, 2),
        "trend": trend,
        "moving_averages": {"ma20": ma20, "ma50": ma50, "ma200": ma200},
        "momentum": {"rsi14": rsi14, "macd": macd, "macd_signal": macd_sig, "macd_hist": macd_hist, "signal": momentum},
        "support_resistance": zones,
        "possible_breakout_above": breakout,
        "possible_breakdown_below": breakdown,
    }