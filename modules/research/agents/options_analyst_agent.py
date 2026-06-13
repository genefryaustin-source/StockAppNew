from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    dealer = context.get("dealer", {})
    vol = context.get("volatility", {})
    smart = context.get("smart_money", {})
    dealer_score = clamp(dealer.get("dealer_score", dealer.get("score", 50)), 0, 100, 50) if isinstance(dealer, dict) else 50
    vol_score = clamp(vol.get("volatility_score", vol.get("score", 50)), 0, 100, 50) if isinstance(vol, dict) else 50
    smart_score = clamp((smart.get("sentiment") or {}).get("score", 50), 0, 100, 50) if isinstance(smart, dict) else 50
    score = clamp(dealer_score*0.35 + vol_score*0.25 + smart_score*0.40)
    positives = ["Options market structure supports a defined-risk expression." if score >= 60 else "Options setup is not yet high-conviction."]
    risks = [] if score >= 60 else ["Dealer/volatility/smart-money alignment is incomplete."]
    return AgentFinding("Options Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(dealer, vol, smart), f"Options expression score for {ticker.upper()} is {score:.1f}/100.", positives, risks, {"dealer_score": dealer_score, "vol_score": vol_score, "smart_score": smart_score})
