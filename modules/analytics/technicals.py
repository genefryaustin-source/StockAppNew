# technicals.py in 
import pandas as pd

def _rsi(series: pd.Series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_technicals(db, symbol: str):
    from modules.market_data.service import get_price_history

    sym = symbol.upper()
    df = get_price_history(db, sym, period="1y", interval="1d")
    if df is None or df.empty or len(df) < 60:
        return {
            "trend": None, "rsi_14": None, "sma_50": None, "sma_200": None,
            "support": None, "resistance": None,
        }

    close = df["Close"].astype(float)
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()
    df["RSI14"] = _rsi(close, 14)

    last = df.iloc[-1]
    sma50 = float(last["SMA50"]) if pd.notna(last["SMA50"]) else None
    sma200 = float(last["SMA200"]) if pd.notna(last["SMA200"]) else None
    rsi14 = float(last["RSI14"]) if pd.notna(last["RSI14"]) else None
    last_px = float(last["Close"])

    # Trend regime: deterministic rule
    trend = "Range"
    if sma50 and sma200:
        if last_px > sma50 > sma200:
            trend = "Uptrend"
        elif last_px < sma50 < sma200:
            trend = "Downtrend"

    # Simple support/resistance: 20d rolling lows/highs
    support = float(df["Low"].astype(float).tail(20).min())
    resistance = float(df["High"].astype(float).tail(20).max())

    return {
        "trend": trend,
        "rsi_14": rsi14,
        "sma_50": sma50,
        "sma_200": sma200,
        "support": support,
        "resistance": resistance,
    }