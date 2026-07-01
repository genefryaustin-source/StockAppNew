"""modules/forex/providers/finnhub_forex_provider.py"""
from __future__ import annotations
from typing import Any
from modules.forex.providers.common import build_history_row, env_key, epoch_seconds, history_payload, normalize_pair, normalize_quote, provider_error, provider_headers, request_json
RATE_URL="https://finnhub.io/api/v1/forex/rate"; CANDLE_URL="https://finnhub.io/api/v1/forex/candle"; PROVIDER="finnhub_fx"
def _api_key() -> str: return env_key("FINNHUB_API_KEY","FINNHUB_KEY")
def _resolution(interval: str) -> str:
    return {"1day":"D","daily":"D","1d":"D","1hour":"60","1h":"60","60min":"60","30min":"30","15min":"15","5min":"5","1min":"1"}.get(str(interval or "1day").lower(),"D")
def get_quote(pair: str) -> dict[str, Any]:
    key=_api_key()
    if not key: return provider_error(PROVIDER,"Finnhub API key not configured",pair=pair)
    base,quote,normalized=normalize_pair(pair); data=request_json(RATE_URL,params={"from":base,"to":quote,"token":key},headers=provider_headers(),timeout=20)
    rate=data.get("rate")
    if rate is None: return provider_error(PROVIDER,"Finnhub returned no usable rate",raw=data,pair=normalized)
    return normalize_quote(PROVIDER,normalized,float(rate),raw=data)
def get_quotes(pairs): return {p:get_quote(p) for p in pairs}
def get_history(pair: str, *, start_date, end_date, interval: str="1day", adjusted: bool=True) -> dict[str, Any]:
    key=_api_key()
    if not key: return history_payload(provider=PROVIDER,pair=pair,interval=interval,rows=[],error="Finnhub API key not configured")
    _,_,normalized=normalize_pair(pair); symbol=f"OANDA:{normalized.replace('/', '_')}"
    data=request_json(CANDLE_URL,params={"symbol":symbol,"resolution":_resolution(interval),"from":epoch_seconds(start_date),"to":epoch_seconds(end_date),"token":key},headers=provider_headers(),timeout=30)
    if data.get("s") not in {"ok","no_data"}: return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=[],raw=data,error=str(data))
    rows=[]; ts=data.get("t") or []; opens=data.get("o") or []; highs=data.get("h") or []; lows=data.get("l") or []; closes=data.get("c") or []; vols=data.get("v") or []
    for i,t in enumerate(ts):
        row=build_history_row(provider=PROVIDER,pair=normalized,asof=t,open_=opens[i] if i<len(opens) else None,high=highs[i] if i<len(highs) else None,low=lows[i] if i<len(lows) else None,close=closes[i] if i<len(closes) else None,volume=vols[i] if i<len(vols) else None,interval=interval,raw={"index":i})
        if row: rows.append(row)
    return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=rows,raw=data,error=None if rows else "Finnhub returned no historical rows")
def get_daily_history(pair: str, *, start_date, end_date, adjusted: bool=True) -> dict[str, Any]: return get_history(pair,start_date=start_date,end_date=end_date,interval="1day",adjusted=adjusted)
def provider_name() -> str: return PROVIDER
def health_check() -> dict[str, Any]:
    try:
        q=get_quote("EUR/USD"); return {"provider":PROVIDER,"healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc: return {"provider":PROVIDER,"healthy":False,"error":str(exc)}
