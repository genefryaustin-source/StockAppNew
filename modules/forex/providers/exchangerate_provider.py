
"""
modules/forex/providers/exchangerate_provider.py
"""

from __future__ import annotations

from datetime import datetime, timezone
import requests

BASE_URL="https://api.exchangerate.host"


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
        f"{BASE_URL}/convert",
        params={
            "from":base,
            "to":quote,
            "amount":1,
        },
        timeout=15,
        headers={"User-Agent":"StockApp Forex"},
    )
    r.raise_for_status()

    data=r.json()

    rate=data.get("result")

    if rate is None:
        info=data.get("info") or {}
        rate=info.get("rate")

    if rate is None:
        quotes=data.get("quotes") or {}
        rate=quotes.get(f"{base}{quote}")

    if rate is None:
        return {
            "error":"exchangerate.host returned no usable rate",
            "provider":"exchangerate_host",
            "raw":data,
        }

    rate=float(rate)

    return {
        "pair":pair,
        "base":base,
        "quote":quote,
        "bid":None,
        "ask":None,
        "mid":rate,
        "last":rate,
        "provider":"exchangerate_host",
        "source":"exchangerate.host",
        "timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw":data,
    }


def get_quotes(pairs):
    return {pair:get_quote(pair) for pair in pairs}


def provider_name()->str:
    return "exchangerate_host"


def health_check()->dict:
    try:
        sample=get_quote("EUR/USD")
        return {
            "provider":"exchangerate_host",
            "healthy":not bool(sample.get("error")),
            "sample":sample,
        }
    except Exception as exc:
        return {
            "provider":"exchangerate_host",
            "healthy":False,
            "error":str(exc),
        }
