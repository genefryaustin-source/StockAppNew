from __future__ import annotations
from typing import Any
from .common import clamp, safe_float
def build_thesis_scorecard(opinions: list[dict[str,Any]], vote: dict[str,Any], consensus: dict[str,Any], council: dict[str,Any]) -> dict[str,Any]:
    s={o.get('analyst','Unknown'):safe_float(o.get('score'),50) for o in opinions or []}
    return {'fundamental_score':round(s.get('Fundamental Analyst',50),1),'valuation_score':round(s.get('Valuation Analyst',50),1),'earnings_score':round(s.get('Earnings Analyst',50),1),'institutional_score':round(s.get('Institutional Analyst',50),1),'macro_score':round(s.get('Macro Analyst',50),1),'sector_score':round(s.get('Sector Analyst',50),1),'risk_score':round(s.get('Risk Analyst',50),1),'agreement_score':consensus.get('agreement_score',0),'conviction_score':consensus.get('conviction_score',0),'decision_score':council.get('decision_score',0),'composite_research_score':round(clamp(safe_float(vote.get('consensus_score'),50)*.5+safe_float(consensus.get('conviction_score'),50)*.25+safe_float(council.get('decision_score'),50)*.25),1)}
