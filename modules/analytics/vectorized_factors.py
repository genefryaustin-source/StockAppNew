import numpy as np
import pandas as pd


def _safe_last(series: pd.Series):
    if series is None or series.empty:
        return None
    v = series.iloc[-1]
    return None if pd.isna(v) else float(v)


def compute_price_factors(close_df: pd.DataFrame) -> pd.DataFrame:
    """
    close_df:
        index   -> dates
        columns -> symbols
        values  -> close prices

    Returns a dataframe indexed by symbol with:
        momentum_score
        growth_score
        quality_score
        value_score
        risk_score
        rsi_14
        sma_50
        sma_200
        vol_20d
        max_drawdown_1y
        trend
        composite_score
        confidence_score
    """

    if close_df is None or close_df.empty:
        return pd.DataFrame()

    close_df = close_df.sort_index().copy()

    # basic returns
    returns = close_df.pct_change()

    # -----------------------------
    # momentum
    # -----------------------------
    mean_ret = returns.mean(skipna=True)
    std_ret = returns.std(skipna=True)
    momentum = (mean_ret / std_ret.replace(0, np.nan)) * np.sqrt(252)

    # -----------------------------
    # growth
    # -----------------------------
    first_valid = close_df.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else np.nan)
    last_valid = close_df.apply(lambda s: s.dropna().iloc[-1] if not s.dropna().empty else np.nan)
    growth = ((last_valid / first_valid.replace(0, np.nan)) - 1.0) * 100.0

    # -----------------------------
    # quality proxy = low volatility
    # -----------------------------
    quality = 100.0 - (returns.std(skipna=True) * 100.0)
    quality = quality.clip(lower=0)

    # -----------------------------
    # value proxy = discount to SMA200
    # -----------------------------
    sma_200_df = close_df.rolling(200, min_periods=200).mean()
    sma_50_df = close_df.rolling(50, min_periods=50).mean()

    sma_200 = sma_200_df.iloc[-1]
    sma_50 = sma_50_df.iloc[-1]

    latest_price = close_df.iloc[-1]
    value = ((sma_200 - latest_price) / sma_200.replace(0, np.nan)) * 100.0

    # -----------------------------
    # risk
    # -----------------------------
    risk = returns.std(skipna=True) * np.sqrt(252) * 100.0

    # -----------------------------
    # RSI(14)
    # -----------------------------
    delta = close_df.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_df = 100.0 - (100.0 / (1.0 + rs))
    rsi_14 = rsi_df.iloc[-1]

    # -----------------------------
    # vol 20d
    # -----------------------------
    vol_20d = returns.tail(20).std(skipna=True) * np.sqrt(252)

    # -----------------------------
    # max drawdown 1y
    # -----------------------------
    one_year = close_df.tail(252)
    rolling_peak = one_year.cummax()
    drawdowns = (one_year - rolling_peak) / rolling_peak
    max_drawdown_1y = drawdowns.min()

    # -----------------------------
    # trend
    # -----------------------------
    trend = pd.Series(index=close_df.columns, dtype=object)

    bull_mask = (latest_price > sma_50) & (sma_50 > sma_200)
    bear_mask = (latest_price < sma_50) & (sma_50 < sma_200)

    trend.loc[bull_mask] = "Uptrend"
    trend.loc[bear_mask] = "Downtrend"
    trend.loc[~bull_mask & ~bear_mask] = "Range"

    # -----------------------------
    # composite
    # -----------------------------
    composite = (
        quality * 0.30 +
        growth * 0.25 +
        value * 0.20 +
        momentum * 0.25
    )

    composite = composite - (risk * 0.10)

    confidence = pd.Series(70.0, index=close_df.columns)

    out = pd.DataFrame({
        "momentum_score": momentum,
        "growth_score": growth,
        "quality_score": quality,
        "value_score": value,
        "risk_score": risk,
        "rsi_14": rsi_14,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "vol_20d": vol_20d,
        "max_drawdown_1y": max_drawdown_1y,
        "trend": trend,
        "composite_score": composite,
        "confidence_score": confidence,
    })

    out.index.name = "symbol"
    out = out.replace([np.inf, -np.inf], np.nan)

    return out