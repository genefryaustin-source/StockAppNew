from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.analytics.snapshot_cache import get_latest_snapshots_df


RISK_ON_ETFS = ["SPY", "QQQ", "IWM"]
DEFENSIVE_ETFS = ["TLT", "GLD", "XLU", "XLP"]


def _close_series(price_cache, symbol: str):
    obj = price_cache.get(symbol)
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        if "Close" not in obj.columns:
            return None
        return obj["Close"].dropna()
    if isinstance(obj, pd.Series):
        return obj.dropna()
    return None


def _pct_change(series: pd.Series, days: int):
    if series is None or len(series) <= days:
        return None
    start = series.iloc[-days - 1]
    end = series.iloc[-1]
    if start == 0:
        return None
    return float((end / start - 1) * 100.0)


def _realized_vol(series: pd.Series, window: int = 20):
    if series is None or len(series) <= window:
        return None
    r = series.pct_change().dropna().tail(window)
    if r.empty:
        return None
    return float(r.std() * (252 ** 0.5) * 100.0)


def _trend_label(series: pd.Series):
    if series is None or len(series) < 200:
        return "Unknown"

    sma50 = series.rolling(50).mean().iloc[-1]
    sma200 = series.rolling(200).mean().iloc[-1]
    price = series.iloc[-1]

    if price > sma50 > sma200:
        return "Bull"
    if price < sma50 < sma200:
        return "Bear"
    return "Transition"


def _breadth_from_snapshots(df: pd.DataFrame):
    if df is None or df.empty:
        return None, None

    work = df.copy()

    if "trend" in work.columns:
        up = int((work["trend"] == "Uptrend").sum())
        down = int((work["trend"] == "Downtrend").sum())
        total = len(work)
        pct_up = (up / total * 100.0) if total > 0 else None
        return pct_up, total

    if "momentum_score" in work.columns:
        mom = pd.to_numeric(work["momentum_score"], errors="coerce")
        up = int((mom > 0).sum())
        total = int(mom.notna().sum())
        pct_up = (up / total * 100.0) if total > 0 else None
        return pct_up, total

    return None, None


def _sector_leadership(df: pd.DataFrame):
    if df is None or df.empty or "sector" not in df.columns or "composite_score" not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    work["composite_score"] = pd.to_numeric(work["composite_score"], errors="coerce")

    out = (
        work.groupby("sector", dropna=False)["composite_score"]
        .mean()
        .reset_index()
        .rename(columns={"composite_score": "avg_composite"})
        .sort_values("avg_composite", ascending=False)
    )

    out["sector"] = out["sector"].fillna("Unknown")
    return out


def render_regime_engine(db, user):
    tenant_id = user["tenant_id"]
    price_cache = st.session_state.get("price_cache", {})

    st.subheader("Phase 16 — Market Regime Engine")

    if not price_cache:
        st.warning("Market data cache not available. Warm the cache first.")
        return

    spy = _close_series(price_cache, "SPY")
    qqq = _close_series(price_cache, "QQQ")
    iwm = _close_series(price_cache, "IWM")
    tlt = _close_series(price_cache, "TLT")
    gld = _close_series(price_cache, "GLD")

    trend = _trend_label(spy)
    vol20 = _realized_vol(spy, 20)
    spy_20 = _pct_change(spy, 20)
    qqq_20 = _pct_change(qqq, 20)
    iwm_20 = _pct_change(iwm, 20)
    tlt_20 = _pct_change(tlt, 20)
    gld_20 = _pct_change(gld, 20)

    snap_df = get_latest_snapshots_df(db, tenant_id)
    breadth_pct, breadth_total = _breadth_from_snapshots(snap_df)
    sectors = _sector_leadership(snap_df)

    offense = 0.0
    defense = 0.0

    for x in [spy_20, qqq_20, iwm_20]:
        if x is not None:
            offense += x

    for x in [tlt_20, gld_20]:
        if x is not None:
            defense += x

    if offense > defense:
        stance = "Risk On"
    elif defense > offense:
        stance = "Defensive"
    else:
        stance = "Neutral"

    if vol20 is not None and vol20 > 28:
        vol_regime = "High Vol"
    elif vol20 is not None and vol20 < 16:
        vol_regime = "Low Vol"
    else:
        vol_regime = "Normal Vol"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SPY Trend", trend)
    c2.metric("Volatility Regime", vol_regime, f"{vol20:.1f}%" if vol20 is not None else "N/A")
    c3.metric("Risk Stance", stance)
    c4.metric(
        "Breadth",
        f"{breadth_pct:.1f}%" if breadth_pct is not None else "N/A",
        f"{breadth_total} symbols" if breadth_total is not None else ""
    )

    st.markdown("### Cross-Asset 20D Performance")
    perf_df = pd.DataFrame(
        [
            {"Asset": "SPY", "Return %": spy_20},
            {"Asset": "QQQ", "Return %": qqq_20},
            {"Asset": "IWM", "Return %": iwm_20},
            {"Asset": "TLT", "Return %": tlt_20},
            {"Asset": "GLD", "Return %": gld_20},
        ]
    )
    st.dataframe(perf_df, use_container_width=True, hide_index=True)

    if not sectors.empty:
        st.markdown("### Sector Leadership")
        st.dataframe(sectors.head(12), use_container_width=True, hide_index=True)