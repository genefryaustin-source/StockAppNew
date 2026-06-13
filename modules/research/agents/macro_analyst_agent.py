from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    m = context.get("macro", {})
    rates = clamp(m.get("rates_pressure", 45), 0, 100, 45)
    liquidity = clamp(m.get("liquidity_score", 55), 0, 100, 55)
    risk_appetite = clamp(m.get("risk_appetite", 55), 0, 100, 55)
    inflation = clamp(m.get("inflation_pressure", 45), 0, 100, 45)
    score = clamp(liquidity*0.35 + risk_appetite*0.35 + (100-rates)*0.15 + (100-inflation)*0.15)
    positives = ["Macro backdrop is supportive for risk assets." if score >= 60 else "Macro backdrop is mixed."]
    risks = [] if score >= 60 else ["Rates, inflation, or liquidity may pressure multiples."]
    return AgentFinding("Macro Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(m), f"Macro alignment score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"rates_pressure": rates, "liquidity_score": liquidity, "risk_appetite": risk_appetite, "inflation_pressure": inflation})
