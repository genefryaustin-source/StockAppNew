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
    contracts = data.get("option_contracts", []) if isinstance(data, dict) else []
    dates = {
        str(c.get("expiration_date"))[:10]
        for c in contracts
        if isinstance(c, dict) and c.get("expiration_date")
    }
    return sorted(dates)


def get_chain(ticker: str, expiration: str | None = None) -> dict:
    key_id, secret = _key_id(), _secret_key()
    if not key_id or not secret:
        return build_chain_payload(ticker, pd.DataFrame(), "alpaca", "No ALPACA_API_KEY/ALPACA_API_SECRET configured")

    expirations = [expiration] if expiration else get_expirations(ticker)
    if not expirations:
        return build_chain_payload(ticker, pd.DataFrame(), "alpaca", f"Alpaca returned no expirations for {ticker}")

    target_expiry = expirations[0]
    rows: list[dict] = []
    page_token = None

    while True:
        params = {
            "feed": get_secret("ALPACA_OPTIONS_FEED") or "indicative",
            "expiration_date": target_expiry,
            "limit": 1000,
        }
        if page_token:
            params["page_token"] = page_token

        r = requests.get(
            f"{_data_base_url()}/v1beta1/options/snapshots/{ticker.upper()}",
            headers=_headers(key_id, secret),
            params=params,
            timeout=(10, 45),
        )
        if r.status_code in (401, 403):
            return build_chain_payload(ticker, pd.DataFrame(), "alpaca", f"Alpaca returned {r.status_code}: {r.text[:300]}")
        if r.status_code == 429:
            raise RuntimeError(f"RATE_LIMIT: Alpaca snapshots returned 429: {r.text[:300]}")
        if r.status_code != 200:
            return build_chain_payload(ticker, pd.DataFrame(), "alpaca", f"Alpaca returned {r.status_code}: {r.text[:300]}")

        data = r.json()
        snapshots = data.get("snapshots", {}) if isinstance(data, dict) else {}

        for symbol, snap in snapshots.items():
            if not isinstance(snap, dict):
                continue
            parsed = _parse_occ_symbol(symbol)
            if not parsed:
                continue

            quote = snap.get("latestQuote") if isinstance(snap.get("latestQuote"), dict) else {}
            trade = snap.get("latestTrade") if isinstance(snap.get("latestTrade"), dict) else {}
            daily = snap.get("dailyBar") if isinstance(snap.get("dailyBar"), dict) else {}
            greeks = snap.get("greeks") if isinstance(snap.get("greeks"), dict) else {}

            bid = safe_float(quote.get("bp"), None)
            ask = safe_float(quote.get("ap"), None)
            mid = None
            if bid is not None and ask is not None and bid > 0 and ask > 0:
                mid = (bid + ask) / 2.0

            rows.append({
                "option_symbol": symbol,
                "expiry": parsed["expiry"],
                "expiration": parsed["expiry"],
                "strike": parsed["strike"],
                "type": parsed["type"],
                "side": parsed["type"],
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "last": safe_float(trade.get("p"), None),
                "volume": safe_float(daily.get("v"), 0.0),
                "open_interest": None,  # not provided by Alpaca's snapshot endpoint
                "iv": safe_float(snap.get("impliedVolatility"), None),
                "delta": safe_float(greeks.get("delta"), None),
                "gamma": safe_float(greeks.get("gamma"), None),
                "theta": safe_float(greeks.get("theta"), None),
                "vega": safe_float(greeks.get("vega"), None),
                "dte": calc_dte(parsed["expiry"]),
                "underlying": ticker.upper(),
                "underlying_price": None,
            })

        page_token = data.get("next_page_token") if isinstance(data, dict) else None
        if not page_token:
            break

    if not rows:
        return build_chain_payload(ticker, pd.DataFrame(), "alpaca", f"Alpaca returned no option rows for {ticker}")

    return build_chain_payload(ticker, pd.DataFrame(rows), "alpaca")