"""
Sprint 8 Phase 1 — Position Lifecycle Intelligence Engine.

Operational lifecycle layer for open options positions:
- Position health scoring
- DTE / expiration monitoring
- Profit target monitoring
- Stop-loss monitoring
- Gamma / theta risk diagnostics
- Assignment risk proxy
- Roll / close / trim / hedge recommendations
- Urgency classification

This module does not place trades. It generates position-management decisions.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_LIFECYCLE_POLICY = {
    "profit_take_pct": 50.0,
    "trim_profit_pct": 30.0,
    "stop_loss_pct": -50.0,
    "warning_loss_pct": -25.0,
    "roll_dte": 21,
    "expiration_warning_dte": 7,
    "gamma_risk_dte": 5,
    "assignment_risk_dte": 5,
    "high_delta_assignment_threshold": 0.75,
    "theta_burn_threshold": -50.0,
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


def normalize_lifecycle_positions(positions: Any) -> pd.DataFrame:
    df = normalize_risk_positions(positions)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "created_at": "",
        "opened_at": "",
        "strategy": "Unclassified",
        "avg_cost": 0,
        "market_value": 0,
        "unrealized_pnl": 0,
        "dte": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "option_type": "",
        "type": "",
        "qty": 0,
        "strike": 0,
        "underlying": "",
        "option_symbol": "",
        "expiry": "",
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    numeric_cols = [
        "avg_cost",
        "market_value",
        "unrealized_pnl",
        "dte",
        "delta",
        "gamma",
        "theta",
        "vega",
        "qty",
        "strike",
        "notional_proxy",
        "net_delta",
        "net_gamma",
        "net_theta",
        "net_vega",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    cost_basis = (df["avg_cost"].abs() * df["qty"].abs() * df.get("multiplier", 100)).replace(0, pd.NA)
    fallback_basis = df["market_value"].abs().replace(0, pd.NA)
    basis = cost_basis.fillna(fallback_basis).fillna(1)

    df["pnl_pct"] = (df["unrealized_pnl"] / basis * 100).replace([float("inf"), -float("inf")], 0).fillna(0)
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

    return df


def score_position_lifecycle(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_LIFECYCLE_POLICY

    pnl_pct = _num(row.get("pnl_pct"), 0)
    dte = _num(row.get("dte"), 0)
    delta = abs(_num(row.get("delta"), 0))
    gamma = abs(_num(row.get("gamma"), 0))
    theta = _num(row.get("theta"), 0)
    net_gamma = abs(_num(row.get("net_gamma"), 0))
    net_theta = _num(row.get("net_theta"), 0)
    qty = _num(row.get("qty"), 0)
    option_type = _safe_str(row.get("option_type")).lower()

    health = 100.0
    urgency_points = 0.0
    flags = []

    if pnl_pct >= policy["profit_take_pct"]:
        flags.append("Profit target reached.")
        urgency_points += 20
        health -= 5
    elif pnl_pct >= policy["trim_profit_pct"]:
        flags.append("Profit is favorable; consider trim.")
        urgency_points += 10

    if pnl_pct <= policy["stop_loss_pct"]:
        flags.append("Stop-loss threshold breached.")
        urgency_points += 35
        health -= 35
    elif pnl_pct <= policy["warning_loss_pct"]:
        flags.append("Loss warning threshold reached.")
        urgency_points += 15
        health -= 15

    if 0 < dte <= policy["expiration_warning_dte"]:
        flags.append("Expiration window approaching.")
        urgency_points += 25
        health -= 20
    elif 0 < dte <= policy["roll_dte"]:
        flags.append("Roll window active.")
        urgency_points += 12
        health -= 5

    if 0 < dte <= policy["gamma_risk_dte"] and (gamma > 0.05 or net_gamma > 100):
        flags.append("Short-dated gamma risk elevated.")
        urgency_points += 20
        health -= 20

    if 0 < dte <= policy["assignment_risk_dte"] and delta >= policy["high_delta_assignment_threshold"]:
        flags.append("Assignment risk elevated.")
        urgency_points += 25
        health -= 25

    if theta <= policy["theta_burn_threshold"] or net_theta <= policy["theta_burn_threshold"]:
        flags.append("Theta burn is elevated.")
        urgency_points += 10
        health -= 10

    if option_type in {"stock", "equity"}:
        flags.append("Stock leg detected; lifecycle rules are options-focused.")

    health = round(max(0, min(100, health)), 2)
    urgency = round(max(0, min(100, urgency_points)), 2)

    if urgency >= 70:
        urgency_level = "CRITICAL"
    elif urgency >= 45:
        urgency_level = "HIGH"
    elif urgency >= 20:
        urgency_level = "MEDIUM"
    else:
        urgency_level = "LOW"

    if health >= 80:
        health_level = "HEALTHY"
    elif health >= 60:
        health_level = "WATCH"
    elif health >= 40:
        health_level = "AT_RISK"
    else:
        health_level = "CRITICAL"

    action = recommend_lifecycle_action(
        pnl_pct=pnl_pct,
        dte=dte,
        delta=delta,
        urgency_level=urgency_level,
        health_level=health_level,
        flags=flags,
        policy=policy,
    )

    return {
        "Position Health Score": health,
        "Position Health": health_level,
        "Urgency Score": urgency,
        "Urgency": urgency_level,
        "Recommended Action": action,
        "Lifecycle Flags": "; ".join(flags) if flags else "No major lifecycle flags.",
    }


def recommend_lifecycle_action(
    pnl_pct: float,
    dte: float,
    delta: float,
    urgency_level: str,
    health_level: str,
    flags: list[str],
    policy: dict[str, Any],
) -> str:
    flag_text = " ".join(flags).lower()

    if "stop-loss" in flag_text:
        return "Close / Reduce"

    if "assignment risk" in flag_text:
        return "Close / Roll"

    if "short-dated gamma" in flag_text:
        return "Hedge / Reduce"

    if pnl_pct >= policy["profit_take_pct"]:
        return "Take Profit"

    if pnl_pct >= policy["trim_profit_pct"]:
        return "Trim"

    if 0 < dte <= policy["expiration_warning_dte"]:
        return "Roll / Close"

    if 0 < dte <= policy["roll_dte"]:
        return "Evaluate Roll"

    if urgency_level in {"CRITICAL", "HIGH"} or health_level in {"CRITICAL", "AT_RISK"}:
        return "Review"

    return "Hold"


def analyze_position_lifecycle(
    positions: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_LIFECYCLE_POLICY
    df = normalize_lifecycle_positions(positions)

    if df.empty:
        return {"available": False, "reason": "No positions available.", "positions": df}

    scores = pd.DataFrame([score_position_lifecycle(row, policy=policy) for _, row in df.iterrows()])
    enriched = pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)

    action_counts = (
        enriched["Recommended Action"]
        .value_counts()
        .rename_axis("Action")
        .reset_index(name="Count")
    )

    urgency_counts = (
        enriched["Urgency"]
        .value_counts()
        .rename_axis("Urgency")
        .reset_index(name="Count")
    )

    avg_health = round(float(enriched["Position Health Score"].mean()), 2)
    max_urgency = round(float(enriched["Urgency Score"].max()), 2)

    if avg_health >= 80:
        portfolio_lifecycle = "HEALTHY"
    elif avg_health >= 60:
        portfolio_lifecycle = "WATCH"
    elif avg_health >= 40:
        portfolio_lifecycle = "AT_RISK"
    else:
        portfolio_lifecycle = "CRITICAL"

    return {
        "available": True,
        "positions": enriched,
        "summary": {
            "position_count": int(len(enriched)),
            "avg_health_score": avg_health,
            "max_urgency_score": max_urgency,
            "portfolio_lifecycle_status": portfolio_lifecycle,
            "action_required_count": int((enriched["Recommended Action"] != "Hold").sum()),
            "critical_count": int((enriched["Urgency"] == "CRITICAL").sum()),
            "high_urgency_count": int((enriched["Urgency"] == "HIGH").sum()),
        },
        "action_counts": action_counts,
        "urgency_counts": urgency_counts,
    }


def build_lifecycle_action_queue(positions: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    report = analyze_position_lifecycle(positions, policy=policy)
    if not report.get("available"):
        return report

    df = report["positions"].copy()
    queue = df[df["Recommended Action"] != "Hold"].copy()

    priority_map = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
    }
    queue["_priority"] = queue["Urgency"].map(priority_map).fillna(9)
    queue = queue.sort_values(["_priority", "Urgency Score", "Position Health Score"], ascending=[True, False, True])
    queue = queue.drop(columns=["_priority"]).reset_index(drop=True)

    show_cols = [
        "underlying",
        "option_symbol",
        "option_type",
        "strategy",
        "expiry",
        "dte",
        "strike",
        "qty",
        "market_value",
        "unrealized_pnl",
        "pnl_pct",
        "Position Health Score",
        "Position Health",
        "Urgency",
        "Recommended Action",
        "Lifecycle Flags",
    ]
    show_cols = [c for c in show_cols if c in queue.columns]

    return {
        "available": True,
        "action_queue": queue[show_cols] if not queue.empty else queue,
        "queue_count": int(len(queue)),
    }


def build_position_lifecycle_report(
    positions: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lifecycle = analyze_position_lifecycle(positions, policy=policy)
    if not lifecycle.get("available"):
        return lifecycle

    queue = build_lifecycle_action_queue(positions, policy=policy)

    return {
        **lifecycle,
        "action_queue": queue,
        "policy": policy or DEFAULT_LIFECYCLE_POLICY,
    }


def summarize_position_lifecycle(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Position lifecycle unavailable: {report.get('reason', 'unknown reason')}"

    summary = report.get("summary", {})

    return (
        f"Portfolio lifecycle status is {summary.get('portfolio_lifecycle_status')} "
        f"with average health {summary.get('avg_health_score')}/100. "
        f"{summary.get('action_required_count')} positions require action, including "
        f"{summary.get('critical_count')} critical and "
        f"{summary.get('high_urgency_count')} high-urgency positions."
    )
