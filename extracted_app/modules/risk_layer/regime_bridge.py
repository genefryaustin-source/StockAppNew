"""
modules/risk_layer/regime_bridge.py

Reuses the exact same trend/volatility/breadth math the Regime Engine page
(modules.market.regime_engine) is built on, so the Risk Layer's read of
"what regime are we in" always agrees with what a user sees on that page --
just computed independently of Streamlit session state, so it can run from
a scheduled job as well as a page view.
"""

from __future__ import annotations

import pandas as pd

from modules.market.regime_engine import (
    RISK_ON_ETFS,
    DEFENSIVE_ETFS,
    _close_series,
    _pct_change,
    _realized_vol,
    _trend_label,
)


def get_market_regime(db) -> dict:
    """
    Returns {label, trend, breadth_pct_risk_on, spy_vol_20d, per_symbol}.
    label is one of "Risk-On", "Risk-Off", "Transition", or "Unknown".
    Never raises -- degrades to "Unknown" if price history isn't available.
    """
    from modules.market_data.price_history_service import load_price_history

    symbols = RISK_ON_ETFS + DEFENSIVE_ETFS
    series_map = {}
    for sym in symbols:
        try:
            # Fast path: stored daily closes -- market regime doesn't
            # need sub-second freshness (regimes don't flip minute to
            # minute), so there's no reason to pay for a live,
            # multi-provider fetch on every single call. Confirmed
            # directly: the previous live-fetch-per-symbol loop here
            # accounted for the entire multi-second-per-symbol delay
            # behind a reported 30+ second portfolio dashboard load.
            df = load_price_history(db, sym)
        except Exception:
            df = None

        if df is None or (hasattr(df, "empty") and df.empty):
            # No stored history for this symbol at all yet (e.g. a
            # fresh deployment) -- fall back to the slower live fetch
            # rather than silently reporting "Unknown" for a symbol
            # that could genuinely be priced.
            try:
                df = get_price_history(db, sym, period="1y", interval="1d")
            except TypeError:
                df = get_price_history(sym, period="1y", interval="1d")
            except Exception:
                df = None

        if df is not None and len(df):
            series_map[sym] = df

    per_symbol = {}
    for sym in symbols:
        series = _close_series(series_map, sym) if sym in series_map else None
        per_symbol[sym] = {
            "trend": _trend_label(series),
            "1m_change_pct": _pct_change(series, 21),
            "vol_20d_annualized_pct": _realized_vol(series, 20),
        }

    spy = per_symbol.get("SPY", {})
    trend = spy.get("trend", "Unknown")
    spy_vol = spy.get("vol_20d_annualized_pct")

    risk_on_up = sum(1 for s in RISK_ON_ETFS if (per_symbol.get(s, {}).get("1m_change_pct") or 0) > 0)
    defensive_up = sum(1 for s in DEFENSIVE_ETFS if (per_symbol.get(s, {}).get("1m_change_pct") or 0) > 0)

    if trend == "Unknown":
        label = "Unknown"
    elif trend == "Bull" and risk_on_up >= defensive_up:
        label = "Risk-On"
    elif trend == "Bear" or defensive_up > risk_on_up:
        label = "Risk-Off"
    else:
        label = "Transition"

    return {
        "label": label,
        "trend": trend,
        "risk_on_breadth": f"{risk_on_up}/{len(RISK_ON_ETFS)}",
        "defensive_breadth": f"{defensive_up}/{len(DEFENSIVE_ETFS)}",
        "spy_vol_20d_annualized_pct": spy_vol,
        "per_symbol": per_symbol,
    }


def regime_risk_multiplier(regime_label: str) -> float:
    """
    Simple regime-aware sizing multiplier consumed by limits.py to tighten
    exposure limits automatically in Risk-Off regimes rather than requiring
    a human to remember to do it. 1.0 = no adjustment.
    """
    return {
        "Risk-On": 1.0,
        "Transition": 0.85,
        "Risk-Off": 0.65,
        "Unknown": 0.85,
    }.get(regime_label, 0.85)