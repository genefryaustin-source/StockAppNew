from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    r = context.get("risk", {})
    beta = float(r.get("beta", 1.1) or 1.1)
    drawdown = clamp(r.get("drawdown_risk", 45), 0, 100, 45)
    concentration = clamp(r.get("concentration_risk", 40), 0, 100, 40)
    event_risk = clamp(r.get("event_risk", 45), 0, 100, 45)
    risk_score = clamp(drawdown*0.35 + concentration*0.25 + event_risk*0.25 + max(0, beta-1)*15, 0, 100, 45)
    score = 100 - risk_score
    positives = ["Risk profile is manageable." if score >= 60 else "Risk needs active sizing and hedging."]
    risks = [] if score >= 60 else ["Position sizing should be reduced or hedged due to elevated risk score."]
    return AgentFinding("Risk Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(r), f"Risk-adjusted score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"beta": beta, "drawdown_risk": drawdown, "concentration_risk": concentration, "event_risk": event_risk})
