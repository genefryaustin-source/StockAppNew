"""Phase 12 — Investment committee decision engine."""
from __future__ import annotations
from typing import Any

COMMITTEE_ROLES=['CIO','Portfolio Manager','Risk Officer','Volatility PM','Research Lead','Execution Trader','Compliance Officer']

def run_investment_committee(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context=context or {}
    base_score=float(context.get('research_score') or context.get('conviction_score') or 62)
    risk_score=float((context.get('risk') or {}).get('risk_score', 75)) if isinstance(context.get('risk'), dict) else 75
    votes=[]
    for role in COMMITTEE_ROLES:
        score=base_score
        if role=='Risk Officer': score=(score+risk_score)/2
        if role=='Compliance Officer': score=80 if risk_score>=65 else 45
        if role=='Volatility PM': score += 5 if context.get('volatility_edge') else 0
        rating='Approve' if score>=70 else 'Conditional' if score>=55 else 'Reject'
        votes.append({'role':role,'score':round(score,1),'vote':rating,'comment':_comment(role,rating)})
    approve=sum(1 for v in votes if v['vote']=='Approve')
    conditional=sum(1 for v in votes if v['vote']=='Conditional')
    decision='Approved' if approve>=4 and risk_score>=65 else 'Conditional Approval' if approve+conditional>=4 else 'Rejected'
    return {'ticker':ticker.upper(),'decision':decision,'approval_votes':approve,'conditional_votes':conditional,'votes':votes,'committee_confidence':round((approve*100+conditional*55)/max(1,len(votes)),1)}

def _comment(role:str,rating:str)->str:
    if rating=='Approve': return f'{role} supports the opportunity within current limits.'
    if rating=='Conditional': return f'{role} requires sizing, hedge, or timing constraints.'
    return f'{role} does not approve under current risk/reward conditions.'
