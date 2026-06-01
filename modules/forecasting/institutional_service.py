"""
modules/forecasting/institutional_service.py

Fetches institutional ownership and 13F filing data for a given ticker.

Primary source  : Fintel API  (set FINTEL_API_KEY in env/secrets)
Secondary source: SEC EDGAR full-index (free, no key)
Fallback        : yfinance institutional holders (always available)

Usage:
    from modules.forecasting.institutional_service import get_institutional_flow
    data = get_institutional_flow("NVDA")
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests
import pandas as pd

_CACHE: dict = {}
_CACHE_TTL = 3600 * 4  # 4 hours — 13F data changes quarterly


def get_institutional_flow(symbol: str) -> dict:
    """
    Returns institutional ownership data for `symbol`.

    Return dict keys:
        ownership_pct   : float | None   — % of shares held by institutions
        net_change_shares : float | None  — net shares bought/sold last quarter
        num_holders     : int | None      — total institutions holding
        top_holders     : list[dict]      — top movers, each with:
                            name, shares_held, pct_change, direction ("inc"|"dec")
        source          : str             — where data came from
        as_of           : str             — filing quarter e.g. "Q1 2026"
    """
    key = symbol.upper()
    cached = _CACHE.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    result = (
        _fetch_fintel(symbol)
        or _fetch_yfinance(symbol)
        or _empty_result(symbol)
    )

    _CACHE[key] = {"ts": time.time(), "data": result}
    return result


# ─────────────────────────────────────────────────────────────
# Source 1: Fintel
# ─────────────────────────────────────────────────────────────

def _fetch_fintel(symbol: str) -> Optional[dict]:
    api_key = os.getenv("FINTEL_API_KEY")
    if not api_key:
        return None

    try:
        url = f"https://fintel.io/api/filings/institutional/{symbol}?token={api_key}&limit=20"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        holders = data.get("holders") or []
        top = []
        net_change = 0

        for h in holders[:10]:
            chg = float(h.get("shares_change") or 0)
            net_change += chg
            top.append({
                "name":        h.get("institution_name") or "Unknown",
                "shares_held": int(h.get("shares") or 0),
                "pct_change":  round(float(h.get("pct_change") or 0), 2),
                "direction":   "inc" if chg >= 0 else "dec",
            })

        return {
            "ownership_pct":      float(data.get("ownership_pct") or 0),
            "net_change_shares":  net_change,
            "num_holders":        int(data.get("total_institutions") or len(holders)),
            "top_holders":        top,
            "source":             "Fintel",
            "as_of":              data.get("quarter") or _current_quarter(),
        }

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Source 2: yfinance (always available, no key needed)
# ─────────────────────────────────────────────────────────────

def _fetch_yfinance(symbol: str) -> Optional[dict]:
    try:
        import yfinance as yf

        tk = yf.Ticker(symbol)
        info = tk.info or {}

        # Institutional holders DataFrame
        inst_holders = tk.institutional_holders
        major_holders = tk.major_holders

        # Ownership pct from major_holders
        ownership_pct = None
        if major_holders is not None and not major_holders.empty:
            for _, row in major_holders.iterrows():
                label = str(row.iloc[1]).lower() if len(row) > 1 else ""
                if "institution" in label:
                    try:
                        ownership_pct = float(str(row.iloc[0]).replace("%", "")) 
                    except Exception:
                        pass

        # Fall back to info dict
        if ownership_pct is None:
            ownership_pct = info.get("heldPercentInstitutions")
            if ownership_pct:
                ownership_pct = round(ownership_pct * 100, 1)

        top_holders = []
        net_change = 0
        num_holders = 0

        if inst_holders is not None and not inst_holders.empty:
            num_holders = len(inst_holders)
            for _, row in inst_holders.head(10).iterrows():
                # yfinance column names vary by version
                name  = row.get("Holder") or row.get("Name") or "Unknown"
                shares = int(row.get("Shares") or row.get("shares") or 0)
                pct_chg = float(row.get("% Change") or row.get("pctChange") or 0)
                direction = "inc" if pct_chg >= 0 else "dec"
                net_change += pct_chg * shares / 100  # rough estimate

                top_holders.append({
                    "name":        str(name),
                    "shares_held": shares,
                    "pct_change":  round(pct_chg, 2),
                    "direction":   direction,
                })

        return {
            "ownership_pct":     ownership_pct,
            "net_change_shares": round(net_change),
            "num_holders":       num_holders or info.get("institutionsCount"),
            "top_holders":       top_holders,
            "source":            "Yahoo Finance / 13F",
            "as_of":             _current_quarter(),
        }

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _empty_result(symbol: str) -> dict:
    return {
        "ownership_pct": None, "net_change_shares": None,
        "num_holders": None, "top_holders": [],
        "source": "unavailable", "as_of": _current_quarter(),
    }


def _current_quarter() -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    q = (now.month - 1) // 3 + 1
    return f"Q{q} {now.year}"
