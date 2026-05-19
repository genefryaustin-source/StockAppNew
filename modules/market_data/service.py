import time
from datetime import datetime, UTC, timedelta
from typing import Dict

import os
import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from diskcache import Cache
from sqlalchemy import func

from modules.utils.symbol_utils import normalize_symbol, is_valid_symbol
from modules.market_data.models import PriceHistory
from modules.utils.paths import get_cache_dir
from modules.utils.config import get_secret


# ---------------------------------------------------
# CACHE SETUP (FIXED FOR EXE + MSI INSTALL)
# ---------------------------------------------------

# Always use centralized path system
CACHE_DIR = get_cache_dir("market_data_cache")

# Ensure directory exists (extra safety for packaged app)
os.makedirs(CACHE_DIR, exist_ok=True)

# Initialize cache ONLY ONCE
CACHE = Cache(CACHE_DIR)

print(f"[market_data] Using cache dir: {CACHE_DIR}")


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _normalize_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    df = df.copy()
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime": "Date"}, inplace=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def _base(sym):
    return str(sym).upper().replace(".US", "").strip()


# ---------------------------------------------------
# FINNHUB (PRIMARY)
# ---------------------------------------------------

def _get_prices_finnhub(symbols):
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return {}

    out = {}

    for sym in symbols:
        try:
            r = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": _base(sym), "token": key},
                timeout=3
            )
            r.raise_for_status()

            data = r.json()

            price = data.get("c")
            volume = data.get("v")

            if price is not None and float(price) > 0:
                out[_base(sym)] = {
                    "price": float(price),
                    "volume": float(volume or 0)
                }

        except Exception as e:
            print(f"PRICE FETCH ERROR: {sym} {e}")

    return out


def _get_price_finnhub(symbol):
    prices = _get_prices_finnhub([symbol])
    return prices.get(_base(symbol))


# ---------------------------------------------------
# EODHD (FALLBACK)
# ---------------------------------------------------

def _get_price_eod(sym):
    key = get_secret("EODHD_API_KEY")
    if not key:
        return None

    try:
        r = requests.get(
            f"https://eodhd.com/api/eod/{_base(sym)}.US",
            params={"api_token": key, "fmt": "json", "limit": 1},
            timeout=5
        )
        r.raise_for_status()

        data = r.json()

        if isinstance(data, list) and data:
            return {
                "price": float(data[-1]["close"]),
                "volume": float(data[-1].get("volume", 0))
            }

    except Exception as e:
        print("EODHD ERROR:", sym, e)

    return None


# ---------------------------------------------------
# YAHOO (LAST RESORT)
# ---------------------------------------------------

def _get_price_yahoo(sym):
    try:
        df = yf.Ticker(sym).history(period="5d")

        if df is not None and not df.empty:
            return {
                "price": float(df["Close"].iloc[-1]),
                "volume": float(df["Volume"].iloc[-1])
            }

    except Exception as e:
        print("Yahoo failed for", sym, e)

    return None


# ---------------------------------------------------
# MASSIVE / LEGACY COMPATIBILITY FALLBACK
# ---------------------------------------------------

def _get_price_massive(sym):
    """
    Legacy compatibility fallback.
    Uses EODHD-backed pricing so existing callers do not break.
    """
    try:
        return _get_price_eod(sym)
    except Exception as e:
        print("MASSIVE COMPAT FALLBACK ERROR:", sym, e)
        return None


def _get_history_finnhub(symbol):
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return None

    try:
        now = int(time.time())
        one_year = now - (365 * 24 * 60 * 60)

        r = requests.get(
            "https://finnhub.io/api/v1/stock/candle",
            params={
                "symbol": _base(symbol),
                "resolution": "D",
                "from": one_year,
                "to": now,
                "token": key
            },
            timeout=8
        )
        r.raise_for_status()

        data = r.json()

        if data.get("s") != "ok":
            return None

        df = pd.DataFrame({
            "Date": pd.to_datetime(data["t"], unit="s"),
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"],
        })

        return df.sort_values("Date").reset_index(drop=True)

    except Exception as e:
        print("FINNHUB HISTORY ERROR:", symbol, e)

    return None


# ---------------------------------------------------
# PRICE HISTORY (NO MORE YAHOO PRIMARY)
# ---------------------------------------------------

def get_price_history(db, symbol, period="1y", interval="1d", force_refresh=False):
    df = None
    print("🔥 PRICE HISTORY CALLED:", symbol)
    sym = normalize_symbol(symbol)

    if not is_valid_symbol(sym):
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    cache_key = f"{sym}:{period}"

    if not force_refresh and cache_key in CACHE:
        cached_df = CACHE[cache_key]
        print("🔥 PRICE HISTORY CACHE HIT:", symbol, cached_df.shape)
        return cached_df

    # -----------------------------------
    # EODHD (PRIMARY FOR HISTORY)
    # -----------------------------------
    try:
        key = get_secret("EODHD_API_KEY")

        if key:
            r = requests.get(
                f"https://eodhd.com/api/eod/{_base(sym)}.US",
                params={
                    "api_token": key,
                    "fmt": "json",
                    "period": "d"
                },
                timeout=10
            )
            r.raise_for_status()

            data = r.json()

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)

                df.rename(columns={
                    "date": "Date",
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume"
                }, inplace=True)

                df["Date"] = pd.to_datetime(df["Date"])
                df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

                CACHE[cache_key] = df
                return df

    except Exception as e:
        print("EODHD HISTORY ERROR:", sym, e)

    # -----------------------------------
    # FINNHUB (BACKUP)
    # -----------------------------------
    try:
        df = _get_history_finnhub(sym)

        if df is not None and not df.empty:
            CACHE[cache_key] = df
            return df

    except Exception as e:
        print("FINNHUB HISTORY FALLBACK ERROR:", sym, e)

    # -----------------------------------
    # YAHOO (FINAL HISTORY FALLBACK)
    # -----------------------------------
    try:
        df = yf.Ticker(sym).history(period=period, interval=interval)

        if df is not None and not df.empty:
            df = df.reset_index()
            if "Datetime" in df.columns:
                df.rename(columns={"Datetime": "Date"}, inplace=True)
            elif "Date" not in df.columns and len(df.columns) > 0:
                df.rename(columns={df.columns[0]: "Date"}, inplace=True)

            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])

            keep_cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[keep_cols]

            for col in ["Date", "Open", "High", "Low", "Close", "Volume"]:
                if col not in df.columns:
                    df[col] = 0 if col != "Date" else pd.NaT

            df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
            df = df.dropna(subset=["Date"])

            CACHE[cache_key] = df
            return df

    except Exception as e:
        print("YAHOO HISTORY FALLBACK ERROR:", sym, e)

    # -----------------------------------
    # FINAL FALLBACK (PREVENT CRASH)
    # -----------------------------------
    print(f"⚠️ NO PRICE DATA RETURNED: {sym}")
    return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])


# ---------------------------------------------------
# BULK PRICE FETCH (SCREENER CORE)
# ---------------------------------------------------

def get_prices_many(db, symbols):
    results = {}

    # -----------------------------
    # 1. FINNHUB FIRST
    # -----------------------------
    fh = _get_prices_finnhub(symbols)

    for s in symbols:
        sym = _base(s)

        if sym in fh:
            row = fh[sym]
            results[sym] = pd.DataFrame([{
                "Date": pd.Timestamp.utcnow(),
                "Close": row["price"],
                "Volume": row["volume"]
            }])
            continue

        # -----------------------------
        # 2. EODHD
        # -----------------------------
        eod = _get_price_eod(sym)

        if eod:
            results[sym] = pd.DataFrame([{
                "Date": pd.Timestamp.utcnow(),
                "Close": eod["price"],
                "Volume": eod["volume"]
            }])
            continue

        # -----------------------------
        # 3. YAHOO LAST
        # -----------------------------
        yh = _get_price_yahoo(sym)

        if yh:
            results[sym] = pd.DataFrame([{
                "Date": pd.Timestamp.utcnow(),
                "Close": yh["price"],
                "Volume": yh["volume"]
            }])
            continue

        results[sym] = pd.DataFrame()

    return results


def get_latest_price(symbol: str):
    try:
        fh = _get_price_finnhub(symbol)
        if fh:
            return fh
    except Exception as e:
        print(f"PRICE FETCH ERROR (Finnhub): {symbol} {e}")

    try:
        eod = _get_price_eod(symbol)
        if eod:
            return eod
    except Exception as e2:
        print(f"PRICE FETCH ERROR (EODHD): {symbol} {e2}")

    try:
        yh = _get_price_yahoo(symbol)
        if yh:
            return yh
    except Exception as e3:
        print(f"PRICE FETCH ERROR (Yahoo): {symbol} {e3}")

    try:
        massive = _get_price_massive(symbol)
        if massive:
            return massive
    except Exception as e4:
        print(f"PRICE FETCH ERROR (Massive): {symbol} {e4}")

    return None


# ---------------------------------------------------
# LATEST PRICE MAP
# ---------------------------------------------------

def get_latest_prices(symbols):
    out = {}

    fh = _get_prices_finnhub(symbols)

    for s in symbols:
        sym = _base(s)

        if sym in fh:
            out[sym] = fh[sym]["price"]
            continue

        eod = _get_price_eod(sym)
        if eod:
            out[sym] = eod["price"]
            continue

        yh = _get_price_yahoo(sym)
        if yh:
            out[sym] = yh["price"]
            continue

        massive = _get_price_massive(sym)
        if massive:
            out[sym] = massive["price"]
            continue

        out[sym] = 0.0

    return out


def get_latest_price_map(symbols):
    return get_latest_prices(symbols)


# ---------------------------------------------------
# CACHE MGMT
# ---------------------------------------------------

def clear_price_cache():
    CACHE.clear()
    return True


def get_stale_symbols(db, max_age_days=3, limit=None):
    try:
        rows = (
            db.query(
                PriceHistory.symbol,
                func.max(PriceHistory.date).label("last_date"),
            )
            .group_by(PriceHistory.symbol)
            .all()
        )

        stale = [r.symbol for r in rows]

        if limit:
            stale = stale[:limit]

        return pd.DataFrame({"symbol": stale})

    except Exception:
        return pd.DataFrame({"symbol": []})


def build_shared_price_cache(
    db,
    symbols,
    min_rows=50,
    period="6mo",
    interval="1d",
    max_api_calls=None,
    **kwargs  # 🔥 future-proof
):
    api_calls = 0
    price_cache = {}
    meta = {}

    for symbol in symbols:
        if max_api_calls is not None and api_calls >= max_api_calls:
            print("API LIMIT REACHED")
            break

        try:
            df = get_price_history(
                db,
                symbol,
                period=period,
                interval=interval
            )

            api_calls += 1

            # 🔥 NEW SAFETY FILTER
            if df is None or len(df) < min_rows:
                continue

            price_cache[symbol] = df
            meta[symbol] = {
                "rows": len(df)
            }

        except Exception as e:
            print("CACHE ERROR:", symbol, e)

    return price_cache, meta


def get_price_history_page_from_db(db, symbol, page=1, page_size=250, period="1y"):
    df = get_price_history(db, symbol, period)
    total = len(df)
    start = (page - 1) * page_size
    return df.iloc[start:start + page_size], total


def massive_fetch_ohlc(symbol: str, period="1y") -> pd.DataFrame:
    """
    REQUIRED for compatibility with updater + legacy modules.
    Uses EODHD as backend instead of Massive.

    DO NOT REMOVE.
    """
    try:
        key = get_secret("EODHD_API_KEY")
        base = str(symbol).upper().replace(".US", "")

        if not key:
            return pd.DataFrame()

        r = requests.get(
            f"https://eodhd.com/api/eod/{base}.US",
            params={
                "api_token": key,
                "fmt": "json",
                "period": "d"
            },
            timeout=10
        )
        r.raise_for_status()

        data = r.json()

        if not isinstance(data, list) or not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        df.rename(columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }, inplace=True)

        df["Date"] = pd.to_datetime(df["Date"])

        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        print("massive_fetch_ohlc fallback error:", symbol, e)
        return pd.DataFrame()