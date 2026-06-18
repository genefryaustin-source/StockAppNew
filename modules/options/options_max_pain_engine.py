"""
Sprint 4 Phase 1 — Options Max Pain Engine.
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


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def calculate_max_pain(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    df = _as_frame(chain_data)
    if df.empty:
        return {"available": False, "reason": "No option chain rows available.", "max_pain": None, "distance_pct": None, "payout_table": pd.DataFrame()}

    required = {"strike", "type", "open_interest"}
    if not required.issubset(df.columns):
        return {"available": False, "reason": f"Missing required columns: {sorted(required - set(df.columns))}", "max_pain": None, "distance_pct": None, "payout_table": pd.DataFrame()}

    if expiry and "expiry" in df.columns:
        df = df[df["expiry"].astype(str) == str(expiry)]

    if df.empty:
        return {"available": False, "reason": "No rows for selected expiration.", "max_pain": None, "distance_pct": None, "payout_table": pd.DataFrame()}

    df = df.copy()
    df["strike"] = _numeric(df["strike"])
    df["open_interest"] = _numeric(df["open_interest"]).fillna(0)
    df["type"] = df["type"].astype(str).str.lower()
    df = df.dropna(subset=["strike"])

    if df.empty:
        return {"available": False, "reason": "No valid strikes available.", "max_pain": None, "distance_pct": None, "payout_table": pd.DataFrame()}

    strikes = sorted(df["strike"].dropna().unique().tolist())
    calls = df[df["type"] == "call"]
    puts = df[df["type"] == "put"]
    rows = []

    for settlement in strikes:
        call_payout = ((settlement - calls["strike"]).clip(lower=0) * calls["open_interest"] * 100).sum()
        put_payout = ((puts["strike"] - settlement).clip(lower=0) * puts["open_interest"] * 100).sum()
        rows.append({
            "settlement_price": float(settlement),
            "call_payout": float(call_payout),
            "put_payout": float(put_payout),
            "total_payout": float(call_payout + put_payout),
        })

    payout_table = pd.DataFrame(rows).sort_values("total_payout").reset_index(drop=True)
    max_pain = float(payout_table.iloc[0]["settlement_price"]) if not payout_table.empty else None

    spot = chain_data.get("underlying_price") if chain_data else None
    try:
        spot = float(spot)
    except Exception:
        spot = None

    distance_pct = None
    pin_bias = "UNKNOWN"
    if spot and max_pain:
        distance_pct = round(((max_pain - spot) / spot) * 100, 2)
        if distance_pct > 1:
            pin_bias = "UPSIDE_PIN"
        elif distance_pct < -1:
            pin_bias = "DOWNSIDE_PIN"
        else:
            pin_bias = "NEAR_SPOT"

    return {
        "available": True,
        "reason": None,
        "expiry": expiry,
        "max_pain": max_pain,
        "distance_pct": distance_pct,
        "pin_bias": pin_bias,
        "payout_table": payout_table,
    }


def summarize_max_pain(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Max pain unavailable: {result.get('reason', 'unknown reason')}"
    mp = result.get("max_pain")
    dist = result.get("distance_pct")
    if dist is None:
        return f"Max pain is estimated near ${mp:,.2f}."
    return f"Max pain is estimated near ${mp:,.2f}, {dist:+.2f}% from spot. Pin bias: {result.get('pin_bias', 'UNKNOWN')}."
