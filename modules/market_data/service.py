import os
import time
from datetime import datetime, UTC, timedelta
from typing import Dict, Iterable, Optional, Any

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
from modules.market_data.providers.marketdata_provider import (
    get_history as marketdata_history,
)

from modules.market_data.providers.alpha_vantage_provider import (
    get_history as alpha_history,
)

# ---------------------------------------------------
# CACHE SETUP
# ---------------------------------------------------

CACHE_DIR = get_cache_dir("market_data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE = Cache(CACHE_DIR)

print(f"[market_data] Using cache dir: {CACHE_DIR}")


# ---------------------------------------------------
# PROVIDER CIRCUIT BREAKERS
# ---------------------------------------------------

_PROVIDER_STATE = {
    "finnhub_disabled_until": 0.0,
    "eodhd_disabled_until": 0.0,
    "yahoo_disabled_until": 0.0,
}

_FAILED_SYMBOLS = {}
FAILED_SYMBOL_TTL_SECONDS = 60 * 30


# ---------------------------------------------------
# COMMON HELPERS
# ---------------------------------------------------

EMPTY_HISTORY_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=EMPTY_HISTORY_COLUMNS)


def _now_ts() -> float:
    return time.time()


def _provider_disabled(provider: str) -> bool:
    key = f"{provider}_disabled_until"
    return _now_ts() < float(_PROVIDER_STATE.get(key, 0.0) or 0.0)

def _all_history_providers_disabled() -> bool:
    return (
        _provider_disabled("eodhd")
        and _provider_disabled("finnhub")
        and _provider_disabled("yahoo")
    )


def _disable_provider(provider: str, seconds: int = 900, reason: str = "") -> None:
    key = f"{provider}_disabled_until"
    _PROVIDER_STATE[key] = _now_ts() + seconds
    print(f"🚨 {provider.upper()} DISABLED FOR {seconds // 60} MIN {reason}".strip())


def _mark_symbol_failed(symbol: str) -> None:
    sym = _base(symbol)
    if sym:
        _FAILED_SYMBOLS[sym] = _now_ts() + FAILED_SYMBOL_TTL_SECONDS


def _symbol_temporarily_failed(symbol: str) -> bool:
    sym = _base(symbol)
    until = float(_FAILED_SYMBOLS.get(sym, 0.0) or 0.0)

    if until <= 0:
        return False

    if _now_ts() > until:
        _FAILED_SYMBOLS.pop(sym, None)
        return False

    return True


def _safe_json(response: requests.Response, provider: str, symbol: str) -> Optional[Any]:
    try:
        if response.status_code != 200:
            err = f"{provider.upper()} HTTP {response.status_code}: {symbol}"

            if response.status_code in (401, 403):
                seconds = 900
                _disable_provider(provider, seconds=seconds, reason=f"for {symbol}")

            elif response.status_code == 429:
                seconds = 900
                _disable_provider(provider, seconds=seconds, reason=f"rate-limited for {symbol}")

            print(err)
            return None

        if not response.text or not response.text.strip():
            print(f"{provider.upper()} EMPTY RESPONSE: {symbol}")
            return None

        return response.json()

    except Exception as e:
        print(f"{provider.upper()} JSON PARSE ERROR: {symbol} {e}")
        return None


def _normalize_df(df):

    import pandas as pd

    REQUIRED_COLS = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)

    df = df.copy()

    # ---------------------------------
    # COLUMN NORMALIZATION
    # ---------------------------------
    rename_map = {}

    for c in df.columns:

        lc = str(c).lower().strip()

        if lc in ("date", "datetime", "timestamp", "time"):
            rename_map[c] = "Date"

        elif lc == "open":
            rename_map[c] = "Open"

        elif lc == "high":
            rename_map[c] = "High"

        elif lc == "low":
            rename_map[c] = "Low"

        elif lc in ("close", "adj close", "adjusted_close"):
            rename_map[c] = "Close"

        elif lc in ("volume", "vol"):
            rename_map[c] = "Volume"

    df.rename(columns=rename_map, inplace=True)

    # ---------------------------------
    # ENSURE REQUIRED COLS EXIST
    # ---------------------------------
    for col in REQUIRED_COLS:

        if col not in df.columns:

            if col == "Date":
                df[col] = pd.NaT
            else:
                df[col] = 0.0

    # ---------------------------------
    # DATE CLEANUP
    # ---------------------------------
    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    # remove timezone awareness
    try:
        if getattr(df["Date"].dt, "tz", None) is not None:
            df["Date"] = df["Date"].dt.tz_convert(None)
    except Exception:
        try:
            df["Date"] = df["Date"].dt.tz_localize(None)
        except Exception:
            pass

    # ---------------------------------
    # NUMERIC CLEANUP
    # ---------------------------------
    numeric_cols = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for col in numeric_cols:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # ---------------------------------
    # DROP BAD ROWS
    # ---------------------------------
    df = df.dropna(subset=["Date", "Close"])

    # ---------------------------------
    # SORT + DEDUPE
    # ---------------------------------
    df = (
        df
        .sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )

    # ---------------------------------
    # FINAL COLUMN ORDER
    # ---------------------------------
    df = df[REQUIRED_COLS]

    return df


def _base(sym: str) -> str:
    if not sym:
        return ""

    try:
        s = normalize_symbol(sym)
    except Exception:
        s = str(sym).upper().strip()

    return str(s).upper().replace(".US", "").strip()


def _valid_base_symbol(symbol: str) -> str:
    sym = _base(symbol)
    if not sym:
        return ""

    try:
        if not is_valid_symbol(sym):
            return ""
    except Exception:
        return ""

    return sym


# ---------------------------------------------------
# FINNHUB PRICE
# ---------------------------------------------------

def _get_prices_finnhub(symbols: Iterable[str]) -> Dict[str, Dict[str, float]]:
    if _provider_disabled("finnhub"):
        print("⚠️ FINNHUB TEMP DISABLED")
        return {}

    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return {}

    out = {}

    for raw_sym in symbols:
        sym = _valid_base_symbol(raw_sym)
        if not sym:
            continue

        try:
            r = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": sym, "token": key},
                timeout=5,
            )

            data = _safe_json(r, "finnhub", sym)
            if not isinstance(data, dict):
                continue

            price = data.get("c")
            volume = data.get("v")

            if price is not None and float(price) > 0:
                out[sym] = {
                    "price": float(price),
                    "volume": float(volume or 0.0),
                }

        except Exception as e:
            err = str(e)

            if "403" in err or "Forbidden" in err:
                _disable_provider("finnhub", reason=f"for {sym}")

            print(f"PRICE FETCH ERROR (Finnhub): {sym} {e}")

    return out


def _get_price_finnhub(symbol: str):
    prices = _get_prices_finnhub([symbol])
    return prices.get(_base(symbol))


# ---------------------------------------------------
# EODHD PRICE
# ---------------------------------------------------

def _get_price_eod(sym: str):

    try:

        from modules.market_data.price_cache import (
            get_price,
        )

        return get_price(sym, None)

    except Exception as e:

        print(
            "LEGACY EOD FALLBACK ERROR",
            sym,
            e,
        )

        return None


# ---------------------------------------------------
# YAHOO PRICE
# ---------------------------------------------------

def _get_price_yahoo(sym: str):
    if _provider_disabled("yahoo"):
        print("⚠️ YAHOO TEMP DISABLED")
        return None

    base = _valid_base_symbol(sym)
    if not base:
        return None

    try:
        time.sleep(0.25)

        df = yf.Ticker(base).history(period="5d")

        if df is not None and not df.empty:
            return {
                "price": float(df["Close"].iloc[-1]),
                "volume": float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0.0,
            }

    except Exception as e:
        err = str(e)

        if "Too Many Requests" in err or "Rate limited" in err or "429" in err:
            _disable_provider("yahoo", reason=f"rate-limited for {base}")

        print("Yahoo failed for", base, e)

    return None


# ---------------------------------------------------
# MASSIVE / LEGACY COMPATIBILITY
# ---------------------------------------------------

def _get_price_massive(sym: str):
    try:
        return _get_price_eod(sym)
    except Exception as e:
        print("MASSIVE COMPAT FALLBACK ERROR:", sym, e)
        return None





# ---------------------------------------------------
# EODHD HISTORY
# ---------------------------------------------------

def _get_history_eodhd(symbol: str) -> pd.DataFrame:
    if _provider_disabled("eodhd"):

        return _empty_history()

    key = get_secret("EODHD_API_KEY")
    if not key:
        return _empty_history()

    sym = _valid_base_symbol(symbol)
    if not sym:
        return _empty_history()

    try:
        r = requests.get(
            f"https://eodhd.com/api/eod/{sym}.US",
            params={
                "api_token": key,
                "fmt": "json",
                "period": "d",
            },
            timeout=12,
        )

        data = _safe_json(r, "eodhd", sym)
        if not isinstance(data, list) or not data:
            return _empty_history()

        df = pd.DataFrame(data)

        df.rename(columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }, inplace=True)

        return _normalize_df(df)

    except Exception as e:
        err = str(e)

        if "401" in err or "Unauthorized" in err:
            # disable quietly
            _disable_provider(
                "eodhd",
                reason=f"for {sym}",
            )

            return _empty_history()

        print("EODHD HISTORY ERROR:", sym, e)

    return _empty_history()


# ---------------------------------------------------
# YAHOO HISTORY
# ---------------------------------------------------

def _get_history_yahoo(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    if _provider_disabled("yahoo"):
        print("⚠️ YAHOO TEMP DISABLED")
        return _empty_history()

    sym = _valid_base_symbol(symbol)
    if not sym:
        return _empty_history()

    try:
        time.sleep(0.25)

        df = yf.Ticker(sym).history(period=period, interval=interval)

        if df is None or df.empty:
            return _empty_history()

        df = df.reset_index()

        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "Date"}, inplace=True)
        elif "Date" not in df.columns and len(df.columns) > 0:
            df.rename(columns={df.columns[0]: "Date"}, inplace=True)

        return _normalize_df(df)

    except Exception as e:
        err = str(e)

        if "Too Many Requests" in err or "Rate limited" in err or "429" in err:
            _disable_provider("yahoo", reason=f"rate-limited for {sym}")

        print("YAHOO HISTORY FALLBACK ERROR:", sym, e)

    return _empty_history()


# ---------------------------------------------------
# PRICE HISTORY
# ---------------------------------------------------

def get_price_history(db, symbol, period="1y", interval="1d", force_refresh=False):
    print("🔥 PRICE HISTORY CALLED:", symbol)
    end = int(datetime.now(UTC).timestamp())

    if period == "1y":
        start = int(
            (datetime.now(UTC) - timedelta(days=365))
            .timestamp()
        )

    elif period == "6mo":
        start = int(
            (datetime.now(UTC) - timedelta(days=180))
            .timestamp()
        )

    elif period == "3mo":
        start = int(
            (datetime.now(UTC) - timedelta(days=90))
            .timestamp()
        )

    else:
        start = int(
            (datetime.now(UTC) - timedelta(days=365))
            .timestamp()
        )
    sym = _valid_base_symbol(symbol)
    if not sym:
        return _empty_history()

    cache_key = f"{sym}:{period}:{interval}"
    print("CACHE CHECK:", cache_key)
    if False and not force_refresh and cache_key in CACHE:
        cached_df = CACHE[cache_key]
        if cached_df is not None and not cached_df.empty:
            print("🔥 PRICE HISTORY CACHE HIT:", sym, cached_df.shape)
            return _normalize_df(cached_df)

    if not force_refresh and _symbol_temporarily_failed(sym):
        print(f"⚠️ SYMBOL TEMP FAILED, SKIPPING: {sym}")
        return _empty_history()

    if _all_history_providers_disabled():
        print(f"⚠️ ALL HISTORY PROVIDERS DISABLED — SKIPPING FETCH: {sym}")
        return _empty_history()

    # -----------------------------------
    # 1. MARKETDATA.APP PRIMARY
    # -----------------------------------
    df = marketdata_history(
        symbol,
        period="1y",
        start=None,
        end=None,
        interval="1d",
    )

    if df is not None and not df.empty:
        CACHE[cache_key] = df
        return df

    # -----------------------------------
    # 2. ALPHA VANTAGE BACKUP
    # -----------------------------------
    df = alpha_history(
        symbol,
        period="1y",
        start=None,
        end=None,
        interval="1d",
    )

    if df is not None and not df.empty:
        CACHE[cache_key] = df
        return df

    # -----------------------------------
    # 3. YAHOO EMERGENCY FALLBACK
    # -----------------------------------
    df = _get_history_yahoo(
        symbol,
        period="1y",
        interval="1d",
    )

    if df is not None and not df.empty:
        CACHE[cache_key] = df
        return df

    print(f"⚠️ NO PRICE DATA RETURNED: {sym}")
    _mark_symbol_failed(sym)
    return _empty_history()


# ---------------------------------------------------
# BULK PRICE FETCH
# ---------------------------------------------------

def get_prices_many(db, symbols):
    results = {}

    clean_symbols = []
    for s in symbols or []:
        sym = _valid_base_symbol(s)
        if sym:
            clean_symbols.append(sym)

    if not clean_symbols:
        return results

    # -----------------------------
    # 1. FINNHUB BULK FIRST
    # -----------------------------
    fh = _get_prices_finnhub(clean_symbols)

    for sym in clean_symbols:
        if sym in results:
            continue

        if sym in fh:
            row = fh[sym]
            results[sym] = pd.DataFrame([{
                "Date": pd.Timestamp.now(UTC),
                "Close": row["price"],
                "Volume": row["volume"],
            }])
            continue

        # -----------------------------
        # 2. EODHD
        # -----------------------------
        eod = _get_price_eod(sym)
        if eod:
            results[sym] = pd.DataFrame([{
                "Date": pd.Timestamp.now(UTC),
                "Close": eod["price"],
                "Volume": eod["volume"],
            }])
            continue

        # -----------------------------
        # 3. YAHOO LAST
        # -----------------------------
        yh = _get_price_yahoo(sym)
        if yh:
            results[sym] = pd.DataFrame([{
                "Date": pd.Timestamp.now(UTC),
                "Close": yh["price"],
                "Volume": yh["volume"],
            }])
            continue

        results[sym] = pd.DataFrame()

    return results


# ---------------------------------------------------
# LATEST PRICE
# ---------------------------------------------------

def get_latest_price(symbol: str):
    sym = _valid_base_symbol(symbol)
    if not sym:
        return None

    try:
        fh = _get_price_finnhub(sym)
        if fh:
            return fh
    except Exception as e:
        print(f"PRICE FETCH ERROR (Finnhub): {sym} {e}")

    try:
        eod = _get_price_eod(sym)
        if eod:
            return eod
    except Exception as e:
        print(f"PRICE FETCH ERROR (EODHD): {sym} {e}")

    try:
        yh = _get_price_yahoo(sym)
        if yh:
            return yh
    except Exception as e:
        print(f"PRICE FETCH ERROR (Yahoo): {sym} {e}")

    try:
        massive = _get_price_massive(sym)
        if massive:
            return massive
    except Exception as e:
        print(f"PRICE FETCH ERROR (Massive): {sym} {e}")

    return None


# ---------------------------------------------------
# LATEST PRICE MAP
# ---------------------------------------------------

def get_latest_prices(symbols):
    out = {}

    clean_symbols = []
    for s in symbols or []:
        sym = _valid_base_symbol(s)
        if sym:
            clean_symbols.append(sym)

    if not clean_symbols:
        return out

    fh = _get_prices_finnhub(clean_symbols)

    for sym in clean_symbols:
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
    _FAILED_SYMBOLS.clear()
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
    max_api_calls=1000,
    **kwargs
):
    api_calls = 0
    price_cache = {}
    meta = {}

    for symbol in symbols or []:
        sym = _valid_base_symbol(symbol)
        if not sym:
            continue

        if _all_history_providers_disabled():
            print("🚨 ALL PROVIDERS DISABLED — STOPPING SHARED CACHE BUILD")
            break

        if max_api_calls is not None and api_calls >= max_api_calls:
            print("API LIMIT REACHED")
            break

        try:
            df = get_price_history(
                db,
                sym,
                period=period,
                interval=interval,
            )

            api_calls += 1

            if df is None or len(df) < min_rows:
                continue

            price_cache[sym] = df
            meta[sym] = {"rows": len(df)}

        except Exception as e:
            print("CACHE ERROR:", sym, e)

    return price_cache, meta


def get_price_history_page_from_db(db, symbol, page=1, page_size=250, period="1y"):
    df = get_price_history(db, symbol, period=period)
    total = len(df)
    start = (page - 1) * page_size
    return df.iloc[start:start + page_size], total


# ---------------------------------------------------
# MASSIVE LEGACY OHLC COMPATIBILITY
# ---------------------------------------------------

def massive_fetch_ohlc(symbol: str, period="1y") -> pd.DataFrame:
    try:
        sym = _valid_base_symbol(symbol)
        if not sym:
            return _empty_history()

        df = _get_history_eodhd(sym)
        if df is not None and not df.empty:
            return df

        return _empty_history()

    except Exception as e:
        print("massive_fetch_ohlc fallback error:", symbol, e)
        return _empty_history()

def preload_histories(
        db,
        symbols,
        period="1y",
        interval="1d",
):
    """
    Bulk preload normalized price histories.

    Returns:
        dict[symbol] -> normalized dataframe
    """

    history_map = {}

    symbols = list(dict.fromkeys([
        str(s).upper().strip()
        for s in (symbols or [])
        if s
    ]))

    print(f"🚀 PRELOADING HISTORIES: {len(symbols)} symbols")

    for i, sym in enumerate(symbols):

        if i % 50 == 0:
            print(f"History preload {i}/{len(symbols)}")

        try:

            df = get_price_history(
                db=db,
                symbol=sym,
                period=period,
                interval=interval,
            )

            if df is None or df.empty:
                continue

            if len(df) < 50:
                continue

            history_map[sym] = df

        except Exception as e:

            print("PRELOAD ERROR:", sym, e)

    print(f"✅ PRELOAD COMPLETE: {len(history_map)} loaded")

    return history_map