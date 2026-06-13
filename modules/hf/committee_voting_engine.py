from __future__ import annotations
from typing import Any
from .common import rating_to_score, score_to_rating, clamp, normalize_weights
DEFAULT_ANALYST_WEIGHTS={'Fundamental Analyst':1.25,'Valuation Analyst':1.15,'Earnings Analyst':1.05,'Institutional Analyst':1.0,'Macro Analyst':.85,'Sector Analyst':.85,'Risk Analyst':1.2}
def vote_committee(opinions: list[dict[str,Any]], weights: dict[str,float]|None=None) -> dict[str,Any]:
    w=normalize_weights(weights or DEFAULT_ANALYST_WEIGHTS); votes=[]; total=0; conf=0
    for o in opinions or []:
        a=str(o.get('analyst') or 'Unknown'); score=clamp(o.get('score',rating_to_score(o.get('rating','Hold')))); c=clamp(o.get('confidence',50)); wt=w.get(a,1/max(1,len(w))); total+=score*wt; conf+=c*wt
        votes.append({'analyst':a,'rating':score_to_rating(score),'score':round(score,1),'confidence':round(c,1),'weight':round(wt,3),'weighted_score':round(score*wt,2)})
    return {'consensus_score':round(clamp(total),1),'consensus_rating':score_to_rating(total),'committee_confidence':round(clamp(conf),1),'votes':votes}
