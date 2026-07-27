from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_risk_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    beta = safe_num(c.get("beta"), 1.1)
    drawdown_risk = safe_num(c.get("drawdown_risk"), 45.0)
    balance_sheet_risk = safe_num(c.get("balance_sheet_risk"), 40.0)
    earnings_risk = safe_num(c.get("earnings_risk"), 45.0)

    risk_penalty = max(0, beta - 1.0) * 12 + drawdown_risk * 0.25 + balance_sheet_risk * 0.20 + earnings_risk * 0.20
    score = clamp(85 - risk_penalty)

    positives, risks = [], []
    if beta < 1.0: positives.append("Beta profile is not aggressive")
    elif beta > 1.5: risks.append("High beta may amplify market drawdowns")
    if drawdown_risk > 60: risks.append("Drawdown risk is elevated")
    else: positives.append("Drawdown risk appears manageable")
    if balance_sheet_risk > 60: risks.append("Balance sheet risk requires committee review")
    if earnings_risk > 60: risks.append("Earnings event risk may require sizing discipline")

    return AgentSignal(
        agent="Risk Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=65 if c else 42,
        thesis=f"{ticker.upper()} risk profile screens as {score_to_rating(score)} after adjusting for beta, drawdown, balance-sheet, and earnings risks.",
        positives=positives or ["Risk profile is acceptable for review"],
        risks=risks or ["Risk profile does not show major red flags"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
