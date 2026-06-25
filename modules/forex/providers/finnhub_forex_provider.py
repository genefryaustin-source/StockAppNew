"""
modules/forex/providers/finnhub_forex_provider.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

BASE_URL="https://finnhub.io/api/v1/forex/rate"

def _normalize(pair:str):
    p=pair.upper().replace("-","/").replace("_","/")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"

def _api_key():
    return (
        os.getenv("FINNHUB_API_KEY")
        or os.getenv("FINNHUB_KEY")
        or ""
    )

def get_quote(pair:str)->dict:
    key=_api_key()
    if not key:
        return {"error":"Finnhub API key not configured","provider":"finnhub_fx"}

    base,quote,pair=_normalize(pair)

    r=requests.get(
        BASE_URL,
        params={
            "from":base,
            "to":quote,
            "token":key,
        },
        timeout=20,
        headers={"User-Agent":"StockApp Forex"},
    )
    r.raise_for_status()

    data=r.json()

    rate=data.get("rate")
    if rate is None:
        return {
            "error":"Finnhub returned no usable rate",
            "provider":"finnhub_fx",
            "raw":data,
        }

    rate=float(rate)

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "mid":rate,
        "last":rate,
        "provider":"finnhub_fx",
        "source":"finnhub",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }

def get_quotes(pairs):
    return {p:get_quote(p) for p in pairs}

def provider_name():
    return "finnhub_fx"

def health_check():
    try:
        q=get_quote("EUR/USD")
        return {
            "provider":"finnhub_fx",
            "healthy":not bool(q.get("error")),
            "sample":q,
        }
    except Exception as exc:
        return {
            "provider":"finnhub_fx",
            "healthy":False,
            "error":str(exc),
        }
