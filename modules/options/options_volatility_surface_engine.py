"""
modules/options/options_volatility_surface_engine.py

Phase 4 Options Volatility & Earnings Intelligence Suite.
Builds IV surface snapshots from existing options chain data.
No new API keys required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import math
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        x = float(v)
        if math.isnan(x):
            return default
        return x
    except Exception:
        return default


def _dte(expiry: Any) -> int:
    try:
        d = datetime.fromisoformat(str(expiry)[:10]).replace(tzinfo=timezone.utc)
        return max(0, (d - datetime.now(timezone.utc)).days)
    except Exception:
        return 0


def chain_to_surface_frame(chain_data: dict[str, Any]) -> pd.DataFrame:
    """Normalize existing get_options_chain output into a surface-ready frame."""
    raw = chain_data.get("all_rows")

    if raw is None:
        raw = chain_data.get("raw_df")
    if isinstance(raw, pd.DataFrame) and not raw.empty:
        df = raw.copy()
    else:
        rows: list[dict[str, Any]] = []
        for exp, chain in (chain_data.get("chain") or chain_data.get("chains") or {}).items():
            for opt_type, key in (("call", "calls"), ("put", "puts")):
                sub = chain.get(key, pd.DataFrame())
                if isinstance(sub, pd.DataFrame):
                    for _, r in sub.iterrows():
                        item = dict(r)
                        item.setdefault("expiry", exp)
                        item.setdefault("type", opt_type)
                        rows.append(item)
                elif isinstance(sub, list):
                    for item in sub:
                        row = dict(item)
                        row.setdefault("expiry", exp)
                        row.setdefault("type", opt_type)
                        rows.append(row)
        df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame()

    rename = {
        "expiration": "expiry",
        "expiration_date": "expiry",
        "impliedVolatility": "iv",
        "openInterest": "open_interest",
        "optionType": "type",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["strike", "iv", "volume", "open_interest", "delta", "gamma", "theta", "vega", "bid", "ask", "last"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "expiry" not in df.columns:
        df["expiry"] = ""
    if "dte" not in df.columns:
        df["dte"] = df["expiry"].map(_dte)
    else:
        df["dte"] = pd.to_numeric(df["dte"], errors="coerce").fillna(df["expiry"].map(_dte))
    if "type" not in df.columns:
        df["type"] = "unknown"
    df["type"] = df["type"].astype(str).str.lower().replace({"c": "call", "p": "put"})
    return df.dropna(subset=["strike"], how="any").reset_index(drop=True)


def build_volatility_surface(chain_data: dict[str, Any]) -> dict[str, Any]:
    df = chain_to_surface_frame(chain_data)
    if df.empty or "iv" not in df.columns:
        return {"error": "No IV surface data available", "surface": [], "summary": {}}

    iv_df = df.dropna(subset=["iv"]).copy()
    if iv_df.empty:
        return {"error": "No IV values available", "surface": [], "summary": {}}

    surface = (
        iv_df.groupby(["dte", "expiry", "strike", "type"], dropna=False)
        .agg(iv=("iv", "mean"), volume=("volume", "sum"), open_interest=("open_interest", "sum"))
        .reset_index()
        .sort_values(["dte", "strike", "type"])
    )

    by_dte = iv_df.groupby("dte")["iv"].median().reset_index(name="median_iv").sort_values("dte")
    by_type = iv_df.groupby("type")["iv"].median().to_dict()

    summary = {
        "contracts_with_iv": int(len(iv_df)),
        "median_iv": float(iv_df["iv"].median()),
        "mean_iv": float(iv_df["iv"].mean()),
        "min_iv": float(iv_df["iv"].min()),
        "max_iv": float(iv_df["iv"].max()),
        "call_median_iv": float(by_type.get("call", 0.0) or 0.0),
        "put_median_iv": float(by_type.get("put", 0.0) or 0.0),
        "front_dte": int(by_dte.iloc[0]["dte"]) if not by_dte.empty else None,
        "front_iv": float(by_dte.iloc[0]["median_iv"]) if not by_dte.empty else None,
        "back_dte": int(by_dte.iloc[-1]["dte"]) if len(by_dte) else None,
        "back_iv": float(by_dte.iloc[-1]["median_iv"]) if len(by_dte) else None,
    }

    return {
        "surface": surface.to_dict("records"),
        "term_points": by_dte.to_dict("records"),
        "summary": summary,
    }
