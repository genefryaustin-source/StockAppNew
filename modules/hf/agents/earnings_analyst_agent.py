from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_earnings_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    eps_revision = safe_num(c.get("eps_revision_score"), 0.0)
    beat_rate = safe_num(c.get("earnings_beat_rate"), 55.0)
    guidance_score = safe_num(c.get("guidance_score"), 50.0)
    post_earnings_drift = safe_num(c.get("post_earnings_drift"), 0.0)

    score = 50 + eps_revision * 0.35 + (beat_rate - 50) * 0.35 + (guidance_score - 50) * 0.25 + post_earnings_drift * 1.2
    score = clamp(score)

    positives, risks = [], []
    if eps_revision > 10: positives.append("Positive EPS revision momentum")
    elif eps_revision < -10: risks.append("Negative EPS revision pressure")
    if beat_rate > 60: positives.append("History of earnings beats")
    else: risks.append("Beat history is not strong enough to carry thesis")
    if guidance_score > 60: positives.append("Guidance trend supports forward estimates")
    elif guidance_score < 45: risks.append("Guidance trend is a concern")

    return AgentSignal(
        agent="Earnings Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=66 if c else 40,
        thesis=f"{ticker.upper()} earnings quality screens as {score_to_rating(score)} from revisions, beat history, guidance, and drift signals.",
        positives=positives or ["Earnings setup is neutral-to-reviewable"],
        risks=risks or ["No major earnings risk surfaced from supplied context"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
