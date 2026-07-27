"""
Sprint 10 Phase 5 — Institutional Volatility Command Center.
Aggregates volatility surface, regime, term structure, and skew intelligence.
Decision-support only; does not place trades.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

DEFAULT_VOL_COMMAND_POLICY = {
    "high_score_threshold": 75,
    "elevated_score_threshold": 60,
    "normal_score_threshold": 40,
    "surface_weight": 0.25,
    "regime_weight": 0.30,
    "term_weight": 0.25,
    "skew_weight": 0.20,
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


def _priority_score(priority: Any) -> int:
    p = str(priority).upper()
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "NORMAL": 3, "LOW": 4}.get(p, 9)


def calculate_surface_component(surface_report: dict[str, Any] | None) -> dict[str, Any]:
    if not surface_report or not surface_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Surface report unavailable."]}

    summary = surface_report.get("summary", {})
    avg_iv = _num(summary.get("avg_iv"), 0)
    opps = _num(summary.get("opportunity_count"), 0)
    iv_regime = str(summary.get("iv_regime", "UNKNOWN"))
    score = 25.0
    drivers: list[str] = []

    if iv_regime == "HIGH_IV":
        score += 35
        drivers.append("Surface average IV is high.")
    elif iv_regime == "LOW_IV":
        score += 20
        drivers.append("Surface average IV is low.")
    elif iv_regime == "NORMAL_IV":
        score += 10
        drivers.append("Surface IV is normal.")

    score += min(25, opps * 8)
    if avg_iv >= 0.80:
        score += 15
        drivers.append("Surface IV is extremely elevated.")

    return {"score": round(max(0, min(100, score)), 2), "label": iv_regime, "drivers": drivers or ["No major surface driver."]}


def calculate_regime_component(regime_report: dict[str, Any] | None) -> dict[str, Any]:
    if not regime_report or not regime_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Regime report unavailable."]}

    summary = regime_report.get("summary", {})
    regime = str(summary.get("current_regime", "UNKNOWN"))
    iv_rank = _num(summary.get("iv_rank"), 0)
    iv_pct = _num(summary.get("iv_percentile"), 0)
    vrp = str(summary.get("volatility_risk_premium", "UNKNOWN"))
    stability = _num(summary.get("stability_score"), 0)
    score = 20.0
    drivers: list[str] = []

    if regime in {"CRISIS_VOL", "HIGH_VOL"}:
        score += 40
        drivers.append("Volatility regime is high/crisis.")
    elif regime == "ELEVATED_VOL":
        score += 30
        drivers.append("Volatility regime is elevated.")
    elif regime in {"LOW_VOL", "EXTREME_LOW_VOL"}:
        score += 20
        drivers.append("Volatility regime is low.")

    if iv_rank >= 70 or iv_pct >= 70:
        score += 20
        drivers.append("IV rank/percentile is high.")
    elif iv_rank <= 20 or iv_pct <= 20:
        score += 12
        drivers.append("IV rank/percentile is low.")

    if vrp == "POSITIVE_VRP":
        score += 15
        drivers.append("Positive volatility risk premium.")
    elif vrp == "NEGATIVE_VRP":
        score += 10
        drivers.append("Negative volatility risk premium.")

    if stability >= 75:
        score += 5

    return {"score": round(max(0, min(100, score)), 2), "label": regime, "drivers": drivers or ["No major regime driver."]}


def calculate_term_component(term_report: dict[str, Any] | None) -> dict[str, Any]:
    if not term_report or not term_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Term structure report unavailable."]}

    summary = term_report.get("summary", {})
    regime = str(summary.get("term_regime", "UNKNOWN"))
    slope_quality = str(summary.get("slope_quality", "UNKNOWN"))
    slope = _num(summary.get("term_slope"), 0)
    opps = _num(summary.get("opportunity_count"), 0)
    score = 20.0
    drivers: list[str] = []

    if regime == "BACKWARDATION":
        score += 35
        drivers.append("Term structure is backwardated.")
    elif regime == "CONTANGO":
        score += 20
        drivers.append("Term structure is in contango.")
    elif regime == "FLAT":
        score += 10
        drivers.append("Term structure is flat.")

    if slope_quality == "STEEP":
        score += 20
        drivers.append("Term slope is steep.")

    score += min(25, opps * 7)
    if abs(slope) >= 0.15:
        score += 10
        drivers.append("Term slope magnitude is large.")

    return {"score": round(max(0, min(100, score)), 2), "label": regime, "drivers": drivers or ["No major term driver."]}


def calculate_skew_component(skew_report: dict[str, Any] | None) -> dict[str, Any]:
    if not skew_report or not skew_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Skew report unavailable."]}

    summary = skew_report.get("summary", {})
    regime = str(summary.get("regime", "UNKNOWN"))
    put_skew = abs(_num(summary.get("put_skew"), 0))
    call_skew = abs(_num(summary.get("call_skew"), 0))
    rr = abs(_num(summary.get("risk_reversal"), 0))
    opps = _num(summary.get("opportunity_count"), 0)
    score = 20.0
    drivers: list[str] = []

    if regime in {"PUT_SKEW_STEEP", "CALL_SKEW_STEEP"}:
        score += 35
        drivers.append("Skew is steep.")
    elif regime == "BALANCED":
        score += 5
        drivers.append("Skew is balanced.")

    score += min(20, max(put_skew, call_skew, rr) * 100)
    score += min(25, opps * 8)
    return {"score": round(max(0, min(100, score)), 2), "label": regime, "drivers": drivers or ["No major skew driver."]}


def calculate_institutional_volatility_score(
    surface_report: dict[str, Any] | None = None,
    regime_report: dict[str, Any] | None = None,
    term_report: dict[str, Any] | None = None,
    skew_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_VOL_COMMAND_POLICY
    surface = calculate_surface_component(surface_report)
    regime = calculate_regime_component(regime_report)
    term = calculate_term_component(term_report)
    skew = calculate_skew_component(skew_report)

    score = (
        surface["score"] * policy["surface_weight"]
        + regime["score"] * policy["regime_weight"]
        + term["score"] * policy["term_weight"]
        + skew["score"] * policy["skew_weight"]
    )
    score = round(max(0, min(100, score)), 2)

    if score >= 85:
        rating = "EXTREME"
    elif score >= policy["high_score_threshold"]:
        rating = "HIGH"
    elif score >= policy["elevated_score_threshold"]:
        rating = "ELEVATED"
    elif score >= policy["normal_score_threshold"]:
        rating = "NORMAL"
    else:
        rating = "LOW"

    return {
        "score": score,
        "rating": rating,
        "surface_component": surface,
        "regime_component": regime,
        "term_component": term,
        "skew_component": skew,
    }


def merge_volatility_opportunities(
    surface_report: dict[str, Any] | None = None,
    regime_report: dict[str, Any] | None = None,
    term_report: dict[str, Any] | None = None,
    skew_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for source, df in [
        ("Vol Surface", _df(_safe_get(surface_report, ["opportunities", "opportunities"], pd.DataFrame()))),
        ("Vol Regime", _df((regime_report or {}).get("recommendations"))),
        ("Term Structure", _df((term_report or {}).get("recommendations"))),
        ("Term Structure", _df(_safe_get(term_report, ["opportunities", "opportunities"], pd.DataFrame()))),
        ("Skew", _df((skew_report or {}).get("opportunities"))),
    ]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            rows.append({
                "Source": source,
                "Priority": row.get("Priority", "Normal"),
                "Opportunity": row.get("Opportunity", row.get("Recommendation", "")),
                "Regime": row.get("Regime", ""),
                "Rationale": row.get("Rationale", ""),
                "Candidate Structures": row.get("Candidate Structures", row.get("Structure", "")),
            })

    queue = pd.DataFrame(rows)
    if not queue.empty:
        queue["_priority_sort"] = queue["Priority"].apply(_priority_score)
        queue = queue.sort_values(["_priority_sort", "Source"]).drop(columns=["_priority_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "opportunities": queue,
        "opportunity_count": int(len(queue)),
        "high_priority_count": int((queue["Priority"].astype(str).str.upper() == "HIGH").sum()) if not queue.empty else 0,
    }


def generate_volatility_playbook(volatility_score: dict[str, Any], opportunities: dict[str, Any]) -> dict[str, Any]:
    rating = volatility_score.get("rating", "NORMAL")
    score = _num(volatility_score.get("score"), 0)
    opp_df = _df(opportunities.get("opportunities"))
    rows: list[dict[str, Any]] = []

    if rating in {"EXTREME", "HIGH"}:
        rows.append({
            "Playbook": "Elevated Volatility Response",
            "Priority": "High",
            "Bias": "Short vol selectively / hedge tail risk",
            "Structures": "Credit spreads, iron condors, covered calls, put spreads, collars",
            "Risk Note": "Avoid naked short gamma. Use defined-risk structures.",
        })
    elif rating == "ELEVATED":
        rows.append({
            "Playbook": "Premium Harvest With Controls",
            "Priority": "Medium",
            "Bias": "Short premium with risk limits",
            "Structures": "Credit spreads, calendars, condors, CSP/CC overlays",
            "Risk Note": "Monitor term and skew instability.",
        })
    elif rating == "LOW":
        rows.append({
            "Playbook": "Long Volatility Search",
            "Priority": "Medium",
            "Bias": "Look for cheap convexity",
            "Structures": "Debit spreads, calendars, long straddles/strangles, diagonals",
            "Risk Note": "Avoid overpaying for poor liquidity.",
        })
    else:
        rows.append({
            "Playbook": "Balanced Volatility Posture",
            "Priority": "Normal",
            "Bias": "Neutral",
            "Structures": "Defined-risk spreads, balanced calendars, neutral premium structures",
            "Risk Note": "Wait for stronger regime confirmation.",
        })

    if not opp_df.empty:
        high = opp_df[opp_df["Priority"].astype(str).str.upper() == "HIGH"]
        if not high.empty:
            rows.append({
                "Playbook": "Work High-Priority Opportunity Queue",
                "Priority": "High",
                "Bias": "Opportunity-driven",
                "Structures": ", ".join(sorted(set(high["Candidate Structures"].dropna().astype(str))))[:300],
                "Risk Note": f"{len(high)} high-priority opportunity rows detected.",
            })

    return {
        "available": True,
        "playbook": pd.DataFrame(rows),
        "top_recommendation": rows[0]["Playbook"] if rows else "No recommendation",
        "score": score,
    }


def build_volatility_command_center_report(
    surface_report: dict[str, Any] | None = None,
    regime_report: dict[str, Any] | None = None,
    term_report: dict[str, Any] | None = None,
    skew_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_VOL_COMMAND_POLICY
    score = calculate_institutional_volatility_score(surface_report, regime_report, term_report, skew_report, policy)
    opportunities = merge_volatility_opportunities(surface_report, regime_report, term_report, skew_report)
    playbook = generate_volatility_playbook(score, opportunities)
    return {
        "available": True,
        "score": score,
        "opportunities": opportunities,
        "playbook": playbook,
        "surface_report": surface_report,
        "regime_report": regime_report,
        "term_report": term_report,
        "skew_report": skew_report,
        "policy": policy,
    }


def summarize_volatility_command_center(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Volatility Command Center unavailable: {report.get('reason', 'unknown reason')}"
    score = report.get("score", {})
    opps = report.get("opportunities", {})
    playbook = report.get("playbook", {})
    return (
        f"Institutional Volatility Score is {score.get('score')}/100 with rating {score.get('rating')}. "
        f"{opps.get('opportunity_count', 0)} volatility opportunities are queued, including "
        f"{opps.get('high_priority_count', 0)} high-priority items. "
        f"Top playbook: {playbook.get('top_recommendation', 'None')}."
    )
