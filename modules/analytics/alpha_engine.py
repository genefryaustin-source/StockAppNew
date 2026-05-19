import pandas as pd
import numpy as np


# =====================================================
# EXISTING FUNCTIONS (PRESERVED)
# =====================================================

def momentum_score(prices):
    returns = prices.pct_change().dropna()

    if returns.empty:
        return 0.0

    std = returns.std()
    if std is None or pd.isna(std) or std == 0:
        return 0.0

    score = returns.mean() / std
    return float(score)


def volatility_score(prices):
    returns = prices.pct_change().dropna()

    if returns.empty:
        return 0.0

    vol = returns.std()
    return float(vol) if pd.notna(vol) else 0.0


def compute_alpha_rank(price_data, sector_map=None):

    import pandas as pd
    import numpy as np

    rows = []

    for ticker, series in price_data.items():

        try:
            series = pd.to_numeric(series, errors="coerce").dropna()

            if len(series) < 50:
                continue

            returns = series.pct_change().dropna()

            # -----------------------------------
            # FACTORS
            # -----------------------------------
            momentum = returns.mean() / (returns.std() + 1e-9)
            volatility = returns.std()

            # Trend (50 vs 200 SMA)
            sma50 = series.rolling(50).mean().iloc[-1]
            sma200 = series.rolling(200).mean().iloc[-1] if len(series) >= 200 else sma50

            trend = (sma50 - sma200) / (sma200 + 1e-9)

            # Max drawdown (risk)
            rolling_max = series.cummax()
            drawdown = ((series / rolling_max) - 1).min()

            rows.append({
                "Ticker": ticker,
                "Momentum": momentum,
                "Volatility": volatility,
                "Trend": trend,
                "Drawdown": drawdown,
                "sector": sector_map.get(ticker) if sector_map else "Unknown"
            })

        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # -----------------------------------
    # NORMALIZATION (Z-SCORES)
    # -----------------------------------
    def zscore(col):
        return (col - col.mean()) / (col.std() + 1e-9)

    df["momentum_z"] = zscore(df["Momentum"])
    df["vol_z"] = zscore(df["Volatility"])
    df["trend_z"] = zscore(df["Trend"])
    df["drawdown_z"] = zscore(df["Drawdown"])

    # -----------------------------------
    # MULTI-FACTOR ALPHA
    # -----------------------------------
    df["alpha_score_raw"] = (
        df["momentum_z"] * 0.4 +
        df["trend_z"] * 0.3 -
        df["vol_z"] * 0.2 +
        df["drawdown_z"] * 0.1
    )

    # -----------------------------------
    # SECTOR-NEUTRAL ADJUSTMENT
    # -----------------------------------
    if "sector" in df.columns:
        df["alpha_score"] = df.groupby("sector")["alpha_score_raw"].transform(
            lambda x: x - x.mean()
        )
    else:
        df["alpha_score"] = df["alpha_score_raw"]

    # -----------------------------------
    # PERCENTILE RANK
    # -----------------------------------
    df["alpha_percentile"] = df["alpha_score"].rank(pct=True) * 100

    # -----------------------------------
    # PORTFOLIO WEIGHTS
    # -----------------------------------
    df["weight"] = df["alpha_percentile"] / df["alpha_percentile"].sum()

    # cap concentration
    df["weight"] = df["weight"].clip(upper=0.10)
    df["weight"] = df["weight"] / df["weight"].sum()

    # -----------------------------------
    # SORT
    # -----------------------------------
    df = df.sort_values("alpha_score", ascending=False)

    print(f"Alpha computed: {len(df)} symbols")

    return df
# =====================================================
# NEW HELPERS
# =====================================================

def _safe_num(series):
    return pd.to_numeric(series, errors="coerce")


def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _clip_series(series, lo=-3.0, hi=3.0):
    return series.clip(lower=lo, upper=hi)


def _zscore(series):
    s = _safe_num(series)
    valid = s.dropna()

    if valid.empty:
        return pd.Series([0.0] * len(s), index=s.index, dtype="float64")

    std = valid.std(ddof=0)

    if std is None or pd.isna(std) or std == 0:
        return pd.Series([0.0] * len(s), index=s.index, dtype="float64")

    out = (s - valid.mean()) / std
    return out.fillna(0.0)


def _sector_neutral_zscores(df, col, higher_is_better=True):
    out = pd.Series(index=df.index, dtype="float64")

    if col not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index, dtype="float64")

    grouped = df.groupby(df["sector"].fillna("Unknown"))

    for _, g in grouped:
        z = _zscore(g[col])
        z = _clip_series(z)

        if not higher_is_better:
            z = -z

        out.loc[g.index] = z

    return out.fillna(0.0)


def _global_zscores(df, col, higher_is_better=True):
    if col not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index, dtype="float64")

    z = _clip_series(_zscore(df[col]))

    if not higher_is_better:
        z = -z

    return z.fillna(0.0)


def _percentile(series):
    s = _safe_num(series)
    if s.dropna().empty:
        return pd.Series([None] * len(s), index=s.index, dtype="float64")
    return (s.rank(method="average", pct=True) * 100.0).round(2)


# =====================================================
# NEW MAIN ENGINE
# =====================================================

def compute_sector_neutral_alpha(
    rank_df: pd.DataFrame,
    *,
    use_sector_neutral: bool = True,
    quality_weight: float = 0.30,
    growth_weight: float = 0.20,
    value_weight: float = 0.25,
    momentum_weight: float = 0.20,
    risk_weight: float = 0.05,
    confidence_boost: bool = True,
) -> pd.DataFrame:
    """
    Institutional-grade alpha model using sector-neutral factor normalization.

    Expected input columns:
      symbol, sector, rating,
      quality_score, growth_score, value_score, momentum_score, risk_score,
      confidence_score, composite_score

    Returns a dataframe with:
      alpha_rank, alpha_score, alpha_percentile,
      factor z-scores, top-decile flags, divergence metrics
    """

    if rank_df is None or rank_df.empty:
        return pd.DataFrame()

    df = rank_df.copy()

    required_defaults = {
        "symbol": None,
        "sector": "Unknown",
        "rating": None,
        "quality_score": 0.0,
        "growth_score": 0.0,
        "value_score": 0.0,
        "momentum_score": 0.0,
        "risk_score": 0.0,
        "confidence_score": 0.0,
        "composite_score": 0.0,
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    # normalize numeric columns
    for col in [
        "quality_score",
        "growth_score",
        "value_score",
        "momentum_score",
        "risk_score",
        "confidence_score",
        "composite_score",
    ]:
        df[col] = _safe_num(df[col])

    # -------------------------------------------------
    # FACTOR NORMALIZATION
    # -------------------------------------------------
    if use_sector_neutral:
        df["quality_z"] = _sector_neutral_zscores(df, "quality_score", higher_is_better=True)
        df["growth_z"] = _sector_neutral_zscores(df, "growth_score", higher_is_better=True)
        df["value_z"] = _sector_neutral_zscores(df, "value_score", higher_is_better=True)
        df["momentum_z"] = _sector_neutral_zscores(df, "momentum_score", higher_is_better=True)
        df["risk_z"] = _sector_neutral_zscores(df, "risk_score", higher_is_better=False)
    else:
        df["quality_z"] = _global_zscores(df, "quality_score", higher_is_better=True)
        df["growth_z"] = _global_zscores(df, "growth_score", higher_is_better=True)
        df["value_z"] = _global_zscores(df, "value_score", higher_is_better=True)
        df["momentum_z"] = _global_zscores(df, "momentum_score", higher_is_better=True)
        df["risk_z"] = _global_zscores(df, "risk_score", higher_is_better=False)

    # -------------------------------------------------
    # RAW ALPHA
    # -------------------------------------------------
    df["alpha_raw"] = (
        df["quality_z"] * quality_weight
        + df["growth_z"] * growth_weight
        + df["value_z"] * value_weight
        + df["momentum_z"] * momentum_weight
        + df["risk_z"] * risk_weight
    )

    # -------------------------------------------------
    # PERCENTILE + SCORE
    # -------------------------------------------------
    df["alpha_percentile"] = _percentile(df["alpha_raw"])

    if confidence_boost:
        conf = df["confidence_score"].fillna(0.0)
        # 70 confidence -> 0.85 multiplier, 100 -> 1.0
        multiplier = 0.5 + (conf / 200.0)
        df["alpha_score"] = (df["alpha_percentile"] * multiplier).round(2)
    else:
        df["alpha_score"] = df["alpha_percentile"]

    # -------------------------------------------------
    # FLAGS
    # -------------------------------------------------
    df["alpha_top_decile"] = df["alpha_percentile"].apply(
        lambda x: bool(pd.notna(x) and x >= 90)
    )
    df["alpha_top_quartile"] = df["alpha_percentile"].apply(
        lambda x: bool(pd.notna(x) and x >= 75)
    )

    # -------------------------------------------------
    # DIVERGENCE VS PERCENTILE / COMPOSITE
    # -------------------------------------------------
    if "percentile_composite" in df.columns:
        df["alpha_minus_percentile"] = (
            _safe_num(df["alpha_percentile"]) - _safe_num(df["percentile_composite"])
        ).round(2)
    else:
        df["alpha_minus_percentile"] = None

    if "composite_pct_raw" in df.columns:
        df["alpha_minus_composite_pct"] = (
            _safe_num(df["alpha_percentile"]) - _safe_num(df["composite_pct_raw"])
        ).round(2)
    else:
        df["alpha_minus_composite_pct"] = None

    # -------------------------------------------------
    # SORT + RANK
    # -------------------------------------------------
    df = df.sort_values(
        by=["alpha_score", "alpha_percentile", "confidence_score", "composite_score"],
        ascending=[False, False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    df["alpha_rank"] = range(1, len(df) + 1)

    preferred = [
        "alpha_rank",
        "symbol",
        "sector",
        "rating",
        "alpha_score",
        "alpha_percentile",
        "alpha_top_decile",
        "alpha_top_quartile",
        "alpha_minus_percentile",
        "alpha_minus_composite_pct",
        "quality_z",
        "growth_z",
        "value_z",
        "momentum_z",
        "risk_z",
        "confidence_score",
        "composite_score",
        "quality_score",
        "growth_score",
        "value_score",
        "momentum_score",
        "risk_score",
    ]

    existing = [c for c in preferred if c in df.columns]
    return df[existing]

def build_top_opportunities(alpha_df, top_n=10):

    if alpha_df is None or alpha_df.empty:
        return {}

    df = alpha_df.copy()

    # Safety
    for col in ["alpha_score", "alpha_percentile", "alpha_minus_percentile",
                "momentum_z", "quality_z", "risk_z"]:
        if col not in df.columns:
            df[col] = None

    # -------------------------------------------------
    # 🟢 1. UNDERVALUED (BEST SIGNAL)
    # -------------------------------------------------
    undervalued = df[
        (df["alpha_percentile"] >= 80) &
        (df["alpha_minus_percentile"] > 10)
    ].sort_values(
        by="alpha_score", ascending=False
    ).head(top_n)

    # -------------------------------------------------
    # 🔵 2. MOMENTUM LEADERS
    # -------------------------------------------------
    momentum = df[
        (df["momentum_z"] > 1.0) &
        (df["alpha_percentile"] >= 70)
    ].sort_values(
        by="momentum_z", ascending=False
    ).head(top_n)

    # -------------------------------------------------
    # 🟡 3. QUALITY COMPOUNDERS
    # -------------------------------------------------
    quality = df[
        (df["quality_z"] > 1.0) &
        (df["risk_z"] > 0.3)
    ].sort_values(
        by="quality_z", ascending=False
    ).head(top_n)

    # -------------------------------------------------
    # 🔴 4. OVERHYPED (SHORT IDEAS)
    # -------------------------------------------------
    overhyped = df[
        (df["alpha_percentile"] < 40) &
        (df["alpha_minus_percentile"] < -10)
    ].sort_values(
        by="alpha_score", ascending=True
    ).head(top_n)

    return {
        "undervalued": undervalued,
        "momentum": momentum,
        "quality": quality,
        "overhyped": overhyped,
    }