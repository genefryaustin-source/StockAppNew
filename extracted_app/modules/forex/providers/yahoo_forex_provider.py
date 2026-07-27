"""modules/forex/providers/yahoo_forex_provider.py"""
from __future__ import annotations
from typing import Any
from modules.forex.providers.common import build_history_row, epoch_seconds, history_payload, normalize_pair, normalize_quote, provider_error, request_json, yahoo_interval
BASE_URL="https://query1.finance.yahoo.com/v8/finance/chart"; PROVIDER="yahoo_fx"
def _symbol(pair: str) -> str:
    base,quote,_=normalize_pair(pair); return f"{base}{quote}=X"
def get_quote(pair: str) -> dict[str, Any]:
    _,_,normalized=normalize_pair(pair); data=request_json(f"{BASE_URL}/{_symbol(normalized)}",params={"interval":"1m","range":"1d"},headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"},timeout=20)
    try:
        result=data["chart"]["result"][0]; meta=result["meta"]; price=float(meta.get("regularMarketPrice") or meta.get("previousClose")); payload=normalize_quote(PROVIDER,normalized,price,raw=data); payload["bid"]=meta.get("bid"); payload["ask"]=meta.get("ask"); return payload
    except Exception: return provider_error(PROVIDER,"Yahoo returned no usable rate",raw=data,pair=normalized)
def get_quotes(pairs): return {p:get_quote(p) for p in pairs}
def get_history(pair: str, *, start_date, end_date, interval: str="1day", adjusted: bool=True) -> dict[str, Any]:
    _,_,normalized=normalize_pair(pair); data=request_json(f"{BASE_URL}/{_symbol(normalized)}",params={"interval":yahoo_interval(interval),"period1":epoch_seconds(start_date),"period2":epoch_seconds(end_date),"includePrePost":"false","events":"history"},headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"},timeout=30)
    try: result=data["chart"]["result"][0]
    except Exception: return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=[],raw=data,error="Yahoo returned no chart result")
    timestamps=result.get("timestamp") or []; quote=((result.get("indicators") or {}).get("quote") or [{}])[0]; opens=quote.get("open") or []; highs=quote.get("high") or []; lows=quote.get("low") or []; closes=quote.get("close") or []; vols=quote.get("volume") or []
    rows=[]
    for i,ts in enumerate(timestamps):
        row=build_history_row(provider=PROVIDER,pair=normalized,asof=ts,open_=opens[i] if i<len(opens) else None,high=highs[i] if i<len(highs) else None,low=lows[i] if i<len(lows) else None,close=closes[i] if i<len(closes) else None,volume=vols[i] if i<len(vols) else None,interval=interval,raw={"index":i})
        if row: rows.append(row)
    return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=rows,raw=data,error=None if rows else "Yahoo returned no historical rows")
def get_daily_history(pair: str, *, start_date, end_date, adjusted: bool=True) -> dict[str, Any]: return get_history(pair,start_date=start_date,end_date=end_date,interval="1day",adjusted=adjusted)
def provider_name() -> str: return PROVIDER
def health_check() -> dict[str, Any]:
    try:
        q=get_quote("EUR/USD"); return {"provider":PROVIDER,"healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc: return {"provider":PROVIDER,"healthy":False,"error":str(exc)}
