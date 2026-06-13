from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    flow = context.get("smart_money", {})
    sentiment = flow.get("sentiment", {}) if isinstance(flow, dict) else {}
    conviction = flow.get("conviction_score", {}) if isinstance(flow, dict) else {}
    score = clamp(sentiment.get("score", conviction.get("score", 50)), 0, 100, 50)
    positives = []
    risks = []
    if score >= 65: positives.append("Institutional/options flow is aligned with accumulation.")
    elif score <= 40: risks.append("Institutional/options flow is defensive or distributional.")
    else: risks.append("Institutional flow is mixed and needs confirmation.")
    return AgentFinding("Institutional Flow Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(flow), f"Institutional flow score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"sentiment": sentiment, "conviction": conviction})
