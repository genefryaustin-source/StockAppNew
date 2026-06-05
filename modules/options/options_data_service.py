"""
modules/options/options_data_service.py

Options data service — chain, Greeks, expirations.
Primary: MarketData.app (already confirmed working in flow_service.py)
Fallback: Finnhub
"""
from __future__ import annotations
import os, time
from datetime import datetime, timezone, date
from typing import Optional
import pandas as pd
import requests
import streamlit as st

_CACHE: dict = {}
_CACHE_TTL = 300  # 5 min

def _secret(key):
    try:
        if key in st.secrets: return str(st.secrets[key])
        for sec in ["alpaca","market_data"]:
            try:
                v = st.secrets.get(sec,{}).get(key,"")
                if v: return str(v)
            except: pass
    except: pass
    v = os.getenv(key,"")
    if v: return v
    try:
        from modules.utils.config import get_secret
        return get_secret(key) or None
    except: return None

def _cached(key):
    e = _CACHE.get(key)
    return e["d"] if e and time.time()-e["t"] < _CACHE_TTL else None

def _cache(key, d):
    _CACHE[key] = {"d": d, "t": time.time()}
    return d

# ── Chain fetch ────────────────────────────────────────────────────────────────
def get_options_chain(ticker: str) -> dict:
    """Full options chain with Greeks from MarketData.app."""
    key = f"chain_{ticker}"
    cached = _cached(key)
    if cached: return cached

    md_key = _secret("MARKETDATA_API_KEY")
    if md_key:
        try:
            r = requests.get(
                f"https://api.marketdata.app/v1/options/chain/{ticker.upper()}/",
                headers={"Authorization": f"Token {md_key}", "Accept": "application/json"},
                timeout=12,
            )
            if r.status_code in (200, 203):
                data = r.json()
                if data.get("s") != "error" and data.get("optionSymbol"):
                    return _cache(key, _parse_chain(ticker, data))
        except Exception as e:
            print(f"[options] MarketData chain error: {e}")

    # Finnhub fallback
    fh_key = _secret("FINNHUB_API_KEY")
    if fh_key:
        try:
            r = requests.get("https://finnhub.io/api/v1/stock/option-chain",
                params={"symbol": ticker.upper(), "token": fh_key}, timeout=10)
            if r.status_code == 200:
                return _cache(key, _parse_finnhub_chain(ticker, r.json()))
        except Exception as e:
            print(f"[options] Finnhub chain error: {e}")

    return {"error": f"No options chain data available for {ticker}.", "ticker": ticker}

def _idx(data, field, i):
    try: return data[field][i]
    except: return None

def _parse_chain(ticker: str, data: dict) -> dict:
    n = len(data.get("optionSymbol") or [])
    rows = []
    for i in range(n):
        rows.append({
            "option_symbol": _idx(data,"optionSymbol",i),
            "expiry":        str(_idx(data,"expiration",i) or "")[:10],
            "strike":        _idx(data,"strike",i),
            "type":          str(_idx(data,"side",i) or "").lower(),
            "bid":           _idx(data,"bid",i),
            "ask":           _idx(data,"ask",i),
            "last":          _idx(data,"last",i),
            "volume":        _idx(data,"volume",i),
            "open_interest": _idx(data,"openInterest",i),
            "iv":            _idx(data,"iv",i),
            "delta":         _idx(data,"delta",i),
            "gamma":         _idx(data,"gamma",i),
            "theta":         _idx(data,"theta",i),
            "vega":          _idx(data,"vega",i),
            "dte":           _calc_dte(_idx(data,"expiration",i)),
        })
    df = pd.DataFrame(rows)
    expirations = sorted(df["expiry"].dropna().unique().tolist()) if not df.empty else []
    chain = {}
    for exp in expirations:
        sub = df[df["expiry"] == exp]
        chain[exp] = {
            "calls": sub[sub["type"]=="call"].sort_values("strike").reset_index(drop=True),
            "puts":  sub[sub["type"]=="put"].sort_values("strike").reset_index(drop=True),
        }
    return {"ticker": ticker, "chain": chain, "expirations": expirations,
            "all_rows": df, "source": "marketdata"}

def _parse_finnhub_chain(ticker: str, data: dict) -> dict:
    rows = []
    for opt_type, key in [("call","data"), ("put","data")]:
        for item in (data.get(key) or []):
            rows.append({
                "option_symbol": item.get("contractName",""),
                "expiry":        str(item.get("expirationDate",""))[:10],
                "strike":        item.get("strike"),
                "type":          opt_type,
                "bid":           item.get("bid"),
                "ask":           item.get("ask"),
                "last":          item.get("lastPrice"),
                "volume":        item.get("volume"),
                "open_interest": item.get("openInterest"),
                "iv":            item.get("impliedVolatility"),
                "delta":         None,"gamma":None,"theta":None,"vega":None,
                "dte":           _calc_dte(str(item.get("expirationDate",""))[:10]),
            })
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    expirations = sorted(df["expiry"].dropna().unique().tolist()) if not df.empty else []
    chain = {}
    for exp in expirations:
        sub = df[df["expiry"] == exp]
        chain[exp] = {
            "calls": sub[sub["type"]=="call"].sort_values("strike").reset_index(drop=True),
            "puts":  sub[sub["type"]=="put"].sort_values("strike").reset_index(drop=True),
        }
    return {"ticker": ticker, "chain": chain, "expirations": expirations,
            "all_rows": df, "source": "finnhub"}

def _calc_dte(expiry) -> Optional[int]:
    try:
        exp_date = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        return (exp_date - date.today()).days
    except: return None

# ── IV Surface ─────────────────────────────────────────────────────────────────
def get_iv_surface(ticker: str) -> pd.DataFrame:
    """Pivot DTE vs strike → IV for surface chart."""
    chain_data = get_options_chain(ticker)
    if "error" in chain_data: return pd.DataFrame()
    df = chain_data.get("all_rows", pd.DataFrame())
    if df.empty: return pd.DataFrame()
    calls = df[df["type"]=="call"].dropna(subset=["dte","strike","iv"])
    if calls.empty: return pd.DataFrame()
    try:
        pivot = calls.pivot_table(index="dte", columns="strike", values="iv", aggfunc="mean")
        return pivot.sort_index()
    except: return pd.DataFrame()

