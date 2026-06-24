from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from modules.options.providers.common import build_chain_payload, calc_dte, get_secret, safe_float


def _idx(data: dict, field: str, i: int) -> Any:
    try:
        return data[field][i]
    except Exception:
        return None


def get_expirations(ticker: str) -> list[str]:
    key = get_secret("MARKETDATA_API_KEY")
    if not key:
        return []

    r = requests.get(
        f"https://api.marketdata.app/v1/options/expirations/{ticker.upper()}/",
        headers={"Authorization": f"Token {key}", "Accept": "application/json"},
        params={"dateformat": "timestamp"},
        timeout=(10, 30),
    )
    if r.status_code == 429:
        raise RuntimeError(f"RATE_LIMIT: MarketData expirations returned 429: {r.text[:300]}")
    if r.status_code not in (200, 203):
        return []

    data = r.json()
    expirations = data.get("expirations") or data.get("expiration") or []
    return sorted([str(x)[:10] for x in expirations if x])


def get_chain(ticker: str, expiration: str | None = None) -> dict:
    key = get_secret("MARKETDATA_API_KEY")
    if not key:
        print("=" * 80)
        print("MARKETDATA DF EXPIRATIONS")
        print(sorted(df["expiry"].dropna().unique().tolist()))
        print("COUNT:", len(df["expiry"].dropna().unique().tolist()))
        print("=" * 80)
        return build_chain_payload(
            ticker=ticker,
            df=pd.DataFrame(rows),
            source="marketdata",
            expirations=expirations,
        )

    expirations: list[str] = []
    if expiration:
        expirations = [expiration]
    else:
        expirations = get_expirations(ticker)
        print("=" * 80)
        print("MARKETDATA EXPIRATIONS")
        print(expirations[:20])
        print("COUNT:", len(expirations))
        print("=" * 80)

    params = {"dateformat": "timestamp"}
    selected_expiration = expiration or (expirations[0] if expirations else None)

    if selected_expiration:
        params["expiration"] = selected_expiration

    r = requests.get(
        f"https://api.marketdata.app/v1/options/chain/{ticker.upper()}/",
        headers={"Authorization": f"Token {key}", "Accept": "application/json"},
        params=params,
        timeout=(10, 45),
    )

    if r.status_code == 401:
        return build_chain_payload(ticker, pd.DataFrame(), "marketdata", "MarketData.app API key invalid")
    if r.status_code == 402:
        return build_chain_payload(ticker, pd.DataFrame(), "marketdata", "MarketData.app plan does not include options")
    if r.status_code == 429:
        raise RuntimeError(f"RATE_LIMIT: MarketData options chain returned 429: {r.text[:300]}")
    if r.status_code not in (200, 203):
        return build_chain_payload(ticker, pd.DataFrame(), "marketdata", f"MarketData.app returned {r.status_code}: {r.text[:300]}")

    data = r.json()
    if not isinstance(data, dict) or data.get("s") == "error" or not data.get("optionSymbol"):
        return build_chain_payload(ticker, pd.DataFrame(), "marketdata", f"MarketData.app returned no options rows for {ticker}")

    rows = []
    n = len(data.get("optionSymbol") or [])
    for i in range(n):
        expiry = str(_idx(data, "expiration", i) or "")[:10]
        bid = safe_float(_idx(data, "bid", i), None)
        ask = safe_float(_idx(data, "ask", i), None)
        mid = safe_float(_idx(data, "mid", i), None)
        if mid is None and bid is not None and ask is not None and bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0
        rows.append({
            "option_symbol": _idx(data, "optionSymbol", i),
            "expiry": expiry,
            "expiration": expiry,
            "strike": safe_float(_idx(data, "strike", i), None),
            "type": str(_idx(data, "side", i) or "").lower(),
            "side": str(_idx(data, "side", i) or "").lower(),
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "last": safe_float(_idx(data, "last", i), None),
            "volume": safe_float(_idx(data, "volume", i), 0.0),
            "open_interest": safe_float(_idx(data, "openInterest", i), 0.0),
            "iv": safe_float(_idx(data, "iv", i), None),
            "delta": safe_float(_idx(data, "delta", i), None),
            "gamma": safe_float(_idx(data, "gamma", i), None),
            "theta": safe_float(_idx(data, "theta", i), None),
            "vega": safe_float(_idx(data, "vega", i), None),
            "dte": safe_float(_idx(data, "dte", i), None) or calc_dte(expiry),
            "underlying": _idx(data, "underlying", i) or ticker.upper(),
            "underlying_price": safe_float(_idx(data, "underlyingPrice", i), None),
            "in_the_money": _idx(data, "inTheMoney", i),
        })
    print("=" * 80)
    print("MARKETDATA EXPIRATIONS")
    print(expirations)
    print("COUNT:", len(expirations))
    print("=" * 80)
    return build_chain_payload(
        ticker=ticker,
        df=pd.DataFrame(rows),
        source="marketdata",
        expirations=expirations,
    )
