import os
import time
from datetime import datetime, UTC, timedelta
from typing import Dict, Iterable, Optional, Any

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from diskcache import Cache
from sqlalchemy import func, text

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
from modules.market_data.providers.polygon import (
    fetch_ohlcv as polygon_history,
)
from modules.market_data.provider_router import (
    get_provider_router,
    is_rate_limit_error,
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
    "polygon_disabled_until": 0.0,
    "marketdata_disabled_until": 0.0,
    "alpha_vantage_disabled_until": 0.0,
}

_FAILED_SYMBOLS = {}
FAILED_SYMBOL_TTL_SECONDS = 60 * 30

# small in-process latest-price cache to stop Alpha/Recommendations from
# repeatedly refetching the same symbols during one Streamlit rerun.
_LATEST_PRICE_CACHE: Dict[str, tuple[float, float]] = {}
LATEST_PRICE_TTL_SECONDS = 60 * 5


# ---------------------------------------------------
# COMMON HELPERS
# ---------------------------------------------------

EMPTY_HISTORY_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=EMPTY_HISTORY_COLUMNS)


def _now_ts() -> float:
    return time.time()


def _provider_disabled(provider: str) -> bool:
    provider = str(provider or "").lower().strip()
    key = f"{provider}_disabled_until"
    return _now_ts() < float(_PROVIDER_STATE.get(key, 0.0) or 0.0)


def _all_history_providers_disabled() -> bool:
    return (
        _provider_disabled("eodhd")
        and _provider_disabled("finnhub")
        and _provider_disabled("yahoo")
    )


def _disable_provider(provider: str, seconds: int = 900, reason: str = "") -> None:
    provider = str(provider or "").lower().strip()
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
                _disable_provider(provider, seconds=900, reason=f"for {symbol}")

            elif response.status_code == 429:
                _disable_provider(provider, seconds=900, reason=f"rate-limited for {symbol}")

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

    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = pd.NaT if col == "Date" else 0.0

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    try:
        if getattr(df["Date"].dt, "tz", None) is not None:
            df["Date"] = df["Date"].dt.tz_convert(None)
    except Exception:
        try:
            df["Date"] = df["Date"].dt.tz_localize(None)
        except Exception:
            pass

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Date", "Close"])
    df = (
        df
        .sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )

    return df[REQUIRED_COLS]


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


def _coerce_price_payload(payload):
    if payload is None:
        return None

    if isinstance(payload, dict):
        payload = payload.get("price")

    try:
        payload = float(payload)
        if payload > 0:
            return payload
    except Exception:
        return None

    return None


def _cache_latest_price(symbol: str, price: float) -> None:
    sym = _valid_base_symbol(symbol)
    price = _coerce_price_payload(price)
    if sym and price is not None:
        _LATEST_PRICE_CACHE[sym] = (price, _now_ts() + LATEST_PRICE_TTL_SECONDS)


def _get_cached_latest_price(symbol: str):
    sym = _valid_base_symbol(symbol)
    if not sym:
        return None

    item = _LATEST_PRICE_CACHE.get(sym)
    if not item:
        return None

    price, expires = item
    if _now_ts() > expires:
        _LATEST_PRICE_CACHE.pop(sym, None)
        return None

    return _coerce_price_payload(price)


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
        if _provider_disabled("finnhub"):
            print("FINNHUB LOOP ABORTED")
            break

        sym = _valid_base_symbol(raw_sym)
        if not sym:
            continue

        try:
            r = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": sym, "token": key},
                timeout=5,
            )
            print("FINNHUB REQUEST:", [sym])
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
            if "429" in err or "rate" in err.lower():
                _disable_provider("finnhub", reason=f"rate-limited for {sym}")
            print(f"PRICE FETCH ERROR (Finnhub): {sym} {e}")

    return out


def _get_price_finnhub(symbol: str):
    prices = _get_prices_finnhub([symbol])
    return prices.get(_base(symbol))


# ---------------------------------------------------
# EODHD PRICE
# ---------------------------------------------------

def _get_price_eod(sym: str):
    return None


# ---------------------------------------------------
# YAHOO PRICE
# ---------------------------------------------------

def _get_price_yahoo(sym: str):
    # Yahoo has been consistently rate-limited in this deployment. Leave the
    # function for compatibility, but do not use it in latest-price routing.
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
            params={"api_token": key, "fmt": "json", "period": "d"},
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
            _disable_provider("eodhd", reason=f"for {sym}")
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

def get_price_history_internal(
    db,
    symbol,
    period="1y",
    interval="1d",
    force_refresh=False,
    provider_override=None,
):
    print("🔥 PRICE HISTORY CALLED:", symbol)
    sym = _valid_base_symbol(symbol)
    router = get_provider_router()
    print("PROVIDER OVERRIDE:", provider_override)

    if provider_override:
        provider_override = provider_override.upper()

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
    # 1. POLYGON PRIMARY FOR HISTORY ONLY
    # -----------------------------------
    if provider_override in (None, "POLYGON") and router.is_available("POLYGON"):
        try:
            start_time = time.time()
            router.wait_for_provider("POLYGON")
            polygon_key = get_secret("POLYGON_API_KEY")

            df = polygon_history(
                symbol=sym,
                period=period,
                interval=interval,
                api_key=polygon_key,
                timeout=15,
            )

            if df is not None and not df.empty:
                latency_ms = (time.time() - start_time) * 1000
                router.mark_success("POLYGON", latency_ms=latency_ms)

                if interval == "1d" and db is not None:
                    _save_history_to_db(db, sym, df)
                else:
                    print(f"SKIPPING DB SAVE FOR INTRADAY HISTORY: {sym} {period} {interval}")

                CACHE[cache_key] = df
                return df

            router.mark_failure("POLYGON")

        except Exception as e:
            if is_rate_limit_error(e):
                router.mark_rate_limited("POLYGON", cooldown_minutes=15)
            else:
                router.mark_failure("POLYGON")
            print(f"POLYGON HISTORY ERROR: {sym}", e)

    # -----------------------------------
    # 2. MARKETDATA.APP HISTORY BACKUP
    # -----------------------------------
    if provider_override in (None, "MARKETDATA") and router.is_available("MARKETDATA"):
        try:
            start_time = time.time()
            router.wait_for_provider("MARKETDATA")

            df = marketdata_history(sym, period="5d", interval="1d")

            if df is not None and not df.empty:
                router.mark_success("MARKETDATA", latency_ms=(time.time() - start_time) * 1000)

                if interval == "1d" and db is not None:
                    _save_history_to_db(db, sym, df)
                else:
                    print(f"SKIPPING DB SAVE FOR INTRADAY HISTORY: {sym} {period} {interval}")

                CACHE[cache_key] = df
                return df

            router.mark_failure("MARKETDATA")

        except Exception as e:
            if is_rate_limit_error(e):
                router.mark_rate_limited("MARKETDATA", cooldown_minutes=15)
            else:
                router.mark_failure("MARKETDATA")
            print(f"MARKETDATA HISTORY ERROR: {sym}", e)

    # -----------------------------------
    # 3. ALPHA VANTAGE HISTORY BACKUP
    # -----------------------------------
    if provider_override in (None, "ALPHA_VANTAGE") and router.is_available("ALPHA_VANTAGE"):
        try:
            start_time = time.time()
            router.wait_for_provider("ALPHA_VANTAGE")

            df = alpha_history(sym, period="5d", interval="1d")

            if df is not None and not df.empty:
                router.mark_success("ALPHA_VANTAGE", latency_ms=(time.time() - start_time) * 1000)

                if interval == "1d" and db is not None:
                    _save_history_to_db(db, sym, df)
                else:
                    print(f"SKIPPING DB SAVE FOR INTRADAY HISTORY: {sym} {period} {interval}")

                CACHE[cache_key] = df
                return df

            router.mark_failure("ALPHA_VANTAGE")

        except Exception as e:
            if is_rate_limit_error(e):
                router.mark_rate_limited("ALPHA_VANTAGE", cooldown_minutes=60)
            else:
                router.mark_failure("ALPHA_VANTAGE")
            print(f"ALPHA HISTORY ERROR: {sym}", e)

    return _empty_history()


def get_price_history(
    db,
    symbol,
    period="1y",
    interval="1d",
    force_refresh=False,
):
    from modules.market_data.autonomous_market_data_orchestrator import (
        get_autonomous_market_data_orchestrator,
    )

    orchestrator = get_autonomous_market_data_orchestrator()

    result = orchestrator.fetch_price_history(
        db=db,
        symbol=symbol,
        period=period,
        interval=interval,
    )

    df = result.get("data")
    if df is not None:
        return df

    return pd.DataFrame()


# ---------------------------------------------------
# BULK PRICE FETCH
# ---------------------------------------------------

def get_prices_many(db, symbols):
    results = {}

    clean_symbols = []
    for s in symbols or []:
        sym = _valid_base_symbol(s)
        if sym and sym not in clean_symbols:
            clean_symbols.append(sym)

    if not clean_symbols:
        return results

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

        results[sym] = pd.DataFrame()

    return results


# ---------------------------------------------------
# LATEST PRICE HELPERS
# ---------------------------------------------------

def _latest_from_history_provider(provider_name: str, symbol: str):
    """
    Latest-price fallback for providers that only have history functions here.

    Important: POLYGON latest quotes are intentionally NOT called here. Your
    Polygon history route works, but the latest/trade quote endpoint produced
    403/429 in this environment. For latest-price requests, POLYGON returns
    None so the caller's failover loop can continue to MARKETDATA, ALPHA, then
    FINNHUB instead of poisoning the run with Polygon quote failures.
    """
    sym = _valid_base_symbol(symbol)
    if not sym:
        return None

    provider_name = str(provider_name or "").upper().strip()
    router = get_provider_router()

    if provider_name == "POLYGON":
        print(f"SKIPPING POLYGON LATEST QUOTE: {sym}")
        return None

    if not router.is_available(provider_name):
        return None

    try:
        router.wait_for_provider(provider_name)

        if provider_name == "MARKETDATA":
            df = marketdata_history(sym, period="5d", interval="1d")

        elif provider_name == "ALPHA_VANTAGE":
            df = alpha_history(
                sym,
                period="5d",
                interval="1d",
            )

        elif provider_name == "TWELVEDATA":
            try:
                from modules.market_data.providers.twelvedata_provider import (
                    get_history as twelvedata_history,
                )
            except Exception:
                return None

            df = twelvedata_history(
                sym,
                period="5d",
                interval="1d",
            )

        else:
            return None

        df = _normalize_df(df)
        if df is None or df.empty or "Close" not in df.columns:
            return None

        close = pd.to_numeric(df["Close"], errors="coerce").dropna()
        if close.empty:
            return None

        return _coerce_price_payload(close.iloc[-1])

    except Exception as e:
        if is_rate_limit_error(e):
            router.mark_rate_limited(provider_name, cooldown_minutes=15)
        else:
            router.mark_failure(provider_name)

        print(f"LATEST PRICE HISTORY FALLBACK ERROR: {provider_name} {sym} {e}")
        return None


# ---------------------------------------------------
# LATEST PRICE
# ---------------------------------------------------

def get_latest_price_internal(symbol: str, provider_override: str | None = None):
    sym = _valid_base_symbol(symbol)
    if not sym:
        return None

    cached = _get_cached_latest_price(sym)
    if cached is not None:
        return cached

    provider = str(provider_override).upper().strip() if provider_override else None

    provider_order = [provider] if provider else [
        "MARKETDATA",
        "ALPHA_VANTAGE",
        "FINNHUB",
    ]

    for provider_name in provider_order:
        try:
            if provider_name == "POLYGON":
                return None

            if provider_name == "FINNHUB":
                if _provider_disabled("finnhub"):
                    return None
                price = _coerce_price_payload(_get_price_finnhub(sym))

            elif provider_name == "MARKETDATA":
                price = _latest_from_history_provider("MARKETDATA", sym)

            elif provider_name == "ALPHA_VANTAGE":
                price = _latest_from_history_provider("ALPHA_VANTAGE", sym)

            else:
                price = None

            if price is not None and price > 0:
                _cache_latest_price(sym, price)
                return price

        except Exception as e:
            print(f"PRICE FETCH ERROR ({provider_name}): {sym} {e}")

    return None


def get_latest_price(
    symbol: str,
    db=None,
):
    # Single-symbol route can still use the orchestrator.
    from modules.market_data.autonomous_market_data_orchestrator import (
        get_autonomous_market_data_orchestrator,
    )

    orchestrator = get_autonomous_market_data_orchestrator()

    result = orchestrator.fetch_latest_price(
        db=db,
        symbol=symbol,
    )

    if isinstance(result, dict):
        return result.get("price")

    return None


# ---------------------------------------------------
# LATEST PRICE MAP
# ---------------------------------------------------

def get_latest_prices(symbols):
    out: Dict[str, float] = {}

    clean_symbols = []
    for s in symbols or []:
        sym = _valid_base_symbol(s)
        if sym and sym not in clean_symbols:
            clean_symbols.append(sym)

    if not clean_symbols:
        return out

    for sym in clean_symbols:
        cached = _get_cached_latest_price(sym)
        if cached is not None:
            out[sym] = cached

    missing = [s for s in clean_symbols if s not in out]
    if not missing:
        return out

    # Finnhub pass. It is not true batch, but this preserves current behavior.
    if not _provider_disabled("finnhub"):
        for sym in missing:
            if _provider_disabled("finnhub"):
                break

            payload = _get_price_finnhub(sym)
            price = _coerce_price_payload(payload)

            if price is not None and price > 0:
                out[sym] = price
                _cache_latest_price(sym, price)

    missing = [s for s in clean_symbols if s not in out]

    # Important: only fallback for small lists like Alpha Engine.
    # Do not do 100 MarketData/Alpha history calls for recommendation scans.
    if len(clean_symbols) <= 20:
        for sym in missing:
            price = get_latest_price_internal(sym, provider_override="MARKETDATA")
            price = _coerce_price_payload(price)

            if price is not None and price > 0:
                out[sym] = price
                _cache_latest_price(sym, price)

    return out


def get_latest_price_map(symbols):
    print("=" * 80)
    print("GET_LATEST_PRICE_MAP")
    print("COUNT:", len(symbols or []))
    print("FIRST 20:", list(symbols or [])[:20])
    print("=" * 80)

    return get_latest_prices(symbols)


# ---------------------------------------------------
# CACHE MGMT
# ---------------------------------------------------

def clear_price_cache():
    CACHE.clear()
    _FAILED_SYMBOLS.clear()
    _LATEST_PRICE_CACHE.clear()
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
    **kwargs,
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
            df = get_price_history(db, sym, period=period, interval=interval)
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
        polygon_key = get_secret("POLYGON_API_KEY")

        df = polygon_history(
            symbol=symbol,
            period=period,
            interval="1d",
            api_key=polygon_key,
            timeout=15,
        )

        if df is not None and not df.empty:
            return _normalize_df(df)

    except Exception as e:
        print("POLYGON MASSIVE FALLBACK ERROR:", symbol, e)

    return _empty_history()


def preload_histories(
    db,
    symbols,
    period="1y",
    interval="1d",
):
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


# ---------------------------------------------------
# PRICE HISTORY PERSISTENCE
# ---------------------------------------------------

def _save_history_to_db(
    db,
    symbol: str,
    df: pd.DataFrame,
):
    """
    Persist normalized daily price history using one bulk upsert.
    """

    if db is None:
        return 0

    if df is None or df.empty:
        return 0

    sym = _valid_base_symbol(symbol)
    if not sym:
        return 0

    try:
        work_df = df.copy()

        if "Date" not in work_df.columns:
            print("PRICE HISTORY SAVE SKIPPED - missing Date column:", sym)
            return 0

        work_df["Date"] = pd.to_datetime(work_df["Date"], errors="coerce")

        try:
            if getattr(work_df["Date"].dt, "tz", None) is not None:
                work_df["Date"] = work_df["Date"].dt.tz_convert(None)
        except Exception:
            try:
                work_df["Date"] = work_df["Date"].dt.tz_localize(None)
            except Exception:
                pass

        work_df = work_df.dropna(subset=["Date"])
        if work_df.empty:
            return 0

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in work_df.columns:
                work_df[col] = 0.0
            work_df[col] = pd.to_numeric(work_df[col], errors="coerce")

        work_df = work_df.dropna(subset=["Close"])
        if work_df.empty:
            return 0

        work_df["Date"] = work_df["Date"].dt.date
        work_df = (
            work_df
            .sort_values("Date")
            .groupby("Date", as_index=False)
            .agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            })
        )

        payload = []
        for _, row in work_df.iterrows():
            payload.append({
                "symbol": sym,
                "date": row["Date"],
                "open": float(row["Open"] or 0.0),
                "high": float(row["High"] or 0.0),
                "low": float(row["Low"] or 0.0),
                "close": float(row["Close"] or 0.0),
                "volume": float(row["Volume"] or 0.0),
            })

        if not payload:
            return 0

        upsert_sql = text("""
            INSERT INTO price_history (
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume
            )
            VALUES (
                :symbol,
                :date,
                :open,
                :high,
                :low,
                :close,
                :volume
            )
            ON CONFLICT (symbol, date)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """)

        db.execute(upsert_sql, payload)
        db.commit()

        rows_saved = len(payload)
        print(f"✅ SAVED {rows_saved} ROWS:", sym)
        return rows_saved

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass

        print("PRICE HISTORY SAVE ERROR:", sym, e)
        return 0
