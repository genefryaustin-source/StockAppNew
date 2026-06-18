"""
Sprint 9 Phase 2 — Wheel Strategy Command Center Engine.

Institutional wheel strategy operations:
- Cash-secured put queue
- Assignment transition queue
- Covered call queue
- Wheel cycle stage classification
- Wheel income / yield scoring
- Wheel completion metrics
- Action queue for CSP -> Assignment -> Covered Call -> Exit / Repeat

This module does not place trades. It creates deterministic wheel-management guidance.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_WHEEL_POLICY = {
    "target_put_delta_min": 0.15,
    "target_put_delta_max": 0.35,
    "target_call_delta_min": 0.15,
    "target_call_delta_max": 0.35,
    "min_annualized_yield": 8.0,
    "assignment_warning_dte": 7,
    "roll_dte": 21,
    "profit_take_pct": 50.0,
    "covered_call_min_shares": 100,
    "cash_buffer_pct": 10.0,
}


def _df(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def normalize_wheel_positions(positions: Any) -> pd.DataFrame:
    df = _df(positions)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "symbol": "",
        "option_symbol": "",
        "asset_type": "",
        "option_type": "",
        "type": "",
        "strategy": "",
        "expiry": "",
        "dte": 0,
        "strike": 0,
        "underlying_price": 0,
        "last_underlying_price": 0,
        "qty": 0,
        "shares": 0,
        "avg_cost": 0,
        "premium": 0,
        "market_price": 0,
        "market_value": 0,
        "unrealized_pnl": 0,
        "delta": 0,
        "iv": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "dte", "strike", "underlying_price", "last_underlying_price", "qty", "shares",
        "avg_cost", "premium", "market_price", "market_value", "unrealized_pnl",
        "delta", "iv",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["underlying"] = (
        df["underlying"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["symbol"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.upper()
    )

    df["option_type"] = (
        df["option_type"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["type"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.lower()
    )

    df["underlying_price"] = df["underlying_price"].where(
        df["underlying_price"] > 0,
        df["last_underlying_price"],
    )

    basis = (df["avg_cost"].abs() * df["qty"].abs() * 100).replace(0, pd.NA)
    fallback = df["market_value"].abs().replace(0, pd.NA)
    df["pnl_pct"] = (df["unrealized_pnl"] / basis.fillna(fallback).fillna(1) * 100).fillna(0)

    return df


def classify_wheel_stage(row: pd.Series) -> str:
    opt_type = _safe_str(row.get("option_type")).lower()
    strategy = _safe_str(row.get("strategy")).lower()
    qty = _num(row.get("qty"), 0)
    shares = _num(row.get("shares"), 0)
    asset_type = _safe_str(row.get("asset_type")).lower()

    if "wheel" in strategy:
        if opt_type == "put" and qty < 0:
            return "Cash-Secured Put"
        if opt_type == "call" and qty < 0:
            return "Covered Call"
        if shares >= 100 or asset_type in {"stock", "equity"}:
            return "Assigned Stock"

    if opt_type == "put" and qty < 0:
        return "Cash-Secured Put"

    if opt_type == "call" and qty < 0:
        return "Covered Call"

    if shares >= 100 or asset_type in {"stock", "equity"}:
        return "Assigned Stock"

    return "Non-Wheel / Review"


def calculate_annualized_yield(row: pd.Series) -> float:
    premium = _num(row.get("premium"), 0)
    market_price = _num(row.get("market_price"), 0)
    strike = _num(row.get("strike"), 0)
    dte = max(1, _num(row.get("dte"), 30))

    capital = strike * 100 if strike > 0 else max(1, abs(_num(row.get("market_value"), 0)))
    income = premium * 100 if premium > 0 else market_price * 100

    return round((income / max(1, capital)) * (365 / dte) * 100, 2)


def score_wheel_position(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_WHEEL_POLICY

    stage = classify_wheel_stage(row)
    delta = abs(_num(row.get("delta"), 0))
    dte = _num(row.get("dte"), 0)
    pnl_pct = _num(row.get("pnl_pct"), 0)
    annual_yield = calculate_annualized_yield(row)

    score = 50.0
    flags = []

    if stage == "Cash-Secured Put":
        if policy["target_put_delta_min"] <= delta <= policy["target_put_delta_max"]:
            score += 20
            flags.append("Put delta is in target wheel range.")
        elif delta > policy["target_put_delta_max"]:
            score -= 10
            flags.append("Put delta is elevated; assignment probability higher.")
        if annual_yield >= policy["min_annualized_yield"]:
            score += 15
            flags.append("Annualized yield meets target.")
        if 0 < dte <= policy["assignment_warning_dte"]:
            score -= 8
            flags.append("Put near assignment window.")

    elif stage == "Covered Call":
        if policy["target_call_delta_min"] <= delta <= policy["target_call_delta_max"]:
            score += 20
            flags.append("Call delta is in target wheel range.")
        elif delta > policy["target_call_delta_max"]:
            score -= 10
            flags.append("Call delta is elevated; shares may be called away.")
        if annual_yield >= policy["min_annualized_yield"]:
            score += 15
            flags.append("Covered call yield meets target.")
        if pnl_pct >= policy["profit_take_pct"]:
            score += 10
            flags.append("Profit capture threshold reached.")

    elif stage == "Assigned Stock":
        score += 5
        flags.append("Assigned stock available for covered call generation.")

    else:
        score -= 20
        flags.append("Position is not currently wheel-classified.")

    if 0 < dte <= policy["roll_dte"] and stage in {"Cash-Secured Put", "Covered Call"}:
        flags.append("Roll window active.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        quality = "STRONG"
    elif score >= 65:
        quality = "GOOD"
    elif score >= 45:
        quality = "WATCH"
    else:
        quality = "WEAK"

    return {
        "Wheel Stage": stage,
        "Wheel Score": score,
        "Wheel Quality": quality,
        "Annualized Wheel Yield": annual_yield,
        "Wheel Flags": "; ".join(flags) if flags else "No major wheel flags.",
    }


def recommend_wheel_action(row: pd.Series, wheel_score: dict[str, Any], policy: dict[str, Any] | None = None) -> str:
    policy = policy or DEFAULT_WHEEL_POLICY

    stage = wheel_score.get("Wheel Stage", "Non-Wheel / Review")
    dte = _num(row.get("dte"), 0)
    pnl_pct = _num(row.get("pnl_pct"), 0)
    delta = abs(_num(row.get("delta"), 0))

    if stage == "Cash-Secured Put":
        if 0 < dte <= policy["assignment_warning_dte"] and delta >= policy["target_put_delta_max"]:
            return "Prepare Assignment / Roll Put"
        if 0 < dte <= policy["roll_dte"]:
            return "Evaluate Put Roll"
        if pnl_pct >= policy["profit_take_pct"]:
            return "Take Profit / Re-Sell Put"
        return "Hold CSP"

    if stage == "Covered Call":
        if 0 < dte <= policy["assignment_warning_dte"] and delta >= policy["target_call_delta_max"]:
            return "Prepare Called-Away / Roll Call"
        if 0 < dte <= policy["roll_dte"]:
            return "Evaluate Call Roll"
        if pnl_pct >= policy["profit_take_pct"]:
            return "Take Profit / Re-Sell Call"
        return "Hold Covered Call"

    if stage == "Assigned Stock":
        return "Sell Covered Call"

    return "Review"


def analyze_wheel_positions(positions: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_WHEEL_POLICY
    df = normalize_wheel_positions(positions)

    if df.empty:
        return {"available": False, "reason": "No positions available.", "positions": df}

    rows = []
    for _, row in df.iterrows():
        scored = score_wheel_position(row, policy)
        action = recommend_wheel_action(row, scored, policy)
        rows.append({**scored, "Recommended Wheel Action": action})

    scored_df = pd.DataFrame(rows)
    enriched = pd.concat([df.reset_index(drop=True), scored_df.reset_index(drop=True)], axis=1)

    wheel_positions = enriched[enriched["Wheel Stage"] != "Non-Wheel / Review"].copy()
    action_queue = wheel_positions[wheel_positions["Recommended Wheel Action"].str.contains("Prepare|Evaluate|Sell|Take", case=False, na=False)].copy()

    summary = {
        "position_count": int(len(enriched)),
        "wheel_position_count": int(len(wheel_positions)),
        "cash_secured_put_count": int((enriched["Wheel Stage"] == "Cash-Secured Put").sum()),
        "covered_call_count": int((enriched["Wheel Stage"] == "Covered Call").sum()),
        "assigned_stock_count": int((enriched["Wheel Stage"] == "Assigned Stock").sum()),
        "wheel_action_count": int(len(action_queue)),
        "avg_wheel_score": round(float(wheel_positions["Wheel Score"].mean()), 2) if not wheel_positions.empty else 0,
        "avg_annualized_yield": round(float(wheel_positions["Annualized Wheel Yield"].mean()), 2) if not wheel_positions.empty else 0,
    }

    return {
        "available": True,
        "positions": enriched,
        "wheel_positions": wheel_positions,
        "action_queue": action_queue,
        "summary": summary,
        "policy": policy,
    }


def build_wheel_stage_summary(report: dict[str, Any]) -> dict[str, Any]:
    if not report.get("available"):
        return report

    df = report.get("wheel_positions")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": True, "by_stage": pd.DataFrame()}

    table = (
        df.groupby("Wheel Stage", as_index=False)
        .agg(
            positions=("Wheel Stage", "size"),
            avg_score=("Wheel Score", "mean"),
            avg_yield=("Annualized Wheel Yield", "mean"),
            actions=("Recommended Wheel Action", lambda s: int((s != "Hold CSP").sum())),
        )
        .sort_values("positions", ascending=False)
        .reset_index(drop=True)
    )

    for col in ["avg_score", "avg_yield"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(2)

    return {"available": True, "by_stage": table}


def build_wheel_command_report(positions: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    base = analyze_wheel_positions(positions, policy)
    if not base.get("available"):
        return base

    by_stage = build_wheel_stage_summary(base)

    return {
        **base,
        "by_stage": by_stage,
    }


def summarize_wheel_command(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Wheel Strategy unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Wheel Command Center found {s.get('wheel_position_count')} wheel positions: "
        f"{s.get('cash_secured_put_count')} CSPs, {s.get('covered_call_count')} covered calls, "
        f"and {s.get('assigned_stock_count')} assigned-stock positions. "
        f"{s.get('wheel_action_count')} wheel actions are queued. "
        f"Average wheel yield is {s.get('avg_annualized_yield')}%."
    )
