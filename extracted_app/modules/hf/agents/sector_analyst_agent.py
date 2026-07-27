from __future__ import annotations
from typing import Any
from modules.hf.agents.base_agent import AgentSignal, clamp, score_to_rating, safe_num, normalize_context


def run_sector_analyst(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    c = normalize_context(context)
    sector_momentum = safe_num(c.get("sector_momentum"), 55.0)
    relative_strength = safe_num(c.get("relative_strength"), 55.0)
    rotation_score = safe_num(c.get("rotation_score"), 50.0)

    score = 50 + (sector_momentum - 50) * 0.35 + (relative_strength - 50) * 0.35 + (rotation_score - 50) * 0.25
    score = clamp(score)

    positives, risks = [], []
    if sector_momentum > 60: positives.append("Sector momentum is favorable")
    elif sector_momentum < 45: risks.append("Sector momentum is unfavorable")
    if relative_strength > 60: positives.append("Ticker shows favorable relative strength")
    elif relative_strength < 45: risks.append("Relative strength is weak")
    if rotation_score > 60: positives.append("Rotation backdrop supports the sector")

    return AgentSignal(
        agent="Sector Analyst",
        ticker=ticker.upper(),
        rating=score_to_rating(score),
        score=round(score, 1),
        confidence=62 if c else 40,
        thesis=f"{ticker.upper()} sector setup screens as {score_to_rating(score)} based on momentum, rotation, and relative-strength inputs.",
        positives=positives or ["Sector setup is neutral"],
        risks=risks or ["No major sector risk identified from supplied context"],
        data_quality="contextual" if c else "fallback",
    ).to_dict()
