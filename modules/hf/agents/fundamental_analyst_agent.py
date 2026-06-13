from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_fundamental_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    revenue_growth = safe_num(c.get("revenue_growth"), 8.0)
    eps_growth = safe_num(c.get("eps_growth"), 7.0)
    gross_margin = safe_num(c.get("gross_margin"), 45.0)
    operating_margin = safe_num(c.get("operating_margin"), 15.0)
    fcf_margin = safe_num(c.get("fcf_margin"), 10.0)
    roic = safe_num(c.get("roic"), 12.0)

    score = 50
    score += clamp(revenue_growth, -20, 30) * 0.45
    score += clamp(eps_growth, -20, 35) * 0.35
    score += (gross_margin - 35) * 0.20
    score += (operating_margin - 10) * 0.35
    score += (fcf_margin - 5) * 0.50
    score += (roic - 8) * 0.60
    score = clamp(score)

    positives = []
    risks = []
    if revenue_growth > 10: positives.append("Above-average revenue growth")
    else: risks.append("Revenue growth is not yet compelling")
    if operating_margin > 18: positives.append("Healthy operating margin profile")
    else: risks.append("Operating leverage still needs confirmation")
    if roic > 15: positives.append("Strong return on invested capital")
    else: risks.append("ROIC does not yet screen as elite")
    if fcf_margin > 12: positives.append("Free-cash-flow conversion supports quality thesis")

    return AgentSignal(
        agent="Fundamental Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=70 if c else 45,
        thesis=f"{ticker.upper()} fundamental quality screens as {score_to_rating(score)} based on growth, margin, cash-flow, and ROIC inputs.",
        positives=positives or ["Fundamental profile is stable enough for committee review"],
        risks=risks or ["Limited visible fundamental risks from supplied context"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
