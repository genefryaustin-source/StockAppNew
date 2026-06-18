"""
Sprint 4 Phase 1 — Options Gamma Wall Engine.
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


def calculate_gamma_walls(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    df = _as_frame(chain_data)
    if df.empty:
        return {"available": False, "reason": "No chain rows available."}

    required = {"strike", "type", "open_interest"}
    if not required.issubset(df.columns):
        return {"available": False, "reason": f"Missing columns: {sorted(required - set(df.columns))}"}

    if expiry and "expiry" in df.columns:
        df = df[df["expiry"].astype(str) == str(expiry)]

    if df.empty:
        return {"available": False, "reason": "No rows for selected expiration."}

    df = df.copy()
    df["strike"] = _num(df["strike"])
    df["open_interest"] = _num(df["open_interest"]).fillna(0)
    df["gamma"] = _num(df["gamma"]).fillna(0) if "gamma" in df.columns else 0.0
    df["type"] = df["type"].astype(str).str.lower()
    df = df.dropna(subset=["strike"])

    if df.empty:
        return {"available": False, "reason": "No valid strikes."}

    if float(df["gamma"].abs().sum() or 0) > 0:
        df["gamma_exposure"] = df["gamma"].abs() * df["open_interest"] * 100
    else:
        df["gamma_exposure"] = df["open_interest"] * 100

    grouped = (
        df.groupby(["strike", "type"], as_index=False)
        .agg(gamma_exposure=("gamma_exposure", "sum"), open_interest=("open_interest", "sum"))
    )

    calls = grouped[grouped["type"] == "call"].sort_values("gamma_exposure", ascending=False)
    puts = grouped[grouped["type"] == "put"].sort_values("gamma_exposure", ascending=False)

    total_by_strike = (
        grouped.groupby("strike", as_index=False)
        .agg(total_gamma_exposure=("gamma_exposure", "sum"), total_oi=("open_interest", "sum"))
        .sort_values("total_gamma_exposure", ascending=False)
        .reset_index(drop=True)
    )

    pivot = grouped.pivot_table(index="strike", columns="type", values="gamma_exposure", aggfunc="sum").fillna(0)
    for col in ["call", "put"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["net_gamma_proxy"] = pivot["call"] - pivot["put"]
    zero_gamma = float((pivot["net_gamma_proxy"].abs()).sort_values().index[0]) if not pivot.empty else None

    return {
        "available": True,
        "expiry": expiry,
        "call_wall": float(calls.iloc[0]["strike"]) if not calls.empty else None,
        "put_wall": float(puts.iloc[0]["strike"]) if not puts.empty else None,
        "gamma_wall": float(total_by_strike.iloc[0]["strike"]) if not total_by_strike.empty else None,
        "zero_gamma": zero_gamma,
        "top_gamma_walls": total_by_strike.head(10),
        "call_walls": calls.head(10),
        "put_walls": puts.head(10),
    }


def summarize_gamma_walls(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Gamma wall analysis unavailable: {result.get('reason', 'unknown reason')}"
    def fmt(v): return "—" if v is None else f"${float(v):,.2f}"
    return f"Call wall: {fmt(result.get('call_wall'))} | Put wall: {fmt(result.get('put_wall'))} | Gamma wall: {fmt(result.get('gamma_wall'))} | Zero-gamma proxy: {fmt(result.get('zero_gamma'))}"
