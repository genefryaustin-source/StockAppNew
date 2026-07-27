"""Phase 12 — Hedge fund strategy book across options, equities, vol, and hedges."""
from __future__ import annotations
from typing import Any

STRATEGY_BOOK = [
    {'strategy':'Smart Money Follow','sleeve':'Directional Options','objective':'Follow high-conviction whale/sweep flow','risk':'Medium','ideal_regime':'Risk-On / Flow Confirmation'},
    {'strategy':'Dealer Gamma Alignment','sleeve':'Volatility / Event','objective':'Trade toward/away from gamma walls','risk':'Medium','ideal_regime':'Pinning or gamma squeeze regimes'},
    {'strategy':'Short Premium Income','sleeve':'Income Options','objective':'Harvest elevated IV using spreads/condors','risk':'Medium','ideal_regime':'High IV / Rangebound'},
    {'strategy':'Earnings Volatility','sleeve':'Volatility / Event','objective':'Exploit event premium mispricing','risk':'High','ideal_regime':'Earnings/Event Week'},
    {'strategy':'Portfolio Hedge Overlay','sleeve':'Hedges / Protection','objective':'Reduce drawdown and tail risk','risk':'Low','ideal_regime':'Risk-Off / Elevated Macro Risk'},
    {'strategy':'Core Thesis Expression','sleeve':'Core Equity / ETF','objective':'Express research scorecard via equity/options','risk':'Medium','ideal_regime':'High research conviction'},
]

def list_strategy_book() -> list[dict[str, Any]]:
    return list(STRATEGY_BOOK)


def recommend_strategy_book(context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    context=context or {}
    sentiment=str(context.get('sentiment','Neutral'))
    vol=str(context.get('volatility_regime','Normal'))
    risk=str(context.get('risk_status','Approved'))
    recs=[]
    for s in STRATEGY_BOOK:
        score=50
        if 'Bullish' in sentiment and s['sleeve'] in ('Directional Options','Core Equity / ETF'): score+=18
        if 'High' in vol and s['strategy'] in ('Short Premium Income','Earnings Volatility'): score+=16
        if 'Review' in risk or 'Lockdown' in risk:
            score += 20 if s['sleeve']=='Hedges / Protection' else -15
        row=dict(s); row['score']=max(0,min(100,score)); row['recommendation']='Primary' if row['score']>=70 else 'Secondary' if row['score']>=55 else 'Defer'
        recs.append(row)
    return sorted(recs,key=lambda r:r['score'],reverse=True)
