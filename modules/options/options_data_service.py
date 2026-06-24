"""
modules/options/options_data_service.py

Backward-compatible options data entry point.

This file intentionally preserves the legacy StockApp return shape used by the
existing options dashboards:
    {ticker, chain, expirations, all_rows, source/provider, contracts}

The chain is now loaded through an options provider router with failover:
    MarketData.app -> Tradier -> Finnhub -> Yahoo
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd

from modules.options.options_provider_router import (
    clear_options_chain_cache,
    get_options_chain_from_router,
)
from modules.options.providers.common import calc_dte as _calc_dte
from modules.options.providers.common import get_secret as _secret


def get_options_chain(ticker: str) -> dict:
    """Return the normalized options chain using provider failover."""
    return get_options_chain_from_router(ticker)


def get_iv_surface(ticker: str) -> pd.DataFrame:
    """Pivot DTE vs strike to IV for the existing IV surface chart."""
    chain_data = get_options_chain(ticker)
    if not isinstance(chain_data, dict) or chain_data.get("error"):
        return pd.DataFrame()

    df = chain_data.get("all_rows", pd.DataFrame())
    if df is None or df.empty:
        return pd.DataFrame()

    if "type" not in df.columns or "iv" not in df.columns:
        return pd.DataFrame()

    calls = df[df["type"].astype(str).str.lower().eq("call")].dropna(
        subset=["dte", "strike", "iv"]
    )
    if calls.empty:
        return pd.DataFrame()

    try:
        pivot = calls.pivot_table(
            index="dte",
            columns="strike",
            values="iv",
            aggfunc="mean",
        )
        return pivot.sort_index()
    except Exception:
        return pd.DataFrame()


# Backward-compatible helpers retained for modules that import them directly.
def _cached(key):
    return None


def _cache(key, d):
    return d
