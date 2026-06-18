"""
Sprint 8 Phase 2 — Rolling Intelligence Engine.

Operational roll-management layer for open options positions.
This module does not place trades. It creates deterministic roll recommendations.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_ROLL_POLICY = {
    "roll_dte": 21,
    "urgent_roll_dte": 7,
    "profit_roll_pct": 50.0,
    "loss_roll_pct": -35.0,
    "high_delta_threshold": 0.70,
    "assignment_risk_dte": 5,
    "target_roll_dte_min": 30,
    "target_roll_dte_max": 60,
    "min_credit_to_roll": 0.01,
    "max_debit_pct_of_risk": 15.0,
}


def _empty(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


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


def normalize_roll_positions(positions: Any) -> pd.DataFrame:
    df = normalize_risk_positions(positions)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "option_symbol": "",
        "option_type": "",
        "type": "",
        "strategy": "Unclassified",
        "expiry": "",
        "strike": 0,
        "qty": 0,
        "avg_cost": 0,
        "market_price": 0,
        "market_value": 0,
        "unrealized_pnl": 0,
        "dte": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "bid": 0,
        "ask": 0,
        "mid": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "strike", "qty", "avg_cost", "market_price", "market_value", "unrealized_pnl",
        "dte", "delta", "gamma", "theta", "vega", "bid", "ask", "mid",
        "notional_proxy", "net_delta", "net_gamma", "net_theta", "net_vega",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

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

    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified").astype(str)

    df["mid"] = df["mid"].where(df["mid"] > 0, ((df["bid"] + df["ask"]) / 2))
    df["mid"] = df["mid"].where(df["mid"] > 0, df["market_price"])

    basis = (df["avg_cost"].abs() * df["qty"].abs() * 100).replace(0, pd.NA)
    fallback = df["market_value"].abs().replace(0, pd.NA)
    df["pnl_pct"] = (df["unrealized_pnl"] / basis.fillna(fallback).fillna(1) * 100).fillna(0)

    return df


def classify_roll_type(row: pd.Series) -> str:
    strategy = _safe_str(row.get("strategy")).lower()
    opt_type = _safe_str(row.get("option_type")).lower()
    qty = _num(row.get("qty"), 0)

    if "covered" in strategy and opt_type == "call":
        return "Covered Call Roll"
    if ("cash" in strategy or "secured" in strategy) and opt_type == "put":
        return "Cash-Secured Put Roll"
    if "vertical" in strategy or "spread" in strategy:
        return "Spread Roll"
    if "calendar" in strategy:
        return "Calendar Roll"
    if "diagonal" in strategy:
        return "Diagonal Roll"
    if qty < 0 and opt_type == "call":
        return "Short Call Roll"
    if qty < 0 and opt_type == "put":
        return "Short Put Roll"
    if opt_type in {"call", "put"}:
        return "Long Option Roll"
    return "Generic Roll Review"


def score_roll_candidate(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_ROLL_POLICY

    dte = _num(row.get("dte"), 0)
    pnl_pct = _num(row.get("pnl_pct"), 0)
    delta = abs(_num(row.get("delta"), 0))
    gamma = abs(_num(row.get("gamma"), 0))
    theta = _num(row.get("theta"), 0)
    qty = _num(row.get("qty"), 0)

    score = 0.0
    flags = []

    if 0 < dte <= policy["urgent_roll_dte"]:
        score += 35
        flags.append("Urgent expiration window.")
    elif 0 < dte <= policy["roll_dte"]:
        score += 22
        flags.append("Standard roll window active.")

    if pnl_pct >= policy["profit_roll_pct"]:
        score += 20
        flags.append("Profit capture threshold reached.")

    if pnl_pct <= policy["loss_roll_pct"]:
        score += 20
        flags.append("Loss threshold suggests defensive roll/review.")

    if 0 < dte <= policy["assignment_risk_dte"] and delta >= policy["high_delta_threshold"] and qty < 0:
        score += 30
        flags.append("Short option assignment risk elevated.")

    if 0 < dte <= 5 and gamma > 0.05:
        score += 12
        flags.append("Short-dated gamma risk.")

    if theta < -25 and dte <= policy["roll_dte"]:
        score += 8
        flags.append("Theta pressure into roll window.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        urgency = "CRITICAL"
    elif score >= 55:
        urgency = "HIGH"
    elif score >= 30:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    if score >= 55:
        decision = "ROLL_NOW"
    elif score >= 30:
        decision = "EVALUATE_ROLL"
    else:
        decision = "HOLD"

    return {
        "Roll Score": score,
        "Roll Urgency": urgency,
        "Roll Decision": decision,
        "Roll Flags": "; ".join(flags) if flags else "No major roll flags.",
    }


def generate_roll_guidance(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_ROLL_POLICY

    roll_type = classify_roll_type(row)
    opt_type = _safe_str(row.get("option_type")).lower()
    strike = _num(row.get("strike"), 0)
    dte = _num(row.get("dte"), 0)
    delta = _num(row.get("delta"), 0)
    qty = _num(row.get("qty"), 0)
    mid = _num(row.get("mid"), 0)

    target_min = int(policy["target_roll_dte_min"])
    target_max = int(policy["target_roll_dte_max"])

    direction = "Same strike / later expiry"
    strike_guidance = strike

    if qty < 0 and opt_type == "call":
        if abs(delta) >= policy["high_delta_threshold"]:
            direction = "Roll out and up"
            strike_guidance = strike * 1.03 if strike else strike
        else:
            direction = "Roll out at same or slightly higher strike"
            strike_guidance = strike * 1.01 if strike else strike
    elif qty < 0 and opt_type == "put":
        if abs(delta) >= policy["high_delta_threshold"]:
            direction = "Roll out and down"
            strike_guidance = strike * 0.97 if strike else strike
        else:
            direction = "Roll out at same or slightly lower strike"
            strike_guidance = strike * 0.99 if strike else strike
    elif qty > 0:
        direction = "Roll out to preserve optionality"
        strike_guidance = strike

    estimated_close = mid
    estimated_new_premium = max(0.01, mid * (1.10 if dte <= 7 else 1.03))
    estimated_net_credit = estimated_new_premium - estimated_close

    if qty > 0:
        estimated_net_credit = -abs(estimated_close - estimated_new_premium)

    debit_credit = "Credit" if estimated_net_credit >= 0 else "Debit"

    return {
        "Roll Type": roll_type,
        "Roll Direction": direction,
        "Target DTE Window": f"{target_min}-{target_max} DTE",
        "Suggested Strike": round(strike_guidance, 2),
        "Current Mid": round(mid, 4),
        "Estimated New Premium": round(estimated_new_premium, 4),
        "Estimated Net Credit/Debit": round(estimated_net_credit, 4),
        "Credit/Debit": debit_credit,
        "Guidance": f"{roll_type}: {direction}; {'seek a net credit' if estimated_net_credit >= 0 else 'limit the net debit'}; avoid market orders.",
    }


def analyze_roll_candidates(positions: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_ROLL_POLICY
    df = normalize_roll_positions(positions)

    if df.empty:
        return {"available": False, "reason": "No positions available.", "positions": df}

    scores = pd.DataFrame([score_roll_candidate(row, policy=policy) for _, row in df.iterrows()])
    guidance = pd.DataFrame([generate_roll_guidance(row, policy=policy) for _, row in df.iterrows()])

    enriched = pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True), guidance.reset_index(drop=True)], axis=1)

    action_queue = enriched[enriched["Roll Decision"] != "HOLD"].copy()
    priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    if not action_queue.empty:
        action_queue["_priority"] = action_queue["Roll Urgency"].map(priority).fillna(9)
        action_queue = action_queue.sort_values(["_priority", "Roll Score"], ascending=[True, False]).drop(columns=["_priority"]).reset_index(drop=True)

    return {
        "available": True,
        "positions": enriched,
        "roll_queue": action_queue,
        "summary": {
            "position_count": int(len(enriched)),
            "roll_candidate_count": int(len(action_queue)),
            "critical_count": int((enriched["Roll Urgency"] == "CRITICAL").sum()),
            "high_count": int((enriched["Roll Urgency"] == "HIGH").sum()),
            "avg_roll_score": round(float(enriched["Roll Score"].mean()), 2),
        },
    }


def build_roll_strategy_summary(roll_report: dict[str, Any]) -> dict[str, Any]:
    if not roll_report.get("available"):
        return roll_report

    df = roll_report.get("positions")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty("No roll positions available.")

    table = (
        df.groupby("Roll Type", as_index=False)
        .agg(
            positions=("Roll Type", "size"),
            avg_score=("Roll Score", "mean"),
            roll_now=("Roll Decision", lambda s: int((s == "ROLL_NOW").sum())),
            evaluate=("Roll Decision", lambda s: int((s == "EVALUATE_ROLL").sum())),
            avg_dte=("dte", "mean"),
            avg_pnl_pct=("pnl_pct", "mean"),
        )
        .sort_values("avg_score", ascending=False)
        .reset_index(drop=True)
    )

    for col in ["avg_score", "avg_dte", "avg_pnl_pct"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(2)

    return {"available": True, "by_roll_type": table}


def build_rolling_intelligence_report(positions: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    roll = analyze_roll_candidates(positions, policy=policy)
    if not roll.get("available"):
        return roll
    by_type = build_roll_strategy_summary(roll)
    return {**roll, "by_roll_type": by_type, "policy": policy or DEFAULT_ROLL_POLICY}


def summarize_rolling_intelligence(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Rolling intelligence unavailable: {report.get('reason', 'unknown reason')}"

    summary = report.get("summary", {})
    return (
        f"Rolling Intelligence found {summary.get('roll_candidate_count')} roll candidates "
        f"out of {summary.get('position_count')} positions. "
        f"{summary.get('critical_count')} are critical and {summary.get('high_count')} are high urgency. "
        f"Average roll score is {summary.get('avg_roll_score')}/100."
    )
