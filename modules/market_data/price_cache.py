import threading
from typing import Dict
import time
import pandas as pd

from modules.market_data.service import get_price_history
from modules.market_data.price_history_service import load_price_history
from modules.market_data.price_history_service import store_price_history
from modules.market_data.price_history_service import download_price_batch


# ---------------------------------------------------
# Global shared cache
# ---------------------------------------------------

_price_cache: Dict[str, pd.DataFrame] = {}

_cache_lock = threading.Lock()


# ---------------------------------------------------
# Main price loader
# ---------------------------------------------------

def get_price(symbol: str, db) -> pd.DataFrame:
    """
    Thread-safe price history getter.

    Priority order:
    1) memory cache
    2) local DB price_history table
    3) Yahoo download (only if missing)
    """

    symbol = symbol.upper()

    # ----------------------------------------
    # 1. Memory cache
    # ----------------------------------------

    if symbol in _price_cache:
        return _price_cache[symbol]

    # ----------------------------------------
    # 2. Local DB table
    # ----------------------------------------

    df = load_price_history(db, symbol)

    if df is not None and not df.empty:

        with _cache_lock:
            _price_cache[symbol] = df

        return df

    # ----------------------------------------
    # 3. Yahoo fallback (rare)
    # ----------------------------------------

    try:

        data = download_price_batch([symbol])

        if data is None or symbol not in data:
            return None

        df = data[symbol].dropna()

        if df.empty:
            return None

        store_price_history(db, symbol, df)

        with _cache_lock:
            _price_cache[symbol] = df

        return df

    except Exception as e:

        print("PRICE DOWNLOAD ERROR", symbol, e)

        return None


# ---------------------------------------------------
# Bulk cache warming
# ---------------------------------------------------

def warm_price_cache(db, symbols):
    """
    Preload price history for many symbols.
    """

    symbols = [s.upper() for s in symbols]

    for s in symbols:

        if s in _price_cache:
            continue

        df = load_price_history(db, s)

        if df is not None and not df.empty:

            with _cache_lock:
                _price_cache[s] = df


# ---------------------------------------------------
# Cache diagnostics
# ---------------------------------------------------

def get_cache_size():

    return len(_price_cache)