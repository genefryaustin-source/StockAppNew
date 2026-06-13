from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_catalyst_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    catalyst_score = safe_num(c.get("catalyst_score"), 55.0)
    event_score = safe_num(c.get("event_score"), 50.0)
    news_momentum = safe_num(c.get("news_momentum"), 50.0)
    product_cycle_score = safe_num(c.get("product_cycle_score"), 50.0)

    score = 50 + (catalyst_score - 50) * 0.35 + (event_score - 50) * 0.25 + (news_momentum - 50) * 0.25 + (product_cycle_score - 50) * 0.20
    score = clamp(score)

    positives, risks = [], []
    if catalyst_score > 65: positives.append("Near-term catalyst stack is favorable")
    elif catalyst_score < 40: risks.append("Catalyst support is weak")
    if news_momentum > 60: positives.append("News momentum supports investor attention")
    if event_score < 40: risks.append("Event setup is not currently favorable")

    return AgentSignal(
        agent="Catalyst Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=62 if c else 39,
        thesis=f"{ticker.upper()} catalyst setup screens as {score_to_rating(score)} based on event, news, and product-cycle inputs.",
        positives=positives or ["Catalyst setup is neutral"],
        risks=risks or ["No immediate negative catalyst identified"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
