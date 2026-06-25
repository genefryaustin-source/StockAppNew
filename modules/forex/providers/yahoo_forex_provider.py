"""
modules/forex/providers/yahoo_forex_provider.py
"""

from __future__ import annotations

from datetime import datetime, timezone
import requests

BASE_URL="https://query1.finance.yahoo.com/v8/finance/chart"

def _normalize(pair:str):
    p=pair.upper().replace("-","/").replace("_","/")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"

def get_quote(pair:str)->dict:
    base,quote,pair=_normalize(pair)
    symbol=f"{base}{quote}=X"

    r=requests.get(
        f"{BASE_URL}/{symbol}",
        params={"interval":"1m","range":"1d"},
        timeout=20,
        headers={"User-Agent":"Mozilla/5.0"},
    )
    r.raise_for_status()
    data=r.json()

    try:
        result=data["chart"]["result"][0]
        meta=result["meta"]
        price=float(meta.get("regularMarketPrice") or meta.get("previousClose"))
        bid=meta.get("bid")
        ask=meta.get("ask")
    except Exception:
        return {
            "error":"Yahoo returned no usable rate",
            "provider":"yahoo_fx",
            "raw":data,
        }

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "bid":bid,
        "ask":ask,
        "mid":price,
        "last":price,
        "provider":"yahoo_fx",
        "source":"yahoo",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }

def get_quotes(pairs):
    return {p:get_quote(p) for p in pairs}

def provider_name():
    return "yahoo_fx"

def health_check():
    try:
        q=get_quote("EUR/USD")
        return {"provider":"yahoo_fx","healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc:
        return {"provider":"yahoo_fx","healthy":False,"error":str(exc)}
