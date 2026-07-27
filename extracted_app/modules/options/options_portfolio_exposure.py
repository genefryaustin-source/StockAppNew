"""Exposure diagnostics for options portfolios."""
from __future__ import annotations
from typing import Any
import pandas as pd


def _sum(positions: list[dict[str, Any]], field: str) -> float:
    total = 0.0
    for p in positions or []:
        try:
            total += float(p.get(field) or 0)
        except Exception:
            pass
    return total


def calculate_exposure_map(positions: list[dict[str, Any]]) -> dict[str, Any]:
    total_value = sum(abs(float(p.get("market_value") or 0)) for p in positions or [])
    return {
        "total_options_exposure": total_value,
        "net_delta": _sum(positions, "delta"),
        "net_gamma": _sum(positions, "gamma"),
        "net_theta": _sum(positions, "theta"),
        "net_vega": _sum(positions, "vega"),
        "net_rho": _sum(positions, "rho"),
        "gross_contracts": sum(abs(float(p.get("qty") or 0)) for p in positions or []),
        "by_underlying": _by_underlying(positions),
    }


def _by_underlying(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(positions or [])
    if df.empty or "underlying" not in df.columns:
        return []
    for col in ["market_value", "delta", "gamma", "theta", "vega"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    grouped = df.groupby("underlying").agg(
        exposure=("market_value", lambda s: abs(s).sum()),
        delta=("delta", "sum"),
        gamma=("gamma", "sum"),
        theta=("theta", "sum"),
        vega=("vega", "sum"),
    ).reset_index()
    return grouped.sort_values("exposure", ascending=False).to_dict("records")
