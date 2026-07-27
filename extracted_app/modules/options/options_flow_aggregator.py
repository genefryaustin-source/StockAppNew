"""
modules/options/options_flow_aggregator.py

Options Smart Money Phase 1 — flow aggregation layer.
Builds institutional premium-flow summaries from the existing options_flow service.

Uses:
    modules.options_flow.flow_service.get_options_summary

No new API keys required.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math

import pandas as pd


@dataclass
class PremiumFlowSummary:
    ticker: str
    spot: float | None
    source: str
    call_premium: float
    put_premium: float
    net_premium: float
    total_premium: float
    call_premium_pct: float
    put_premium_pct: float
    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    pc_vol: float
    pc_oi: float
    pc_sentiment: str
    net_sentiment: str
    iv_rank: float
    iv_median: float
    max_pain: float | None
    unusual_contracts: list[dict[str, Any]]
    expirations: list[str]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except Exception:
        return default


def load_options_summary(ticker: str) -> dict[str, Any]:
    """Load the existing options summary safely."""
    try:
        from modules.options_flow.flow_service import get_options_summary
        result = get_options_summary(ticker)
        if isinstance(result, dict):
            return result
        return {"error": "Options summary returned non-dict payload"}
    except Exception as exc:
        return {"error": str(exc)}


def aggregate_premium_flow(ticker: str) -> dict[str, Any]:
    """
    Aggregate call/put premium, volume, OI, IV, and unusual-contract data.
    Returns a dict because Streamlit pages and AI advisors consume JSON-like data.
    """
    summary = load_options_summary(ticker)
    if "error" in summary:
        return {
            "ticker": ticker.upper(),
            "error": summary.get("error", "Options summary unavailable"),
            "unusual_contracts": [],
        }

    call_premium = _num(summary.get("call_premium"))
    put_premium = _num(summary.get("put_premium"))
    total_premium = call_premium + put_premium
    net_premium = _num(summary.get("net_premium"), call_premium - put_premium)

    call_pct = call_premium / total_premium if total_premium > 0 else 0.0
    put_pct = put_premium / total_premium if total_premium > 0 else 0.0

    payload = PremiumFlowSummary(
        ticker=str(summary.get("ticker") or ticker).upper(),
        spot=_num(summary.get("spot"), 0.0) or None,
        source=str(summary.get("source") or "unknown"),
        call_premium=call_premium,
        put_premium=put_premium,
        net_premium=net_premium,
        total_premium=total_premium,
        call_premium_pct=call_pct,
        put_premium_pct=put_pct,
        call_volume=_int(summary.get("call_volume")),
        put_volume=_int(summary.get("put_volume")),
        call_oi=_int(summary.get("call_oi")),
        put_oi=_int(summary.get("put_oi")),
        pc_vol=_num(summary.get("pc_vol")),
        pc_oi=_num(summary.get("pc_oi")),
        pc_sentiment=str(summary.get("pc_sentiment") or "Neutral"),
        net_sentiment=str(summary.get("net_sentiment") or ("Bullish" if net_premium > 0 else "Bearish" if net_premium < 0 else "Neutral")),
        iv_rank=_num(summary.get("iv_rank"), 50.0),
        iv_median=_num(summary.get("iv_median")),
        max_pain=summary.get("max_pain"),
        unusual_contracts=list(summary.get("unusual_contracts") or []),
        expirations=list(summary.get("expirations") or []),
    )
    result = asdict(payload)
    result["bias"] = classify_premium_bias(result)
    result["top_expirations"] = top_expirations(result["unusual_contracts"])
    result["top_strikes"] = top_strikes(result["unusual_contracts"])
    return result


def classify_premium_bias(flow: dict[str, Any]) -> str:
    net = _num(flow.get("net_premium"))
    total = _num(flow.get("total_premium"))
    if total <= 0:
        return "Neutral"
    ratio = net / total
    if ratio >= 0.35:
        return "Strong Bullish"
    if ratio >= 0.10:
        return "Bullish"
    if ratio <= -0.35:
        return "Strong Bearish"
    if ratio <= -0.10:
        return "Bearish"
    return "Neutral"


def unusual_contracts_frame(flow: dict[str, Any]) -> pd.DataFrame:
    rows = list(flow.get("unusual_contracts") or [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ["premium_est", "volume", "open_interest", "vol_oi_ratio", "strike"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def top_expirations(contracts: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    if not contracts:
        return []
    df = pd.DataFrame(contracts)
    if df.empty or "expiry" not in df.columns:
        return []
    if "premium_est" not in df.columns:
        df["premium_est"] = 0
    grouped = (
        df.groupby("expiry", dropna=False)
        .agg(contracts=("expiry", "count"), premium=("premium_est", "sum"))
        .reset_index()
        .sort_values("premium", ascending=False)
        .head(limit)
    )
    return grouped.to_dict("records")


def top_strikes(contracts: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    if not contracts:
        return []
    df = pd.DataFrame(contracts)
    if df.empty or "strike" not in df.columns:
        return []
    if "premium_est" not in df.columns:
        df["premium_est"] = 0
    if "type" not in df.columns:
        df["type"] = "UNKNOWN"
    grouped = (
        df.groupby(["type", "strike"], dropna=False)
        .agg(contracts=("strike", "count"), premium=("premium_est", "sum"), volume=("volume", "sum"))
        .reset_index()
        .sort_values("premium", ascending=False)
        .head(limit)
    )
    return grouped.to_dict("records")


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
