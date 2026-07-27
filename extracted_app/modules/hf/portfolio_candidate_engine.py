from __future__ import annotations
from typing import Any
def build_portfolio_candidate(ticker: str, recommendation: dict[str,Any], scorecard: dict[str,Any]) -> dict[str,Any]:
    score=float(scorecard.get('composite_research_score',50)); priority='High' if score>=75 else 'Medium' if score>=55 else 'Low'
    return {'ticker':ticker.upper(),'candidate_priority':priority,'research_score':round(score,1),'recommended_action':recommendation.get('recommended_action'),'suggested_position_size':recommendation.get('suggested_position_size'),'status':'candidate' if priority!='Low' else 'watchlist'}
