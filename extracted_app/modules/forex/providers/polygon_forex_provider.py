"""
modules/forex/providers/polygon_forex_provider.py

Polygon Forex provider. Sprint 25 Phase 4.5B provider standardization.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from modules.forex.providers.common import build_history_row, env_key, history_payload, normalize_pair, normalize_quote, polygon_timespan, provider_error, provider_headers, request_json
BASE_URL = "https://api.polygon.io/v2/aggs/ticker"
PROVIDER = "polygon_fx"
def _api_key() -> str: return env_key("POLYGON_API_KEY", "POLYGON_KEY")
def _polygon_symbol(pair: str) -> str:
    base, quote, _ = normalize_pair(pair); return f"C:{base}{quote}"
def get_quote(pair: str) -> dict[str, Any]:
    key = _api_key()
    if not key: return provider_error(PROVIDER, "Polygon API key not configured", pair=pair)
    _, _, normalized = normalize_pair(pair); symbol = _polygon_symbol(normalized)
    data = request_json(f"{BASE_URL}/{symbol}/prev", params={"adjusted":"true","apikey":key}, headers=provider_headers(), timeout=20)
    results = data.get("results") or []
    if not results: return provider_error(PROVIDER, "Polygon returned no usable rate", raw=data, pair=normalized)
    row = results[0]; price = row.get("c") or row.get("vw") or row.get("o")
    if price is None: return provider_error(PROVIDER, "Polygon returned no close/price value", raw=data, pair=normalized)
    payload = normalize_quote(PROVIDER, normalized, float(price), raw=data)
    payload.update({"open":row.get("o"),"high":row.get("h"),"low":row.get("l"),"close":row.get("c"),"volume":row.get("v"),"timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    return payload
def get_quotes(pairs): return {p: get_quote(p) for p in pairs}
def get_history(pair: str, *, start_date, end_date, interval: str = "1day", adjusted: bool = True) -> dict[str, Any]:
    key = _api_key()
    if not key: return history_payload(provider=PROVIDER, pair=pair, interval=interval, rows=[], error="Polygon API key not configured")
    _, _, normalized = normalize_pair(pair); multiplier, timespan = polygon_timespan(interval); symbol = _polygon_symbol(normalized)
    data = request_json(f"{BASE_URL}/{symbol}/range/{multiplier}/{timespan}/{str(start_date)[:10]}/{str(end_date)[:10]}", params={"adjusted":str(bool(adjusted)).lower(),"sort":"asc","limit":50000,"apikey":key}, headers=provider_headers(), timeout=30)
    rows=[]
    for item in data.get("results") or []:
        row = build_history_row(provider=PROVIDER, pair=normalized, asof=item.get("t"), open_=item.get("o"), high=item.get("h"), low=item.get("l"), close=item.get("c") or item.get("vw"), volume=item.get("v"), interval=interval, raw=item)
        if row: rows.append(row)
    return history_payload(provider=PROVIDER, pair=normalized, interval=interval, rows=rows, raw=data, error=None if rows else "Polygon returned no historical rows")
def get_daily_history(pair: str, *, start_date, end_date, adjusted: bool = True) -> dict[str, Any]: return get_history(pair, start_date=start_date, end_date=end_date, interval="1day", adjusted=adjusted)
def provider_name() -> str: return PROVIDER
def health_check() -> dict[str, Any]:
    try:
        q = get_quote("EUR/USD"); return {"provider":PROVIDER,"healthy":not bool(q.get("error")),"sample":q}
    except Exception as exc: return {"provider":PROVIDER,"healthy":False,"error":str(exc)}
