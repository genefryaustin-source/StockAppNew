"""
modules/market/global_indices.py

Major Global Indices

Real Yahoo Finance data for the US and international benchmark
indices, reusing modules.market.macro_dashboard.fetch_yahoo_history
(the same proven fetch macro_dashboard.py and commodities_data.py
already use).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC

import pandas as pd

# Confirmed against Yahoo Finance directly. Nasdaq-100 is ^NDX, not
# ^IXIC (the broader Nasdaq Composite) -- ^NDX is what "Nasdaq-100" in
# a mobile spec conventionally means.
INDEX_SYMBOLS = {
    "US": {
        "S&P 500": "^GSPC",
        "Nasdaq-100": "^NDX",
        "Dow Jones": "^DJI",
        "Russell 2000": "^RUT",
    },
    "Global": {
        "STOXX 600": "^STOXX",
        "Nikkei 225": "^N225",
        "Hang Seng": "^HSI",
        "FTSE 100": "^FTSE",
    },
}

TIMEOUT_SECONDS = 8
MAX_WORKERS = 8


def _flat_symbols() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for region, symbols in INDEX_SYMBOLS.items():
        for label, symbol in symbols.items():
            out[label] = (symbol, region)
    return out


def _parallel_load(symbols: dict[str, str], period: str = "1mo") -> dict[str, pd.DataFrame]:
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


def get_major_indices() -> dict:
    """
    Current level, 1-day % / point change, and a 5-day sparkline
    (closing prices) for each tracked index. An index whose fetch
    failed is reported with "available": false rather than a
    fabricated value.
    """
    label_to_symbol_region = _flat_symbols()
    fetch_map = {label: symbol for label, (symbol, _region) in label_to_symbol_region.items()}

    data = _parallel_load(fetch_map, period="1mo")

    indices = []

    for label, (symbol, region) in label_to_symbol_region.items():
        df = data.get(label)

        if df is None or df.empty:
            indices.append({
                "name": label,
                "symbol": symbol,
                "region": region,
                "available": False,
            })
            continue

        closes = df["Close"].dropna()

        if len(closes) < 2:
            indices.append({
                "name": label,
                "symbol": symbol,
                "region": region,
                "available": False,
            })
            continue

        last_price = float(closes.iloc[-1])
        prev_price = float(closes.iloc[-2])
        point_change = last_price - prev_price
        pct_change = round((point_change / prev_price) * 100.0, 2) if prev_price else None

        sparkline = [round(float(v), 2) for v in closes.iloc[-5:].tolist()]

        indices.append({
            "name": label,
            "symbol": symbol,
            "region": region,
            "available": True,
            "last_price": round(last_price, 2),
            "point_change": round(point_change, 2),
            "pct_change": pct_change,
            "sparkline_5d": sparkline,
        })

    return {
        "as_of": datetime.now(UTC).isoformat(),
        "index_count": len(indices),
        "indices": indices,
    }