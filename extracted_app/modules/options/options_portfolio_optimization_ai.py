"""
Sprint 12 Phase 1 — Portfolio Optimization AI Engine.

Autonomous Institutional Options CIO layer:
- Portfolio objective scoring
- Risk-adjusted optimization recommendations
- Position sizing / capital allocation overlay
- Income / volatility / market-maker signal integration
- Constraint-aware optimization queue
- CIO-style portfolio optimization playbook

This module does not place trades. It produces deterministic optimization guidance.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY = {
    "target_health_score": 80,
    "max_single_position_pct": 15.0,
    "max_symbol_exposure_pct": 25.0,
    "target_cash_pct": 10.0,
    "max_short_gamma_score": 70.0,
    "min_liquidity_score": 50.0,
    "income_priority_weight": 0.20,
    "risk_priority_weight": 0.35,
    "liquidity_priority_weight": 0.20,
    "construction_priority_weight": 0.25,
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_get(d: Any, path: list[str], default: Any = None) -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def _df(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def normalize_optimization_positions(positions: Any) -> pd.DataFrame:
    df = _df(positions)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "symbol": "",
        "option_symbol": "",
        "strategy": "",
        "type": "",
        "option_type": "",
        "qty": 0,
        "strike": 0,
        "expiry": "",
        "dte": 0,
        "market_value": 0,
        "notional": 0,
        "unrealized_pnl": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "iv": 0,
        "liquidity_score": 50,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "qty", "strike", "dte", "market_value", "notional", "unrealized_pnl",
        "delta", "gamma", "theta", "vega", "iv", "liquidity_score",
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

    df["position_value"] = df["market_value"].abs().where(df["market_value"].abs() > 0, df["notional"].abs())

    return df


def calculate_portfolio_objective_score(
    risk_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY

    risk_score = _num(_safe_get(risk_report, ["risk_score", "risk_score"], risk_report.get("risk_score", 50) if isinstance(risk_report, dict) else 50), 50)
    construction_score = _num(_safe_get(construction_report, ["score", "construction_score"], construction_report.get("construction_score", 70) if isinstance(construction_report, dict) else 70), 70)
    income_yield = _num(_safe_get(income_report, ["summary", "annualized_yield"], 0), 0)
    liquidity_score = _num(_safe_get(liquidity_report, ["summary", "avg_liquidity_score"], 60), 60)
    mm_score = _num(_safe_get(market_maker_report, ["score", "score"], 40), 40)
    vol_score = _num(_safe_get(volatility_report, ["score", "score"], 40), 40)

    risk_component = max(0, 100 - risk_score)
    construction_component = construction_score
    income_component = min(100, income_yield * 5)
    liquidity_component = liquidity_score
    market_condition_penalty = max(0, (mm_score + vol_score) / 2 - 60)

    objective = (
        risk_component * policy["risk_priority_weight"]
        + construction_component * policy["construction_priority_weight"]
        + income_component * policy["income_priority_weight"]
        + liquidity_component * policy["liquidity_priority_weight"]
        - market_condition_penalty * 0.25
    )

    objective = round(max(0, min(100, objective)), 2)

    if objective >= 85:
        rating = "EXCELLENT"
    elif objective >= 70:
        rating = "STRONG"
    elif objective >= 55:
        rating = "WATCH"
    elif objective >= 40:
        rating = "AT_RISK"
    else:
        rating = "CRITICAL"

    drivers = []
    if risk_score > 70:
        drivers.append("Risk score is elevated.")
    if construction_score < 70:
        drivers.append("Construction score is below target.")
    if income_yield < 5:
        drivers.append("Income yield contribution is low.")
    if liquidity_score < policy["min_liquidity_score"]:
        drivers.append("Liquidity score is below minimum.")
    if market_condition_penalty > 0:
        drivers.append("Market-maker / volatility conditions require caution.")

    return {
        "objective_score": objective,
        "objective_rating": rating,
        "risk_component": round(risk_component, 2),
        "construction_component": round(construction_component, 2),
        "income_component": round(income_component, 2),
        "liquidity_component": round(liquidity_component, 2),
        "market_condition_penalty": round(market_condition_penalty, 2),
        "drivers": drivers or ["Portfolio objective is within optimization policy."],
    }


def identify_position_optimization_actions(
    positions: Any,
    risk_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY
    df = normalize_optimization_positions(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No positions available.",
            "action_queue": pd.DataFrame(),
        }

    total_value = float(df["position_value"].sum()) or 1.0
    df["portfolio_pct"] = df["position_value"] / total_value * 100

    rows = []

    for _, row in df.iterrows():
        symbol = row.get("underlying", "")
        position_pct = _num(row.get("portfolio_pct"), 0)
        gamma = abs(_num(row.get("gamma"), 0))
        dte = _num(row.get("dte"), 0)
        liquidity = _num(row.get("liquidity_score"), 50)
        pnl = _num(row.get("unrealized_pnl"), 0)
        theta = _num(row.get("theta"), 0)

        score = 50.0
        actions = []
        priority = "Normal"

        if position_pct > policy["max_single_position_pct"]:
            score -= 20
            actions.append("Trim position size")
            priority = "High"

        if liquidity < policy["min_liquidity_score"]:
            score -= 15
            actions.append("Reduce / avoid adding due to weak liquidity")
            priority = "Medium" if priority != "High" else priority

        if gamma > 0.10 and dte <= 14:
            score -= 15
            actions.append("Reduce near-term gamma exposure")
            priority = "High"

        if theta < -50 and dte <= 21:
            score -= 10
            actions.append("Review theta decay")
            priority = "Medium" if priority != "High" else priority

        if pnl > 0 and dte <= 14:
            actions.append("Consider profit capture")
            priority = "Medium" if priority != "High" else priority

        if not actions:
            actions.append("Hold / monitor")

        rows.append({
            "Underlying": symbol,
            "Option Symbol": row.get("option_symbol", ""),
            "Strategy": row.get("strategy", ""),
            "DTE": dte,
            "Portfolio %": round(position_pct, 2),
            "Gamma": gamma,
            "Theta": theta,
            "Liquidity Score": liquidity,
            "Unrealized PnL": pnl,
            "Optimization Score": round(max(0, min(100, score)), 2),
            "Priority": priority,
            "Recommended Action": "; ".join(actions),
        })

    queue = pd.DataFrame(rows)
    queue = queue[queue["Recommended Action"] != "Hold / monitor"].copy()

    if not queue.empty:
        order = {"High": 0, "Medium": 1, "Normal": 2, "Low": 3}
        queue["_sort"] = queue["Priority"].map(order).fillna(9)
        queue = queue.sort_values(["_sort", "Optimization Score"]).drop(columns=["_sort"]).reset_index(drop=True)

    by_symbol = (
        df.groupby("underlying", as_index=False)
        .agg(
            total_value=("position_value", "sum"),
            positions=("underlying", "size"),
            net_delta=("delta", "sum"),
            net_gamma=("gamma", "sum"),
            net_theta=("theta", "sum"),
            net_vega=("vega", "sum"),
        )
        .sort_values("total_value", ascending=False)
        .reset_index(drop=True)
    )
    by_symbol["portfolio_pct"] = by_symbol["total_value"] / total_value * 100

    return {
        "available": True,
        "action_queue": queue,
        "by_symbol": by_symbol,
        "positions": df,
        "summary": {
            "position_count": int(len(df)),
            "optimization_action_count": int(len(queue)),
            "largest_position_pct": round(float(df["portfolio_pct"].max()), 2),
            "symbol_count": int(df["underlying"].nunique()),
        },
    }


def build_allocation_recommendations(
    position_actions: dict[str, Any],
    objective_score: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY

    if not position_actions.get("available"):
        return position_actions

    by_symbol = _df(position_actions.get("by_symbol"))
    queue = _df(position_actions.get("action_queue"))

    rows = []

    if not by_symbol.empty:
        concentrated = by_symbol[by_symbol["portfolio_pct"] > policy["max_symbol_exposure_pct"]]
        for _, row in concentrated.iterrows():
            rows.append({
                "Recommendation": "Reduce symbol concentration",
                "Priority": "High",
                "Target": row.get("underlying", ""),
                "Current Exposure %": round(float(row.get("portfolio_pct", 0)), 2),
                "Rationale": "Symbol exposure exceeds max policy limit.",
            })

    if objective_score.get("objective_rating") in {"AT_RISK", "CRITICAL"}:
        rows.append({
            "Recommendation": "De-risk portfolio",
            "Priority": "High",
            "Target": "Portfolio",
            "Current Exposure %": "",
            "Rationale": "Portfolio objective score is below acceptable threshold.",
        })

    if queue.empty and not rows:
        rows.append({
            "Recommendation": "Maintain current allocation",
            "Priority": "Normal",
            "Target": "Portfolio",
            "Current Exposure %": "",
            "Rationale": "No major optimization actions detected.",
        })

    return {
        "available": True,
        "allocation_recommendations": pd.DataFrame(rows),
    }


def generate_portfolio_optimization_playbook(
    objective_score: dict[str, Any],
    position_actions: dict[str, Any],
    allocation_recommendations: dict[str, Any],
) -> dict[str, Any]:
    rating = objective_score.get("objective_rating", "WATCH")
    rows = []

    if rating in {"CRITICAL", "AT_RISK"}:
        rows.append({
            "Step": 1,
            "Playbook": "Risk Reduction First",
            "Priority": "High",
            "Action": "Trim concentrated, illiquid, or high-gamma positions before adding new trades.",
        })
    elif rating == "WATCH":
        rows.append({
            "Step": 1,
            "Playbook": "Selective Optimization",
            "Priority": "Medium",
            "Action": "Work high-priority action queue and improve portfolio construction.",
        })
    else:
        rows.append({
            "Step": 1,
            "Playbook": "Optimization Mode",
            "Priority": "Normal",
            "Action": "Maintain risk controls while selectively adding high-quality opportunities.",
        })

    action_count = _num(_safe_get(position_actions, ["summary", "optimization_action_count"], 0), 0)
    if action_count > 0:
        rows.append({
            "Step": 2,
            "Playbook": "Work Position Action Queue",
            "Priority": "High" if action_count >= 5 else "Medium",
            "Action": f"Review and resolve {int(action_count)} position optimization actions.",
        })

    alloc = _df(allocation_recommendations.get("allocation_recommendations"))
    if not alloc.empty:
        rows.append({
            "Step": 3,
            "Playbook": "Allocation Review",
            "Priority": "Medium",
            "Action": "Apply allocation recommendations to reduce concentration and improve capital efficiency.",
        })

    return {
        "available": True,
        "playbook": pd.DataFrame(rows),
        "top_playbook": rows[0]["Playbook"] if rows else "No playbook",
    }


def build_portfolio_optimization_report(
    positions: Any,
    risk_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY

    objective = calculate_portfolio_objective_score(
        risk_report=risk_report,
        construction_report=construction_report,
        income_report=income_report,
        liquidity_report=liquidity_report,
        market_maker_report=market_maker_report,
        volatility_report=volatility_report,
        policy=policy,
    )

    actions = identify_position_optimization_actions(
        positions=positions,
        risk_report=risk_report,
        liquidity_report=liquidity_report,
        policy=policy,
    )

    allocation = build_allocation_recommendations(
        position_actions=actions,
        objective_score=objective,
        policy=policy,
    ) if actions.get("available") else {
        "available": False,
        "reason": actions.get("reason", "No actions available."),
        "allocation_recommendations": pd.DataFrame(),
    }

    playbook = generate_portfolio_optimization_playbook(
        objective_score=objective,
        position_actions=actions,
        allocation_recommendations=allocation,
    )

    summary = {
        "objective_score": objective.get("objective_score"),
        "objective_rating": objective.get("objective_rating"),
        "optimization_action_count": _safe_get(actions, ["summary", "optimization_action_count"], 0),
        "largest_position_pct": _safe_get(actions, ["summary", "largest_position_pct"], 0),
        "symbol_count": _safe_get(actions, ["summary", "symbol_count"], 0),
        "top_playbook": playbook.get("top_playbook"),
    }

    return {
        "available": True,
        "summary": summary,
        "objective": objective,
        "actions": actions,
        "allocation": allocation,
        "playbook": playbook,
        "policy": policy,
    }


def summarize_portfolio_optimization(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Portfolio Optimization AI unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Portfolio Optimization AI score is {s.get('objective_score')}/100 "
        f"with rating {s.get('objective_rating')}. "
        f"{s.get('optimization_action_count')} optimization actions are queued. "
        f"Largest position is {s.get('largest_position_pct')}% of portfolio. "
        f"Top playbook: {s.get('top_playbook')}."
    )
