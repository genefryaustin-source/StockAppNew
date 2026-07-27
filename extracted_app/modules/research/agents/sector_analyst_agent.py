from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    s = context.get("sector", {})
    rel_strength = clamp(s.get("relative_strength", 55), 0, 100, 55)
    rotation = clamp(s.get("rotation_score", 52), 0, 100, 52)
    breadth = clamp(s.get("sector_breadth", 50), 0, 100, 50)
    score = clamp(rel_strength*0.45 + rotation*0.35 + breadth*0.20)
    positives = ["Sector participation is constructive." if score >= 60 else "Sector leadership is not yet decisive."]
    risks = [] if score >= 60 else ["Weak sector rotation could reduce follow-through."]
    return AgentFinding("Sector Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(s), f"Sector alignment score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"relative_strength": rel_strength, "rotation_score": rotation, "sector_breadth": breadth})
