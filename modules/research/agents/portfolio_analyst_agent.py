from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    p = context.get("portfolio", {})
    allocation_fit = clamp(p.get("allocation_fit", 60), 0, 100, 60)
    diversification = clamp(p.get("diversification_benefit", 55), 0, 100, 55)
    risk_budget = clamp(p.get("risk_budget_fit", 58), 0, 100, 58)
    score = clamp(allocation_fit*0.35 + diversification*0.25 + risk_budget*0.40)
    positives = ["Portfolio fit is acceptable." if score >= 60 else "Portfolio fit needs tighter risk budgeting."]
    risks = [] if score >= 60 else ["Could increase concentration or exceed desired risk budget."]
    return AgentFinding("Portfolio Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(p), f"Portfolio fit score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"allocation_fit": allocation_fit, "diversification": diversification, "risk_budget": risk_budget})
