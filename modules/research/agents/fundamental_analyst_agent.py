from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    fundamentals = context.get("fundamentals", {})
    revenue_growth = clamp(fundamentals.get("revenue_growth", 8), -30, 50, 8)
    eps_growth = clamp(fundamentals.get("eps_growth", 7), -50, 60, 7)
    margin = clamp(fundamentals.get("operating_margin", 18), -20, 60, 18)
    roic = clamp(fundamentals.get("roic", 12), -20, 60, 12)
    fcf = clamp(fundamentals.get("fcf_margin", 10), -30, 50, 10)
    score = clamp(50 + revenue_growth * 0.45 + eps_growth * 0.35 + (margin - 15) * 0.55 + (roic - 10) * 0.6 + (fcf - 8) * 0.45)
    positives, risks = [], []
    if revenue_growth > 10: positives.append("Revenue growth supports expanding business momentum.")
    else: risks.append("Revenue growth is modest or unconfirmed.")
    if margin > 20: positives.append("Margins appear healthy relative to a baseline institutional hurdle.")
    else: risks.append("Margin profile needs confirmation before assigning premium quality.")
    if roic > 15: positives.append("ROIC suggests attractive reinvestment economics.")
    else: risks.append("ROIC is not yet strong enough to independently support a quality premium.")
    return AgentFinding("Fundamental Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(fundamentals), f"{ticker.upper()} fundamental quality score is {score:.1f}/100.", positives, risks, {"revenue_growth": revenue_growth, "eps_growth": eps_growth, "operating_margin": margin, "roic": roic, "fcf_margin": fcf})
