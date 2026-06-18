
"""
Sprint 12 Phase 4 — Autonomous Income Management Engine
"""

from __future__ import annotations
from typing import Any
import pandas as pd


DEFAULT_INCOME_POLICY = {
    "target_monthly_income": 2500.0,
    "target_annual_yield": 12.0,
    "min_liquidity_score": 50.0,
    "max_assignment_risk": 40.0,
    "max_single_income_source_pct": 35.0,
}


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _df(v: Any) -> pd.DataFrame:
    if isinstance(v, pd.DataFrame):
        return v.copy()
    if isinstance(v, list):
        return pd.DataFrame(v)
    return pd.DataFrame()


def build_income_sources(
    covered_call_report=None,
    csp_report=None,
    wheel_report=None,
    income_report=None,
):
    rows = []

    cc = _df((covered_call_report or {}).get("candidates"))
    for _, r in cc.iterrows():
        rows.append({
            "Source": "Covered Calls",
            "Underlying": r.get("Underlying", ""),
            "Income": _num(r.get("premium", 0)),
            "Yield": _num(r.get("Estimated Annual Yield %", 0)),
            "Liquidity": _num(r.get("liquidity_score", 60)),
            "Assignment Risk": 25,
        })

    csp = _df((csp_report or {}).get("approved"))
    for _, r in csp.iterrows():
        rows.append({
            "Source": "Cash Secured Puts",
            "Underlying": r.get("underlying", ""),
            "Income": _num(r.get("mid", 0)),
            "Yield": _num(r.get("Annualized Yield %", 0)),
            "Liquidity": _num(r.get("liquidity_score", 60)),
            "Assignment Risk": _num(r.get("Assignment Probability %", 0)),
        })

    wheel = _df((wheel_report or {}).get("action_queue"))
    for _, r in wheel.iterrows():
        rows.append({
            "Source": "Wheel",
            "Underlying": r.get("underlying", ""),
            "Income": _num(r.get("Annualized Wheel Yield", 0)),
            "Yield": _num(r.get("Annualized Wheel Yield", 0)),
            "Liquidity": _num(r.get("liquidity_score", 60)),
            "Assignment Risk": 20,
        })

    return pd.DataFrame(rows)


def score_income_program(income_sources, policy=None):
    policy = policy or DEFAULT_INCOME_POLICY

    df = _df(income_sources)

    if df.empty:
        return {
            "available": False,
            "reason": "No income sources available."
        }

    total_income = float(df["Income"].sum())
    avg_yield = float(df["Yield"].mean())
    avg_liquidity = float(df["Liquidity"].mean())
    avg_assignment = float(df["Assignment Risk"].mean())

    score = 50

    if avg_yield >= policy["target_annual_yield"]:
        score += 20

    if avg_liquidity >= policy["min_liquidity_score"]:
        score += 15

    if avg_assignment <= policy["max_assignment_risk"]:
        score += 15

    score = max(0, min(100, round(score, 2)))

    if score >= 85:
        rating = "EXCELLENT"
    elif score >= 70:
        rating = "STRONG"
    elif score >= 55:
        rating = "WATCH"
    else:
        rating = "AT_RISK"

    return {
        "available": True,
        "score": score,
        "rating": rating,
        "monthly_income": round(total_income, 2),
        "annualized_income": round(total_income * 12, 2),
        "avg_yield": round(avg_yield, 2),
        "avg_liquidity": round(avg_liquidity, 2),
        "avg_assignment_risk": round(avg_assignment, 2),
    }


def build_income_action_queue(income_sources, policy=None):
    policy = policy or DEFAULT_INCOME_POLICY

    df = _df(income_sources)

    rows = []

    for _, r in df.iterrows():

        if r["Liquidity"] < policy["min_liquidity_score"]:
            rows.append({
                "Priority": "Medium",
                "Source": r["Source"],
                "Action": "Replace illiquid income source",
            })

        if r["Assignment Risk"] > policy["max_assignment_risk"]:
            rows.append({
                "Priority": "High",
                "Source": r["Source"],
                "Action": "Reduce assignment exposure",
            })

    return pd.DataFrame(rows)


def build_autonomous_income_management_report(
    covered_call_report=None,
    csp_report=None,
    wheel_report=None,
    income_report=None,
    policy=None,
):
    policy = policy or DEFAULT_INCOME_POLICY

    sources = build_income_sources(
        covered_call_report,
        csp_report,
        wheel_report,
        income_report,
    )

    score = score_income_program(sources, policy)

    queue = build_income_action_queue(sources, policy)

    return {
        "available": True,
        "sources": sources,
        "score": score,
        "queue": queue,
        "summary": {
            "income_score": score.get("score", 0),
            "income_rating": score.get("rating", "UNKNOWN"),
            "income_sources": len(sources),
            "action_count": len(queue),
        }
    }


def summarize_autonomous_income_management(report):
    if not report.get("available"):
        return report.get("reason", "Unavailable")

    s = report["summary"]

    return (
        f"Income score {s['income_score']}/100 "
        f"({s['income_rating']}). "
        f"{s['income_sources']} income sources. "
        f"{s['action_count']} actions queued."
    )
