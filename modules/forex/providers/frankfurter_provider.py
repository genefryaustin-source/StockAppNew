
"""
modules/forex/providers/frankfurter_provider.py
"""

from __future__ import annotations

from datetime import datetime, timezone
import requests

BASE_URL="https://api.frankfurter.app"

def _normalize(pair:str):
    p=pair.upper().replace("-","/").replace("_","/")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"

def get_quote(pair:str)->dict:
    base,quote,pair=_normalize(pair)
    r=requests.get(
        f"{BASE_URL}/latest",
        params={"from":base,"to":quote},
        timeout=15,
        headers={"User-Agent":"StockApp Forex"}
    )
    r.raise_for_status()
    data=r.json()

    rate=(data.get("rates") or {}).get(quote)
    if rate is None:
        return {"error":"Frankfurter returned no usable rate","raw":data}

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "mid":float(rate),
        "last":float(rate),
        "provider":"frankfurter",
        "source":"frankfurter",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }

def get_quotes(pairs):
    return {p:get_quote(p) for p in pairs}

def provider_name()->str:
    return "frankfurter"

def health_check()->dict:
    try:
        q=get_quote("EUR/USD")
        return {
            "provider":"frankfurter",
            "healthy":not bool(q.get("error")),
            "sample":q,
        }
    except Exception as exc:
        return {
            "provider":"frankfurter",
            "healthy":False,
            "error":str(exc),
        }
