from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_macro_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    rate_sensitivity = safe_num(c.get("rate_sensitivity"), 50.0)
    cycle_score = safe_num(c.get("economic_cycle_score"), 55.0)
    liquidity_score = safe_num(c.get("liquidity_score"), 55.0)
    dollar_sensitivity = safe_num(c.get("dollar_sensitivity"), 40.0)

    score = 50 + (cycle_score - 50) * 0.35 + (liquidity_score - 50) * 0.30 - max(0, rate_sensitivity - 60) * 0.20 - max(0, dollar_sensitivity - 65) * 0.12
    score = clamp(score)

    positives, risks = [], []
    if cycle_score > 60: positives.append("Macro cycle backdrop supports risk assets")
    elif cycle_score < 45: risks.append("Macro cycle backdrop is unfavorable")
    if liquidity_score > 60: positives.append("Liquidity conditions support multiple expansion")
    elif liquidity_score < 45: risks.append("Liquidity conditions may pressure valuation")
    if rate_sensitivity > 70: risks.append("High rate sensitivity may create drawdown risk")

    return AgentSignal(
        agent="Macro Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=60 if c else 38,
        thesis=f"{ticker.upper()} macro setup screens as {score_to_rating(score)} based on cycle, liquidity, and rate-sensitivity inputs.",
        positives=positives or ["Macro setup is not disqualifying"],
        risks=risks or ["Macro risk is not dominant from supplied context"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
