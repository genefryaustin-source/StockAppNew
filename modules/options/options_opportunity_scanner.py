"""
Sprint 4 Phase 5 — Options Opportunity Scanner.

Combines Sprint 4 intelligence reports into normalized opportunity candidates.
Works with optional/missing report data and avoids hard dependencies on UI state.
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


def _safe(value: Any, default: Any = None) -> Any:
    return default if value is None else value


def infer_directional_bias(
    intelligence_report: dict[str, Any] | None = None,
    flow_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 50.0
    reasons: list[str] = []

    pressure = (intelligence_report or {}).get("pressure", {})
    if pressure.get("available"):
        p = float(pressure.get("pressure_score", 50))
        score += (p - 50) * 0.25
        reasons.append(f"Expiration pressure {pressure.get('expiration_pressure')} ({p}/100)")

    flow_bias = (flow_report or {}).get("bias")
    flow_score = float((flow_report or {}).get("regime_score", 0) or 0)
    if flow_bias == "BULLISH":
        score += min(15, flow_score * 0.15)
        reasons.append("Flow bias bullish")
    elif flow_bias == "BEARISH":
        score -= min(15, flow_score * 0.15)
        reasons.append("Flow bias bearish")

    dealer = (market_maker_report or {}).get("dealer", {})
    if dealer.get("delta_bias") == "DEALER_SHORT_DELTA":
        score += 5
        reasons.append("Dealer short-delta pressure")
    elif dealer.get("delta_bias") == "DEALER_LONG_DELTA":
        score -= 5
        reasons.append("Dealer long-delta pressure")

    skew = (volatility_report or {}).get("skew", {})
    if skew.get("skew_regime") == "FEAR_SKEW":
        score -= 3
        reasons.append("Put skew elevated")
    elif skew.get("skew_regime") == "CALL_DEMAND_SKEW":
        score += 3
        reasons.append("Call skew elevated")

    score = max(0.0, min(100.0, round(score, 2)))

    if score >= 60:
        bias = "BULLISH"
    elif score <= 40:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return {"bias": bias, "direction_score": score, "reasons": reasons}


def scan_option_opportunities(
    ticker: str,
    chain_data: dict[str, Any] | None,
    intelligence_report: dict[str, Any] | None = None,
    flow_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
    max_candidates: int = 25,
) -> list[dict[str, Any]]:
    df = _as_frame(chain_data)
    if df.empty:
        return []

    df = df.copy()
    for col in ["expiry", "strike", "type", "bid", "ask", "last", "iv", "delta", "volume", "open_interest", "dte", "option_symbol"]:
        if col not in df.columns:
            df[col] = None

    df["strike"] = _num(df["strike"])
    df["bid"] = _num(df["bid"]).fillna(0)
    df["ask"] = _num(df["ask"]).fillna(0)
    df["last"] = _num(df["last"]).fillna(0)
    df["iv"] = _num(df["iv"])
    df["delta"] = _num(df["delta"])
    df["volume"] = _num(df["volume"]).fillna(0)
    df["open_interest"] = _num(df["open_interest"]).fillna(0)
    df["dte"] = _num(df["dte"])
    df["type"] = df["type"].astype(str).str.lower()
    df["mid"] = ((df["bid"] + df["ask"]) / 2).mask(lambda s: s <= 0, df["last"]).fillna(0)
    df["spread"] = (df["ask"] - df["bid"]).clip(lower=0)
    df["spread_pct"] = (df["spread"] / df["mid"].replace(0, 1)).clip(lower=0)
    df["liquidity_rank"] = (
        df["volume"].rank(pct=True).fillna(0) * 0.45
        + df["open_interest"].rank(pct=True).fillna(0) * 0.45
        + (1 - df["spread_pct"].rank(pct=True).fillna(1)) * 0.10
    )

    bias = infer_directional_bias(
        intelligence_report=intelligence_report,
        flow_report=flow_report,
        market_maker_report=market_maker_report,
        volatility_report=volatility_report,
    )

    vol_regime = (volatility_report or {}).get("volatility_regime", "UNKNOWN")
    opportunities: list[dict[str, Any]] = []

    # Single-leg candidate seeds.
    liquid = df[(df["mid"] > 0) & (df["volume"] >= 10)].copy()
    if liquid.empty:
        liquid = df[df["mid"] > 0].copy()

    if bias["bias"] == "BULLISH":
        calls = liquid[liquid["type"] == "call"].copy()
        calls = calls.sort_values(["liquidity_rank", "open_interest"], ascending=False).head(max_candidates)
        for _, row in calls.iterrows():
            opportunities.append({
                "ticker": ticker.upper(),
                "strategy": "Bull Call Spread",
                "direction": "BULLISH",
                "expiry": row.get("expiry"),
                "primary_strike": row.get("strike"),
                "option_type": "call",
                "reference_contract": row.get("option_symbol"),
                "estimated_cost": round(float(row.get("mid") or 0), 2),
                "liquidity_score": round(float(row.get("liquidity_rank") or 0) * 100, 2),
                "rationale": "Bullish bias plus liquid call structure candidate.",
            })

    elif bias["bias"] == "BEARISH":
        puts = liquid[liquid["type"] == "put"].copy()
        puts = puts.sort_values(["liquidity_rank", "open_interest"], ascending=False).head(max_candidates)
        for _, row in puts.iterrows():
            opportunities.append({
                "ticker": ticker.upper(),
                "strategy": "Bear Put Spread",
                "direction": "BEARISH",
                "expiry": row.get("expiry"),
                "primary_strike": row.get("strike"),
                "option_type": "put",
                "reference_contract": row.get("option_symbol"),
                "estimated_cost": round(float(row.get("mid") or 0), 2),
                "liquidity_score": round(float(row.get("liquidity_rank") or 0) * 100, 2),
                "rationale": "Bearish bias plus liquid put structure candidate.",
            })

    else:
        neutral = liquid.sort_values(["liquidity_rank", "open_interest"], ascending=False).head(max_candidates)
        neutral_strategy = "Iron Condor" if vol_regime in {"ELEVATED_VOL", "EXTREME_VOL", "EVENT_VOL"} else "Calendar Spread"
        for _, row in neutral.iterrows():
            opportunities.append({
                "ticker": ticker.upper(),
                "strategy": neutral_strategy,
                "direction": "NEUTRAL",
                "expiry": row.get("expiry"),
                "primary_strike": row.get("strike"),
                "option_type": row.get("type"),
                "reference_contract": row.get("option_symbol"),
                "estimated_cost": round(float(row.get("mid") or 0), 2),
                "liquidity_score": round(float(row.get("liquidity_rank") or 0) * 100, 2),
                "rationale": f"Neutral bias with {vol_regime} volatility regime.",
            })

    # Add volatility-specific ideas.
    if vol_regime in {"ELEVATED_VOL", "EXTREME_VOL", "EVENT_VOL"}:
        opportunities.append({
            "ticker": ticker.upper(),
            "strategy": "Short Premium Basket",
            "direction": "NEUTRAL",
            "expiry": None,
            "primary_strike": None,
            "option_type": "multi-leg",
            "reference_contract": "",
            "estimated_cost": None,
            "liquidity_score": 50,
            "rationale": "Elevated volatility regime supports defined-risk premium selling.",
        })
    elif vol_regime == "LOW_VOL":
        opportunities.append({
            "ticker": ticker.upper(),
            "strategy": "Long Volatility Basket",
            "direction": "VOL_EXPANSION",
            "expiry": None,
            "primary_strike": None,
            "option_type": "multi-leg",
            "reference_contract": "",
            "estimated_cost": None,
            "liquidity_score": 50,
            "rationale": "Low volatility regime supports long-premium or debit structures.",
        })

    return opportunities[:max_candidates]
