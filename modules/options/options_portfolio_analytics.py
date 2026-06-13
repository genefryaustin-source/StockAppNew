"""Portfolio analytics for Phase 6 Options Portfolio Command Center."""
from __future__ import annotations
from typing import Any
import math
import pandas as pd


def _num(v: Any, d: float = 0.0) -> float:
    try:
        if v is None:
            return d
        if isinstance(v, float) and math.isnan(v):
            return d
        return float(v)
    except Exception:
        return d


def summarize_options_portfolio(positions: list[dict[str, Any]]) -> dict[str, Any]:
    df = pd.DataFrame(positions or [])
    if df.empty:
        return {
            "position_count": 0,
            "total_market_value": 0.0,
            "total_unrealized_pnl": 0.0,
            "net_delta": 0.0,
            "net_gamma": 0.0,
            "net_theta": 0.0,
            "net_vega": 0.0,
            "net_rho": 0.0,
            "income_estimate_monthly": 0.0,
            "largest_risk_position": None,
            "largest_winner": None,
            "largest_loser": None,
            "underlying_count": 0,
            "strategy_count": 0,
        }

    for col in ["market_value", "unrealized_pnl", "delta", "gamma", "theta", "vega", "rho", "qty"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    total_value = float(df["market_value"].abs().sum())
    pnl = float(df["unrealized_pnl"].sum())
    risk_idx = df["market_value"].abs().idxmax() if not df.empty else None
    win_idx = df["unrealized_pnl"].idxmax() if not df.empty else None
    lose_idx = df["unrealized_pnl"].idxmin() if not df.empty else None

    # crude monthly income proxy: short option theta capture
    income_est = float((-df["theta"].sum()) * 21) if "theta" in df else 0.0

    return {
        "position_count": int(len(df)),
        "total_market_value": total_value,
        "total_unrealized_pnl": pnl,
        "pnl_pct": pnl / total_value if total_value else 0.0,
        "net_delta": float(df["delta"].sum()),
        "net_gamma": float(df["gamma"].sum()),
        "net_theta": float(df["theta"].sum()),
        "net_vega": float(df["vega"].sum()),
        "net_rho": float(df["rho"].sum()),
        "income_estimate_monthly": income_est,
        "largest_risk_position": df.loc[risk_idx].to_dict() if risk_idx is not None else None,
        "largest_winner": df.loc[win_idx].to_dict() if win_idx is not None else None,
        "largest_loser": df.loc[lose_idx].to_dict() if lose_idx is not None else None,
        "underlying_count": int(df.get("underlying", pd.Series(dtype=str)).nunique()) if "underlying" in df else 0,
        "strategy_count": int(df.get("strategy_name", pd.Series(dtype=str)).nunique()) if "strategy_name" in df else 0,
    }


def exposure_by_underlying(positions: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(positions or [])
    if df.empty or "underlying" not in df.columns:
        return pd.DataFrame()
    for col in ["market_value", "unrealized_pnl", "delta", "gamma", "theta", "vega", "rho"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    grouped = df.groupby("underlying", dropna=False).agg(
        positions=("option_symbol", "count"),
        market_value=("market_value", lambda x: float(abs(x).sum())),
        unrealized_pnl=("unrealized_pnl", "sum"),
        delta=("delta", "sum"),
        gamma=("gamma", "sum"),
        theta=("theta", "sum"),
        vega=("vega", "sum"),
        rho=("rho", "sum"),
    ).reset_index()
    return grouped.sort_values("market_value", ascending=False)


def exposure_by_strategy(positions: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(positions or [])
    if df.empty:
        return pd.DataFrame()
    if "strategy_name" not in df.columns:
        df["strategy_name"] = "Single Leg"
    for col in ["market_value", "unrealized_pnl", "theta", "vega"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df.groupby("strategy_name", dropna=False).agg(
        positions=("option_symbol", "count"),
        market_value=("market_value", lambda x: float(abs(x).sum())),
        unrealized_pnl=("unrealized_pnl", "sum"),
        theta=("theta", "sum"),
        vega=("vega", "sum"),
    ).reset_index().sort_values("market_value", ascending=False)
