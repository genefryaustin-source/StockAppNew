"""
Sprint 8 Phase 5 — Institutional Portfolio Command Center.

Master institutional options portfolio command layer:
- Portfolio health scoring
- Risk state aggregation
- Lifecycle / roll / income / assignment queues
- Autonomous manager summary
- CIO-style action queue
- Institutional operating summary

This module does not place trades. It aggregates existing Sprint 5-8 engines.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


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


def _table(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def calculate_portfolio_health_score(
    risk_report: dict[str, Any] | None = None,
    stress_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    guardrails_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    lifecycle_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    autonomous_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 100.0
    drivers = []

    risk_score = _num(_safe_get(risk_report, ["risk_score", "risk_score"], 0))
    if risk_score > 70:
        score -= 18
        drivers.append("Portfolio risk score is elevated.")
    elif risk_score > 50:
        score -= 8
        drivers.append("Portfolio risk score is moderate.")

    stress_loss = 0.0
    worst = _safe_get(stress_report, ["scenarios", "worst_case"], {})
    if isinstance(worst, dict):
        stress_loss = abs(_num(worst.get("Total P&L % Notional"), 0))
    if stress_loss > 15:
        score -= 18
        drivers.append("Stress loss is high.")
    elif stress_loss > 8:
        score -= 8
        drivers.append("Stress loss is moderate.")

    greeks_score = _num(_safe_get(greeks_report, ["score", "greeks_risk_score"], 0))
    if greeks_score > 70:
        score -= 14
        drivers.append("Greeks exposure risk is elevated.")

    breaches = _num((guardrails_report or {}).get("breach_count", 0))
    if breaches > 0:
        score -= min(20, breaches * 8)
        drivers.append(f"{int(breaches)} guardrail breach(es) detected.")

    construction_score = _num(_safe_get(construction_report, ["score", "construction_score"], 75))
    if construction_score < 50:
        score -= 12
        drivers.append("Portfolio construction score is weak.")
    elif construction_score < 70:
        score -= 6
        drivers.append("Portfolio construction could be improved.")

    lifecycle_actions = _num(_safe_get(lifecycle_report, ["summary", "action_required_count"], 0))
    lifecycle_critical = _num(_safe_get(lifecycle_report, ["summary", "critical_count"], 0))
    if lifecycle_critical > 0:
        score -= min(15, lifecycle_critical * 8)
        drivers.append("Critical lifecycle actions exist.")
    elif lifecycle_actions > 0:
        score -= min(8, lifecycle_actions * 2)
        drivers.append("Position lifecycle actions are pending.")

    roll_candidates = _num(_safe_get(roll_report, ["summary", "roll_candidate_count"], 0))
    if roll_candidates > 0:
        score -= min(8, roll_candidates * 2)
        drivers.append("Roll candidates are pending.")

    assignment_alerts = _num(_safe_get(assignment_report, ["summary", "assignment_alert_count"], 0))
    critical_assignment = _num(_safe_get(assignment_report, ["summary", "critical_assignment_count"], 0))
    critical_expiration = _num(_safe_get(assignment_report, ["summary", "critical_expiration_count"], 0))
    if critical_assignment > 0 or critical_expiration > 0:
        score -= 18
        drivers.append("Critical assignment or expiration risk detected.")
    elif assignment_alerts > 0:
        score -= min(10, assignment_alerts * 2)
        drivers.append("Assignment or expiration alerts are active.")

    manager_pressure = _num(_safe_get(autonomous_report, ["management_state", "manager_pressure_score"], 0))
    if manager_pressure > 70:
        score -= 12
        drivers.append("Autonomous manager pressure is high.")
    elif manager_pressure > 45:
        score -= 6
        drivers.append("Autonomous manager pressure is moderate.")

    annual_yield = _num(_safe_get(income_report, ["summary", "annualized_yield"], 0))
    if annual_yield > 0:
        score += min(5, annual_yield / 10)

    score = round(max(0, min(100, score)), 2)

    if score >= 85:
        level = "EXCELLENT"
    elif score >= 70:
        level = "STRONG"
    elif score >= 55:
        level = "WATCH"
    elif score >= 40:
        level = "AT_RISK"
    else:
        level = "CRITICAL"

    return {
        "portfolio_health_score": score,
        "portfolio_health_level": level,
        "drivers": drivers or ["No major command-center risk drivers detected."],
    }


def build_master_action_queue(
    lifecycle_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    autonomous_report: dict[str, Any] | None = None,
    guardrails_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []

    breaches = (guardrails_report or {}).get("breaches", []) or []
    for breach in breaches:
        rows.append({
            "Source": "Guardrails",
            "Priority": "Critical",
            "Action": str(breach),
            "Category": "Risk",
            "Status": "Open",
        })

    lifecycle_queue = _table(_safe_get(lifecycle_report, ["action_queue", "action_queue"], pd.DataFrame()))
    if not lifecycle_queue.empty:
        for _, row in lifecycle_queue.head(25).iterrows():
            rows.append({
                "Source": "Lifecycle",
                "Priority": str(row.get("Urgency", "Medium")),
                "Action": str(row.get("Recommended Action", "Review")),
                "Category": "Position",
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Status": "Open",
            })

    roll_queue = _table((roll_report or {}).get("roll_queue"))
    if not roll_queue.empty:
        for _, row in roll_queue.head(25).iterrows():
            rows.append({
                "Source": "Rolling",
                "Priority": str(row.get("Roll Urgency", "Medium")),
                "Action": str(row.get("Roll Decision", "Evaluate Roll")),
                "Category": "Roll",
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Status": "Open",
            })

    assignment_queue = _table((assignment_report or {}).get("alert_queue"))
    if not assignment_queue.empty:
        for _, row in assignment_queue.head(25).iterrows():
            priority = row.get("Assignment Risk", row.get("Expiration Risk", "Medium"))
            rows.append({
                "Source": "Assignment",
                "Priority": str(priority),
                "Action": str(row.get("Recommended Action", "Review Assignment/Expiration")),
                "Category": "Assignment/Expiration",
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Status": "Open",
            })

    auto_queue = _table(_safe_get(autonomous_report, ["action_queue", "action_queue"], pd.DataFrame()))
    if not auto_queue.empty:
        for _, row in auto_queue.head(25).iterrows():
            rows.append({
                "Source": "Auto Manager",
                "Priority": str(row.get("Priority", "Normal")),
                "Action": str(row.get("Action", "")),
                "Category": str(row.get("Category", "Portfolio")),
                "Status": str(row.get("Status", "Open")),
            })

    queue = pd.DataFrame(rows)

    if not queue.empty:
        priority_order = {
            "Critical": 0, "CRITICAL": 0,
            "High": 1, "HIGH": 1,
            "Medium": 2, "MEDIUM": 2,
            "Normal": 3, "LOW": 4, "Low": 4,
        }
        queue["_sort"] = queue["Priority"].map(priority_order).fillna(9)
        queue = queue.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "action_queue": queue,
        "action_count": int(len(queue)),
        "critical_count": int((queue["Priority"].astype(str).str.upper() == "CRITICAL").sum()) if not queue.empty else 0,
        "high_count": int((queue["Priority"].astype(str).str.upper() == "HIGH").sum()) if not queue.empty else 0,
    }


def build_command_center_report(
    risk_report: dict[str, Any] | None = None,
    stress_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    guardrails_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    lifecycle_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    autonomous_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    health = calculate_portfolio_health_score(
        risk_report=risk_report,
        stress_report=stress_report,
        greeks_report=greeks_report,
        guardrails_report=guardrails_report,
        construction_report=construction_report,
        lifecycle_report=lifecycle_report,
        roll_report=roll_report,
        income_report=income_report,
        assignment_report=assignment_report,
        autonomous_report=autonomous_report,
    )

    queue = build_master_action_queue(
        lifecycle_report=lifecycle_report,
        roll_report=roll_report,
        assignment_report=assignment_report,
        autonomous_report=autonomous_report,
        guardrails_report=guardrails_report,
    )

    return {
        "available": True,
        "health": health,
        "action_queue": queue,
        "risk_report": risk_report,
        "stress_report": stress_report,
        "greeks_report": greeks_report,
        "guardrails_report": guardrails_report,
        "construction_report": construction_report,
        "lifecycle_report": lifecycle_report,
        "roll_report": roll_report,
        "income_report": income_report,
        "assignment_report": assignment_report,
        "autonomous_report": autonomous_report,
    }


def summarize_command_center(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Command Center unavailable: {report.get('reason', 'unknown reason')}"

    health = report.get("health", {})
    queue = report.get("action_queue", {})

    return (
        f"Portfolio Command Center health is {health.get('portfolio_health_level')} "
        f"({health.get('portfolio_health_score')}/100). "
        f"{queue.get('action_count', 0)} actions are queued, including "
        f"{queue.get('critical_count', 0)} critical and {queue.get('high_count', 0)} high-priority items."
    )
