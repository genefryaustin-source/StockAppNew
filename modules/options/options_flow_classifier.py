"""
Sprint 4 Phase 2 — Institutional Flow Classifier.

FIX:
- Replaces invalid pandas call:
    df["last"].replace(0, df["mid"])
  with a safe vectorized fallback using mask/fillna.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _as_frame(flow_data: Any) -> pd.DataFrame:
    if isinstance(flow_data, pd.DataFrame):
        return flow_data.copy()
    if isinstance(flow_data, list):
        return pd.DataFrame(flow_data)
    if isinstance(flow_data, dict):
        for key in ("flows", "alerts", "unusual", "items", "rows", "contracts"):
            val = flow_data.get(key)
            if isinstance(val, pd.DataFrame):
                return val.copy()
            if isinstance(val, list):
                return pd.DataFrame(val)
        df = flow_data.get("all_rows")
        if isinstance(df, pd.DataFrame):
            return df.copy()
    return pd.DataFrame()


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def classify_flow(flow_data: Any, min_volume: int = 100) -> dict[str, Any]:
    df = _as_frame(flow_data)
    if df.empty:
        return {
            "available": False,
            "reason": "No flow rows available.",
            "classified": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    df = df.copy()

    for col in [
        "type",
        "volume",
        "open_interest",
        "bid",
        "ask",
        "last",
        "iv",
        "delta",
        "expiry",
        "strike",
    ]:
        if col not in df.columns:
            df[col] = None

    df["type"] = df["type"].astype(str).str.lower()
    df["volume"] = _num(df["volume"]).fillna(0)
    df["open_interest"] = _num(df["open_interest"]).fillna(0)
    df["bid"] = _num(df["bid"]).fillna(0)
    df["ask"] = _num(df["ask"]).fillna(0)
    df["last"] = _num(df["last"]).fillna(0)
    df["iv"] = _num(df["iv"])
    df["delta"] = _num(df["delta"])
    df["strike"] = _num(df["strike"])

    df = df[df["volume"] >= min_volume].copy()
    if df.empty:
        return {
            "available": False,
            "reason": f"No flow rows above minimum volume {min_volume}.",
            "classified": pd.DataFrame(),
            "summary": pd.DataFrame(),
        }

    df["vol_oi_ratio"] = df["volume"] / df["open_interest"].replace(0, 1)
    df["mid"] = (df["bid"] + df["ask"]) / 2

    df["near_ask"] = (
        (df["ask"] > 0)
        & (df["mid"] > 0)
        & (df["last"] >= (df["mid"] + (df["ask"] - df["mid"]) * 0.5))
    )

    df["near_bid"] = (
        (df["bid"] > 0)
        & (df["mid"] > 0)
        & (df["last"] <= (df["mid"] - (df["mid"] - df["bid"]) * 0.5))
    )

    trade_price = df["last"].mask(df["last"] <= 0, df["mid"]).fillna(0)
    df["premium"] = trade_price * df["volume"] * 100

    def classify(row: pd.Series) -> str:
        opt_type = str(row.get("type", "")).lower()
        near_ask = bool(row.get("near_ask"))
        near_bid = bool(row.get("near_bid"))
        voi = float(row.get("vol_oi_ratio") or 0)
        volume = float(row.get("volume") or 0)
        oi = float(row.get("open_interest") or 0)

        if voi >= 3 and volume >= 500:
            if near_ask and opt_type == "call":
                return "BULLISH_SPECULATION"
            if near_ask and opt_type == "put":
                return "BEARISH_SPECULATION"
            if near_bid and opt_type == "call":
                return "CALL_DISTRIBUTION"
            if near_bid and opt_type == "put":
                return "PUT_DISTRIBUTION"

        if oi > 0 and volume > oi * 1.5:
            return "OPENING_FLOW"

        if opt_type == "put" and near_ask and volume >= 250:
            return "PROTECTIVE_HEDGING"

        if opt_type == "call" and near_bid and volume >= 250:
            return "COVERED_CALL_SUPPLY"

        return "NEUTRAL_FLOW"

    df["flow_class"] = df.apply(classify, axis=1)

    summary = (
        df.groupby("flow_class", as_index=False)
        .agg(
            count=("flow_class", "size"),
            volume=("volume", "sum"),
            premium=("premium", "sum"),
        )
        .sort_values("premium", ascending=False)
        .reset_index(drop=True)
    )

    return {
        "available": True,
        "classified": df.reset_index(drop=True),
        "summary": summary,
        "total_volume": int(df["volume"].sum()),
        "total_premium": float(df["premium"].sum()),
        "dominant_class": str(summary.iloc[0]["flow_class"])
        if not summary.empty
        else "NEUTRAL_FLOW",
    }


def summarize_flow_classification(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Flow classification unavailable: {result.get('reason', 'unknown reason')}"

    return (
        f"Dominant flow class: {result.get('dominant_class')} with "
        f"{result.get('total_volume', 0):,} contracts and "
        f"${result.get('total_premium', 0):,.0f} premium."
    )