"""
modules/options_flow/flow_service.py

Options Flow & Dark Pool Intelligence — Service Layer.

Data sources:
  1. MarketData.app  (/v1/options/chain/) — your PRIMARY provider, already wired
  2. Finnhub         (/stock/option-chain) — fallback, same key you already have
  3. Insider data    (/stock/insider-transactions) — Finnhub, already working

No new API keys needed — uses what's already in secrets.toml.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests
import streamlit as st

_CACHE: dict = {}
_CACHE_TTL = 1800  # 30 minutes


# ─────────────────────────────────────────────────────────────
# Secrets
# ─────────────────────────────────────────────────────────────

def _get_secret(key: str) -> Optional[str]:
    """
    Read a secret — mirrors modules.utils.config.get_secret exactly.
    Priority: st.secrets → env var → None
    """
    # 1. Streamlit secrets (primary — works when app is running)
    try:
        if key in st.secrets:
            val = st.secrets[key]
            if val:
                return str(val)
    except Exception:
        pass

    # 2. Environment variable
    val = os.getenv(key, "")
    if val:
        return val

    # 3. Direct toml read (works in test scripts outside Streamlit)
    try:
        import toml
        from pathlib import Path
        for p in [Path(".streamlit/secrets.toml"),
                  Path("C:/StockApp/.streamlit/secrets.toml")]:
            if p.exists():
                data = toml.load(p)
                val = data.get(key, "")
                if val:
                    return str(val)
    except Exception:
        pass

    return None


def api_available() -> bool:
    return bool(
        _get_secret("MARKETDATA_API_KEY")
        or _get_secret("FINNHUB_API_KEY")
    )


# ─────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────

def _get_cached(key: str):
    entry = _CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None

def _set_cached(key: str, data):
    _CACHE[key] = {"data": data, "ts": time.time()}


# ─────────────────────────────────────────────────────────────
# MarketData.app options chain
# ─────────────────────────────────────────────────────────────

def _get_options_marketdata(ticker: str) -> dict:
    """
    Fetch options chain from MarketData.app.
    Endpoint: GET /v1/options/chain/{symbol}/
    Auth: Token {MARKETDATA_API_KEY}
    """
    key = _get_secret("MARKETDATA_API_KEY")
    if not key:
        return {"error": "No MARKETDATA_API_KEY"}

    try:
        r = requests.get(
            f"https://api.marketdata.app/v1/options/chain/{ticker.upper()}/",
            headers={
                "Authorization": f"Token {key}",
                "Accept": "application/json",
            },
            params={"dateformat": "timestamp"},
            timeout=15,
        )
        if r.status_code == 401:
            return {"error": "MarketData.app API key invalid"}
        if r.status_code == 402:
            return {"error": "MarketData.app plan doesn't include options — check your plan at marketdata.app"}
        if r.status_code == 429:
            return {"error": "MarketData.app rate limited — try again in a moment"}
        if r.status_code not in (200, 203):
            return {"error": f"MarketData.app returned {r.status_code}: {r.text[:100]}"}

        data = r.json()
        if data.get("s") == "error":
            return {"error": data.get("errmsg", "MarketData.app error")}

        return _parse_marketdata_chain(ticker, data)

    except Exception as e:
        return {"error": str(e)}


def _parse_marketdata_chain(ticker: str, data: dict) -> dict:
    """Parse MarketData.app options chain response into standard format."""
    import pandas as pd

    # MarketData returns parallel arrays
    n = len(data.get("optionSymbol", []))
    if n == 0:
        return {"error": "No options data returned"}

    rows = []
    for i in range(n):
        rows.append({
            "optionSymbol":    _idx(data, "optionSymbol", i),
            "underlying":      _idx(data, "underlying", i),
            "expiry":          _ts_to_date(_idx(data, "expiration", i)),
            "strike":          _idx(data, "strike", i),
            "side":            str(_idx(data, "side", i) or "").lower(),
            "lastPrice":       _idx(data, "last", i),
            "bid":             _idx(data, "bid", i),
            "ask":             _idx(data, "ask", i),
            "volume":          _idx(data, "volume", i) or 0,
            "openInterest":    _idx(data, "openInterest", i) or 0,
            "impliedVolatility": _idx(data, "iv", i),
            "delta":           _idx(data, "delta", i),
            "gamma":           _idx(data, "gamma", i),
            "theta":           _idx(data, "theta", i),
            "vega":            _idx(data, "vega", i),
            "inTheMoney":      _idx(data, "inTheMoney", i),
        })

    df_all = pd.DataFrame(rows)
    calls_df = df_all[df_all["side"] == "call"].copy()
    puts_df  = df_all[df_all["side"] == "put"].copy()

    expirations = sorted(df_all["expiry"].dropna().unique().tolist())
    chain_data  = {}
    for exp in expirations[:8]:
        chain_data[exp] = {
            "calls": calls_df[calls_df["expiry"] == exp].copy(),
            "puts":  puts_df[puts_df["expiry"]  == exp].copy(),
        }

    # Spot price
    spot = _idx(data, "underlyingPrice", 0) or _idx(data, "last", 0)

    return {
        "ticker":      ticker.upper(),
        "spot":        float(spot) if spot else None,
        "expirations": expirations,
        "chains":      chain_data,
        "source":      "marketdata",
        "raw_df":      df_all,
    }


def _idx(data: dict, key: str, i: int):
    lst = data.get(key, [])
    return lst[i] if lst and i < len(lst) else None


def _ts_to_date(ts) -> str:
    if not ts:
        return ""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return str(ts)[:10]


# ─────────────────────────────────────────────────────────────
# Finnhub fallback options chain
# ─────────────────────────────────────────────────────────────

def _get_options_finnhub(ticker: str) -> dict:
    """
    Fetch options chain from Finnhub.
    Endpoint: GET /api/v1/stock/option-chain
    Returns a simplified chain (fewer greeks, no per-contract volume).
    """
    key = _get_secret("FINNHUB_API_KEY")
    if not key:
        return {"error": "No FINNHUB_API_KEY"}

    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/option-chain",
            params={"symbol": ticker.upper(), "token": key},
            timeout=12,
        )
        if r.status_code != 200:
            return {"error": f"Finnhub returned {r.status_code}"}

        data = r.json()
        if not data or "data" not in data:
            return {"error": "No Finnhub options data"}

        import pandas as pd
        calls_list, puts_list = [], []
        expirations = set()

        for exp_block in (data.get("data") or []):
            exp = str(exp_block.get("expirationDate") or "")[:10]
            expirations.add(exp)
            for c in (exp_block.get("options", {}).get("CALL") or []):
                calls_list.append(_fh_row(c, exp))
            for p in (exp_block.get("options", {}).get("PUT") or []):
                puts_list.append(_fh_row(p, exp))

        calls_df = pd.DataFrame(calls_list) if calls_list else pd.DataFrame()
        puts_df  = pd.DataFrame(puts_list)  if puts_list  else pd.DataFrame()

        chain_data = {}
        for exp in sorted(expirations)[:8]:
            chain_data[exp] = {
                "calls": calls_df[calls_df["expiry"] == exp].copy() if not calls_df.empty else pd.DataFrame(),
                "puts":  puts_df[puts_df["expiry"]   == exp].copy() if not puts_df.empty  else pd.DataFrame(),
            }

        spot = float(data.get("lastTradePrice") or 0) or None

        return {
            "ticker":      ticker.upper(),
            "spot":        spot,
            "expirations": sorted(expirations),
            "chains":      chain_data,
            "source":      "finnhub",
        }
    except Exception as e:
        return {"error": str(e)}


def _fh_row(opt: dict, exp: str) -> dict:
    return {
        "expiry":          exp,
        "strike":          opt.get("strike"),
        "lastPrice":       opt.get("lastPrice"),
        "bid":             opt.get("bid"),
        "ask":             opt.get("ask"),
        "volume":          opt.get("volume") or 0,
        "openInterest":    opt.get("openInterest") or 0,
        "impliedVolatility": opt.get("impliedVolatility"),
        "inTheMoney":      opt.get("inTheMoney"),
        "delta":           None,
        "gamma":           None,
    }


# ─────────────────────────────────────────────────────────────
# Main entry points
# ─────────────────────────────────────────────────────────────

def get_options_chain(ticker: str) -> dict:
    """
    Fetch options chain — tries MarketData.app first, Finnhub as fallback.
    Results cached for 30 minutes.
    """
    cache_key = f"chain_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # Try MarketData.app first (primary provider)
    result = _get_options_marketdata(ticker)
    if "error" not in result:
        _set_cached(cache_key, result)
        return result

    md_error = result["error"]

    # Fallback to Finnhub
    result = _get_options_finnhub(ticker)
    if "error" not in result:
        _set_cached(cache_key, result)
        return result

    # Both failed — return combined error
    return {"error": f"MarketData.app: {md_error} | Finnhub: {result['error']}"}


def get_options_summary(ticker: str) -> dict:
    """
    Compute options analytics from chain:
    P/C ratio, max pain, IV rank, unusual volume, net premium flow.
    """
    cache_key = f"summary_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    chain_data = get_options_chain(ticker)
    if "error" in chain_data:
        return chain_data

    import pandas as pd
    import numpy as np

    spot       = chain_data.get("spot", 0) or 0
    all_calls  = []
    all_puts   = []

    for exp, chain in chain_data.get("chains", {}).items():
        c = chain["calls"].copy()
        p = chain["puts"].copy()
        if not c.empty:
            c["expiry"] = exp
            all_calls.append(c)
        if not p.empty:
            p["expiry"] = exp
            all_puts.append(p)

    if not all_calls and not all_puts:
        return {"error": "No chain data to analyse"}

    calls_df = pd.concat(all_calls, ignore_index=True) if all_calls else pd.DataFrame()
    puts_df  = pd.concat(all_puts,  ignore_index=True) if all_puts  else pd.DataFrame()

    def _vol(df):
        return float(df["volume"].fillna(0).sum()) if not df.empty and "volume" in df.columns else 0
    def _oi(df):
        return float(df["openInterest"].fillna(0).sum()) if not df.empty else 0

    call_vol  = _vol(calls_df)
    put_vol   = _vol(puts_df)
    call_oi   = _oi(calls_df)
    put_oi    = _oi(puts_df)
    pc_vol    = round(put_vol / call_vol, 3) if call_vol > 0 else 0
    pc_oi     = round(put_oi  / call_oi,  3) if call_oi  > 0 else 0

    # Net premium (last price × OI × 100)
    def _prem(df):
        if df.empty or "lastPrice" not in df.columns:
            return 0.0
        lp = pd.to_numeric(df["lastPrice"], errors="coerce").fillna(0)
        oi = pd.to_numeric(df["openInterest"], errors="coerce").fillna(0)
        return float((lp * oi * 100).sum())

    call_prem = _prem(calls_df)
    put_prem  = _prem(puts_df)
    net_prem  = call_prem - put_prem

    # IV rank
    iv_vals = []
    for df in [calls_df, puts_df]:
        if not df.empty and "impliedVolatility" in df.columns:
            iv_vals += pd.to_numeric(df["impliedVolatility"], errors="coerce").dropna().tolist()
    current_iv = float(np.median(iv_vals)) if iv_vals else 0
    iv_min     = float(np.percentile(iv_vals, 10)) if iv_vals else 0
    iv_max     = float(np.percentile(iv_vals, 90)) if iv_vals else 1
    iv_rank    = round((current_iv - iv_min) / (iv_max - iv_min) * 100, 1) if iv_max > iv_min else 50

    # Max pain
    max_pain = _compute_max_pain(calls_df, puts_df)

    # Unusual volume
    unusual = _find_unusual_volume(calls_df, puts_df, ticker, spot)

    result = {
        "ticker":        ticker.upper(),
        "spot":          spot,
        "source":        chain_data.get("source", "unknown"),
        "call_volume":   int(call_vol),
        "put_volume":    int(put_vol),
        "call_oi":       int(call_oi),
        "put_oi":        int(put_oi),
        "pc_vol":        pc_vol,
        "pc_oi":         pc_oi,
        "pc_sentiment":  "Bullish" if pc_vol < 0.7 else "Bearish" if pc_vol > 1.3 else "Neutral",
        "call_premium":  call_prem,
        "put_premium":   put_prem,
        "net_premium":   net_prem,
        "net_sentiment": "Bullish" if net_prem > 0 else "Bearish",
        "max_pain":      max_pain,
        "iv_median":     round(current_iv * 100, 1),
        "iv_rank":       iv_rank,
        "unusual_contracts": unusual,
        "expirations":   chain_data.get("expirations", []),
    }
    _set_cached(cache_key, result)
    return result


def _compute_max_pain(calls_df, puts_df) -> Optional[float]:
    try:
        import pandas as pd
        all_strikes = sorted(set(
            pd.to_numeric(calls_df["strike"], errors="coerce").dropna().tolist() +
            pd.to_numeric(puts_df["strike"],  errors="coerce").dropna().tolist()
        ))
        if not all_strikes:
            return None

        min_pain = float("inf")
        max_pain_strike = all_strikes[len(all_strikes)//2]

        for s in all_strikes:
            cp = calls_df[pd.to_numeric(calls_df["strike"], errors="coerce") < s]
            pp = puts_df[pd.to_numeric(puts_df["strike"],   errors="coerce") > s]
            call_pain = float(pd.to_numeric(cp["openInterest"], errors="coerce").fillna(0).sum() *
                              max(0, s - pd.to_numeric(cp["strike"], errors="coerce").fillna(s).mean()))
            put_pain  = float(pd.to_numeric(pp["openInterest"], errors="coerce").fillna(0).sum() *
                              max(0, pd.to_numeric(pp["strike"], errors="coerce").fillna(s).mean() - s))
            total = call_pain + put_pain
            if total < min_pain:
                min_pain = total
                max_pain_strike = s

        return round(float(max_pain_strike), 2)
    except Exception:
        return None


def _find_unusual_volume(calls_df, puts_df, ticker: str, spot: float) -> list[dict]:
    import pandas as pd
    unusual = []
    for df, opt_type in [(calls_df, "CALL"), (puts_df, "PUT")]:
        if df.empty:
            continue
        d = df.copy()
        d["volume"]       = pd.to_numeric(d.get("volume", 0),       errors="coerce").fillna(0)
        d["openInterest"] = pd.to_numeric(d.get("openInterest", 0), errors="coerce").fillna(0)
        d["strike"]       = pd.to_numeric(d.get("strike", 0),       errors="coerce").fillna(0)
        d["lastPrice"]    = pd.to_numeric(d.get("lastPrice", 0),    errors="coerce").fillna(0)
        d["iv"]           = pd.to_numeric(d.get("impliedVolatility", 0), errors="coerce").fillna(0)

        d = d[(d["volume"] > 100) & (d["openInterest"] > 0)]
        if d.empty:
            continue

        d["vol_oi"] = d["volume"] / d["openInterest"].replace(0, float("nan"))
        d = d[d["vol_oi"] > 2.0].sort_values("vol_oi", ascending=False)

        for _, row in d.head(5).iterrows():
            strike = float(row["strike"])
            vol    = int(row["volume"])
            oi     = int(row["openInterest"])
            lp     = float(row["lastPrice"])
            iv     = float(row["iv"])
            exp    = str(row.get("expiry", ""))[:10]
            prem   = round(lp * 100 * vol)
            otm    = round((strike - spot) / spot * 100, 1) if spot and opt_type == "CALL" else \
                     round((spot - strike) / spot * 100, 1) if spot else 0

            unusual.append({
                "ticker":        ticker.upper(),
                "type":          opt_type,
                "expiry":        exp,
                "strike":        strike,
                "volume":        vol,
                "open_interest": oi,
                "vol_oi_ratio":  round(float(row["vol_oi"]), 1),
                "iv_pct":        round(iv * 100, 1),
                "last_price":    lp,
                "otm_pct":       otm,
                "premium_est":   prem,
                "premium_fmt":   f"${prem/1e6:.2f}M" if prem >= 1e6 else f"${prem/1e3:.0f}K",
                "sentiment":     "BULLISH" if opt_type == "CALL" else "BEARISH",
            })

    return sorted(unusual, key=lambda x: x["premium_est"], reverse=True)[:20]


# ─────────────────────────────────────────────────────────────
# Dark Pool proxy (institutional activity from options chain)
# ─────────────────────────────────────────────────────────────

def _get_finra_token() -> Optional[str]:
    """
    Get OAuth Bearer token from FINRA developer API.
    Expects FINRA_API_KEY in format "clientId:clientSecret"
    from developer.finra.org free account registration.
    """
    raw = _get_secret("FINRA_API_KEY") or ""
    if not raw or ":" not in raw:
        return None

    client_id, client_secret = raw.split(":", 1)

    try:
        r = requests.post(
            "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token",
            params={"grant_type": "client_credentials"},
            auth=(client_id.strip(), client_secret.strip()),
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        print(f"[finra] token error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[finra] token exception: {e}")
    return None


def get_finra_dark_pool(ticker: str) -> dict:
    """
    Fetch dark pool volume from FINRA ATS Transparency API.
    Requires FINRA_API_KEY = "clientId:clientSecret" in secrets.toml
    (free account at developer.finra.org).

    Falls back to institutional proxy from options chain if no key.
    """
    cache_key = f"dp_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # ── Real FINRA data (if key present) ─────────────────────
    finra_raw = _get_secret("FINRA_API_KEY") or ""
    if finra_raw and ":" in finra_raw:
        token = _get_finra_token()
        if token:
            result = _fetch_finra_ats(ticker, token)
            if "error" not in result:
                _set_cached(cache_key, result)
                return result
            print(f"[finra] data fetch failed: {result.get('error')}")

    # ── Fallback: institutional proxy from options chain ──────
    result = _compute_inst_proxy(ticker)
    _set_cached(cache_key, result)
    return result


def _fetch_finra_ats(ticker: str, token: str) -> dict:
    """
    Query FINRA ATS weekly summary for a specific ticker.

    CONFIRMED from testing:
    - FINRA ignores the issueSymbolIdentifier query param
    - Returns mixed rows: ATS_W_VOL_STATS (market-wide) and ATS_W_SMBL_FIRM (per-ticker/firm)
    - Per-ticker rows have summaryTypeCode = ATS_W_SMBL_FIRM and issueSymbolIdentifier = ticker
    - Must fetch a large limit and filter client-side by issueSymbolIdentifier
    - Aggregate all ATS firms for the ticker per week to get total dark pool volume
    - Then compare against the ATS_W_VOL_STATS total market volume for the same week
      to compute dark pool % for that ticker
    """
    import statistics

    try:
        ticker_upper = ticker.upper()

        # POST with compareFilters — confirmed working from testing.
        # Filters to ATS_W_SMBL_FIRM rows for this specific ticker only.
        # Must include Content-Type: application/json for POST to work.
        r = requests.post(
            "https://api.finra.org/data/group/otcMarket/name/weeklySummary",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept":        "application/json",
                "Content-Type":  "application/json",
            },
            json={
                "compareFilters": [
                    {
                        "fieldName":   "issueSymbolIdentifier",
                        "compareType": "EQUAL",
                        "fieldValue":  ticker_upper,
                    },
                    {
                        "fieldName":   "summaryTypeCode",
                        "compareType": "EQUAL",
                        "fieldValue":  "ATS_W_SMBL_FIRM",
                    },
                ],
                "limit": 200,
            },
            timeout=15,
        )

        if r.status_code != 200:
            return {"error": f"FINRA API {r.status_code}: {r.text[:150]}"}

        ticker_rows = r.json()
        if not ticker_rows:
            return {"error": f"No FINRA ATS data for {ticker_upper}. "
                             "This symbol may not have ATS dark pool volume reported."}

        # Fetch market-wide ATS volume for the same weeks (for % calculation)
        r2 = requests.post(
            "https://api.finra.org/data/group/otcMarket/name/weeklySummary",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept":        "application/json",
                "Content-Type":  "application/json",
            },
            json={
                "compareFilters": [
                    {"fieldName": "summaryTypeCode", "compareType": "EQUAL",
                     "fieldValue": "ATS_W_VOL_STATS"},
                ],
                "limit": 12,
            },
            timeout=10,
        )
        market_rows = {}
        if r2.status_code == 200:
            for row in r2.json():
                week = str(row.get("weekStartDate") or "")[:10]
                if week:
                    market_rows[week] = row

        if not ticker_rows:
            return {
                "error": (
                    f"No per-ticker data for {ticker} in this page. "
                    f"FINRA has {len(all_rows)} rows but none match {ticker}. "
                    "FINRA data is only available for actively traded NMS stocks with ATS volume."
                )
            }

        # Aggregate dark pool volume per week across all ATS firms for this ticker
        by_week: dict = {}
        for row in ticker_rows:
            week = str(row.get("weekStartDate") or row.get("summaryStartDate") or "")[:10]
            vol  = int(row.get("totalWeeklyShareQuantity") or 0)
            if week:
                by_week[week] = by_week.get(week, 0) + vol

        if not by_week:
            return {"error": f"No weekly volume data for {ticker}"}

        import statistics

        # Build weekly records — use market volume if available
        # If market vol unavailable, track raw ATS volume and use
        # week-over-week change as the anomaly signal instead
        weeks = []
        total_ats_vol = sum(by_week.values())

        for week, dark_vol in sorted(by_week.items(), reverse=True)[:10]:
            market_row = market_rows.get(week, {})
            market_vol = int(market_row.get("totalWeeklyShareQuantity") or 0)

            if market_vol > 0:
                # Real dark pool %
                dark_pct = round(dark_vol / market_vol * 100, 4)
            else:
                # Fallback: this ticker's ATS vol as % of its own total reported ATS vol
                dark_pct = round(dark_vol / total_ats_vol * 100, 2) if total_ats_vol > 0 else 0

            weeks.append({
                "week":      week,
                "dark_vol":  dark_vol,
                "total_vol": market_vol or dark_vol,
                "dark_pct":  dark_pct,
            })

        # Z-score on raw dark volume (works even without market vol)
        vols = [w["dark_vol"] for w in weeks]
        mean_vol = statistics.mean(vols) if vols else 0
        std_vol  = statistics.stdev(vols) if len(vols) > 1 else 1
        latest   = weeks[0]
        z_score  = round((latest["dark_vol"] - mean_vol) / std_vol, 2) if std_vol else 0

        # Also compute dark_pct z-score if we have real market vol
        dark_pcts = [w["dark_pct"] for w in weeks if w["dark_pct"] > 0 and w["total_vol"] != w["dark_vol"]]
        if dark_pcts and len(dark_pcts) > 1:
            mean_dp = statistics.mean(dark_pcts)
            std_dp  = statistics.stdev(dark_pcts)
            z_score = round((latest["dark_pct"] - mean_dp) / std_dp, 2) if std_dp else z_score
            mean_display = round(mean_dp, 4)
        else:
            mean_display = round(statistics.mean([w["dark_pct"] for w in weeks]), 2) if weeks else 0

        signal = (
            "🔴 Unusual dark pool activity" if z_score > 1.5
            else "🟡 Slightly elevated"      if z_score > 0.5
            else "🟢 Normal"
        )

        has_market_vol = any(w["total_vol"] != w["dark_vol"] for w in weeks)
        data_note = (
            f"FINRA ATS Transparency — {ticker_upper} dark pool volume. "
            + ("Dark pool % = ATS vol / total market ATS vol per week. " if has_market_vol
               else "Showing raw ATS volume (market total unavailable for % calc). ")
            + "~1 week delay. Z-score flags unusually high weeks."
        )

        return {
            "ticker":         ticker_upper,
            "source":         "finra",
            "latest_week":    latest["week"],
            "dark_vol":       latest["dark_vol"],
            "total_vol":      latest["total_vol"],
            "dark_pct":       latest["dark_pct"],
            "mean_dark_pct":  mean_display,
            "z_score":        z_score,
            "signal":         signal,
            "weekly_history": weeks,
            "data_note":      data_note,
        }

    except Exception as e:
        return {"error": str(e)}


def _compute_inst_proxy(ticker: str) -> dict:
    """Institutional activity proxy from options chain when no FINRA key."""
    summary = get_options_summary(ticker)
    if "error" in summary:
        return {
            "error":    summary["error"],
            "source":   "proxy",
            "data_note":"Options data unavailable",
        }

    pc_oi      = summary.get("pc_oi", 1.0)
    iv_rank    = summary.get("iv_rank", 50)
    total_prem = summary.get("call_premium", 0) + summary.get("put_premium", 0)

    prem_score = min(100, total_prem / 5e7 * 100) if total_prem > 0 else 0
    pc_score   = min(100, abs(pc_oi - 1.0) * 80)
    inst_score = round(prem_score * 0.45 + pc_score * 0.30 + iv_rank * 0.25, 1)

    signal = (
        "🔴 High institutional options activity" if inst_score > 65
        else "🟡 Moderate institutional activity"  if inst_score > 35
        else "🟢 Normal activity levels"
    )

    return {
        "ticker":        ticker.upper(),
        "source":        "proxy",
        "inst_score":    inst_score,
        "signal":        signal,
        "pc_oi":         pc_oi,
        "iv_rank":       iv_rank,
        "total_premium": total_prem,
        "dark_pct":      None,
        "z_score":       None,
        "weekly_history":[],
        "data_note": (
            f"Institutional proxy from {summary.get('source','').upper()} options data. "
            "Add FINRA_API_KEY=clientId:secret to secrets for real dark pool data."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Insider transactions (Finnhub — already working)
# ─────────────────────────────────────────────────────────────

def get_insider_transactions(ticker: str) -> list[dict]:
    cache_key = f"insider_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    key = _get_secret("FINNHUB_API_KEY")
    if not key:
        return []

    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/insider-transactions",
            params={"symbol": ticker.upper(), "token": key},
            timeout=8,
        )
        if r.status_code != 200:
            return []

        results = []
        for t in (r.json().get("data") or []):
            shares = int(t.get("change") or 0)
            price  = float(t.get("transactionPrice") or 0)
            results.append({
                "name":         str(t.get("name") or ""),
                "date":         str(t.get("transactionDate") or ""),
                "shares":       shares,
                "price":        price,
                "value":        abs(shares) * price,
                "is_buy":       shares > 0,
                "type":         "BUY" if shares > 0 else "SELL",
                "shares_after": int(t.get("share") or 0),
            })

        _set_cached(cache_key, results)
        return results
    except Exception:
        return []


# Unused Whales upgrade slot (returns [] without key — UI hides the tab)
def unusual_whales_available() -> bool:
    return bool(_get_secret("UNUSUAL_WHALES_API_KEY"))

def get_realtime_flow_alerts(ticker=None, limit=50) -> list[dict]:
    return []

def get_realtime_darkpool(ticker=None, limit=50) -> list[dict]:
    return []