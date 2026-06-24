from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd


def get_secret(key: str) -> Optional[str]:
    """Read a secret from Streamlit, environment, or app config without hard dependency."""
    try:
        import streamlit as st  # type: ignore
        try:
            if key in st.secrets:
                val = st.secrets[key]
                if val:
                    return str(val)
        except Exception:
            pass

        for section in ("alpaca", "market_data", "tradier", "polygon", "options"):
            try:
                val = st.secrets.get(section, {}).get(key, "")
                if val:
                    return str(val)
            except Exception:
                pass
    except Exception:
        pass

    val = os.getenv(key, "")
    if val:
        return val

    try:
        from modules.utils.config import get_secret as app_get_secret  # type: ignore
        val = app_get_secret(key)
        return str(val) if val else None
    except Exception:
        return None


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def calc_dte(expiry: Any) -> Optional[int]:
    try:
        exp_date = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        return (exp_date - date.today()).days
    except Exception:
        return None


def normalize_side(value: Any, option_symbol: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in ("call", "calls", "c"):
        return "call"
    if raw in ("put", "puts", "p"):
        return "put"
    sym = str(option_symbol or "").upper()
    if len(sym) >= 9:
        # OCC-like symbols usually contain YYMMDD[C/P]
        import re
        m = re.search(r"\d{6}([CP])\d{8}$", sym)
        if m:
            return "call" if m.group(1) == "C" else "put"
    return raw


def build_chain_payload(
    ticker: str,
    df: pd.DataFrame,
    source: str,
    error: str | None = None,
    expirations: list[str] | None = None,
) -> dict:
    """Return the legacy StockApp chain shape expected by existing dashboards."""
    ticker = str(ticker or "").upper().strip()

    required = [
        "option_symbol", "expiry", "expiration", "type", "side", "strike",
        "bid", "ask", "mid", "last", "volume", "open_interest",
        "iv", "delta", "gamma", "theta", "vega", "dte", "underlying", "underlying_price",
    ]

    if df is None:
        df = pd.DataFrame()

    df = df.copy()
    for col in required:
        if col not in df.columns:
            df[col] = None

    if not df.empty:
        df["expiry"] = df["expiry"].fillna(df["expiration"]).astype(str).str[:10]
        df["expiration"] = df["expiration"].fillna(df["expiry"]).astype(str).str[:10]
        df["type"] = [normalize_side(t, s) for t, s in zip(df["type"], df["option_symbol"])]
        df["side"] = df["type"]
        for col in ["strike", "bid", "ask", "mid", "last", "volume", "open_interest", "iv", "delta", "gamma", "theta", "vega", "underlying_price"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if df["mid"].isna().all() or (df["mid"].fillna(0) == 0).all():
            df["mid"] = ((df["bid"].fillna(0) + df["ask"].fillna(0)) / 2.0).where((df["bid"].fillna(0) + df["ask"].fillna(0)) > 0, df["last"])
        df["dte"] = df["dte"].where(df["dte"].notna(), df["expiry"].apply(calc_dte))
        df["underlying"] = df["underlying"].fillna(ticker)

    if expirations:
        expirations = sorted(
            [str(x)[:10] for x in expirations if x]
        )
    else:
        expirations = (
            sorted(
                [
                    x
                    for x in df.get("expiry", pd.Series(dtype=str))
                .dropna()
                .unique()
                .tolist()
                    if str(x)
                ]
            )
            if not df.empty
            else []
        )
    chain: dict[str, dict[str, pd.DataFrame]] = {}
    for exp in expirations:
        sub = df[df["expiry"] == exp].copy()
        calls = sub[sub["type"].astype(str).str.lower() == "call"].sort_values("strike").reset_index(drop=True)
        puts = sub[sub["type"].astype(str).str.lower() == "put"].sort_values("strike").reset_index(drop=True)
        chain[exp] = {"calls": calls, "puts": puts}

    payload = {
        "ticker": ticker,
        "chain": chain,
        "expirations": expirations,
        "all_rows": df.reset_index(drop=True) if not df.empty else df,
        "source": source,
        "provider": source,
        "contracts": int(len(df)) if df is not None else 0,
    }
    if error:
        payload["error"] = error
    return payload
