from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    c = context.get("catalysts", {})
    earnings = clamp(c.get("earnings_catalyst", 55), 0, 100, 55)
    product = clamp(c.get("product_catalyst", 45), 0, 100, 45)
    corporate = clamp(c.get("corporate_action_catalyst", 40), 0, 100, 40)
    news = clamp(c.get("news_momentum", 50), 0, 100, 50)
    score = clamp(earnings*0.35 + product*0.20 + corporate*0.20 + news*0.25)
    positives = ["Catalyst calendar can support thesis acceleration." if score >= 60 else "Catalyst picture is limited or uncertain."]
    risks = [] if score >= 60 else ["Without a clear catalyst, thesis realization may take longer."]
    return AgentFinding("Catalyst Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(c), f"Catalyst score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"earnings": earnings, "product": product, "corporate": corporate, "news": news})
