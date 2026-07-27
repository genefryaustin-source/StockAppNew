from __future__ import annotations
from typing import Any
def build_research_memo(ticker: str, vote: dict[str,Any], consensus: dict[str,Any], council: dict[str,Any], thesis: dict[str,Any], recommendation: dict[str,Any]) -> str:
    bull='\n'.join(f'- {x}' for x in thesis.get('bull_thesis',[])); bear='\n'.join(f'- {x}' for x in thesis.get('bear_thesis',[])); risks='\n'.join(f'- {x}' for x in thesis.get('risk_thesis',[]))
    return f"""# Investment Committee Memo — {ticker.upper()}

## Executive Summary
Committee rating: **{vote.get('consensus_rating')}** ({vote.get('consensus_score')}/100).  
Council decision: **{council.get('decision')}** ({council.get('decision_score')}/100).  
Recommended action: **{recommendation.get('recommended_action')}**.

## Bull Thesis
{bull or '- No high-conviction bull thesis registered.'}

## Bear Thesis
{bear or '- No high-conviction bear thesis registered.'}

## Key Risks
{risks or '- Standard market, liquidity, and execution risk.'}

## Scenario Analysis
Expected return: **{council.get('expected_return')}**  
Expected risk: **{council.get('expected_risk')}**  
Risk/reward: **{council.get('risk_reward')}**

## Final Recommendation
{recommendation.get('recommended_action')} with suggested size: **{recommendation.get('suggested_position_size')}**.
"""
