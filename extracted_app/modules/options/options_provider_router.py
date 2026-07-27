from __future__ import annotations

import time
from typing import Callable

import pandas as pd

from modules.options.providers import (
    massive_provider,
    finnhub_provider,
    marketdata_provider,
    tradier_provider,
    yahoo_provider,
)
from modules.options.providers.common import build_chain_payload

_CHAIN_CACHE: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 300
_PROVIDER_COOLDOWNS: dict[str, float] = {}
_RATE_LIMIT_COOLDOWN_SECONDS = 15 * 60

ProviderFn = Callable[[str, str | None], dict]

_PROVIDER_ORDER: list[tuple[str, ProviderFn]] = [
    ("massive", massive_provider.get_chain),
    ("marketdata", marketdata_provider.get_chain),
    ("tradier", tradier_provider.get_chain),
    ("finnhub", finnhub_provider.get_chain),
    ("yahoo", yahoo_provider.get_chain),
]


def _cache_key(ticker: str, expiration: str | None = None) -> str:
    return f"{str(ticker).upper().strip()}:{expiration or 'nearest'}"


def _get_cached(key: str) -> dict | None:
    entry = _CHAIN_CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL_SECONDS:
        return entry["data"]
    return None


def _set_cached(key: str, data: dict) -> dict:
    _CHAIN_CACHE[key] = {"ts": time.time(), "data": data}
    return data


def clear_options_chain_cache() -> None:
    _CHAIN_CACHE.clear()


def _provider_available(provider: str) -> bool:
    until = _PROVIDER_COOLDOWNS.get(provider, 0)
    return time.time() >= until


def _mark_rate_limited(provider: str) -> None:
    _PROVIDER_COOLDOWNS[provider] = time.time() + _RATE_LIMIT_COOLDOWN_SECONDS


def get_options_chain_from_router(ticker: str, expiration: str | None = None, force_refresh: bool = False) -> dict:
    import traceback

    print("=" * 100)
    print("OPTIONS ROUTER CALLER")
    traceback.print_stack(limit=10)
    print("=" * 100)
    ticker = str(ticker or "").upper().strip()
    if not ticker:
        return build_chain_payload(ticker, pd.DataFrame(), "router", "Ticker is required")

    key = _cache_key(ticker, expiration)
    if not force_refresh:
        cached = _get_cached(key)
        if cached and not cached.get("error"):
            return cached

    errors: list[str] = []

    for provider_name, provider_fn in _PROVIDER_ORDER:

        print("=" * 100)
        print("OPTIONS ROUTER REQUEST")
        print("PROVIDER:", provider_name)
        print("TICKER:", ticker)
        print("EXPIRATION:", expiration)
        print("=" * 100)
        if not _provider_available(provider_name):
            errors.append(f"{provider_name}: cooling down after rate limit")
            continue

        try:
            result = provider_fn(ticker, expiration)
            print("=" * 100)
            print("OPTIONS ROUTER RESPONSE")
            print("PROVIDER:", provider_name)
            print("TYPE:", type(result))

            if isinstance(result, dict):
                print("KEYS:", list(result.keys()))

                if "error" in result:
                    print("ERROR:", result.get("error"))

                df = result.get("all_rows")

                if isinstance(df, pd.DataFrame):
                    print("ROWS:", len(df))

            print("=" * 100)
        except Exception as e:

            import traceback

            print("=" * 100)
            print("OPTIONS PROVIDER FAILED")
            print("PROVIDER:", provider_name)
            print("ERROR:", str(e))
            traceback.print_exc()
            print("=" * 100)

            msg = str(e)

            if "RATE LIMIT" in msg or "429" in msg:
                _mark_rate_limited(provider_name)
                errors.append(f"{provider_name}: rate limited")
            else:
                errors.append(f"{provider_name}: {msg}")

            continue

        if not isinstance(result, dict):
            errors.append(f"{provider_name}: invalid provider response")
            continue

        df = result.get("all_rows")
        has_rows = isinstance(df, pd.DataFrame) and not df.empty
        has_chain = bool(result.get("chain"))

        if not result.get("error") and (has_rows or has_chain):
            result["provider"] = provider_name
            result["source"] = result.get("source") or provider_name
            result["failover_errors"] = errors
            print("=" * 80)
            print("CHAIN EXPIRATIONS")
            print(result.get("expirations"))
            print("COUNT:", len(result.get("expirations", [])))
            print("=" * 80)
            return _set_cached(key, result)

        if result.get("error"):
            errors.append(f"{provider_name}: {result.get('error')}")
        else:
            errors.append(f"{provider_name}: no contracts returned")

    return {
        "ticker": ticker,
        "chain": {},
        "expirations": [],
        "all_rows": pd.DataFrame(),
        "source": "none",
        "provider": "none",
        "contracts": 0,
        "error": f"No options chain data available for {ticker}.",
        "failover_errors": errors,
    }
