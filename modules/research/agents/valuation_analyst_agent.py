from __future__ import annotations
from typing import Any
from .research_agent_registry import AgentFinding, clamp, rating_from_score, confidence_from_evidence


def run(ticker: str, context: dict[str, Any] | None = None) -> AgentFinding:
    context = context or {}
    valuation = context.get("valuation", {})
    pe = valuation.get("pe", 24)
    ev_sales = valuation.get("ev_sales", 4)
    fcf_yield = valuation.get("fcf_yield", 3.5)
    target_upside = valuation.get("target_upside", 8)
    pe_score = 70 if pe and pe < 18 else 55 if pe and pe < 30 else 42
    sales_score = 68 if ev_sales and ev_sales < 3 else 55 if ev_sales and ev_sales < 8 else 40
    fcf_score = clamp(45 + float(fcf_yield or 0) * 6, 20, 90, 55)
    upside_score = clamp(50 + float(target_upside or 0) * 1.5, 10, 95, 55)
    score = clamp(pe_score*0.25 + sales_score*0.20 + fcf_score*0.25 + upside_score*0.30)
    positives = ["Valuation setup has positive expected-return potential." if score >= 60 else "Valuation is not clearly compelling yet."]
    risks = [] if score >= 60 else ["Multiple compression risk remains if growth or rates disappoint."]
    return AgentFinding("Valuation Analyst", rating_from_score(score), round(score,1), confidence_from_evidence(valuation), f"{ticker.upper()} valuation score is {score:.1f}/100.", positives, risks, {"pe": pe, "ev_sales": ev_sales, "fcf_yield": fcf_yield, "target_upside": target_upside})
