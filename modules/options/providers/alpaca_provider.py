from __future__ import annotations

import re
from typing import Any

import pandas as pd
import requests

from modules.options.providers.common import build_chain_payload, calc_dte, get_secret, safe_float

_OCC_RE = re.compile(r"^(?P<root>[A-Z.]+)(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<type>[CP])(?P<strike>\d{8})$")


def _key_id() -> str | None:
    return (
        get_secret("ALPACA_API_KEY")
        or get_secret("ALPACA_API_KEY_ID")
        or get_secret("APCA_API_KEY_ID")
    )


def _secret_key() -> str | None:
    return (
        get_secret("ALPACA_API_SECRET")
        or get_secret("ALPACA_API_SECRET_KEY")
        or get_secret("APCA_API_SECRET_KEY")
    )


def _trading_base_url() -> str:
    return (get_secret("ALPACA_BASE_URL") or "https://paper-api.alpaca.markets").rstrip("/")


def _data_base_url() -> str:
    return (get_secret("ALPACA_DATA_BASE_URL") or "https://data.alpaca.markets").rstrip("/")


def _headers(key_id: str, secret: str) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": key_id,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
    }


def _parse_occ_symbol(symbol: str) -> dict[str, Any] | None:
    m = _OCC_RE.match(str(symbol or "").strip().upper())
    if not m:
        return None
    yy, mm, dd = m.group("yy"), m.group("mm"), m.group("dd")
    return {
        "root": m.group("root"),
        "expiry": f"20{yy}-{mm}-{dd}",
        "type": "call" if m.group("type") == "C" else "put",
        "strike": int(m.group("strike")) / 1000.0,
    }


def get_expirations(ticker: str) -> list[str]:
    key_id, secret = _key_id(), _secret_key()
    if not key_id or not secret:
        return []

    r = requests.get(
        f"{_trading_base_url()}/v2/options/contracts",
        headers=_headers(key_id, secret),
        params={"underlying_symbols": ticker.upper(), "status": "active", "limit": 1000},
        timeout=(10, 30),
    )
    if r.status_code == 429:
        raise RuntimeError(f"RATE_LIMIT: Alpaca contracts returned 429: {r.text[:300]}")
    if r.status_code not in (200,):
        return []

    data = r.json()