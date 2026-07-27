"""
Sprint 7 Phase 3 — Institutional Trade Planner Engine.

Institutional trade planning layer:
- Converts optimized trade ideas into executable trade plans
- Produces trade checklist, timing plan, sizing plan, hedge/risk controls
- Scores readiness before execution
- Generates "approve / revise / reject" planning decisions
- Produces deterministic plan outputs for dashboards and future autonomous layers

Designed to sit after:
Strategy Factory -> Liquidity -> Position Sizing -> Capital Allocation -> Trade Optimization
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_PLANNER_POLICY = {
    "min_optimization_score": 65,
    "min_liquidity_score": 55,
    "max_greeks_risk_score": 70,
    "max_portfolio_risk_score": 70,
    "max_slippage_bps": 150,
    "max_spread_pct": 15,
    "require_defined_risk": True,
    "require_exit_plan": True,
    "require_hedge_review": True,
}


def _frame(data: Any) -> pd.DataFrame:
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame()


def _num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _value(row: pd.Series, key: str, default: Any = None) -> Any:
    try:
        value = row.get(key, default)
        return default if pd.isna(value) else value
    except Exception:
        return default


def classify_trade_plan_type(strategy: Any) -> str:
    s = str(strategy or "").lower()

    if any(x in s for x in ["condor", "credit", "covered", "cash secured", "income", "short premium"]):
        return "Income"
    if any(x in s for x in ["straddle", "strangle", "calendar", "diagonal", "volatility"]):
        return "Volatility"
    if any(x in s for x in ["hedge", "protective", "collar"]):
        return "Hedge"
    if any(x in s for x in ["call", "put", "debit", "spread"]):
        return "Directional"

    return "Opportunistic"


def normalize_trade_ideas(trades: Any) -> pd.DataFrame:
    df = _frame(trades)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "ticker": "",
        "underlying": "",
        "strategy": "",
        "strategy_bucket": "",
        "direction": "",
        "entry_price": 0,
        "target_price": 0,
        "stop_price": 0,
        "max_loss": 0,
        "max_profit": 0,
        "capital_required": 0,
        "allocated_capital": 0,
        "recommended_contracts": 0,
        "optimization_score": 0,
        "recommended_action": "",
        "liquidity_score": 50,
        "execution_score": 70,
        "greeks_risk_score": 50,
        "portfolio_risk_score": 50,
        "spread_pct": 0,
        "slippage_bps": 0,
        "probability_of_profit": 0,
        "risk_reward": 0,
        "conviction": 50,
        "dte": 0,
        "expiry": "",
        "notes": "",
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    numeric_cols = [
        "entry_price",
        "target_price",
        "stop_price",
        "max_loss",
        "max_profit",
        "capital_required",
        "allocated_capital",
        "recommended_contracts",
        "optimization_score",
        "liquidity_score",
        "execution_score",
        "greeks_risk_score",
        "portfolio_risk_score",
        "spread_pct",
        "slippage_bps",
        "probability_of_profit",
        "risk_reward",
        "conviction",
        "dte",
    ]

    for col in numeric_cols:
        df[col] = _num(df[col])

    df["ticker"] = (
        df["ticker"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["underlying"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.upper()
    )

    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified").astype(str)

    df["strategy_bucket"] = (
        df["strategy_bucket"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["strategy"].apply(classify_trade_plan_type))
        .fillna("Opportunistic")
        .astype(str)
    )

    return df


def build_trade_checklist(row: pd.Series, policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    policy = policy or DEFAULT_PLANNER_POLICY

    spread_pct = float(_value(row, "spread_pct", 0) or 0)
    spread_percent = spread_pct * 100 if 0 < spread_pct <= 1 else spread_pct

    checks = [
        {
            "Check": "Optimization score",
            "Status": "PASS" if float(_value(row, "optimization_score", 0)) >= policy["min_optimization_score"] else "FAIL",
            "Detail": f"Score {_value(row, 'optimization_score', 0)} vs minimum {policy['min_optimization_score']}.",
        },
        {
            "Check": "Liquidity",
            "Status": "PASS" if float(_value(row, "liquidity_score", 0)) >= policy["min_liquidity_score"] else "FAIL",
            "Detail": f"Liquidity {_value(row, 'liquidity_score', 0)} vs minimum {policy['min_liquidity_score']}.",
        },
        {
            "Check": "Greeks risk",
            "Status": "PASS" if float(_value(row, "greeks_risk_score", 0)) <= policy["max_greeks_risk_score"] else "REVIEW",
            "Detail": f"Greeks risk {_value(row, 'greeks_risk_score', 0)} vs max {policy['max_greeks_risk_score']}.",
        },
        {
            "Check": "Portfolio risk",
            "Status": "PASS" if float(_value(row, "portfolio_risk_score", 0)) <= policy["max_portfolio_risk_score"] else "REVIEW",
            "Detail": f"Portfolio risk {_value(row, 'portfolio_risk_score', 0)} vs max {policy['max_portfolio_risk_score']}.",
        },
        {
            "Check": "Slippage",
            "Status": "PASS" if float(_value(row, "slippage_bps", 0)) <= policy["max_slippage_bps"] else "REVIEW",
            "Detail": f"Slippage {_value(row, 'slippage_bps', 0)} bps vs max {policy['max_slippage_bps']} bps.",
        },
        {
            "Check": "Bid/ask spread",
            "Status": "PASS" if spread_percent <= policy["max_spread_pct"] else "REVIEW",
            "Detail": f"Spread {spread_percent:.2f}% vs max {policy['max_spread_pct']}%.",
        },
        {
            "Check": "Exit plan",
            "Status": "PASS" if float(_value(row, "target_price", 0)) > 0 or float(_value(row, "stop_price", 0)) > 0 else "REVIEW",
            "Detail": "Target/stop present." if float(_value(row, "target_price", 0)) > 0 or float(_value(row, "stop_price", 0)) > 0 else "Target/stop missing.",
        },
    ]

    return checks


def calculate_plan_readiness(checklist: list[dict[str, Any]]) -> dict[str, Any]:
    if not checklist:
        return {
            "readiness_score": 0,
            "readiness_level": "UNREADY",
            "decision": "REJECT",
        }

    pass_count = sum(1 for c in checklist if c.get("Status") == "PASS")
    review_count = sum(1 for c in checklist if c.get("Status") == "REVIEW")
    fail_count = sum(1 for c in checklist if c.get("Status") == "FAIL")

    score = pass_count / max(1, len(checklist)) * 100
    score -= review_count * 5
    score -= fail_count * 20
    score = round(max(0, min(100, score)), 2)

    if fail_count > 0:
        decision = "REVISE"
    elif score >= 85:
        decision = "APPROVE"
    elif score >= 65:
        decision = "APPROVE_WITH_REVIEW"
    elif score >= 45:
        decision = "REVISE"
    else:
        decision = "REJECT"

    if score >= 85:
        level = "READY"
    elif score >= 65:
        level = "REVIEW_READY"
    elif score >= 45:
        level = "NEEDS_WORK"
    else:
        level = "UNREADY"

    return {
        "readiness_score": score,
        "readiness_level": level,
        "decision": decision,
        "pass_count": pass_count,
        "review_count": review_count,
        "fail_count": fail_count,
    }


def build_entry_plan(row: pd.Series) -> dict[str, Any]:
    liquidity = float(_value(row, "liquidity_score", 50) or 50)
    spread_pct = float(_value(row, "spread_pct", 0) or 0)
    spread_percent = spread_pct * 100 if 0 < spread_pct <= 1 else spread_pct
    contracts = int(float(_value(row, "recommended_contracts", 0) or 0))

    if liquidity >= 80 and spread_percent <= 5:
        order_type = "Limit near midpoint"
        execution_style = "Single clip acceptable"
    elif liquidity >= 60 and spread_percent <= 12:
        order_type = "Limit order with price improvement"
        execution_style = "Work order patiently"
    else:
        order_type = "Small limit clips only"
        execution_style = "Split into small clips or avoid"

    return {
        "Order Type": order_type,
        "Execution Style": execution_style,
        "Recommended Contracts": contracts,
        "Entry Price": round(float(_value(row, "entry_price", 0) or 0), 4),
        "Timing": "Avoid first/last 10 minutes unless urgent.",
        "Routing": "Do not use market orders for options.",
    }


def build_exit_plan(row: pd.Series) -> dict[str, Any]:
    entry = float(_value(row, "entry_price", 0) or 0)
    target = float(_value(row, "target_price", 0) or 0)
    stop = float(_value(row, "stop_price", 0) or 0)
    max_loss = float(_value(row, "max_loss", 0) or 0)
    max_profit = float(_value(row, "max_profit", 0) or 0)

    if target <= 0 and entry > 0 and max_profit > 0:
        target = entry + max_profit * 0.50

    if stop <= 0 and entry > 0 and max_loss > 0:
        stop = max(0, entry - max_loss * 0.50)

    return {
        "Profit Target": round(target, 4),
        "Stop / Risk Exit": round(stop, 4),
        "Time Stop": "Exit or review at 50% of original DTE.",
        "Volatility Exit": "Exit/reprice if IV regime changes materially.",
        "Risk Exit": "Exit if portfolio risk state moves to RISK_OFF.",
    }


def build_risk_controls(row: pd.Series) -> dict[str, Any]:
    bucket = str(_value(row, "strategy_bucket", "Opportunistic"))
    greeks_risk = float(_value(row, "greeks_risk_score", 50) or 50)
    portfolio_risk = float(_value(row, "portfolio_risk_score", 50) or 50)

    controls = []

    if greeks_risk >= 70:
        controls.append("Require Greeks review before entry.")
    if portfolio_risk >= 70:
        controls.append("Require portfolio risk approval before entry.")
    if bucket == "Volatility":
        controls.append("Monitor IV crush / expansion sensitivity.")
    if bucket == "Income":
        controls.append("Monitor short gamma and assignment risk.")
    if bucket == "Directional":
        controls.append("Confirm directional thesis and stop level.")
    if bucket == "Hedge":
        controls.append("Confirm hedge objective and offset target exposure.")

    if not controls:
        controls.append("Standard risk controls apply.")

    return {
        "Strategy Bucket": bucket,
        "Controls": controls,
        "Review Cadence": "Daily while open; intraday if risk state changes.",
    }


def build_single_trade_plan(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_PLANNER_POLICY
    checklist = build_trade_checklist(row, policy)
    readiness = calculate_plan_readiness(checklist)

    return {
        "Ticker": _value(row, "ticker", ""),
        "Strategy": _value(row, "strategy", "Unclassified"),
        "Strategy Bucket": _value(row, "strategy_bucket", "Opportunistic"),
        "Direction": _value(row, "direction", ""),
        "Planner Decision": readiness.get("decision"),
        "Readiness Score": readiness.get("readiness_score"),
        "Readiness Level": readiness.get("readiness_level"),
        "Optimization Score": round(float(_value(row, "optimization_score", 0) or 0), 2),
        "Conviction": round(float(_value(row, "conviction", 0) or 0), 2),
        "Liquidity Score": round(float(_value(row, "liquidity_score", 0) or 0), 2),
        "Recommended Contracts": int(float(_value(row, "recommended_contracts", 0) or 0)),
        "Capital Required": round(float(_value(row, "capital_required", 0) or 0), 2),
        "Allocated Capital": round(float(_value(row, "allocated_capital", 0) or 0), 2),
        "Entry Plan": build_entry_plan(row),
        "Exit Plan": build_exit_plan(row),
        "Risk Controls": build_risk_controls(row),
        "Checklist": pd.DataFrame(checklist),
    }


def build_institutional_trade_plan(
    trade_candidates: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_PLANNER_POLICY
    df = normalize_trade_ideas(trade_candidates)

    if df.empty:
        return {
            "available": False,
            "reason": "No trade candidates available.",
            "plans": pd.DataFrame(),
        }

    plans = [build_single_trade_plan(row, policy) for _, row in df.iterrows()]

    summary_rows = []
    checklist_rows = []
    for idx, plan in enumerate(plans):
        summary_rows.append({
            "Plan ID": idx + 1,
            "Ticker": plan["Ticker"],
            "Strategy": plan["Strategy"],
            "Bucket": plan["Strategy Bucket"],
            "Decision": plan["Planner Decision"],
            "Readiness Score": plan["Readiness Score"],
            "Readiness Level": plan["Readiness Level"],
            "Optimization Score": plan["Optimization Score"],
            "Liquidity Score": plan["Liquidity Score"],
            "Contracts": plan["Recommended Contracts"],
            "Capital Required": plan["Capital Required"],
            "Allocated Capital": plan["Allocated Capital"],
        })

        checklist = plan.get("Checklist")
        if isinstance(checklist, pd.DataFrame):
            temp = checklist.copy()
            temp.insert(0, "Plan ID", idx + 1)
            temp.insert(1, "Ticker", plan["Ticker"])
            temp.insert(2, "Strategy", plan["Strategy"])
            checklist_rows.append(temp)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["Readiness Score", "Optimization Score"],
        ascending=False,
    ).reset_index(drop=True)

    checklist_table = pd.concat(checklist_rows, ignore_index=True) if checklist_rows else pd.DataFrame()

    approved_count = int(summary["Decision"].isin(["APPROVE", "APPROVE_WITH_REVIEW"]).sum())
    revise_count = int((summary["Decision"] == "REVISE").sum())
    reject_count = int((summary["Decision"] == "REJECT").sum())

    avg_readiness = round(float(summary["Readiness Score"].mean()), 2) if not summary.empty else 0

    return {
        "available": True,
        "plans": plans,
        "plan_summary": summary,
        "checklist": checklist_table,
        "summary": {
            "plan_count": int(len(summary)),
            "approved_count": approved_count,
            "revise_count": revise_count,
            "reject_count": reject_count,
            "avg_readiness_score": avg_readiness,
            "top_plan": summary.head(1).to_dict("records")[0] if not summary.empty else {},
        },
    }


def summarize_institutional_trade_plan(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Trade planning unavailable: {report.get('reason', 'unknown reason')}"

    summary = report.get("summary", {})
    top = summary.get("top_plan", {})

    return (
        f"Trade Planner reviewed {summary.get('plan_count')} candidate plans. "
        f"{summary.get('approved_count')} are approved/review-ready, "
        f"{summary.get('revise_count')} need revision, and "
        f"{summary.get('reject_count')} are rejected. "
        f"Top plan: {top.get('Ticker', '—')} {top.get('Strategy', '—')} "
        f"with readiness {top.get('Readiness Score', 0)}/100."
    )
