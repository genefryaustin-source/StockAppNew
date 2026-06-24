from __future__ import annotations

import pandas as pd
import requests

from modules.options.providers.common import build_chain_payload, calc_dte, get_secret, safe_float


def get_chain(ticker: str, expiration: str | None = None) -> dict:
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return build_chain_payload(ticker, pd.DataFrame(), "finnhub", "No FINNHUB_API_KEY configured")
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/option-chain",
            params={"symbol": ticker.upper(), "token": key},
            timeout=(10, 30),
        )
        if r.status_code == 429:
            raise RuntimeError(f"RATE_LIMIT: Finnhub options chain returned 429: {r.text[:300]}")
        if r.status_code != 200:
            return build_chain_payload(ticker, pd.DataFrame(), "finnhub", f"Finnhub returned {r.status_code}: {r.text[:300]}")
        data = r.json()
        rows = []
        # Finnhub formats vary by entitlement; support common nested structure.
        for block in data.get("data", []) if isinstance(data, dict) else []:
            exp = str(block.get("expirationDate") or block.get("expiration") or expiration or "")[:10]
            for side_key, opt_type in (("calls", "call"), ("puts", "put"), ("call", "call"), ("put", "put")):
                for item in block.get(side_key, []) or []:
                    rows.append({
                        "option_symbol": item.get("contractName") or item.get("symbol") or "",
                        "expiry": exp,
                        "expiration": exp,
                        "strike": safe_float(item.get("strike"), None),
                        "type": opt_type,
                        "side": opt_type,
                        "bid": safe_float(item.get("bid"), None),
                        "ask": safe_float(item.get("ask"), None),
                        "mid": None,
                        "last": safe_float(item.get("lastPrice", item.get("last")), None),
                        "volume": safe_float(item.get("volume"), 0.0),
                        "open_interest": safe_float(item.get("openInterest"), 0.0),
                        "iv": safe_float(item.get("impliedVolatility"), None),
                        "delta": None,
                        "gamma": None,
                        "theta": None,
                        "vega": None,
                        "dte": calc_dte(exp),
                        "underlying": ticker.upper(),
                        "underlying_price": None,
                    })
        return build_chain_payload(ticker, pd.DataFrame(rows), "finnhub")
    except Exception as e:
        if "RATE_LIMIT" in str(e):
            raise
        return build_chain_payload(ticker, pd.DataFrame(), "finnhub", f"Finnhub options error: {e}")
