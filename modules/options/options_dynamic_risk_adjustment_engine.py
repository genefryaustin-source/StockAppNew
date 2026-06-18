"""
Sprint 7 Phase 2 — Dynamic Risk Adjustment Engine.

Institutional dynamic risk adjustment layer:
- Reads portfolio risk, stress, Greeks, liquidity, hedge need, and volatility regime
- Produces risk-adjustment actions
- Recommends exposure scaling
- Suggests hedge, trim, rebalance, pause, or add-risk decisions
- Generates deterministic portfolio risk adjustment plan

Designed to work with existing Sprint 5/6/7 engines but remains defensive:
missing inputs are handled safely.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_RISK_ADJUSTMENT_POLICY = {
    "max_portfolio_risk_score": 70,
    "max_greeks_risk_score": 70,
    "max_stress_loss_pct": 10,
    "min_liquidity_score": 55,
    "max_hedge_need_score": 70,
    "target_gross_exposure_pct": 100,
    "risk_off_scale": 0.50,
    "risk_reduce_scale": 0.75,
    "risk_neutral_scale": 1.00,
    "risk_on_scale": 1.15,
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


def _classify_regime(volatility_regime: Any = None, market_regime: Any = None) -> str:
    text = f"{volatility_regime or ''} {market_regime or ''}".lower()

    if any(x in text for x in ["crash", "panic", "risk-off", "risk off", "high vol", "stress"]):
        return "RISK_OFF"
    if any(x in text for x in ["volatile", "expansion", "uncertain"]):
        return "DEFENSIVE"
    if any(x in text for x in ["bull", "risk-on", "risk on", "calm", "low vol"]):
        return "RISK_ON"

    return "NEUTRAL"


def evaluate_dynamic_risk_state(
    positions: Any,
    portfolio_risk_report: dict[str, Any] | None = None,
    stress_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    hedge_report: dict[str, Any] | None = None,
    volatility_regime: Any = None,
    market_regime: Any = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_RISK_ADJUSTMENT_POLICY
    df = normalize_risk_positions(positions)

    if df.empty:
        return _empty("No positions available.")

    portfolio_risk_score = _num(
        _safe_get(portfolio_risk_report, ["risk_score", "risk_score"], 0)
    )

    greeks_risk_score = _num(
        _safe_get(greeks_report, ["score", "greeks_risk_score"], 0)
    )

    hedge_need_score = _num(
        _safe_get(hedge_report, ["hedge_need", "hedge_need_score"], 0)
    )

    liquidity_score = _num(
        _safe_get(liquidity_report, ["summary", "avg_liquidity_score"], 75)
    )

    worst_loss_pct = 0.0
    worst = _safe_get(stress_report, ["scenarios", "worst_case"], {})
    if isinstance(worst, dict):
        worst_loss_pct = abs(_num(worst.get("Total P&L % Notional"), 0))

    regime = _classify_regime(volatility_regime, market_regime)

    pressure = 0.0
    drivers = []

    if portfolio_risk_score > policy["max_portfolio_risk_score"]:
        pressure += 25
        drivers.append("Portfolio risk exceeds policy threshold.")

    if greeks_risk_score > policy["max_greeks_risk_score"]:
        pressure += 25
        drivers.append("Greeks risk exceeds policy threshold.")

    if worst_loss_pct > policy["max_stress_loss_pct"]:
        pressure += 25
        drivers.append("Stress loss exceeds policy threshold.")

    if liquidity_score < policy["min_liquidity_score"]:
        pressure += 15
        drivers.append("Liquidity score below policy threshold.")

    if hedge_need_score > policy["max_hedge_need_score"]:
        pressure += 20
        drivers.append("Hedge need exceeds policy threshold.")

    if regime == "RISK_OFF":
        pressure += 20
        drivers.append("Market regime is risk-off.")
    elif regime == "DEFENSIVE":
        pressure += 10
        drivers.append("Market regime is defensive.")
    elif regime == "RISK_ON":
        pressure -= 10
        drivers.append("Market regime supports selective risk-on behavior.")

    pressure = round(max(0, min(100, pressure)), 2)

    if pressure >= 80:
        state = "RISK_OFF"
    elif pressure >= 55:
        state = "REDUCE_RISK"
    elif pressure >= 30:
        state = "NEUTRAL_DEFENSIVE"
    elif pressure <= 15 and regime == "RISK_ON":
        state = "RISK_ON"
    else:
        state = "NEUTRAL"

    return {
        "available": True,
        "risk_state": state,
        "risk_pressure_score": pressure,
        "portfolio_risk_score": portfolio_risk_score,
        "greeks_risk_score": greeks_risk_score,
        "worst_stress_loss_pct": round(worst_loss_pct, 2),
        "liquidity_score": liquidity_score,
        "hedge_need_score": hedge_need_score,
        "market_regime": regime,
        "drivers": drivers or ["No significant risk pressure detected."],
    }


def determine_exposure_scale(risk_state: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_RISK_ADJUSTMENT_POLICY

    state = risk_state.get("risk_state", "NEUTRAL")

    if state == "RISK_OFF":
        scale = policy["risk_off_scale"]
        action = "CUT_RISK"
    elif state == "REDUCE_RISK":
        scale = policy["risk_reduce_scale"]
        action = "REDUCE_EXPOSURE"
    elif state == "NEUTRAL_DEFENSIVE":
        scale = 0.90
        action = "DEFENSIVE_REBALANCE"
    elif state == "RISK_ON":
        scale = policy["risk_on_scale"]
        action = "SELECTIVE_ADD_RISK"
    else:
        scale = policy["risk_neutral_scale"]
        action = "MAINTAIN"

    return {
        "available": True,
        "recommended_action": action,
        "exposure_scale": round(float(scale), 4),
        "target_exposure_pct": round(float(scale) * 100, 2),
        "description": _describe_scale_action(action, scale),
    }


def _describe_scale_action(action: str, scale: float) -> str:
    if action == "CUT_RISK":
        return f"Cut gross exposure toward {scale * 100:.0f}% of current exposure."
    if action == "REDUCE_EXPOSURE":
        return f"Reduce exposure toward {scale * 100:.0f}% of current exposure."
    if action == "DEFENSIVE_REBALANCE":
        return "Maintain core exposure but rebalance toward hedged and liquid structures."
    if action == "SELECTIVE_ADD_RISK":
        return f"Allow selective additions up to {scale * 100:.0f}% of current exposure."
    return "Maintain current exposure."


def build_position_adjustment_plan(
    positions: Any,
    risk_state: dict[str, Any],
    scale: dict[str, Any],
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    df = df.copy()
    exposure_scale = float(scale.get("exposure_scale", 1.0))
    action = scale.get("recommended_action", "MAINTAIN")

    if "risk_contribution" not in df.columns:
        df["risk_contribution"] = (
            df["net_delta"].abs() * 0.25
            + df["net_gamma"].abs() * 0.30
            + df["net_vega"].abs() * 0.25
            + df["net_theta"].abs() * 0.10
            + df["notional_proxy"].abs() * 0.10
        )

    total_risk = max(1.0, float(df["risk_contribution"].sum() or 1.0))
    df["risk_share_pct"] = (df["risk_contribution"] / total_risk * 100).round(2)

    rows = []
    for _, row in df.sort_values("risk_contribution", ascending=False).iterrows():
        qty = _num(row.get("qty"), 0)
        target_qty = qty * exposure_scale

        if action in {"CUT_RISK", "REDUCE_EXPOSURE", "DEFENSIVE_REBALANCE"}:
            qty_change = target_qty - qty
        elif action == "SELECTIVE_ADD_RISK":
            qty_change = max(0, target_qty - qty)
        else:
            qty_change = 0

        if abs(qty_change) < 0.5:
            instruction = "Hold"
        elif qty_change < 0:
            instruction = "Trim"
        else:
            instruction = "Add"

        if action == "DEFENSIVE_REBALANCE" and row.get("risk_share_pct", 0) > 25:
            instruction = "Trim / Hedge"

        rows.append({
            "Underlying": row.get("underlying", ""),
            "Option Symbol": row.get("option_symbol", ""),
            "Type": row.get("option_type", row.get("type", "")),
            "Expiry": row.get("expiry", ""),
            "Strike": row.get("strike", 0),
            "Current Qty": round(qty, 2),
            "Target Qty": round(target_qty, 2),
            "Qty Change": round(qty_change, 2),
            "Instruction": instruction,
            "Risk Share %": row.get("risk_share_pct", 0),
            "Notional Proxy": round(_num(row.get("notional_proxy"), 0), 2),
            "Net Delta": round(_num(row.get("net_delta"), 0), 4),
            "Net Gamma": round(_num(row.get("net_gamma"), 0), 4),
            "Net Vega": round(_num(row.get("net_vega"), 0), 4),
        })

    plan = pd.DataFrame(rows)

    return {
        "available": True,
        "adjustment_plan": plan,
        "action": action,
        "exposure_scale": exposure_scale,
    }


def generate_dynamic_risk_actions(
    risk_state: dict[str, Any],
    scale: dict[str, Any],
) -> dict[str, Any]:
    if not risk_state.get("available"):
        return risk_state

    actions = []
    state = risk_state.get("risk_state")
    pressure = _num(risk_state.get("risk_pressure_score"), 0)

    if state == "RISK_OFF":
        actions.extend([
            {"Priority": "Critical", "Action": "Cut gross exposure", "Reason": "Risk pressure is extreme."},
            {"Priority": "Critical", "Action": "Add or increase tail hedge", "Reason": "Portfolio requires downside protection."},
            {"Priority": "High", "Action": "Pause new directional trades", "Reason": "Risk-off regime detected."},
        ])
    elif state == "REDUCE_RISK":
        actions.extend([
            {"Priority": "High", "Action": "Trim largest risk contributors", "Reason": "Risk pressure is elevated."},
            {"Priority": "Medium", "Action": "Prefer defined-risk structures", "Reason": "Reduce open-ended exposure."},
        ])
    elif state == "NEUTRAL_DEFENSIVE":
        actions.extend([
            {"Priority": "Medium", "Action": "Rebalance toward liquid structures", "Reason": "Defensive posture recommended."},
            {"Priority": "Medium", "Action": "Review hedge candidates", "Reason": "Risk is manageable but not low."},
        ])
    elif state == "RISK_ON":
        actions.extend([
            {"Priority": "Normal", "Action": "Allow selective risk additions", "Reason": "Risk pressure is low and regime is favorable."},
            {"Priority": "Normal", "Action": "Prioritize high-liquidity, high-conviction trades", "Reason": "Add risk selectively."},
        ])
    else:
        actions.append({
            "Priority": "Normal",
            "Action": "Maintain exposure",
            "Reason": "Risk state is neutral.",
        })

    if risk_state.get("liquidity_score", 100) < 55:
        actions.append({
            "Priority": "High",
            "Action": "Avoid illiquid contracts",
            "Reason": "Liquidity score below threshold.",
        })

    if risk_state.get("hedge_need_score", 0) > 70:
        actions.append({
            "Priority": "High",
            "Action": "Implement hedge plan",
            "Reason": "Hedge need is elevated.",
        })

    table = pd.DataFrame(actions)

    return {
        "available": True,
        "actions": table,
        "risk_pressure_score": pressure,
        "recommended_action": scale.get("recommended_action"),
    }


def build_dynamic_risk_adjustment_report(
    positions: Any,
    portfolio_risk_report: dict[str, Any] | None = None,
    stress_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    hedge_report: dict[str, Any] | None = None,
    volatility_regime: Any = None,
    market_regime: Any = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    df = normalize_risk_positions(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No options positions available.",
            "positions": df,
        }

    risk_state = evaluate_dynamic_risk_state(
        positions=df,
        portfolio_risk_report=portfolio_risk_report,
        stress_report=stress_report,
        greeks_report=greeks_report,
        liquidity_report=liquidity_report,
        hedge_report=hedge_report,
        volatility_regime=volatility_regime,
        market_regime=market_regime,
        policy=policy,
    )

    scale = determine_exposure_scale(risk_state, policy)
    plan = build_position_adjustment_plan(df, risk_state, scale)
    actions = generate_dynamic_risk_actions(risk_state, scale)

    return {
        "available": True,
        "positions": df,
        "risk_state": risk_state,
        "exposure_scale": scale,
        "adjustment_plan": plan,
        "actions": actions,
    }


def summarize_dynamic_risk_adjustment(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Dynamic risk adjustment unavailable: {report.get('reason', 'unknown reason')}"

    risk_state = report.get("risk_state", {})
    scale = report.get("exposure_scale", {})

    return (
        f"Dynamic risk state is {risk_state.get('risk_state')} "
        f"with pressure score {risk_state.get('risk_pressure_score')}/100. "
        f"Recommended action: {scale.get('recommended_action')} "
        f"at {scale.get('target_exposure_pct')}% target exposure."
    )
