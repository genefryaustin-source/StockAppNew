"""
Sprint 11 Phase 5 — Market Maker Command Center.

Aggregates Sprint 11 market-maker intelligence:
- Dealer Positioning Intelligence
- Gamma Exposure Intelligence
- Dealer Hedging Flow Engine
- Liquidity Provider Intelligence

Outputs:
- Market Maker Composite Score
- Market Maker Regime
- Institutional support/resistance map
- Opportunity queue
- Market-maker playbook

This module does not place trades.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_MM_COMMAND_POLICY = {
    "dealer_weight": 0.30,
    "gamma_weight": 0.25,
    "hedging_weight": 0.25,
    "liquidity_weight": 0.20,
    "high_score_threshold": 75,
    "elevated_score_threshold": 60,
    "normal_score_threshold": 40,
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
    if p == "CRITICAL":
        return 0
    if p == "HIGH":
        return 1
    if p == "MEDIUM":
        return 2
    if p == "NORMAL":
        return 3
    if p == "LOW":
        return 4
    return 9


def calculate_dealer_component(dealer_report: dict[str, Any] | None) -> dict[str, Any]:
    if not dealer_report or not dealer_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Dealer positioning report unavailable."]}

    s = dealer_report.get("summary", {})
    positioning = str(s.get("positioning_regime", "UNKNOWN"))
    gamma_regime = str(s.get("gamma_regime", "UNKNOWN"))
    delta_regime = str(s.get("delta_regime", "UNKNOWN"))
    flip_dist = abs(_num(s.get("distance_to_flip_pct"), 99))

    score = 25.0
    drivers = []

    if positioning == "AMPLIFYING":
        score += 35
        drivers.append("Dealer positioning is amplifying.")
    elif positioning == "DAMPENING":
        score += 20
        drivers.append("Dealer positioning is dampening/pinning.")
    elif positioning == "BALANCED":
        score += 10
        drivers.append("Dealer positioning is balanced.")

    if gamma_regime == "SHORT_GAMMA":
        score += 25
        drivers.append("Dealer gamma regime is short gamma.")
    elif gamma_regime == "LONG_GAMMA":
        score += 15
        drivers.append("Dealer gamma regime is long gamma.")

    if delta_regime in {"BUY_PRESSURE", "SELL_PRESSURE"}:
        score += 15
        drivers.append(f"Dealer delta regime indicates {delta_regime}.")

    if flip_dist <= 2:
        score += 15
        drivers.append("Spot is near gamma flip.")

    return {
        "score": round(max(0, min(100, score)), 2),
        "label": positioning,
        "drivers": drivers or ["No major dealer-positioning driver."],
    }


def calculate_gamma_component(gamma_report: dict[str, Any] | None) -> dict[str, Any]:
    if not gamma_report or not gamma_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Gamma exposure report unavailable."]}

    s = gamma_report.get("summary", {})
    regime = str(s.get("gamma_regime", "UNKNOWN"))
    net_gamma = abs(_num(s.get("net_gamma"), 0))

    score = 25.0
    drivers = []

    if regime == "NEGATIVE_GAMMA":
        score += 40
        drivers.append("Negative gamma exposure can amplify moves.")
    elif regime == "POSITIVE_GAMMA":
        score += 20
        drivers.append("Positive gamma exposure can dampen moves.")

    if net_gamma >= 5_000_000:
        score += 25
        drivers.append("Net gamma magnitude is very high.")
    elif net_gamma >= 1_000_000:
        score += 15
        drivers.append("Net gamma magnitude is elevated.")

    return {
        "score": round(max(0, min(100, score)), 2),
        "label": regime,
        "drivers": drivers or ["No major gamma-exposure driver."],
    }


def calculate_hedging_component(hedging_report: dict[str, Any] | None) -> dict[str, Any]:
    if not hedging_report or not hedging_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Dealer hedging-flow report unavailable."]}

    s = hedging_report.get("summary", {})
    regime = str(s.get("hedging_flow_regime", "UNKNOWN"))
    intensity = str(s.get("flow_intensity", "UNKNOWN"))
    acceleration = str(s.get("gamma_acceleration", "UNKNOWN"))
    abs_pressure = abs(_num(s.get("total_absolute_flow_pressure"), 0))

    score = 20.0
    drivers = []

    if regime == "ACTIVE_HEDGING_PRESSURE":
        score += 40
        drivers.append("Dealer hedging flow is active.")
    elif regime == "MODERATE_HEDGING_PRESSURE":
        score += 25
        drivers.append("Dealer hedging flow is moderate.")

    if intensity == "HIGH":
        score += 20
        drivers.append("Hedging-flow intensity is high.")
    elif intensity == "MEDIUM":
        score += 10
        drivers.append("Hedging-flow intensity is medium.")

    if acceleration == "GAMMA_ACCELERATION":
        score += 20
        drivers.append("Gamma acceleration is active.")

    if abs_pressure >= 5_000_000:
        score += 10
        drivers.append("Absolute hedge-flow pressure is very large.")

    return {
        "score": round(max(0, min(100, score)), 2),
        "label": regime,
        "drivers": drivers or ["No major hedging-flow driver."],
    }


def calculate_liquidity_component(liquidity_report: dict[str, Any] | None) -> dict[str, Any]:
    if not liquidity_report or not liquidity_report.get("available"):
        return {"score": 0.0, "label": "UNAVAILABLE", "drivers": ["Liquidity provider report unavailable."]}

    s = liquidity_report.get("summary", {})
    regime = str(s.get("liquidity_regime", "UNKNOWN"))
    avg_score = _num(s.get("avg_liquidity_score"), 0)
    stress_count = _num(s.get("stress_count"), 0)
    illiquid_count = _num(s.get("illiquid_count"), 0)

    score = 20.0
    drivers = []

    if regime == "STRESSED_LIQUIDITY":
        score += 40
        drivers.append("Liquidity providers are stressed.")
    elif regime == "THIN_LIQUIDITY":
        score += 30
        drivers.append("Liquidity is thin.")
    elif regime == "NORMAL_LIQUIDITY":
        score += 15
        drivers.append("Liquidity is normal.")
    elif regime == "DEEP_LIQUIDITY":
        score += 5
        drivers.append("Liquidity is deep.")

    if avg_score < 40:
        score += 20
        drivers.append("Average liquidity score is weak.")

    if stress_count > 0:
        score += min(20, stress_count * 2)
        drivers.append("Stressed contracts are present.")

    if illiquid_count > 0:
        score += min(15, illiquid_count)

    return {
        "score": round(max(0, min(100, score)), 2),
        "label": regime,
        "drivers": drivers or ["No major liquidity driver."],
    }


def calculate_market_maker_score(
    dealer_report: dict[str, Any] | None = None,
    gamma_report: dict[str, Any] | None = None,
    hedging_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_MM_COMMAND_POLICY

    dealer = calculate_dealer_component(dealer_report)
    gamma = calculate_gamma_component(gamma_report)
    hedging = calculate_hedging_component(hedging_report)
    liquidity = calculate_liquidity_component(liquidity_report)

    score = (
        dealer["score"] * policy["dealer_weight"]
        + gamma["score"] * policy["gamma_weight"]
        + hedging["score"] * policy["hedging_weight"]
        + liquidity["score"] * policy["liquidity_weight"]
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
        "dealer_component": dealer,
        "gamma_component": gamma,
        "hedging_component": hedging,
        "liquidity_component": liquidity,
    }


def classify_market_maker_regime(
    dealer_report: dict[str, Any] | None = None,
    gamma_report: dict[str, Any] | None = None,
    hedging_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dealer_positioning = _safe_get(dealer_report, ["summary", "positioning_regime"], "UNKNOWN")
    dealer_gamma = _safe_get(dealer_report, ["summary", "gamma_regime"], "UNKNOWN")
    gamma_regime = _safe_get(gamma_report, ["summary", "gamma_regime"], "UNKNOWN")
    hedging_regime = _safe_get(hedging_report, ["summary", "hedging_flow_regime"], "UNKNOWN")
    liquidity_regime = _safe_get(liquidity_report, ["summary", "liquidity_regime"], "UNKNOWN")

    drivers = []

    if liquidity_regime in {"STRESSED_LIQUIDITY", "THIN_LIQUIDITY"}:
        regime = "LIQUIDITY_STRESS"
        drivers.append("Liquidity provider conditions are stressed or thin.")
    elif hedging_regime == "ACTIVE_HEDGING_PRESSURE":
        regime = "HEDGE_CHASE"
        drivers.append("Dealer hedging flow pressure is active.")
    elif dealer_gamma == "SHORT_GAMMA" or gamma_regime == "NEGATIVE_GAMMA":
        regime = "TREND_AMPLIFICATION"
        drivers.append("Short/negative gamma conditions can amplify moves.")
    elif dealer_gamma == "LONG_GAMMA" or gamma_regime == "POSITIVE_GAMMA":
        regime = "PINNING"
        drivers.append("Long/positive gamma conditions can dampen/pin moves.")
    elif liquidity_regime == "DEEP_LIQUIDITY":
        regime = "LIQUIDITY_ABUNDANT"
        drivers.append("Liquidity provider conditions are deep.")
    else:
        regime = "BALANCED_MARKET_MAKER"

    return {
        "available": True,
        "market_maker_regime": regime,
        "dealer_positioning": dealer_positioning,
        "dealer_gamma": dealer_gamma,
        "gamma_regime": gamma_regime,
        "hedging_regime": hedging_regime,
        "liquidity_regime": liquidity_regime,
        "drivers": drivers or ["Market-maker regime is balanced."],
    }


def build_support_resistance_map(
    dealer_report: dict[str, Any] | None = None,
    gamma_report: dict[str, Any] | None = None,
    hedging_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []

    dealer_summary = (dealer_report or {}).get("summary", {})
    for name, signal in [("top_call_wall", "Call Wall"), ("top_put_wall", "Put Wall"), ("gamma_flip", "Dealer Gamma Flip")]:
        strike = _num(dealer_summary.get(name), 0)
        if strike:
            rows.append({"Strike": strike, "Signal": signal, "Source": "Dealer Positioning", "Strength": "High" if signal != "Dealer Gamma Flip" else "Medium"})

    gamma_summary = (gamma_report or {}).get("summary", {})
    gamma_flip = _num(gamma_summary.get("gamma_flip"), 0)
    if gamma_flip:
        rows.append({"Strike": gamma_flip, "Signal": "Gamma Exposure Flip", "Source": "Gamma Exposure", "Strength": "High"})

    hedge_pressure = _df(_safe_get(hedging_report, ["zones", "pressure_zones"], pd.DataFrame()))
    if not hedge_pressure.empty and "strike" in hedge_pressure.columns:
        for _, row in hedge_pressure.head(10).iterrows():
            rows.append({
                "Strike": row.get("strike", 0),
                "Signal": "Hedge Pressure Zone",
                "Source": "Dealer Hedging Flow",
                "Strength": "High" if _num(row.get("pressure_rank"), 99) <= 3 else "Medium",
            })

    liquidity_chain = _df(_safe_get(liquidity_report, ["lp_map", "by_strike"], pd.DataFrame()))
    if not liquidity_chain.empty and "strike" in liquidity_chain.columns:
        strong = liquidity_chain.sort_values(["avg_liquidity_score", "total_open_interest"], ascending=False).head(10)
        for _, row in strong.iterrows():
            rows.append({
                "Strike": row.get("strike", 0),
                "Signal": "Liquidity Cluster",
                "Source": "Liquidity Providers",
                "Strength": "High" if _num(row.get("avg_liquidity_score"), 0) >= 75 else "Medium",
            })

    table = pd.DataFrame(rows)
    if not table.empty:
        table["Strike"] = pd.to_numeric(table["Strike"], errors="coerce").fillna(0)
        table = table[table["Strike"] > 0].drop_duplicates(["Strike", "Signal", "Source"]).sort_values("Strike").reset_index(drop=True)

    return {
        "available": True,
        "support_resistance_map": table,
        "level_count": int(len(table)),
    }


def merge_market_maker_opportunities(
    dealer_report: dict[str, Any] | None = None,
    gamma_report: dict[str, Any] | None = None,
    hedging_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []

    for source, report, key in [
        ("Dealer Positioning", dealer_report, "recommendations"),
        ("Dealer Hedging Flow", hedging_report, "recommendations"),
        ("Liquidity Providers", liquidity_report, "recommendations"),
    ]:
        df = _df((report or {}).get(key))
        if not df.empty:
            for _, row in df.iterrows():
                rows.append({
                    "Source": source,
                    "Priority": row.get("Priority", "Normal"),
                    "Recommendation": row.get("Recommendation", ""),
                    "Rationale": row.get("Rationale", ""),
                    "Structures": row.get("Structures", row.get("Execution Playbook", "")),
                })

    gamma_summary = (gamma_report or {}).get("summary", {})
    if gamma_report and gamma_report.get("available"):
        rows.append({
            "Source": "Gamma Exposure",
            "Priority": "High" if gamma_summary.get("gamma_regime") == "NEGATIVE_GAMMA" else "Normal",
            "Recommendation": f"Gamma Regime Review: {gamma_summary.get('gamma_regime')}",
            "Rationale": f"Net gamma {gamma_summary.get('net_gamma')}, gamma flip {gamma_summary.get('gamma_flip')}.",
            "Structures": "Use gamma regime to select trend/range structures.",
        })

    queue = pd.DataFrame(rows)
    if not queue.empty:
        queue["_sort"] = queue["Priority"].apply(_priority_score)
        queue = queue.sort_values(["_sort", "Source"]).drop(columns=["_sort"]).reset_index(drop=True)

    return {
        "available": True,
        "opportunity_queue": queue,
        "opportunity_count": int(len(queue)),
        "high_priority_count": int((queue["Priority"].astype(str).str.upper() == "HIGH").sum()) if not queue.empty else 0,
    }


def generate_market_maker_playbook(
    score: dict[str, Any],
    regime: dict[str, Any],
    opportunities: dict[str, Any],
) -> dict[str, Any]:
    mm_regime = regime.get("market_maker_regime", "BALANCED_MARKET_MAKER")
    rating = score.get("rating", "NORMAL")
    rows = []

    if mm_regime == "TREND_AMPLIFICATION":
        rows.append({
            "Playbook": "Momentum / Trend Amplification",
            "Priority": "High",
            "Bias": "Directional",
            "Structures": "Debit spreads, defined-risk momentum structures, avoid naked short gamma",
            "Risk Note": "Moves may extend if dealers chase hedges.",
        })
    elif mm_regime == "PINNING":
        rows.append({
            "Playbook": "Pinning / Mean Reversion",
            "Priority": "Medium",
            "Bias": "Range / mean reversion",
            "Structures": "Iron condors, calendars, credit spreads near walls",
            "Risk Note": "Watch gamma flip and wall breaks.",
        })
    elif mm_regime == "HEDGE_CHASE":
        rows.append({
            "Playbook": "Hedge-Chase Response",
            "Priority": "High",
            "Bias": "Volatility expansion",
            "Structures": "Defined-risk directional spreads, long gamma review",
            "Risk Note": "Dealer flows may intensify quickly.",
        })
    elif mm_regime == "LIQUIDITY_STRESS":
        rows.append({
            "Playbook": "Liquidity Stress Defense",
            "Priority": "High",
            "Bias": "Execution caution",
            "Structures": "Reduce size, use patient limit orders, avoid illiquid strikes",
            "Risk Note": "Execution quality may dominate strategy quality.",
        })
    elif mm_regime == "LIQUIDITY_ABUNDANT":
        rows.append({
            "Playbook": "Liquidity Harvesting",
            "Priority": "Normal",
            "Bias": "Execution-friendly",
            "Structures": "Defined-risk spreads, liquidity-supported premium trades",
            "Risk Note": "Liquidity is supportive but still use limits.",
        })
    else:
        rows.append({
            "Playbook": "Balanced Market-Maker Conditions",
            "Priority": "Normal",
            "Bias": "Balanced",
            "Structures": "Defined-risk spreads and balanced premium structures",
            "Risk Note": "Wait for clearer dealer/flow confirmation.",
        })

    if rating in {"HIGH", "EXTREME"}:
        rows.append({
            "Playbook": "Elevated MM Risk Overlay",
            "Priority": "High",
            "Bias": "Risk control",
            "Structures": "Reduce gross short gamma and avoid crowded illiquid strikes",
            "Risk Note": "Composite MM score is elevated.",
        })

    queue = _df(opportunities.get("opportunity_queue"))
    if not queue.empty:
        high = queue[queue["Priority"].astype(str).str.upper() == "HIGH"]
        if not high.empty:
            rows.append({
                "Playbook": "Work High-Priority MM Queue",
                "Priority": "High",
                "Bias": "Opportunity-driven",
                "Structures": "; ".join(high["Structures"].dropna().astype(str).head(3)),
                "Risk Note": f"{len(high)} high-priority market-maker opportunity rows detected.",
            })

    return {
        "available": True,
        "playbook": pd.DataFrame(rows),
        "top_recommendation": rows[0]["Playbook"] if rows else "No recommendation",
    }


def build_market_maker_command_center_report(
    dealer_report: dict[str, Any] | None = None,
    gamma_report: dict[str, Any] | None = None,
    hedging_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_MM_COMMAND_POLICY

    score = calculate_market_maker_score(
        dealer_report=dealer_report,
        gamma_report=gamma_report,
        hedging_report=hedging_report,
        liquidity_report=liquidity_report,
        policy=policy,
    )

    regime = classify_market_maker_regime(
        dealer_report=dealer_report,
        gamma_report=gamma_report,
        hedging_report=hedging_report,
        liquidity_report=liquidity_report,
    )

    sr_map = build_support_resistance_map(
        dealer_report=dealer_report,
        gamma_report=gamma_report,
        hedging_report=hedging_report,
        liquidity_report=liquidity_report,
    )

    opportunities = merge_market_maker_opportunities(
        dealer_report=dealer_report,
        gamma_report=gamma_report,
        hedging_report=hedging_report,
        liquidity_report=liquidity_report,
    )

    playbook = generate_market_maker_playbook(score, regime, opportunities)

    return {
        "available": True,
        "score": score,
        "regime": regime,
        "support_resistance": sr_map,
        "opportunities": opportunities,
        "playbook": playbook,
        "dealer_report": dealer_report,
        "gamma_report": gamma_report,
        "hedging_report": hedging_report,
        "liquidity_report": liquidity_report,
        "policy": policy,
    }


def summarize_market_maker_command_center(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Market Maker Command Center unavailable: {report.get('reason', 'unknown reason')}"

    score = report.get("score", {})
    regime = report.get("regime", {})
    opps = report.get("opportunities", {})
    playbook = report.get("playbook", {})

    return (
        f"Market Maker Score is {score.get('score')}/100 with rating {score.get('rating')}. "
        f"Regime is {regime.get('market_maker_regime')}. "
        f"{opps.get('opportunity_count', 0)} opportunity rows are queued, "
        f"including {opps.get('high_priority_count', 0)} high-priority items. "
        f"Top playbook: {playbook.get('top_recommendation', 'None')}."
    )
