"""
modules/forex/providers/twelvedata_forex_provider.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

BASE_URL="https://api.twelvedata.com/price"

def _normalize(pair:str):
    p=pair.upper().replace("-","/").replace("_","/")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"

def _api_key():
    return (
        os.getenv("TWELVEDATA_API_KEY")
        or os.getenv("TWELVEDATA_KEY")
        or ""
    )

def get_quote(pair:str)->dict:
    key=_api_key()
    if not key:
        return {"error":"TwelveData API key not configured","provider":"twelvedata_fx"}

    base,quote,pair=_normalize(pair)
    symbol=f"{base}/{quote}"

    r=requests.get(
        BASE_URL,
        params={
            "symbol":symbol,
            "apikey":key,
        },
        timeout=20,
        headers={"User-Agent":"StockApp Forex"},
    )
    r.raise_for_status()

    data=r.json()

    if data.get("status")=="error":
        return {
            "error":data.get("message","TwelveData error"),
            "provider":"twelvedata_fx",
            "raw":data,
        }

    rate=data.get("price")

    if rate is None:
        return {
            "error":"TwelveData returned no usable rate",
            "provider":"twelvedata_fx",
            "raw":data,
        }

    rate=float(rate)

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "mid":rate,
        "last":rate,
        "provider":"twelvedata_fx",
        "source":"twelvedata",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }

def get_quotes(pairs):
    return {p:get_quote(p) for p in pairs}

def provider_name():
    return "twelvedata_fx"

def health_check():
    try:
        q=get_quote("EUR/USD")
        return {
            "provider":"twelvedata_fx",
            "healthy":not bool(q.get("error")),
            "sample":q,
        }
    except Exception as exc:
        return {
            "provider":"twelvedata_fx",
            "healthy":False,
            "error":str(exc),
        }
