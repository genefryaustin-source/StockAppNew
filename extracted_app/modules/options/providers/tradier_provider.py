from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from modules.options.providers.common import build_chain_payload, calc_dte, get_secret, safe_float


def _token() -> str | None:
    return (
        get_secret("TRADIER_ACCESS_TOKEN")
        or get_secret("TRADIER_API_KEY")
        or get_secret("TRADIER_TOKEN")
    )


def _base_url() -> str:
    return (get_secret("TRADIER_BASE_URL") or "https://api.tradier.com/v1").rstrip("/")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def get_expirations(ticker: str) -> list[str]:
    token = _token()
    if not token:
        return []
    r = requests.get(
        f"{_base_url()}/markets/options/expirations",
        headers=_headers(token),
        params={"symbol": ticker.upper(), "includeAllRoots": "true", "strikes": "false"},
        timeout=(10, 30),
    )
    if r.status_code == 429:
        raise RuntimeError(f"RATE_LIMIT: Tradier expirations returned 429: {r.text[:300]}")
    if r.status_code not in (200, 203):
        return []
    data = r.json()
    dates = data.get("expirations", {}).get("date", []) if isinstance(data, dict) else []
    return sorted([str(x)[:10] for x in _as_list(dates) if x])


def get_chain(ticker: str, expiration: str | None = None) -> dict:
    token = _token()
    if not token:
        return build_chain_payload(ticker, pd.DataFrame(), "tradier", "No TRADIER_ACCESS_TOKEN configured")

    expirations = [expiration] if expiration else get_expirations(ticker)
    if not expirations:
        return build_chain_payload(ticker, pd.DataFrame(), "tradier", f"Tradier returned no expirations for {ticker}")

    r = requests.get(
        f"{_base_url()}/markets/options/chains",
        headers=_headers(token),
        params={"symbol": ticker.upper(), "expiration": expirations[0], "greeks": "true"},
        timeout=(10, 45),
    )
    if r.status_code == 401:
        return build_chain_payload(ticker, pd.DataFrame(), "tradier", "Tradier token invalid")
    if r.status_code == 429:
        raise RuntimeError(f"RATE_LIMIT: Tradier options chain returned 429: {r.text[:300]}")
    if r.status_code not in (200, 203):
        return build_chain_payload(ticker, pd.DataFrame(), "tradier", f"Tradier returned {r.status_code}: {r.text[:300]}")

    data = r.json()
    options = data.get("options", {}).get("option", []) if isinstance(data, dict) else []
    options = _as_list(options)
    if not options:
        return build_chain_payload(ticker, pd.DataFrame(), "tradier", f"Tradier returned no option rows for {ticker}")

    rows = []
    for item in options:
        if not isinstance(item, dict):
            continue
        greeks = item.get("greeks") if isinstance(item.get("greeks"), dict) else {}
        expiry = str(item.get("expiration_date") or expirations[0])[:10]
        bid = safe_float(item.get("bid"), None)
        ask = safe_float(item.get("ask"), None)
        mid = None
        if bid is not None and ask is not None and bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0
        rows.append({
            "option_symbol": item.get("symbol") or item.get("option_symbol") or "",
            "expiry": expiry,
            "expiration": expiry,
            "strike": safe_float(item.get("strike"), None),
            "type": str(item.get("option_type") or item.get("type") or "").lower(),
            "side": str(item.get("option_type") or item.get("type") or "").lower(),
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "last": safe_float(item.get("last"), None),
            "volume": safe_float(item.get("volume"), 0.0),
            "open_interest": safe_float(item.get("open_interest"), 0.0),
            "iv": safe_float(greeks.get("mid_iv", greeks.get("smv_vol", greeks.get("iv"))), None),
            "delta": safe_float(greeks.get("delta"), None),
            "gamma": safe_float(greeks.get("gamma"), None),
            "theta": safe_float(greeks.get("theta"), None),
            "vega": safe_float(greeks.get("vega"), None),
            "dte": calc_dte(expiry),
            "underlying": ticker.upper(),
            "underlying_price": None,
        })
    return build_chain_payload(ticker, pd.DataFrame(rows), "tradier")
