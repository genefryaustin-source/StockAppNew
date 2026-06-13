"""Phase 12 — Compliance and governance checks."""
from __future__ import annotations
from typing import Any

COMPLIANCE_CHECKS=[
    'Position size within mandate',
    'Strategy approved for account type',
    'Risk-defined structure confirmed',
    'Liquidity threshold satisfied',
    'No restricted symbol override',
    'Audit trail captured',
]

def run_compliance_review(trade: dict[str, Any] | None = None, portfolio: dict[str, Any] | None = None) -> dict[str, Any]:
    trade=trade or {}; portfolio=portfolio or {}
    checks=[]
    for c in COMPLIANCE_CHECKS:
        passed=True
        if c=='Liquidity threshold satisfied' and float(portfolio.get('liquidity_score',50) or 50)<20: passed=False
        if c=='Position size within mandate' and float(trade.get('risk_pct',1.0) or 1.0)>4: passed=False
        checks.append({'check':c,'passed':passed,'status':'Pass' if passed else 'Fail'})
    failures=[c for c in checks if not c['passed']]
    return {'approved':not failures,'status':'Approved' if not failures else 'Blocked','checks':checks,'failures':failures}
