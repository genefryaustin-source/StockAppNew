"""
Sprint 9 Phase 1 — Institutional Portfolio Operations Engine.

Portfolio operations layer for the institutional options OS:
- Daily operating state
- Operational workload / action queue
- Ops health scoring
- SLA-style urgency buckets
- Queue aggregation across Command Center, Lifecycle, Rolling, Assignment, Income, Autonomous Manager
- Operating playbook generation

This module does not place trades. It produces deterministic operating guidance.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_OPERATIONS_POLICY = {
    "max_open_actions": 25,
    "max_critical_actions": 0,
    "max_high_actions": 5,
    "target_health_score": 80,
    "assignment_alert_limit": 0,
    "roll_candidate_limit": 10,
    "lifecycle_action_limit": 10,
    "income_review_days": 7,
}


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


def _df(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def classify_operating_state(
    command_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_OPERATIONS_POLICY
    command_report = command_report or {}

    health_score = _num(_safe_get(command_report, ["health", "portfolio_health_score"], 0))
    health_level = _safe_get(command_report, ["health", "portfolio_health_level"], "UNKNOWN")

    action_count = _num(_safe_get(command_report, ["action_queue", "action_count"], 0))
    critical_count = _num(_safe_get(command_report, ["action_queue", "critical_count"], 0))
    high_count = _num(_safe_get(command_report, ["action_queue", "high_count"], 0))

    pressure = 0.0
    drivers = []

    if health_score < policy["target_health_score"]:
        pressure += min(35, (policy["target_health_score"] - health_score) * 0.8)
        drivers.append("Portfolio health below operating target.")

    if action_count > policy["max_open_actions"]:
        pressure += 20
        drivers.append("Open action queue exceeds operating capacity.")

    if critical_count > policy["max_critical_actions"]:
        pressure += 30
        drivers.append("Critical action queue is not clear.")

    if high_count > policy["max_high_actions"]:
        pressure += 15
        drivers.append("High-priority action queue is elevated.")

    pressure = round(max(0, min(100, pressure)), 2)

    if pressure >= 80 or critical_count > 0:
        state = "INCIDENT_RESPONSE"
    elif pressure >= 55:
        state = "RISK_REDUCTION"
    elif pressure >= 30:
        state = "ACTIVE_MANAGEMENT"
    else:
        state = "NORMAL_OPERATIONS"

    return {
        "available": True,
        "operating_state": state,
        "operations_pressure_score": pressure,
        "portfolio_health_score": health_score,
        "portfolio_health_level": health_level,
        "open_action_count": int(action_count),
        "critical_action_count": int(critical_count),
        "high_action_count": int(high_count),
        "drivers": drivers or ["Operating state is within normal limits."],
    }


def build_operations_workload(
    command_report: dict[str, Any] | None = None,
    lifecycle_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    autonomous_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []

    master = _df(_safe_get(command_report, ["action_queue", "action_queue"], pd.DataFrame()))
    if not master.empty:
        for _, row in master.iterrows():
            rows.append({
                "Source": row.get("Source", "Command Center"),
                "Priority": row.get("Priority", "Normal"),
                "Category": row.get("Category", "Portfolio"),
                "Action": row.get("Action", ""),
                "Ticker": row.get("Ticker", ""),
                "Symbol": row.get("Symbol", ""),
                "Status": row.get("Status", "Open"),
            })

    lifecycle_q = _df(_safe_get(lifecycle_report, ["action_queue", "action_queue"], pd.DataFrame()))
    if not lifecycle_q.empty:
        for _, row in lifecycle_q.iterrows():
            rows.append({
                "Source": "Lifecycle",
                "Priority": row.get("Urgency", "Medium"),
                "Category": "Lifecycle",
                "Action": row.get("Recommended Action", "Review"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Status": "Open",
            })

    roll_q = _df((roll_report or {}).get("roll_queue"))
    if not roll_q.empty:
        for _, row in roll_q.iterrows():
            rows.append({
                "Source": "Rolling",
                "Priority": row.get("Roll Urgency", "Medium"),
                "Category": "Roll",
                "Action": row.get("Roll Decision", "Evaluate Roll"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Status": "Open",
            })

    assignment_q = _df((assignment_report or {}).get("alert_queue"))
    if not assignment_q.empty:
        for _, row in assignment_q.iterrows():
            rows.append({
                "Source": "Assignment",
                "Priority": row.get("Assignment Risk", row.get("Expiration Risk", "Medium")),
                "Category": "Assignment / Expiration",
                "Action": row.get("Recommended Action", "Review"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Status": "Open",
            })

    auto_q = _df(_safe_get(autonomous_report, ["action_queue", "action_queue"], pd.DataFrame()))
    if not auto_q.empty:
        for _, row in auto_q.iterrows():
            rows.append({
                "Source": "Autonomous Manager",
                "Priority": row.get("Priority", "Normal"),
                "Category": row.get("Category", "Portfolio"),
                "Action": row.get("Action", ""),
                "Ticker": "",
                "Symbol": "",
                "Status": row.get("Status", "Open"),
            })

    workload = pd.DataFrame(rows)

    if not workload.empty:
        workload = workload.drop_duplicates(
            subset=["Source", "Category", "Action", "Ticker", "Symbol"],
            keep="first",
        ).reset_index(drop=True)

        priority_order = {
            "Critical": 0, "CRITICAL": 0,
            "High": 1, "HIGH": 1,
            "Medium": 2, "MEDIUM": 2,
            "Normal": 3,
            "Low": 4, "LOW": 4,
        }
        workload["_sort"] = workload["Priority"].map(priority_order).fillna(9)
        workload = workload.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    by_source = (
        workload.groupby("Source", as_index=False)
        .agg(Actions=("Source", "size"))
        .sort_values("Actions", ascending=False)
        .reset_index(drop=True)
        if not workload.empty else pd.DataFrame(columns=["Source", "Actions"])
    )

    by_priority = (
        workload.groupby("Priority", as_index=False)
        .agg(Actions=("Priority", "size"))
        .sort_values("Actions", ascending=False)
        .reset_index(drop=True)
        if not workload.empty else pd.DataFrame(columns=["Priority", "Actions"])
    )

    return {
        "available": True,
        "workload": workload,
        "by_source": by_source,
        "by_priority": by_priority,
        "workload_count": int(len(workload)),
    }


def generate_operations_playbook(operating_state: dict[str, Any]) -> dict[str, Any]:
    state = operating_state.get("operating_state", "NORMAL_OPERATIONS")

    if state == "INCIDENT_RESPONSE":
        rows = [
            {"Step": 1, "Action": "Freeze new risk additions", "Owner": "Portfolio Manager", "Priority": "Critical"},
            {"Step": 2, "Action": "Resolve critical assignment / guardrail items", "Owner": "Risk Manager", "Priority": "Critical"},
            {"Step": 3, "Action": "Trim or hedge largest risk contributors", "Owner": "Trader", "Priority": "High"},
            {"Step": 4, "Action": "Re-run command center after actions", "Owner": "Operations", "Priority": "High"},
        ]
    elif state == "RISK_REDUCTION":
        rows = [
            {"Step": 1, "Action": "Prioritize high-risk lifecycle and roll items", "Owner": "Trader", "Priority": "High"},
            {"Step": 2, "Action": "Review hedge and dynamic-risk recommendations", "Owner": "Risk Manager", "Priority": "High"},
            {"Step": 3, "Action": "Avoid low-liquidity new trades", "Owner": "Execution", "Priority": "Medium"},
        ]
    elif state == "ACTIVE_MANAGEMENT":
        rows = [
            {"Step": 1, "Action": "Work lifecycle and roll queue", "Owner": "Trader", "Priority": "Medium"},
            {"Step": 2, "Action": "Review income and assignment alerts", "Owner": "Operations", "Priority": "Medium"},
            {"Step": 3, "Action": "Approve only optimized trade plans", "Owner": "Portfolio Manager", "Priority": "Normal"},
        ]
    else:
        rows = [
            {"Step": 1, "Action": "Monitor command center", "Owner": "Operations", "Priority": "Normal"},
            {"Step": 2, "Action": "Review income generation opportunities", "Owner": "Portfolio Manager", "Priority": "Normal"},
            {"Step": 3, "Action": "Maintain portfolio construction targets", "Owner": "Risk Manager", "Priority": "Normal"},
        ]

    return {
        "available": True,
        "playbook": pd.DataFrame(rows),
    }


def build_institutional_operations_report(
    command_report: dict[str, Any] | None = None,
    lifecycle_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    autonomous_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_OPERATIONS_POLICY

    operating_state = classify_operating_state(command_report, policy=policy)
    workload = build_operations_workload(
        command_report=command_report,
        lifecycle_report=lifecycle_report,
        roll_report=roll_report,
        assignment_report=assignment_report,
        income_report=income_report,
        autonomous_report=autonomous_report,
    )
    playbook = generate_operations_playbook(operating_state)

    return {
        "available": True,
        "operating_state": operating_state,
        "workload": workload,
        "playbook": playbook,
        "policy": policy,
    }


def summarize_institutional_operations(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Institutional Operations unavailable: {report.get('reason', 'unknown reason')}"

    state = report.get("operating_state", {})
    workload = report.get("workload", {})

    return (
        f"Institutional operations state is {state.get('operating_state')} "
        f"with pressure score {state.get('operations_pressure_score')}/100. "
        f"{workload.get('workload_count', 0)} operational items are open."
    )
