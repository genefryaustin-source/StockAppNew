from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_institutional_flow_agent(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    ownership_delta = safe_num(c.get("institutional_ownership_delta"), 0.0)
    smart_money_score = safe_num(c.get("smart_money_score"), 55.0)
    accumulation_score = safe_num(c.get("accumulation_score"), 50.0)
    insider_score = safe_num(c.get("insider_score"), 50.0)

    score = 50 + ownership_delta * 1.4 + (smart_money_score - 50) * 0.35 + (accumulation_score - 50) * 0.35 + (insider_score - 50) * 0.15
    score = clamp(score)

    positives, risks = [], []
    if ownership_delta > 3: positives.append("Institutional ownership appears to be increasing")
    elif ownership_delta < -3: risks.append("Institutional ownership appears to be decreasing")
    if smart_money_score > 65: positives.append("Smart-money signal supports accumulation")
    if accumulation_score < 40: risks.append("Accumulation signal is weak")

    return AgentSignal(
        agent="Institutional Flow Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=64 if c else 39,
        thesis=f"{ticker.upper()} institutional flow screens as {score_to_rating(score)} from ownership, accumulation, and smart-money inputs.",
        positives=positives or ["Institutional flow is neutral-to-supportive"],
        risks=risks or ["No major institutional distribution risk identified"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
