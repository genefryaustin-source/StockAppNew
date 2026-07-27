"""
Sprint 7 Phase 5 — Autonomous Portfolio Manager.

Decision-support layer for autonomous options portfolio management.

This module DOES NOT place trades. It produces:
- Portfolio management state
- Autonomous recommendations
- Risk-aware action queue
- Rebalance priorities
- Execution handoff candidates
- Governance status

Designed to consume outputs from Sprint 5/6/7 engines while remaining defensive
when some reports are unavailable.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_AUTONOMOUS_POLICY = {
    "autonomy_level": "ADVISORY",          # OBSERVE | ADVISORY | APPROVAL_REQUIRED | AUTONOMOUS_SIM
    "max_portfolio_risk_score": 70,
    "max_stress_loss_pct": 12,
    "max_hedge_need_score": 70,
    "min_liquidity_score": 55,
    "min_trade_optimization_score": 65,
    "min_planner_readiness_score": 65,
    "allow_add_risk_when_risk_off": False,
    "require_human_approval": True,
}


def _empty(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _safe_get(d: Any, path: list[str], default: Any = None) -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def evaluate_portfolio_management_state(
    positions: Any,
    portfolio_risk_report: dict[str, Any] | None = None,
    stress_report: dict[str, Any] | None = None,
    hedge_report: dict[str, Any] | None = None,
    dynamic_risk_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_AUTONOMOUS_POLICY
    df = normalize_risk_positions(positions)

    if df.empty:
        return _empty("No options positions available.")

    portfolio_risk = _num(_safe_get(portfolio_risk_report, ["risk_score", "risk_score"], 0))
    stress_loss = 0.0
    worst = _safe_get(stress_report, ["scenarios", "worst_case"], {})
    if isinstance(worst, dict):
        stress_loss = abs(_num(worst.get("Total P&L % Notional"), 0))

    hedge_need = _num(_safe_get(hedge_report, ["hedge_need", "hedge_need_score"], 0))
    dynamic_state = _safe_get(dynamic_risk_report, ["risk_state", "risk_state"], "NEUTRAL")
    dynamic_pressure = _num(_safe_get(dynamic_risk_report, ["risk_state", "risk_pressure_score"], 0))
    liquidity = _num(_safe_get(liquidity_report, ["summary", "avg_liquidity_score"], 75))
    construction_score = _num(_safe_get(construction_report, ["score", "construction_score"], 75))

    pressure = 0.0
    drivers = []

    if portfolio_risk > policy["max_portfolio_risk_score"]:
        pressure += 25
        drivers.append("Portfolio risk above policy.")

    if stress_loss > policy["max_stress_loss_pct"]:
        pressure += 25
        drivers.append("Stress loss above policy.")

    if hedge_need > policy["max_hedge_need_score"]:
        pressure += 20
        drivers.append("Hedge need above policy.")

    if liquidity < policy["min_liquidity_score"]:
        pressure += 15
        drivers.append("Liquidity below policy.")

    if construction_score < 60:
        pressure += 15
        drivers.append("Portfolio construction score weak.")

    if str(dynamic_state).upper() in {"RISK_OFF", "REDUCE_RISK"}:
        pressure += 20
        drivers.append(f"Dynamic risk state is {dynamic_state}.")

    pressure = round(min(100, max(0, pressure + dynamic_pressure * 0.15)), 2)

    if pressure >= 80:
        manager_state = "DEFENSIVE"
    elif pressure >= 55:
        manager_state = "RISK_REDUCTION"
    elif pressure >= 30:
        manager_state = "BALANCED"
    else:
        manager_state = "OPPORTUNISTIC"

    return {
        "available": True,
        "manager_state": manager_state,
        "manager_pressure_score": pressure,
        "portfolio_risk_score": portfolio_risk,
        "stress_loss_pct": round(stress_loss, 2),
        "hedge_need_score": hedge_need,
        "dynamic_risk_state": dynamic_state,
        "dynamic_pressure_score": dynamic_pressure,
        "liquidity_score": liquidity,
        "construction_score": construction_score,
        "drivers": drivers or ["No major autonomous management pressure detected."],
    }


def generate_autonomous_recommendations(
    management_state: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_AUTONOMOUS_POLICY

    if not management_state.get("available"):
        return management_state

    state = management_state.get("manager_state", "BALANCED")
    actions = []

    if state == "DEFENSIVE":
        actions.extend([
            {
                "Priority": "Critical",
                "Action": "Reduce gross exposure",
                "Category": "Risk",
                "Reason": "Autonomous manager state is DEFENSIVE.",
                "Requires Approval": True,
            },
            {
                "Priority": "Critical",
                "Action": "Increase hedge coverage",
                "Category": "Hedging",
                "Reason": "Portfolio protection should be prioritized.",
                "Requires Approval": True,
            },
            {
                "Priority": "High",
                "Action": "Pause new directional risk",
                "Category": "Execution",
                "Reason": "Risk pressure does not support adding directional exposure.",
                "Requires Approval": False,
            },
        ])

    elif state == "RISK_REDUCTION":
        actions.extend([
            {
                "Priority": "High",
                "Action": "Trim largest risk contributors",
                "Category": "Risk",
                "Reason": "Risk pressure is elevated.",
                "Requires Approval": True,
            },
            {
                "Priority": "Medium",
                "Action": "Rotate toward defined-risk income or hedge structures",
                "Category": "Construction",
                "Reason": "Reduce portfolio fragility.",
                "Requires Approval": True,
            },
        ])

    elif state == "BALANCED":
        actions.extend([
            {
                "Priority": "Normal",
                "Action": "Maintain current risk profile",
                "Category": "Portfolio",
                "Reason": "Risk pressure is manageable.",
                "Requires Approval": False,
            },
            {
                "Priority": "Normal",
                "Action": "Only approve high-quality optimized trades",
                "Category": "Execution",
                "Reason": "Preserve quality filter.",
                "Requires Approval": False,
            },
        ])

    else:
        actions.extend([
            {
                "Priority": "Normal",
                "Action": "Allow selective capital deployment",
                "Category": "Opportunity",
                "Reason": "Portfolio state supports selective risk additions.",
                "Requires Approval": policy.get("require_human_approval", True),
            },
            {
                "Priority": "Normal",
                "Action": "Prioritize high-liquidity, high-conviction trades",
                "Category": "Execution",
                "Reason": "Risk state is supportive but quality filters remain active.",
                "Requires Approval": policy.get("require_human_approval", True),
            },
        ])

    if management_state.get("liquidity_score", 100) < policy["min_liquidity_score"]:
        actions.append({
            "Priority": "High",
            "Action": "Avoid low-liquidity option contracts",
            "Category": "Liquidity",
            "Reason": "Liquidity score below policy threshold.",
            "Requires Approval": False,
        })

    if management_state.get("hedge_need_score", 0) > policy["max_hedge_need_score"]:
        actions.append({
            "Priority": "High",
            "Action": "Review hedge candidate queue",
            "Category": "Hedging",
            "Reason": "Hedge need score above policy threshold.",
            "Requires Approval": True,
        })

    return {
        "available": True,
        "recommendations": pd.DataFrame(actions),
    }


def build_action_queue(
    recommendations: dict[str, Any],
    trade_optimization_report: dict[str, Any] | None = None,
    trade_planner_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_AUTONOMOUS_POLICY

    rows = []

    recs = recommendations.get("recommendations")
    if isinstance(recs, pd.DataFrame) and not recs.empty:
        for _, row in recs.iterrows():
            rows.append({
                "Source": "Portfolio Manager",
                "Priority": row.get("Priority", "Normal"),
                "Action": row.get("Action", ""),
                "Category": row.get("Category", ""),
                "Reason": row.get("Reason", ""),
                "Requires Approval": bool(row.get("Requires Approval", True)),
                "Status": "Pending Approval" if bool(row.get("Requires Approval", True)) else "Ready",
            })

    candidates = _safe_get(trade_optimization_report, ["top_trades"], None)
    if isinstance(candidates, pd.DataFrame) and not candidates.empty:
        for _, row in candidates.head(5).iterrows():
            score = _num(row.get("optimization_score"), 0)
            if score >= policy["min_trade_optimization_score"]:
                rows.append({
                    "Source": "Trade Optimization",
                    "Priority": "High" if score >= 80 else "Medium",
                    "Action": f"Review optimized trade: {row.get('ticker', '')} {row.get('strategy', '')}",
                    "Category": "Trade",
                    "Reason": f"Optimization score {score}/100.",
                    "Requires Approval": True,
                    "Status": "Pending Approval",
                })

    plans = _safe_get(trade_planner_report, ["plan_summary"], None)
    if isinstance(plans, pd.DataFrame) and not plans.empty:
        for _, row in plans.head(5).iterrows():
            readiness = _num(row.get("Readiness Score"), 0)
            decision = str(row.get("Decision", ""))
            if readiness >= policy["min_planner_readiness_score"] and decision in {"APPROVE", "APPROVE_WITH_REVIEW"}:
                rows.append({
                    "Source": "Trade Planner",
                    "Priority": "High" if readiness >= 85 else "Medium",
                    "Action": f"Approve planned trade: {row.get('Ticker', '')} {row.get('Strategy', '')}",
                    "Category": "Trade Plan",
                    "Reason": f"Planner readiness {readiness}/100.",
                    "Requires Approval": True,
                    "Status": "Pending Approval",
                })

    queue = pd.DataFrame(rows)

    if not queue.empty:
        priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Normal": 3, "Low": 4}
        queue["_sort"] = queue["Priority"].map(priority_order).fillna(9)
        queue = queue.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "action_queue": queue,
        "action_count": int(len(queue)),
        "approval_required_count": int(queue["Requires Approval"].sum()) if not queue.empty else 0,
    }


def evaluate_governance_status(
    action_queue: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_AUTONOMOUS_POLICY
    queue = action_queue.get("action_queue")

    if not isinstance(queue, pd.DataFrame) or queue.empty:
        return {
            "available": True,
            "governance_status": "CLEAR",
            "approval_required": False,
            "reason": "No actions pending.",
        }

    approval_required = bool(queue["Requires Approval"].any())
    critical_count = int((queue["Priority"] == "Critical").sum())

    if critical_count > 0:
        status = "CRITICAL_REVIEW"
    elif approval_required:
        status = "APPROVAL_REQUIRED"
    elif policy.get("autonomy_level") == "OBSERVE":
        status = "OBSERVE_ONLY"
    else:
        status = "READY"

    return {
        "available": True,
        "governance_status": status,
        "approval_required": approval_required,
        "critical_actions": critical_count,
        "autonomy_level": policy.get("autonomy_level", "ADVISORY"),
        "reason": (
            "Human approval required before execution handoff."
            if approval_required
            else "No approval blockers detected."
        ),
    }


def build_autonomous_portfolio_manager_report(
    positions: Any,
    portfolio_risk_report: dict[str, Any] | None = None,
    stress_report: dict[str, Any] | None = None,
    hedge_report: dict[str, Any] | None = None,
    dynamic_risk_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    trade_optimization_report: dict[str, Any] | None = None,
    trade_planner_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_AUTONOMOUS_POLICY
    df = normalize_risk_positions(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No options positions available.",
            "positions": df,
        }

    state = evaluate_portfolio_management_state(
        positions=df,
        portfolio_risk_report=portfolio_risk_report,
        stress_report=stress_report,
        hedge_report=hedge_report,
        dynamic_risk_report=dynamic_risk_report,
        liquidity_report=liquidity_report,
        construction_report=construction_report,
        policy=policy,
    )

    recs = generate_autonomous_recommendations(state, policy=policy)
    queue = build_action_queue(
        recommendations=recs,
        trade_optimization_report=trade_optimization_report,
        trade_planner_report=trade_planner_report,
        policy=policy,
    )
    governance = evaluate_governance_status(queue, policy=policy)

    return {
        "available": True,
        "positions": df,
        "management_state": state,
        "recommendations": recs,
        "action_queue": queue,
        "governance": governance,
        "policy": policy,
    }


def summarize_autonomous_portfolio_manager(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Autonomous Portfolio Manager unavailable: {report.get('reason', 'unknown reason')}"

    state = report.get("management_state", {})
    governance = report.get("governance", {})
    queue = report.get("action_queue", {})

    return (
        f"Autonomous Portfolio Manager state is {state.get('manager_state')} "
        f"with pressure score {state.get('manager_pressure_score')}/100. "
        f"Governance status is {governance.get('governance_status')}. "
        f"{queue.get('action_count', 0)} actions are queued."
    )
