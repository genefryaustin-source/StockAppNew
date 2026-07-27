from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_valuation_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    forward_pe = safe_num(c.get("forward_pe"), 22.0)
    ev_sales = safe_num(c.get("ev_sales"), 4.0)
    fcf_yield = safe_num(c.get("fcf_yield"), 4.0)
    upside_to_target = safe_num(c.get("upside_to_target"), 8.0)

    score = 55
    score += (25 - forward_pe) * 0.8
    score += (6 - ev_sales) * 2.0
    score += (fcf_yield - 3) * 4.0
    score += upside_to_target * 0.9
    score = clamp(score)

    positives, risks = [], []
    if forward_pe < 18: positives.append("Forward multiple appears reasonable")
    elif forward_pe > 35: risks.append("Forward multiple implies elevated expectations")
    if fcf_yield >= 5: positives.append("FCF yield provides valuation support")
    else: risks.append("FCF yield does not provide strong downside support")
    if upside_to_target > 15: positives.append("Consensus target implies meaningful upside")
    elif upside_to_target < 0: risks.append("Consensus target implies downside risk")

    return AgentSignal(
        agent="Valuation Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=68 if c else 42,
        thesis=f"{ticker.upper()} valuation screens as {score_to_rating(score)} given multiple, FCF yield, and target-upside assumptions.",
        positives=positives or ["Valuation is acceptable for committee review"],
        risks=risks or ["Valuation risk appears manageable from supplied context"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
