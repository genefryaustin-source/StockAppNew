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

    # ECB's reference-rate dataset only publishes EUR-denominated series --
    # the SDMX series key is always D.{FOREIGN_CCY}.EUR.SP00.A (rate of 1
    # EUR expressed in FOREIGN_CCY). The previous code built the key
    # directly from the pair's own base/quote (e.g. "D.EUR.JPY.SP00.A" for
    # EUR/JPY), which never exists in ECB's dataset -- every single call
    # 404'd (observed adding ~1.3-1.6s of pure wasted latency per pair in
    # production, on every quote refresh). Cross pairs that don't involve
    # EUR at all (e.g. USD/CAD) aren't published by ECB at all; fail fast
    # with an honest error instead of making a request that can only fail.
    if base == "EUR":
        foreign = quote
        invert = False
    elif quote == "EUR":
        foreign = base
        invert = True
    else:
        return {
            "error": "ECB only publishes EUR reference rates; pair does not involve EUR",
            "provider": "ecb",
        }

    series=f"D.{foreign}.EUR.SP00.A"
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

    if invert:
        # series gives foreign-per-EUR; when the pair's quote currency is
        # EUR (e.g. USD/EUR), the mid rate needed is EUR-per-foreign.
        if not value:
            return {
                "error":"ECB returned no usable rate",
                "provider":"ecb",
                "raw":data,
            }
        value = 1.0 / value

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