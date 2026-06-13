from __future__ import annotations
from typing import Any


def generate_investment_thesis(ticker: str, components: dict[str, Any], scorecard: dict[str, Any]) -> dict[str, Any]:
    label = scorecard.get("research_label", "Neutral")
    score = scorecard.get("composite_research_score", 50)
    bull = [
        f"Composite research score is {score}/100 ({label}).",
        components.get("fundamental", {}).get("summary", "Fundamental profile is mixed."),
        f"Institutional ownership read: {components.get('ownership', {}).get('ownership_read', 'Neutral')}.",
    ]
    bear = [
        "Catalyst timing and macro regime can overwhelm company-specific factors.",
        f"Analyst dispersion: {components.get('analyst', {}).get('analyst_dispersion', 50)}.",
        f"Market regime: {components.get('regime', {}).get('regime', 'Neutral')}.",
    ]
    return {"ticker": ticker.upper(), "bull_thesis": bull, "bear_thesis": bear,
            "risk_thesis": ["Position sizing should reflect earnings and volatility risk.", "Confirm price trend and liquidity before entry."],
            "valuation_thesis": "Valuation support is constructive" if score >= 60 else "Valuation requires confirmation",
            "catalyst_thesis": f"Top catalyst: {components.get('catalysts', {}).get('top_catalyst', {}).get('Catalyst', 'Earnings')}",
            "institutional_thesis": f"Institutional activity is {components.get('ownership', {}).get('ownership_read', 'Neutral')}.",
            "options_expression": "Use defined-risk bullish spreads" if score >= 62 else "Use hedged income or wait for confirmation" if score >= 42 else "Avoid directional premium buying until thesis improves"}
