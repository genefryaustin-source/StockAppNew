"""
Sprint 4 Phase 1 — Options Pin Risk Engine.
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


def calculate_pin_risk(chain_data: dict[str, Any] | None, expiry: str | None = None, underlying_price: float | None = None) -> dict[str, Any]:
    df = _as_frame(chain_data)
    if df.empty:
        return {"available": False, "reason": "No chain rows available."}

    required = {"strike", "open_interest"}
    if not required.issubset(df.columns):
        return {"available": False, "reason": f"Missing columns: {sorted(required - set(df.columns))}"}

    if expiry and "expiry" in df.columns:
        df = df[df["expiry"].astype(str) == str(expiry)]

    if df.empty:
        return {"available": False, "reason": "No rows for selected expiration."}

    df = df.copy()
    df["strike"] = _num(df["strike"])
    df["open_interest"] = _num(df["open_interest"]).fillna(0)
    df = df.dropna(subset=["strike"])

    if underlying_price is None:
        try:
            underlying_price = float(chain_data.get("underlying_price"))
        except Exception:
            underlying_price = None

    grouped = (
        df.groupby("strike", as_index=False)
        .agg(total_open_interest=("open_interest", "sum"))
        .sort_values("total_open_interest", ascending=False)
        .reset_index(drop=True)
    )

    if grouped.empty:
        return {"available": False, "reason": "No open interest by strike."}

    pin_strike = float(grouped.iloc[0]["strike"])
    max_oi = float(grouped.iloc[0]["total_open_interest"] or 0)
    total_oi = float(grouped["total_open_interest"].sum() or 1)
    concentration = max_oi / total_oi

    distance_pct = None
    proximity_score = 0.5
    if underlying_price:
        distance_pct = abs((pin_strike - underlying_price) / underlying_price) * 100
        proximity_score = max(0.0, min(1.0, 1 - (distance_pct / 10)))

    pin_probability = round(min(0.98, concentration * 0.65 + proximity_score * 0.35), 3)

    if pin_probability >= 0.70:
        risk_level = "HIGH"
    elif pin_probability >= 0.45:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "available": True,
        "expiry": expiry,
        "pin_strike": pin_strike,
        "pin_probability": pin_probability,
        "risk_level": risk_level,
        "distance_pct": round(distance_pct, 2) if distance_pct is not None else None,
        "oi_concentration": round(concentration, 3),
        "top_pin_candidates": grouped.head(10),
    }


def summarize_pin_risk(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Pin risk unavailable: {result.get('reason', 'unknown reason')}"
    return f"Pin risk is {result.get('risk_level')} around ${result.get('pin_strike'):,.2f} with estimated probability {result.get('pin_probability'):.0%}."
