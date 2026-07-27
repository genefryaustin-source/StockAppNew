"""
Sprint 4 Phase 1 — Expiration Pressure Engine.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _as_frame(chain_data: dict[str, Any] | None) -> pd.DataFrame:
    if not chain_data:
        return pd.DataFrame()
    df = chain_data.get("all_rows")
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if isinstance(df, list):
        return pd.DataFrame(df)
    return pd.DataFrame()


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def calculate_expiration_pressure(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    df = _as_frame(chain_data)
    if df.empty:
        return {"available": False, "reason": "No chain rows available."}

    required = {"type", "open_interest", "volume"}
    if not required.issubset(df.columns):
        return {"available": False, "reason": f"Missing columns: {sorted(required - set(df.columns))}"}

    if expiry and "expiry" in df.columns:
        df = df[df["expiry"].astype(str) == str(expiry)]

    if df.empty:
        return {"available": False, "reason": "No rows for selected expiration."}

    df = df.copy()
    df["type"] = df["type"].astype(str).str.lower()
    df["open_interest"] = _num(df["open_interest"]).fillna(0)
    df["volume"] = _num(df["volume"]).fillna(0)

    call_pressure = float((df[df["type"] == "call"]["open_interest"] + df[df["type"] == "call"]["volume"]).sum())
    put_pressure = float((df[df["type"] == "put"]["open_interest"] + df[df["type"] == "put"]["volume"]).sum())
    total = max(1.0, call_pressure + put_pressure)
    net = (call_pressure - put_pressure) / total
    pressure_score = round(50 + net * 50, 2)

    if pressure_score >= 65:
        regime = "BULLISH"
    elif pressure_score <= 35:
        regime = "BEARISH"
    else:
        regime = "BALANCED"

    return {
        "available": True,
        "expiry": expiry,
        "expiration_pressure": regime,
        "pressure_score": pressure_score,
        "call_pressure": round(call_pressure, 2),
        "put_pressure": round(put_pressure, 2),
        "net_pressure": round(net, 3),
        "call_share": round(call_pressure / total, 3),
        "put_share": round(put_pressure / total, 3),
    }


def summarize_expiration_pressure(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Expiration pressure unavailable: {result.get('reason', 'unknown reason')}"
    return f"Expiration pressure is {result.get('expiration_pressure')} with score {result.get('pressure_score')}/100."
