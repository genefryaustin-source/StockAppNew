"""
modules/market/commodities_data.py

Commodities Market Data

Real futures prices via Yahoo Finance -- reuses modules.market.
macro_dashboard.fetch_yahoo_history (the same proven, working raw
HTTP fetch macro_dashboard.py already uses for treasury yields and
VIX), rather than a separate, duplicated implementation.

Nothing under this name existed anywhere in this codebase before --
this is a new module, not a fix to an existing one.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC

import pandas as pd

# Standard Yahoo Finance continuous-futures tickers ("XX=F"), grouped
# by sector the way commodities are conventionally categorized.
# Sticking to long-established, stable exchange-listed contracts
# (COMEX/NYMEX/CBOT/ICE/CME) whose Yahoo tickers have been the same
# for decades, rather than more obscure or newer contracts whose
# ticker conventions are less certain.
COMMODITY_SYMBOLS = {
    "Precious Metals": {
        "Gold": "GC=F",
        "Silver": "SI=F",
        "Platinum": "PL=F",
        "Palladium": "PA=F",
    },
    "Energy": {
        "Crude Oil (WTI)": "CL=F",
        "Brent Crude": "BZ=F",
        "Natural Gas": "NG=F",
        "Heating Oil": "HO=F",
        "RBOB Gasoline": "RB=F",
    },
    "Industrial Metals": {
        "Copper": "HG=F",
    },
    "Agriculture": {
        "Corn": "ZC=F",
        "Wheat": "ZW=F",
        "Soybeans": "ZS=F",
        "Coffee": "KC=F",
        "Sugar": "SB=F",
        "Cotton": "CT=F",
        "Cocoa": "CC=F",
    },
    "Livestock": {
        "Live Cattle": "LE=F",
        "Lean Hogs": "HE=F",
        "Feeder Cattle": "GF=F",
    },
}

TIMEOUT_SECONDS = 8
MAX_WORKERS = 8


def _flat_symbols(category: str | None = None) -> dict[str, tuple[str, str]]:
    """label -> (symbol, category), optionally filtered to one category."""
    out: dict[str, tuple[str, str]] = {}
    for cat, symbols in COMMODITY_SYMBOLS.items():
        if category is not None and cat.lower() != category.lower():
            continue
        for label, symbol in symbols.items():
            out[label] = (symbol, cat)
    return out


def list_categories() -> list[str]:
    return list(COMMODITY_SYMBOLS.keys())


def _parallel_load(symbols: dict[str, str], period: str = "3mo") -> dict[str, pd.DataFrame]:
    from modules.market.macro_dashboard import fetch_yahoo_history

    results: dict[str, pd.DataFrame] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_yahoo_history, symbol, period): label
            for label, symbol in symbols.items()
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                results[label] = future.result(timeout=TIMEOUT_SECONDS)
            except Exception:
                results[label] = pd.DataFrame()

    return results


def _pct_change(df: pd.DataFrame, days: int) -> float | None:
    if df is None or df.empty or len(df) <= days:
        return None

    closes = df["Close"].dropna()
    if len(closes) <= days:
        return None

    start = closes.iloc[-(days + 1)]
    end = closes.iloc[-1]

    if start == 0:
        return None

    return round(float((end / start - 1.0) * 100.0), 2)


def get_commodities_snapshot(category: str | None = None) -> dict:
    """
    Current price and 1d/5d/30d % change for each tracked commodity
    future, from real Yahoo Finance daily closes. Optionally scoped to
    one category (see list_categories()); unrecognized category names
    return zero commodities rather than raising, so a client typo
    degrades gracefully.  A commodity whose fetch failed (network
    issue, symbol temporarily unavailable) is reported with
    "available": false rather than a fabricated price.
    """
    label_to_symbol_category = _flat_symbols(category)
    fetch_map = {label: symbol for label, (symbol, _cat) in label_to_symbol_category.items()}

    data = _parallel_load(fetch_map, period="3mo")

    commodities = []

    for label, (symbol, cat) in label_to_symbol_category.items():
        df = data.get(label)

        if df is None or df.empty:
            commodities.append({
                "name": label,
                "symbol": symbol,
                "category": cat,
                "available": False,
            })
            continue

        latest_price = float(df["Close"].dropna().iloc[-1])

        commodities.append({
            "name": label,
            "symbol": symbol,
            "category": cat,
            "available": True,
            "price": round(latest_price, 2),
            "change_1d_pct": _pct_change(df, 1),
            "change_5d_pct": _pct_change(df, 5),
            "change_30d_pct": _pct_change(df, 30),
        })

    return {
        "as_of": datetime.now(UTC).isoformat(),
        "categories": list_categories(),
        "commodity_count": len(commodities),
        "commodities": commodities,
    }