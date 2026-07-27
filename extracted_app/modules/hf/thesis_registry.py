from __future__ import annotations
from typing import Any
from .common import utc_now
def build_thesis_registry(ticker: str, opinions: list[dict[str,Any]], council: dict[str,Any]) -> dict[str,Any]:
    bull=[o.get('thesis') for o in opinions if float(o.get('score',50))>=68]; bear=[]; risks=[]
    for o in opinions:
        risks.extend(o.get('risks',[]) or [])
        if float(o.get('score',50))<45: bear.append(o.get('thesis'))
    return {'ticker':ticker.upper(),'created_at':utc_now(),'bull_thesis':bull[:5] or ['Bull case requires stronger growth, earnings, or valuation support.'],'bear_thesis':bear[:5] or ['Bear case centers on valuation, macro, earnings, and execution risk.'],'risk_thesis':list(dict.fromkeys(risks))[:8],'catalyst_thesis':['Earnings update','Estimate revisions','Sector rotation','Institutional ownership changes'],'valuation_thesis':f"Investment Council decision: {council.get('decision')} with expected return {council.get('expected_return')}."}
