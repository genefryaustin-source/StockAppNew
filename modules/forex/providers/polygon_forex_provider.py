"""
modules/forex/providers/polygon_forex_provider.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
import requests

BASE_URL="https://api.polygon.io/v2/aggs/ticker"


def _normalize(pair:str):
    p=pair.upper().replace("-","/").replace("_","/")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"


def _api_key():
    return (
        os.getenv("POLYGON_API_KEY")
        or os.getenv("POLYGON_KEY")
        or ""
    )


def get_quote(pair:str)->dict:
    key=_api_key()
    if not key:
        return {"error":"Polygon API key not configured","provider":"polygon_fx"}

    base,quote,pair=_normalize(pair)
    symbol=f"C:{base}{quote}"

    r=requests.get(
        f"{BASE_URL}/{symbol}/prev",
        params={"adjusted":"true","apikey":key},
        timeout=20,
        headers={"User-Agent":"StockApp Forex"},
    )
    r.raise_for_status()

    data=r.json()

    results=data.get("results") or []
    if not results:
        return {
            "error":"Polygon returned no usable rate",
            "provider":"polygon_fx",
            "raw":data,
        }

    row=results[0]
    price=float(row.get("c") or row.get("vw") or row.get("o"))

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "mid":price,
        "last":price,
        "open":row.get("o"),
        "high":row.get("h"),
        "low":row.get("l"),
        "close":row.get("c"),
        "volume":row.get("v"),
        "provider":"polygon_fx",
        "source":"polygon",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }


def get_quotes(pairs):
    return {p:get_quote(p) for p in pairs}


def provider_name():
    return "polygon_fx"


def health_check():
    try:
        q=get_quote("EUR/USD")
        return {
            "provider":"polygon_fx",
            "healthy":not bool(q.get("error")),
            "sample":q,
        }
    except Exception as exc:
        return {
            "provider":"polygon_fx",
            "healthy":False,
            "error":str(exc),
        }
