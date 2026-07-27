"""
modules/hf/multi_agent_equity_orchestrator.py

Stock HF-2 multi-agent equity research orchestrator.
Runs specialized analyst agents and forms a committee-level consensus.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from modules.hf.agents.fundamental_analyst_agent import run_fundamental_analyst
from modules.hf.agents.valuation_analyst_agent import run_valuation_analyst
from modules.hf.agents.earnings_analyst_agent import run_earnings_analyst
from modules.hf.agents.macro_analyst_agent import run_macro_analyst
from modules.hf.agents.sector_analyst_agent import run_sector_analyst
from modules.hf.agents.institutional_flow_agent import run_institutional_flow_agent
from modules.hf.agents.risk_analyst_agent import run_risk_analyst
from modules.hf.agents.catalyst_analyst_agent import run_catalyst_analyst


AGENT_REGISTRY = [
    ("Fundamental Analyst", run_fundamental_analyst, 1.20),
    ("Valuation Analyst", run_valuation_analyst, 1.10),
    ("Earnings Analyst", run_earnings_analyst, 1.05),
    ("Macro Analyst", run_macro_analyst, 0.85),
    ("Sector Analyst", run_sector_analyst, 0.90),
    ("Institutional Flow Analyst", run_institutional_flow_agent, 1.00),
    ("Risk Analyst", run_risk_analyst, 1.15),
    ("Catalyst Analyst", run_catalyst_analyst, 0.95),
]


def run_multi_agent_research(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    signals: list[dict[str, Any]] = []
    for _, fn, weight in AGENT_REGISTRY:
        try:
            sig = fn(ticker, context)
            sig["weight"] = weight
            signals.append(sig)
        except Exception as exc:
            signals.append({
                "agent": getattr(fn, "__name__", "Unknown"),
                "ticker": ticker.upper(),
                "rating": "Hold",
                "score": 50.0,
                "confidence": 20.0,
                "thesis": f"Agent failed safely: {exc}",
                "positives": [],
                "risks": [str(exc)],
                "data_quality": "error",
                "weight": weight,
            })

    consensus = build_agent_consensus(signals)
    return {
        "ticker": ticker.upper(),
        "signals": signals,
        "consensus": consensus,
        "agent_count": len(signals),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_agent_consensus(signals: list[dict[str, Any]]) -> dict[str, Any]:
    if not signals:
        return {
            "rating": "Hold",
            "score": 50.0,
            "confidence": 0.0,
            "agreement": 0.0,
            "disagreement": 100.0,
            "conviction": "Low",
        }

    weighted_score = 0.0
    weight_sum = 0.0
    confidence_sum = 0.0
    ratings = []
    for s in signals:
        weight = float(s.get("weight", 1.0) or 1.0)
        score = float(s.get("score", 50.0) or 50.0)
        conf = float(s.get("confidence", 50.0) or 50.0)
        weighted_score += score * weight * (conf / 100.0)
        weight_sum += weight * (conf / 100.0)
        confidence_sum += conf
        ratings.append(str(s.get("rating", "Hold")))

    score = round(weighted_score / max(weight_sum, 0.0001), 1)
    rating = _score_to_rating(score)
    confidence = round(confidence_sum / len(signals), 1)
    most_common = Counter(ratings).most_common(1)[0][1]
    agreement = round((most_common / len(ratings)) * 100.0, 1)
    disagreement = round(100.0 - agreement, 1)

    if score >= 75 and confidence >= 65 and agreement >= 45:
        conviction = "High"
    elif score >= 60 and confidence >= 50:
        conviction = "Medium"
    elif score <= 35 and confidence >= 55:
        conviction = "High Negative"
    else:
        conviction = "Low"

    positives: list[str] = []
    risks: list[str] = []
    for s in signals:
        positives.extend(list(s.get("positives") or [])[:2])
        risks.extend(list(s.get("risks") or [])[:2])

    return {
        "rating": rating,
        "score": score,
        "confidence": confidence,
        "agreement": agreement,
        "disagreement": disagreement,
        "conviction": conviction,
        "top_positives": positives[:8],
        "top_risks": risks[:8],
        "rating_distribution": dict(Counter(ratings)),
    }


def _score_to_rating(score: float) -> str:
    if score >= 85:
        return "Strong Buy"
    if score >= 68:
        return "Buy"
    if score >= 52:
        return "Hold"
    if score >= 38:
        return "Reduce"
    if score >= 20:
        return "Sell"
    return "Strong Sell"
