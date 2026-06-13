from __future__ import annotations
from typing import Any
import statistics
from .common import clamp
def score_consensus(vote_result: dict[str,Any]) -> dict[str,Any]:
    scores=[float(v.get('score',50)) for v in vote_result.get('votes',[]) or []]
    if not scores: return {'agreement_score':0,'disagreement_score':100,'conviction_score':0,'dispersion':0}
    disp=statistics.pstdev(scores) if len(scores)>1 else 0; agreement=clamp(100-disp*2.2); conf=float(vote_result.get('committee_confidence',50)); cons=float(vote_result.get('consensus_score',50)); strength=abs(cons-50)*2; conv=clamp(agreement*.35+conf*.30+strength*.35)
    return {'agreement_score':round(agreement,1),'disagreement_score':round(100-agreement,1),'conviction_score':round(conv,1),'dispersion':round(disp,2),'highest_score':round(max(scores),1),'lowest_score':round(min(scores),1)}
def controversial(opinions: list[dict[str,Any]]) -> list[dict[str,Any]]:
    s=sorted(opinions or [], key=lambda x:float(x.get('score',50))); return [] if len(s)<2 else [s[0],s[-1]]
