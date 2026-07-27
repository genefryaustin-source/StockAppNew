"""
Sprint 12 Phase 3 — Autonomous Risk Rebalancing Engine.

Autonomous Institutional Options CIO layer:
- Portfolio risk-state ingestion
- Risk rebalance trigger detection
- Delta/gamma/theta/vega rebalance guidance
- Concentration / liquidity / guardrail rebalance guidance
- Rebalance action queue
- CIO-style autonomous risk rebalancing playbook

This module does not place trades. It produces deterministic rebalancing guidance.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_RISK_REBALANCING_POLICY = {
    "max_risk_score": 65.0,
    "target_risk_score": 45.0,
    "max_delta_abs": 250.0,
    "max_gamma_abs": 50.0,
    "max_vega_abs": 500.0,
    "max_theta_decay": -500.0,
    "max_single_symbol_pct": 25.0,
    "min_liquidity_score": 50.0,
    "urgent_dte": 7,
    "rebalance_score_threshold": 65.0,
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


def normalize_rebalance_positions(positions: Any) -> pd.DataFrame:
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

    df["position_value"] = df["market_value"].abs().where(
        df["market_value"].abs() > 0,
        df["notional"].abs(),
    )

    return df


def evaluate_risk_rebalance_triggers(
    positions: Any,
    risk_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    guardrails_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_RISK_REBALANCING_POLICY
    df = normalize_rebalance_positions(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No positions available.",
            "triggers": pd.DataFrame(),
        }

    total_value = float(df["position_value"].sum()) or 1.0
    df["portfolio_pct"] = df["position_value"] / total_value * 100

    risk_score = _num(
        _safe_get(risk_report, ["risk_score", "risk_score"], risk_report.get("risk_score", 0) if isinstance(risk_report, dict) else 0),
        0,
    )

    net_delta = _num(_safe_get(risk_report, ["net_greeks", "delta"], df["delta"].sum()), df["delta"].sum())
    net_gamma = _num(_safe_get(risk_report, ["net_greeks", "gamma"], df["gamma"].sum()), df["gamma"].sum())
    net_theta = _num(_safe_get(risk_report, ["net_greeks", "theta"], df["theta"].sum()), df["theta"].sum())
    net_vega = _num(_safe_get(risk_report, ["net_greeks", "vega"], df["vega"].sum()), df["vega"].sum())

    guardrail_breaches = _num((guardrails_report or {}).get("breach_count", 0), 0)
    liquidity_regime = _safe_get(liquidity_report, ["summary", "liquidity_regime"], "UNKNOWN")
    mm_rating = _safe_get(market_maker_report, ["score", "rating"], "NORMAL")
    vol_rating = _safe_get(volatility_report, ["score", "rating"], "NORMAL")

    rows = []

    if risk_score > policy["max_risk_score"]:
        rows.append({
            "Trigger": "Portfolio Risk Score",
            "Severity": "High",
            "Metric": risk_score,
            "Threshold": policy["max_risk_score"],
            "Action": "Reduce portfolio risk to target score.",
        })

    if abs(net_delta) > policy["max_delta_abs"]:
        rows.append({
            "Trigger": "Delta Exposure",
            "Severity": "Medium",
            "Metric": round(net_delta, 4),
            "Threshold": policy["max_delta_abs"],
            "Action": "Rebalance directional exposure.",
        })

    if abs(net_gamma) > policy["max_gamma_abs"]:
        rows.append({
            "Trigger": "Gamma Exposure",
            "Severity": "High",
            "Metric": round(net_gamma, 4),
            "Threshold": policy["max_gamma_abs"],
            "Action": "Reduce high gamma exposure or add offsetting gamma hedge.",
        })

    if net_theta < policy["max_theta_decay"]:
        rows.append({
            "Trigger": "Theta Decay",
            "Severity": "Medium",
            "Metric": round(net_theta, 4),
            "Threshold": policy["max_theta_decay"],
            "Action": "Review excessive theta burn.",
        })

    if abs(net_vega) > policy["max_vega_abs"]:
        rows.append({
            "Trigger": "Vega Exposure",
            "Severity": "Medium",
            "Metric": round(net_vega, 4),
            "Threshold": policy["max_vega_abs"],
            "Action": "Reduce volatility sensitivity or balance vega.",
        })

    if guardrail_breaches > 0:
        rows.append({
            "Trigger": "Guardrail Breach",
            "Severity": "High",
            "Metric": int(guardrail_breaches),
            "Threshold": 0,
            "Action": "Resolve guardrail breaches before adding new risk.",
        })

    if liquidity_regime in {"STRESSED_LIQUIDITY", "THIN_LIQUIDITY"}:
        rows.append({
            "Trigger": "Liquidity Conditions",
            "Severity": "High" if liquidity_regime == "STRESSED_LIQUIDITY" else "Medium",
            "Metric": liquidity_regime,
            "Threshold": "NORMAL_LIQUIDITY",
            "Action": "Reduce illiquid exposures and use patient execution.",
        })

    if mm_rating in {"HIGH", "EXTREME"}:
        rows.append({
            "Trigger": "Market Maker Stress",
            "Severity": "Medium",
            "Metric": mm_rating,
            "Threshold": "ELEVATED",
            "Action": "Reduce short gamma and crowded strike exposure.",
        })

    if vol_rating in {"HIGH", "EXTREME"}:
        rows.append({
            "Trigger": "Volatility Stress",
            "Severity": "Medium",
            "Metric": vol_rating,
            "Threshold": "ELEVATED",
            "Action": "Review volatility-sensitive positions.",
        })

    by_symbol = (
        df.groupby("underlying", as_index=False)
        .agg(
            total_value=("position_value", "sum"),
            positions=("underlying", "size"),
            net_delta=("delta", "sum"),
            net_gamma=("gamma", "sum"),
            net_theta=("theta", "sum"),
            net_vega=("vega", "sum"),
            avg_liquidity=("liquidity_score", "mean"),
            min_dte=("dte", "min"),
        )
        .sort_values("total_value", ascending=False)
        .reset_index(drop=True)
    )
    by_symbol["portfolio_pct"] = by_symbol["total_value"] / total_value * 100

    concentrated = by_symbol[by_symbol["portfolio_pct"] > policy["max_single_symbol_pct"]]
    for _, row in concentrated.iterrows():
        rows.append({
            "Trigger": "Symbol Concentration",
            "Severity": "High",
            "Metric": f"{row.get('underlying')} {row.get('portfolio_pct'):.2f}%",
            "Threshold": f"{policy['max_single_symbol_pct']}%",
            "Action": "Reduce symbol concentration.",
        })

    urgent = df[(df["dte"] > 0) & (df["dte"] <= policy["urgent_dte"])]
    if not urgent.empty:
        rows.append({
            "Trigger": "Urgent Expiration",
            "Severity": "High",
            "Metric": int(len(urgent)),
            "Threshold": 0,
            "Action": "Review expiring positions for roll/close/assignment risk.",
        })

    triggers = pd.DataFrame(rows)
    if not triggers.empty:
        order = {"High": 0, "Medium": 1, "Low": 2}
        triggers["_sort"] = triggers["Severity"].map(order).fillna(9)
        triggers = triggers.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "triggers": triggers,
        "by_symbol": by_symbol,
        "positions": df,
        "summary": {
            "trigger_count": int(len(triggers)),
            "high_trigger_count": int((triggers["Severity"] == "High").sum()) if not triggers.empty else 0,
            "risk_score": round(risk_score, 2),
            "net_delta": round(net_delta, 4),
            "net_gamma": round(net_gamma, 4),
            "net_theta": round(net_theta, 4),
            "net_vega": round(net_vega, 4),
            "largest_symbol_pct": round(float(by_symbol["portfolio_pct"].max()), 2) if not by_symbol.empty else 0,
        },
    }


def score_rebalance_need(triggers_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_RISK_REBALANCING_POLICY

    if not triggers_report.get("available"):
        return triggers_report

    triggers = _df(triggers_report.get("triggers"))
    s = triggers_report.get("summary", {})

    score = 0.0
    drivers = []

    high_count = _num(s.get("high_trigger_count"), 0)
    trigger_count = _num(s.get("trigger_count"), 0)
    risk_score = _num(s.get("risk_score"), 0)

    score += min(45, high_count * 15)
    score += min(25, trigger_count * 5)

    if risk_score > policy["max_risk_score"]:
        score += min(30, risk_score - policy["max_risk_score"])
        drivers.append("Risk score exceeds max policy.")

    if high_count > 0:
        drivers.append("High-severity rebalance triggers exist.")
    if trigger_count > 3:
        drivers.append("Multiple rebalance triggers are active.")

    score = round(max(0, min(100, score)), 2)

    if score >= 85:
        urgency = "CRITICAL"
    elif score >= policy["rebalance_score_threshold"]:
        urgency = "HIGH"
    elif score >= 40:
        urgency = "MEDIUM"
    elif score > 0:
        urgency = "LOW"
    else:
        urgency = "NONE"

    return {
        "available": True,
        "rebalance_score": score,
        "rebalance_urgency": urgency,
        "drivers": drivers or ["No material rebalance need detected."],
    }


def build_rebalance_action_queue(
    triggers_report: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_RISK_REBALANCING_POLICY

    if not triggers_report.get("available"):
        return triggers_report

    rows = []
    triggers = _df(triggers_report.get("triggers"))
    by_symbol = _df(triggers_report.get("by_symbol"))
    positions = _df(triggers_report.get("positions"))

    for _, row in triggers.iterrows():
        rows.append({
            "Priority": row.get("Severity", "Medium"),
            "Source": row.get("Trigger", ""),
            "Target": "Portfolio",
            "Action": row.get("Action", ""),
            "Metric": row.get("Metric", ""),
            "Threshold": row.get("Threshold", ""),
        })

    if not by_symbol.empty:
        concentrated = by_symbol[by_symbol["portfolio_pct"] > policy["max_single_symbol_pct"]]
        for _, row in concentrated.iterrows():
            rows.append({
                "Priority": "High",
                "Source": "Concentration",
                "Target": row.get("underlying", ""),
                "Action": "Trim exposure or add offsetting hedge.",
                "Metric": f"{row.get('portfolio_pct'):.2f}%",
                "Threshold": f"{policy['max_single_symbol_pct']}%",
            })

    if not positions.empty:
        illiquid = positions[positions["liquidity_score"] < policy["min_liquidity_score"]]
        for _, row in illiquid.head(20).iterrows():
            rows.append({
                "Priority": "Medium",
                "Source": "Liquidity",
                "Target": row.get("option_symbol", row.get("underlying", "")),
                "Action": "Reduce or avoid adding to illiquid position.",
                "Metric": row.get("liquidity_score", 0),
                "Threshold": policy["min_liquidity_score"],
            })

        urgent = positions[(positions["dte"] > 0) & (positions["dte"] <= policy["urgent_dte"])]
        for _, row in urgent.head(20).iterrows():
            rows.append({
                "Priority": "High",
                "Source": "Expiration",
                "Target": row.get("option_symbol", row.get("underlying", "")),
                "Action": "Close, roll, or prepare assignment decision.",
                "Metric": row.get("dte", 0),
                "Threshold": policy["urgent_dte"],
            })

    queue = pd.DataFrame(rows)
    if not queue.empty:
        order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        queue["_sort"] = queue["Priority"].map(order).fillna(9)
        queue = queue.sort_values(["_sort", "Source"]).drop(columns=["_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "rebalance_queue": queue,
        "action_count": int(len(queue)),
        "high_action_count": int((queue["Priority"] == "High").sum()) if not queue.empty else 0,
    }


def generate_rebalancing_playbook(
    rebalance_score: dict[str, Any],
    action_queue: dict[str, Any],
) -> dict[str, Any]:
    urgency = rebalance_score.get("rebalance_urgency", "NONE")
    rows = []

    if urgency in {"CRITICAL", "HIGH"}:
        rows.append({
            "Step": 1,
            "Playbook": "Immediate Risk Reduction",
            "Priority": "High",
            "Action": "Freeze new risk additions and work high-priority rebalance queue.",
        })
        rows.append({
            "Step": 2,
            "Playbook": "Greek Neutralization",
            "Priority": "High",
            "Action": "Reduce excess delta/gamma/vega exposures with defined-risk offsets.",
        })
    elif urgency == "MEDIUM":
        rows.append({
            "Step": 1,
            "Playbook": "Controlled Rebalance",
            "Priority": "Medium",
            "Action": "Resolve medium/high triggers before adding new trades.",
        })
    elif urgency == "LOW":
        rows.append({
            "Step": 1,
            "Playbook": "Monitor Rebalance Triggers",
            "Priority": "Low",
            "Action": "Monitor current triggers and rebalance opportunistically.",
        })
    else:
        rows.append({
            "Step": 1,
            "Playbook": "No Rebalance Required",
            "Priority": "Normal",
            "Action": "Portfolio is within rebalance policy.",
        })

    if action_queue.get("high_action_count", 0) > 0:
        rows.append({
            "Step": 3,
            "Playbook": "High Priority Action Queue",
            "Priority": "High",
            "Action": f"Resolve {action_queue.get('high_action_count')} high-priority rebalance actions.",
        })

    return {
        "available": True,
        "playbook": pd.DataFrame(rows),
        "top_playbook": rows[0]["Playbook"] if rows else "No playbook",
    }


def build_autonomous_risk_rebalancing_report(
    positions: Any,
    risk_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    guardrails_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_RISK_REBALANCING_POLICY

    triggers = evaluate_risk_rebalance_triggers(
        positions=positions,
        risk_report=risk_report,
        greeks_report=greeks_report,
        guardrails_report=guardrails_report,
        liquidity_report=liquidity_report,
        market_maker_report=market_maker_report,
        volatility_report=volatility_report,
        policy=policy,
    )

    if not triggers.get("available"):
        return triggers

    score = score_rebalance_need(triggers, policy=policy)
    queue = build_rebalance_action_queue(triggers, policy=policy)
    playbook = generate_rebalancing_playbook(score, queue)

    summary = {
        "rebalance_score": score.get("rebalance_score"),
        "rebalance_urgency": score.get("rebalance_urgency"),
        "trigger_count": _safe_get(triggers, ["summary", "trigger_count"], 0),
        "high_trigger_count": _safe_get(triggers, ["summary", "high_trigger_count"], 0),
        "action_count": queue.get("action_count", 0),
        "high_action_count": queue.get("high_action_count", 0),
        "top_playbook": playbook.get("top_playbook"),
    }

    return {
        "available": True,
        "summary": summary,
        "triggers": triggers,
        "score": score,
        "queue": queue,
        "playbook": playbook,
        "policy": policy,
    }


def summarize_autonomous_risk_rebalancing(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Autonomous Risk Rebalancing unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Autonomous Risk Rebalancing score is {s.get('rebalance_score')}/100 "
        f"with urgency {s.get('rebalance_urgency')}. "
        f"{s.get('trigger_count')} triggers and {s.get('action_count')} actions are active. "
        f"Top playbook: {s.get('top_playbook')}."
    )
