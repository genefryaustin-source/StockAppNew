"""modules/forex/providers/twelvedata_forex_provider.py"""
from __future__ import annotations
from typing import Any
from modules.forex.providers.common import build_history_row, env_key, history_payload, normalize_pair, normalize_quote, provider_error, provider_headers, request_json, twelvedata_interval
PRICE_URL="https://api.twelvedata.com/price"; TIME_SERIES_URL="https://api.twelvedata.com/time_series"; PROVIDER="twelvedata_fx"
def _api_key() -> str: return env_key("TWELVEDATA_API_KEY", "TWELVEDATA_KEY")
def _symbol(pair: str) -> str:
    base, quote, _ = normalize_pair(pair); return f"{base}/{quote}"
def get_quote(pair: str) -> dict[str, Any]:
    key=_api_key()
    if not key: return provider_error(PROVIDER,"TwelveData API key not configured",pair=pair)
    _,_,normalized=normalize_pair(pair); data=request_json(PRICE_URL,params={"symbol":_symbol(normalized),"apikey":key},headers=provider_headers(),timeout=20)
    if data.get("status")=="error": return provider_error(PROVIDER,data.get("message","TwelveData error"),raw=data,pair=normalized)
    rate=data.get("price")
    if rate is None: return provider_error(PROVIDER,"TwelveData returned no usable rate",raw=data,pair=normalized)
    return normalize_quote(PROVIDER,normalized,float(rate),raw=data)
def get_quotes(pairs): return {p:get_quote(p) for p in pairs}
def get_history(pair: str, *, start_date, end_date, interval: str="1day", adjusted: bool=True) -> dict[str, Any]:
    key=_api_key()
    if not key: return history_payload(provider=PROVIDER,pair=pair,interval=interval,rows=[],error="TwelveData API key not configured")
    _,_,normalized=normalize_pair(pair); data=request_json(TIME_SERIES_URL,params={"symbol":_symbol(normalized),"interval":twelvedata_interval(interval),"start_date":str(start_date)[:10],"end_date":str(end_date)[:10],"outputsize":5000,"order":"ASC","apikey":key},headers=provider_headers(),timeout=30)
    if data.get("status")=="error": return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=[],raw=data,error=data.get("message","TwelveData error"))
    rows=[]
    for item in data.get("values") or []:
        row=build_history_row(provider=PROVIDER,pair=normalized,asof=item.get("datetime"),open_=item.get("open"),high=item.get("high"),low=item.get("low"),close=item.get("close"),volume=item.get("volume"),interval=interval,raw=item)
        if row: rows.append(row)
    return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=rows,raw=data,error=None if rows else "TwelveData returned no historical rows")
def get_daily_history(pair: str, *, start_date, end_date, adjusted: bool=True) -> dict[str, Any]: return get_history(pair,start_date=start_date,end_date=end_date,interval="1day",adjusted=adjusted)
def provider_name() -> str: return PROVIDER
def health_check() -> dict[str, Any]:
    try:
        q=get_quote("EUR/USD"); return {"provider":PROVIDER,"healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc: return {"provider":PROVIDER,"healthy":False,"error":str(exc)}
