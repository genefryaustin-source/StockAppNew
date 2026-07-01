"""modules/forex/providers/alpha_vantage_forex_provider.py"""
from __future__ import annotations
from typing import Any
from modules.forex.providers.common import alpha_vantage_function, build_history_row, env_key, history_payload, normalize_pair, normalize_quote, parse_date, provider_error, provider_headers, request_json
BASE_URL="https://www.alphavantage.co/query"; PROVIDER="alpha_vantage_fx"
def _api_key() -> str: return env_key("ALPHA_VANTAGE_API_KEY","ALPHAVANTAGE_API_KEY","ALPHA_VANTAGE_KEY")
def get_quote(pair: str) -> dict[str, Any]:
    key=_api_key()
    if not key: return provider_error(PROVIDER,"Alpha Vantage API key not configured",pair=pair)
    base,quote,normalized=normalize_pair(pair); data=request_json(BASE_URL,params={"function":"CURRENCY_EXCHANGE_RATE","from_currency":base,"to_currency":quote,"apikey":key},headers=provider_headers(),timeout=20)
    rate=(data.get("Realtime Currency Exchange Rate") or {}).get("5. Exchange Rate")
    if rate is None: return provider_error(PROVIDER,"Alpha Vantage returned no usable rate",raw=data,pair=normalized)
    return normalize_quote(PROVIDER,normalized,float(rate),raw=data)
def get_quotes(pairs): return {p:get_quote(p) for p in pairs}
def get_history(pair: str, *, start_date, end_date, interval: str="1day", adjusted: bool=True) -> dict[str, Any]:
    key=_api_key()
    if not key: return history_payload(provider=PROVIDER,pair=pair,interval=interval,rows=[],error="Alpha Vantage API key not configured")
    base,quote,normalized=normalize_pair(pair); function,extra=alpha_vantage_function(interval)
    data=request_json(BASE_URL,params={"function":function,"from_symbol":base,"to_symbol":quote,"apikey":key,**extra},headers=provider_headers(),timeout=30)
    if "Error Message" in data: return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=[],raw=data,error=data.get("Error Message"))
    if "Note" in data and len(data.keys())<=2: return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=[],raw=data,error=data.get("Note"))
    time_series=None
    for key_name in data.keys():
        if "Time Series" in key_name: time_series=data.get(key_name); break
    if not isinstance(time_series,dict): return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=[],raw=data,error="Alpha Vantage returned no time series")
    start=parse_date(start_date); end=parse_date(end_date); rows=[]
    for asof,item in sorted(time_series.items()):
        d=parse_date(asof)
        if d<start or d>end: continue
        row=build_history_row(provider=PROVIDER,pair=normalized,asof=asof,open_=item.get("1. open"),high=item.get("2. high"),low=item.get("3. low"),close=item.get("4. close"),volume=item.get("5. volume"),interval=interval,raw=item)
        if row: rows.append(row)
    return history_payload(provider=PROVIDER,pair=normalized,interval=interval,rows=rows,raw=data,error=None if rows else "Alpha Vantage returned no historical rows")
def get_daily_history(pair: str, *, start_date, end_date, adjusted: bool=True) -> dict[str, Any]: return get_history(pair,start_date=start_date,end_date=end_date,interval="1day",adjusted=adjusted)
def provider_name() -> str: return PROVIDER
def health_check() -> dict[str, Any]:
    try:
        q=get_quote("EUR/USD"); return {"provider":PROVIDER,"healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc: return {"provider":PROVIDER,"healthy":False,"error":str(exc)}
