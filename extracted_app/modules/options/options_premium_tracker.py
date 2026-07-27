"""
modules/options/options_premium_tracker.py

Premium flow helpers for Options Smart Money Center.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def premium_by_type(contracts: list[dict[str, Any]]) -> dict[str, float]:
    call_premium = 0.0
    put_premium = 0.0
    for row in contracts or []:
        if str(row.get("type", "")).upper() == "CALL":
            call_premium += _num(row.get("premium_est"))
        elif str(row.get("type", "")).upper() == "PUT":
            put_premium += _num(row.get("premium_est"))
    total = call_premium + put_premium
    return {
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": call_premium - put_premium,
        "total_premium": total,
        "call_pct": call_premium / total if total else 0.0,
        "put_pct": put_premium / total if total else 0.0,
    }


def premium_leaderboard(contracts: list[dict[str, Any]], limit: int = 20) -> pd.DataFrame:
    if not contracts:
        return pd.DataFrame()
    df = pd.DataFrame(contracts)
    if "premium_est" not in df.columns:
        df["premium_est"] = 0
    df["premium_est"] = pd.to_numeric(df["premium_est"], errors="coerce").fillna(0)
    return df.sort_values("premium_est", ascending=False).head(limit).reset_index(drop=True)


def premium_by_expiry(contracts: list[dict[str, Any]]) -> pd.DataFrame:
    if not contracts:
        return pd.DataFrame()
    df = pd.DataFrame(contracts)
    if df.empty or "expiry" not in df.columns:
        return pd.DataFrame()
    if "premium_est" not in df.columns:
        df["premium_est"] = 0
    if "type" not in df.columns:
        df["type"] = "UNKNOWN"
    df["premium_est"] = pd.to_numeric(df["premium_est"], errors="coerce").fillna(0)
    grouped = df.pivot_table(index="expiry", columns="type", values="premium_est", aggfunc="sum", fill_value=0).reset_index()
    grouped["total"] = grouped.drop(columns=["expiry"], errors="ignore").sum(axis=1)
    return grouped.sort_values("total", ascending=False)


def premium_by_strike(contracts: list[dict[str, Any]]) -> pd.DataFrame:
    if not contracts:
        return pd.DataFrame()
    df = pd.DataFrame(contracts)
    if df.empty or "strike" not in df.columns:
        return pd.DataFrame()
    if "premium_est" not in df.columns:
        df["premium_est"] = 0
    if "type" not in df.columns:
        df["type"] = "UNKNOWN"
    df["premium_est"] = pd.to_numeric(df["premium_est"], errors="coerce").fillna(0)
    grouped = df.groupby(["type", "strike"], dropna=False).agg(
        premium=("premium_est", "sum"),
        contracts=("strike", "count"),
        volume=("volume", "sum"),
    ).reset_index()
    return grouped.sort_values("premium", ascending=False)


def format_money(value: Any) -> str:
    val = _num(value)
    sign = "-" if val < 0 else ""
    val = abs(val)
    if val >= 1_000_000_000:
        return f"{sign}${val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"{sign}${val / 1_000_000:.2f}M"
    if val >= 1_000:
        return f"{sign}${val / 1_000:.0f}K"
    return f"{sign}${val:,.0f}"
