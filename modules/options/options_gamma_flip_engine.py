"""
Sprint 4 Phase 3 — Gamma Flip Engine.

Estimates gamma flip / zero-gamma proxy from call/put gamma pressure.
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


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def calculate_gamma_flip(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
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
        df["gamma_pressure"] = df["gamma"].abs() * df["open_interest"] * 100
    else:
        df["gamma_pressure"] = df["open_interest"] * 100

    grouped = (
        df.groupby(["strike", "type"], as_index=False)
        .agg(gamma_pressure=("gamma_pressure", "sum"))
    )

    pivot = grouped.pivot_table(index="strike", columns="type", values="gamma_pressure", aggfunc="sum").fillna(0)
    for col in ["call", "put"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["net_gamma_pressure"] = pivot["call"] - pivot["put"]
    pivot = pivot.sort_index()

    gamma_flip = None
    if not pivot.empty:
        abs_min = pivot["net_gamma_pressure"].abs().sort_values()
        gamma_flip = float(abs_min.index[0])

    positive_gamma = float(pivot[pivot["net_gamma_pressure"] > 0]["net_gamma_pressure"].sum()) if not pivot.empty else 0
    negative_gamma = float(abs(pivot[pivot["net_gamma_pressure"] < 0]["net_gamma_pressure"].sum())) if not pivot.empty else 0

    if positive_gamma > negative_gamma * 1.25:
        regime = "POSITIVE_GAMMA_DOMINANT"
    elif negative_gamma > positive_gamma * 1.25:
        regime = "NEGATIVE_GAMMA_DOMINANT"
    else:
        regime = "MIXED_GAMMA"

    table = pivot.reset_index().rename(columns={"index": "strike"})

    return {
        "available": True,
        "expiry": expiry,
        "gamma_flip": gamma_flip,
        "zero_gamma_proxy": gamma_flip,
        "gamma_regime": regime,
        "positive_gamma_pressure": round(positive_gamma, 2),
        "negative_gamma_pressure": round(negative_gamma, 2),
        "gamma_table": table.head(50),
    }


def summarize_gamma_flip(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Gamma flip unavailable: {result.get('reason', 'unknown reason')}"
    gf = result.get("gamma_flip")
    gf_text = "—" if gf is None else f"${float(gf):,.2f}"
    return f"Gamma flip proxy is {gf_text}. Regime: {result.get('gamma_regime')}."
