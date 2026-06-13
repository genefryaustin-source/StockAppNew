from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    e = context.get("earnings", {})
    beat_rate = clamp(e.get("beat_rate", 58), 0, 100, 58)
    revision = clamp(e.get("estimate_revision_score", 52), 0, 100, 52)
    guidance = clamp(e.get("guidance_score", 50), 0, 100, 50)
    post_drift = clamp(e.get("post_earnings_drift", 50), 0, 100, 50)
    score = clamp(beat_rate*0.25 + revision*0.35 + guidance*0.25 + post_drift*0.15)
    positives = []
    risks = []
    if revision > 60: positives.append("Estimate revisions are constructive.")
    else: risks.append("Estimate revision momentum is not yet clearly positive.")
    if beat_rate > 60: positives.append("Historical beat profile supports earnings quality.")
    else: risks.append("Beat/miss profile requires caution around reporting dates.")
    return AgentFinding("Earnings Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(e), f"{ticker.upper()} earnings setup score is {score:.1f}/100.", positives, risks, {"beat_rate": beat_rate, "revision": revision, "guidance": guidance, "post_drift": post_drift})
