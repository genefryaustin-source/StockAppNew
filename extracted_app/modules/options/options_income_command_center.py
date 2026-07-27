"""
Sprint 9 Phase 5 — Institutional Income Command Center.

Master income operations layer:
- Aggregates Income Intelligence
- Wheel Strategy Command Center
- Covered Call Factory
- Cash Secured Put Factory
- Rolling Intelligence
- Assignment / Expiration Intelligence
- Produces income health score, income action queue, yield dashboard, and operating summary

This module does not place trades. It creates deterministic income-management guidance.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_INCOME_COMMAND_POLICY = {
    "target_annualized_yield": 10.0,
    "min_income_health_score": 75,
    "max_assignment_alerts": 0,
    "max_roll_queue": 10,
    "max_income_queue": 20,
    "min_cash_deployment_pct": 40.0,
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


def calculate_income_health_score(
    income_report: dict[str, Any] | None = None,
    wheel_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    csp_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_INCOME_COMMAND_POLICY

    score = 100.0
    drivers = []

    annual_yield = _num(_safe_get(income_report, ["summary", "annualized_yield"], 0))
    if annual_yield < policy["target_annualized_yield"]:
        score -= min(25, (policy["target_annualized_yield"] - annual_yield) * 2)
        drivers.append("Income yield is below target.")
    else:
        score += min(5, (annual_yield - policy["target_annualized_yield"]) * 0.5)

    wheel_actions = _num(_safe_get(wheel_report, ["summary", "wheel_action_count"], 0))
    if wheel_actions > 0:
        score -= min(12, wheel_actions * 2)
        drivers.append("Wheel action queue is active.")

    covered_candidates = _num((covered_call_report or {}).get("candidate_count", 0))
    if covered_candidates <= 0:
        score -= 8
        drivers.append("No covered call candidates available.")

    csp_approved = _num(_safe_get(csp_report, ["summary", "approved_count"], 0))
    if csp_approved <= 0:
        score -= 8
        drivers.append("No approved cash-secured put candidates available.")

    roll_candidates = _num(_safe_get(roll_report, ["summary", "roll_candidate_count"], 0))
    if roll_candidates > policy["max_roll_queue"]:
        score -= 12
        drivers.append("Roll queue exceeds income operations threshold.")
    elif roll_candidates > 0:
        score -= 5
        drivers.append("Roll queue requires review.")

    assignment_alerts = _num(_safe_get(assignment_report, ["summary", "assignment_alert_count"], 0))
    critical_assignment = _num(_safe_get(assignment_report, ["summary", "critical_assignment_count"], 0))
    critical_expiration = _num(_safe_get(assignment_report, ["summary", "critical_expiration_count"], 0))

    if critical_assignment > 0 or critical_expiration > 0:
        score -= 25
        drivers.append("Critical assignment or expiration risk threatens income operations.")
    elif assignment_alerts > policy["max_assignment_alerts"]:
        score -= min(15, assignment_alerts * 3)
        drivers.append("Assignment / expiration alerts are active.")

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
        "income_health_score": score,
        "income_health_level": level,
        "annualized_yield": annual_yield,
        "drivers": drivers or ["Income operations are within policy."],
    }


def build_income_action_queue(
    wheel_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    csp_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []

    wheel_q = _df((wheel_report or {}).get("action_queue"))
    if not wheel_q.empty:
        for _, row in wheel_q.head(25).iterrows():
            rows.append({
                "Source": "Wheel",
                "Priority": "High" if "Prepare" in str(row.get("Recommended Wheel Action", "")) else "Medium",
                "Action": row.get("Recommended Wheel Action", "Review Wheel"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Category": row.get("Wheel Stage", "Wheel"),
            })

    covered = _df((covered_call_report or {}).get("candidates"))
    if not covered.empty:
        for _, row in covered.head(25).iterrows():
            rows.append({
                "Source": "Covered Call Factory",
                "Priority": "Normal",
                "Action": row.get("Action", "Sell Covered Call"),
                "Ticker": row.get("Underlying", row.get("underlying", "")),
                "Symbol": "",
                "Category": "Covered Call",
            })

    csp = _df((csp_report or {}).get("approved"))
    if not csp.empty:
        for _, row in csp.head(25).iterrows():
            rows.append({
                "Source": "Cash Secured Put Factory",
                "Priority": "High" if _num(row.get("Opportunity Score"), 0) >= 80 else "Normal",
                "Action": row.get("Recommendation", "Sell Put"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Category": "Cash Secured Put",
            })

    roll_q = _df((roll_report or {}).get("roll_queue"))
    if not roll_q.empty:
        for _, row in roll_q.head(25).iterrows():
            rows.append({
                "Source": "Rolling",
                "Priority": row.get("Roll Urgency", "Medium"),
                "Action": row.get("Roll Decision", "Evaluate Roll"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Category": "Roll",
            })

    assignment_q = _df((assignment_report or {}).get("alert_queue"))
    if not assignment_q.empty:
        for _, row in assignment_q.head(25).iterrows():
            priority = row.get("Assignment Risk", row.get("Expiration Risk", "Medium"))
            rows.append({
                "Source": "Assignment",
                "Priority": priority,
                "Action": row.get("Recommended Action", "Review Assignment"),
                "Ticker": row.get("underlying", ""),
                "Symbol": row.get("option_symbol", ""),
                "Category": "Assignment / Expiration",
            })

    queue = pd.DataFrame(rows)

    if not queue.empty:
        priority_order = {
            "Critical": 0, "CRITICAL": 0,
            "High": 1, "HIGH": 1,
            "Medium": 2, "MEDIUM": 2,
            "Normal": 3,
            "Low": 4, "LOW": 4,
        }
        queue["_sort"] = queue["Priority"].map(priority_order).fillna(9)
        queue = queue.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "income_action_queue": queue,
        "action_count": int(len(queue)),
        "critical_count": int((queue["Priority"].astype(str).str.upper() == "CRITICAL").sum()) if not queue.empty else 0,
        "high_count": int((queue["Priority"].astype(str).str.upper() == "HIGH").sum()) if not queue.empty else 0,
    }


def build_income_source_summary(
    income_report: dict[str, Any] | None = None,
    wheel_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    csp_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [
        {
            "Source": "Income Intelligence",
            "Metric": "Annualized Yield",
            "Value": _safe_get(income_report, ["summary", "annualized_yield"], 0),
        },
        {
            "Source": "Wheel",
            "Metric": "Avg Wheel Yield",
            "Value": _safe_get(wheel_report, ["summary", "avg_annualized_yield"], 0),
        },
        {
            "Source": "Covered Calls",
            "Metric": "Candidate Count",
            "Value": (covered_call_report or {}).get("candidate_count", 0),
        },
        {
            "Source": "Cash Secured Puts",
            "Metric": "Approved Count",
            "Value": _safe_get(csp_report, ["summary", "approved_count"], 0),
        },
        {
            "Source": "Cash Secured Puts",
            "Metric": "Avg CSP Yield",
            "Value": _safe_get(csp_report, ["summary", "avg_annualized_yield"], 0),
        },
    ]

    return {
        "available": True,
        "income_sources": pd.DataFrame(rows),
    }


def build_institutional_income_command_report(
    income_report: dict[str, Any] | None = None,
    wheel_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    csp_report: dict[str, Any] | None = None,
    roll_report: dict[str, Any] | None = None,
    assignment_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_INCOME_COMMAND_POLICY

    health = calculate_income_health_score(
        income_report=income_report,
        wheel_report=wheel_report,
        covered_call_report=covered_call_report,
        csp_report=csp_report,
        roll_report=roll_report,
        assignment_report=assignment_report,
        policy=policy,
    )

    queue = build_income_action_queue(
        wheel_report=wheel_report,
        covered_call_report=covered_call_report,
        csp_report=csp_report,
        roll_report=roll_report,
        assignment_report=assignment_report,
    )

    sources = build_income_source_summary(
        income_report=income_report,
        wheel_report=wheel_report,
        covered_call_report=covered_call_report,
        csp_report=csp_report,
    )

    return {
        "available": True,
        "health": health,
        "queue": queue,
        "sources": sources,
        "income_report": income_report,
        "wheel_report": wheel_report,
        "covered_call_report": covered_call_report,
        "csp_report": csp_report,
        "roll_report": roll_report,
        "assignment_report": assignment_report,
        "policy": policy,
    }


def summarize_income_command(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Income Command Center unavailable: {report.get('reason', 'unknown reason')}"

    health = report.get("health", {})
    queue = report.get("queue", {})

    return (
        f"Income Command Center health is {health.get('income_health_level')} "
        f"({health.get('income_health_score')}/100). "
        f"Annualized yield is {health.get('annualized_yield')}%. "
        f"{queue.get('action_count', 0)} income actions are queued, including "
        f"{queue.get('critical_count', 0)} critical and {queue.get('high_count', 0)} high-priority items."
    )
