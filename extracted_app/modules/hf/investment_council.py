from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .common import clamp, safe_float
@dataclass
class ScenarioCase:
    name: str; probability: float; expected_return: float; expected_risk: float; thesis: str
    def to_dict(self): return asdict(self)
def build_investment_council(ticker: str, committee: dict[str,Any], consensus: dict[str,Any]|None=None) -> dict[str,Any]:
    consensus=consensus or {}; score=safe_float(committee.get('consensus_score'),50); conv=safe_float(consensus.get('conviction_score'),50); base=(score-50)/50*.18; risk=max(.08,.28-conv/500)
    cases=[ScenarioCase('Bull Case',.25+conv/500,base+.22,risk*1.1,'Multiple expansion plus execution upside.'),ScenarioCase('Base Case',.50,base,risk,'Committee consensus case with current information.'),ScenarioCase('Bear Case',max(.10,.25-conv/800),base-.24,risk*1.35,'Thesis impairment, macro pressure, or earnings disappointment.')]
    total=sum(c.probability for c in cases)
    for c in cases: c.probability/=total
    er=sum(c.probability*c.expected_return for c in cases); rr=sum(c.probability*c.expected_risk for c in cases); ds=clamp(50+er*120+conv*.25-rr*45); decision='Approve' if ds>=75 else 'Approve Small' if ds>=60 else 'Watchlist' if ds>=45 else 'Reject'
    return {'ticker':ticker.upper(),'decision':decision,'decision_score':round(ds,1),'expected_return':round(er,4),'expected_risk':round(rr,4),'risk_reward':round(er/rr,2) if rr else None,'scenarios':[c.to_dict() for c in cases]}
from typing import Any


def build_investment_council_view(report: dict[str, Any]) -> dict[str, Any]:
    consensus = dict(report.get("consensus") or {})
    score = float(consensus.get("score", 50.0) or 50.0)
    confidence = float(consensus.get("confidence", 50.0) or 50.0)

    bull_return = round(max(5.0, (score - 50) * 0.9 + confidence * 0.15), 1)
    base_return = round((score - 50) * 0.35, 1)
    bear_return = round(-max(5.0, (60 - score) * 0.6 + (100 - confidence) * 0.12), 1)

    bull_prob = min(55.0, max(20.0, score * 0.45))
    bear_prob = min(45.0, max(15.0, (100 - score) * 0.35))
    base_prob = max(10.0, 100.0 - bull_prob - bear_prob)
    total = bull_prob + base_prob + bear_prob
    bull_prob, base_prob, bear_prob = bull_prob / total, base_prob / total, bear_prob / total

    expected_return = round(bull_return * bull_prob + base_return * base_prob + bear_return * bear_prob, 1)
    return {
        "bull_case": {"probability": round(bull_prob, 2), "return_pct": bull_return},
        "base_case": {"probability": round(base_prob, 2), "return_pct": base_return},
        "bear_case": {"probability": round(bear_prob, 2), "return_pct": bear_return},
        "expected_return_pct": expected_return,
        "risk_reward": round(abs(expected_return / bear_return), 2) if bear_return else None,
        "council_action": _action(expected_return, confidence),
    }


def _action(expected_return: float, confidence: float) -> str:
    if expected_return >= 12 and confidence >= 60:
        return "Candidate for Core Long Review"
    if expected_return >= 6:
        return "Candidate for Starter Position / Watchlist"
    if expected_return <= -5:
        return "Avoid / Short Watch"
    return "Monitor"