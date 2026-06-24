from __future__ import annotations

"""
modules/options/providers/massive_provider.py

Massive/Polygon options provider for the StockApp options provider router.

Design goals:
- Preserve the legacy options provider return shape via build_chain_payload().
- Keep Massive at low request volume through in-memory TTL caches.
- Avoid crawling the entire options universe for high-volume underlyings like SPY.
- Load one selected expiration at a time for quotes/greeks.
- Return clean provider errors so the router can fail over safely.

Expected router interface:
    get_chain(ticker: str, expiration: str | None = None) -> dict
"""

import time
from datetime import date
from typing import Any

import pandas as pd
import requests

from modules.options.providers.common import (
    build_chain_payload,
    calc_dte,
    get_secret,
    safe_float,
)

BASE_URL = "https://api.polygon.io"

# Conservative defaults to protect the provider quota.
EXPIRATION_CACHE_TTL_SECONDS = 60 * 60          # 1 hour
CHAIN_CACHE_TTL_SECONDS = 5 * 60                # 5 minutes
RATE_LIMIT_COOLDOWN_SECONDS = 10 * 60           # 10 minutes
REQUEST_TIMEOUT = (10, 45)

# Reference endpoint can be huge for SPY/QQQ. With sorting by expiration_date,
# the first pages provide near-term expirations without walking the full universe.
MAX_EXPIRATION_PAGES = 2
MAX_EXPIRATIONS = 40

# Snapshot options endpoint is per expiration. A few pages is enough for most
# listed expirations while preventing accidental runaway pagination.
MAX_SNAPSHOT_PAGES = 4
SNAPSHOT_LIMIT = 250

_EXPIRATION_CACHE: dict[str, tuple[float, list[str]]] = {}
_CHAIN_CACHE: dict[str, tuple[float, dict]] = {}
_RATE_LIMITED_UNTIL = 0.0


def _api_key() -> str | None:
    return (
        get_secret("MASSIVE_API_KEY")
        or get_secret("POLYGON_API_KEY")
        or get_secret("POLYGON_API")
    )


def _today_iso() -> str:
    return date.today().isoformat()


def _cache_get(cache: dict[str, tuple[float, Any]], key: str, ttl: int):
    entry = cache.get(key)
    if not entry:
        return None

    ts, value = entry
    if time.time() - ts > ttl:
        cache.pop(key, None)
        return None

    return value


def _cache_set(cache: dict[str, tuple[float, Any]], key: str, value):
    cache[key] = (time.time(), value)
    return value


def clear_massive_provider_cache() -> None:
    """Optional helper for tests/manual refresh."""
    _EXPIRATION_CACHE.clear()
    _CHAIN_CACHE.clear()


def _is_rate_limited() -> bool:
    return time.time() < _RATE_LIMITED_UNTIL


def _mark_rate_limited() -> None:
    global _RATE_LIMITED_UNTIL
    _RATE_LIMITED_UNTIL = time.time() + RATE_LIMIT_COOLDOWN_SECONDS


def _normalize_option_symbol(symbol: Any) -> str:
    """Convert Polygon/Massive option ticker O:SPY... to Alpaca/OCC-like SPY..."""
    s = str(symbol or "").strip().upper()
    if s.startswith("O:"):
        return s[2:]
    return s


def _contract_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in ("call", "calls", "c"):
        return "call"
    if raw in ("put", "puts", "p"):
        return "put"
    return raw


def _request_json(url: str, params: dict[str, Any] | None = None) -> dict:

    if _is_rate_limited():
        raise RuntimeError(
            "RATE_LIMIT: Massive provider cooling down after 429"
        )

    api_key = _api_key()

    if not api_key:
        raise RuntimeError(
            "No MASSIVE_API_KEY configured"
        )

    request_params = dict(params or {})
    request_params["apiKey"] = api_key

    response = requests.get(
        url,
        params=request_params,
        timeout=REQUEST_TIMEOUT,
    )

    print("=" * 80)
    print("MASSIVE REQUEST")
    print("URL:", response.url)
    print("STATUS:", response.status_code)
    print("=" * 80)

    if response.status_code == 429:

        print("=" * 80)
        print("MASSIVE RATE LIMIT")
        print(response.text[:2000])
        print("=" * 80)

        _mark_rate_limited()

        raise RuntimeError(
            f"RATE_LIMIT: Massive returned 429: "
            f"{response.text[:300]}"
        )

    if response.status_code in (401, 403):

        print("=" * 80)
        print("MASSIVE AUTH FAILURE")
        print(response.text[:2000])
        print("=" * 80)

        raise RuntimeError(
            f"Massive authorization error "
            f"{response.status_code}: "
            f"{response.text[:300]}"
        )

    if response.status_code != 200:

        print("=" * 80)
        print("MASSIVE REQUEST FAILURE")
        print(response.text[:2000])
        print("=" * 80)

        raise RuntimeError(
            f"Massive returned "
            f"{response.status_code}: "
            f"{response.text[:300]}"
        )

    try:

        data = response.json()

        print("=" * 80)
        print("MASSIVE JSON KEYS")
        print(list(data.keys()))

        if "status" in data:
            print("STATUS:", data.get("status"))

        if "message" in data:
            print("MESSAGE:", data.get("message"))

        if "results" in data:
            print(
                "RESULT COUNT:",
                len(data.get("results") or [])
            )

        print("=" * 80)

        return data

    except Exception as exc:

        print("=" * 80)
        print("MASSIVE INVALID JSON")
        print(response.text[:2000])
        print("=" * 80)

        raise RuntimeError(
            f"Massive returned invalid JSON: {exc}"
        ) from exc


def get_expirations(ticker: str) -> list[str]:
    """
    Return a bounded, cached list of option expiration dates.
    """

    ticker = str(ticker or "").upper().strip()

    if not ticker:
        return []

    if not _api_key():
        print("MASSIVE: NO API KEY")
        return []

    cached = _cache_get(
        _EXPIRATION_CACHE,
        ticker,
        EXPIRATION_CACHE_TTL_SECONDS,
    )

    if cached is not None:
        print(f"MASSIVE CACHE HIT: {ticker}")
        return list(cached)

    expirations: set[str] = set()

    url = f"{BASE_URL}/v3/reference/options/contracts"

    params = {
        "underlying_ticker": ticker,
        "limit": 1000,
        "sort": "expiration_date",
        "order": "asc",
    }

    page_count = 0

    while (
        url
        and page_count < MAX_EXPIRATION_PAGES
        and len(expirations) < MAX_EXPIRATIONS
    ):

        page_count += 1

        print("=" * 80)
        print("MASSIVE EXPIRATION REQUEST")
        print("PAGE:", page_count)
        print("URL:", url)
        print("PARAMS:", params)
        print("=" * 80)

        try:
            data = _request_json(
                url,
                params=params,
            )

        except Exception as e:

            print("=" * 80)
            print("MASSIVE EXPIRATION EXCEPTION")
            print(str(e))
            print("=" * 80)

            break

        print("=" * 80)
        print("MASSIVE EXPIRATION RESPONSE")
        print("PAGE:", page_count)
        print("KEYS:", list(data.keys()))

        if "status" in data:
            print("STATUS:", data.get("status"))

        if "message" in data:
            print("MESSAGE:", data.get("message"))

        results = data.get("results", []) or []

        print("RESULT COUNT:", len(results))

        if results:
            print("FIRST RESULT:")
            print(results[0])

        print("=" * 80)

        for item in results:

            exp = item.get("expiration_date")

            if exp:

                expirations.add(str(exp)[:10])

                if len(expirations) >= MAX_EXPIRATIONS:
                    break

        next_url = data.get("next_url")

        print("NEXT URL:", bool(next_url))

        if not next_url:
            break

        url = next_url

        # next_url already contains cursor params
        params = {}

    out = sorted(expirations)

    print("=" * 80)
    print("EXPIRATIONS FOUND")
    print(out)
    print("COUNT:", len(out))
    print("=" * 80)

    return _cache_set(
        _EXPIRATION_CACHE,
        ticker,
        out,
    )


def _snapshot_rows_for_expiration(ticker: str, expiry: str) -> list[dict[str, Any]]:
    url = f"{BASE_URL}/v3/snapshot/options/{ticker.upper()}"
    params: dict[str, Any] = {
        "expiration_date": expiry,
        "limit": SNAPSHOT_LIMIT,
    }

    rows: list[dict[str, Any]] = []
    page_count = 0

    while url and page_count < MAX_SNAPSHOT_PAGES:
        page_count += 1

        data = _request_json(url, params=params)

        for contract in data.get("results", []) or []:
            parsed = _parse_snapshot_contract(contract, ticker, expiry)
            if parsed.get("option_symbol"):
                rows.append(parsed)

        next_url = data.get("next_url")
        if not next_url:
            break

        url = next_url
        params = {}

    return rows


def get_chain(
    ticker: str,
    expiration: str | None = None,
) -> dict:
    """Return normalized options chain data for one expiration.

    If expiration is omitted, the nearest expiration is loaded, but the returned
    payload also includes the cached expiration list so the UI can populate the
    selector without loading every expiration's chain.
    """
    ticker = str(ticker or "").upper().strip()
    if not ticker:
        return build_chain_payload(
            ticker,
            pd.DataFrame(),
            "massive",
            "Ticker is required",
        )

    if not _api_key():
        return build_chain_payload(
            ticker,
            pd.DataFrame(),
            "massive",
            "No MASSIVE_API_KEY configured",
        )

    cache_key = f"{ticker}:{expiration or 'nearest'}"
    cached = _cache_get(_CHAIN_CACHE, cache_key, CHAIN_CACHE_TTL_SECONDS)
    if cached is not None and not cached.get("error"):
        return cached

    try:
        expirations = [str(expiration)[:10]] if expiration else get_expirations(ticker)

        if not expirations:
            return build_chain_payload(
                ticker,
                pd.DataFrame(),
                "massive",
                f"No expirations returned for {ticker}",
            )

        selected_expiry = expirations[0]
        try:
            rows = _snapshot_rows_for_expiration(
                ticker,
                selected_expiry,
            )

        except RuntimeError as exc:

            if "authorization" in str(exc).lower():
                return build_chain_payload(
                    ticker,
                    pd.DataFrame(),
                    "massive",
                    f"Massive snapshot entitlement missing: {exc}",
                )

            raise
        df = pd.DataFrame(rows)

        if df.empty:
            payload = build_chain_payload(
                ticker,
                df,
                "massive",
                f"Massive returned no options rows for {ticker} {selected_expiry}",
            )
            return _cache_set(_CHAIN_CACHE, cache_key, payload)

        payload = build_chain_payload(ticker, df, "massive")

        # Preserve expiration selector behavior without loading all chains.
        if not expiration:
            payload["expirations"] = expirations
        else:
            payload["expirations"] = [selected_expiry]

        payload["provider"] = "massive"
        payload["source"] = "massive"
        payload["contracts"] = int(len(df))

        return _cache_set(_CHAIN_CACHE, cache_key, payload)

    except RuntimeError as exc:
        return build_chain_payload(
            ticker,
            pd.DataFrame(),
            "massive",
            str(exc),
        )
    except Exception as exc:
        return build_chain_payload(
            ticker,
            pd.DataFrame(),
            "massive",
            f"Massive options error: {exc}",
        )
