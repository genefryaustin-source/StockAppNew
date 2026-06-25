"""
modules/forex/providers/alpha_vantage_forex_provider.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

BASE_URL = "https://www.alphavantage.co/query"


def _normalize(pair: str):
    p = pair.upper().replace("-", "/").replace("_", "/")
    if "/" in p:
        b, q = p.split("/", 1)
    else:
        b, q = p[:3], p[3:6]
    return b[:3], q[:3], f"{b[:3]}/{q[:3]}"


def _api_key():
    return (
        os.getenv("ALPHA_VANTAGE_API_KEY")
        or os.getenv("ALPHAVANTAGE_API_KEY")
        or os.getenv("ALPHA_VANTAGE_KEY")
        or ""
    )


def get_quote(pair: str) -> dict:
    key = _api_key()
    if not key:
        return {"error": "Alpha Vantage API key not configured", "provider": "alpha_vantage_fx"}

    base, quote, pair = _normalize(pair)

    r = requests.get(
        BASE_URL,
        params={
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": base,
            "to_currency": quote,
            "apikey": key,
        },
        timeout=20,
        headers={"User-Agent": "StockApp Forex"},
    )
    r.raise_for_status()
    data = r.json()

    fx = data.get("Realtime Currency Exchange Rate") or {}
    rate = fx.get("5. Exchange Rate")

    if rate is None:
        return {
            "error": "Alpha Vantage returned no usable rate",
            "provider": "alpha_vantage_fx",
            "raw": data,
        }

    rate = float(rate)

    return {
        "pair": pair,
        "base": base,
        "quote": quote,
        "mid": rate,
        "last": rate,
        "provider": "alpha_vantage_fx",
        "source": "alpha_vantage",
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw": data,
    }


def get_quotes(pairs):
    return {p: get_quote(p) for p in pairs}


def provider_name():
    return "alpha_vantage_fx"


def health_check():
    try:
        q = get_quote("EUR/USD")
        return {
            "provider": "alpha_vantage_fx",
            "healthy": not bool(q.get("error")),
            "sample": q,
        }
    except Exception as exc:
        return {
            "provider": "alpha_vantage_fx",
            "healthy": False,
            "error": str(exc),
        }
