"""
modules/forex/providers/ecb_provider.py
"""

from __future__ import annotations

from datetime import datetime, timezone
import requests

BASE_URL="https://data-api.ecb.europa.eu/service/data/EXR"

def _normalize(pair:str):
    p=pair.upper().replace("-","/").replace("_","/")
    if "/" in p:
        b,q=p.split("/",1)
    else:
        b,q=p[:3],p[3:6]
    return b[:3],q[:3],f"{b[:3]}/{q[:3]}"

def get_quote(pair:str)->dict:
    base,quote,pair=_normalize(pair)

    series=f"D.{base}.{quote}.SP00.A"
    url=f"{BASE_URL}/{series}"

    r=requests.get(
        url,
        params={"lastNObservations":1,"format":"jsondata"},
        timeout=20,
        headers={"User-Agent":"StockApp Forex"},
    )
    r.raise_for_status()

    data=r.json()

    try:
        value=float(
            data["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]["0"][0]
        )
    except Exception:
        return {
            "error":"ECB returned no usable rate",
            "provider":"ecb",
            "raw":data,
        }

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "mid":value,
        "last":value,
        "provider":"ecb",
        "source":"ecb",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }

def get_quotes(pairs):
    return {p:get_quote(p) for p in pairs}

def provider_name():
    return "ecb"

def health_check():
    try:
        q=get_quote("EUR/USD")
        return {"provider":"ecb","healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc:
        return {"provider":"ecb","healthy":False,"error":str(exc)}
