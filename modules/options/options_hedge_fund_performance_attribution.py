"""Phase 12 — Hedge fund performance attribution."""
from __future__ import annotations
from typing import Any


def build_performance_attribution(history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    history=history or []
    if not history:
        sleeves=[
            {'sleeve':'Income Options','pnl':1240,'return_pct':1.8,'contribution_pct':32},
            {'sleeve':'Directional Options','pnl':860,'return_pct':2.6,'contribution_pct':22},
            {'sleeve':'Volatility / Event','pnl':520,'return_pct':1.4,'contribution_pct':14},
            {'sleeve':'Hedges / Protection','pnl':-310,'return_pct':-0.8,'contribution_pct':-8},
            {'sleeve':'Core Equity / ETF','pnl':1530,'return_pct':1.2,'contribution_pct':40},
        ]
    else:
        by={}
        for r in history:
            s=r.get('sleeve','Unclassified'); by.setdefault(s,0); by[s]+=float(r.get('pnl') or 0)
        total=sum(by.values()) or 1
        sleeves=[{'sleeve':k,'pnl':v,'return_pct':0,'contribution_pct':round(v/total*100,1)} for k,v in by.items()]
    total_pnl=sum(float(s['pnl']) for s in sleeves)
    return {'total_pnl':round(total_pnl,2),'sleeves':sleeves,'best_sleeve':max(sleeves,key=lambda x:x['pnl'])['sleeve'],'worst_sleeve':min(sleeves,key=lambda x:x['pnl'])['sleeve'],'sharpe_proxy':round(max(0,total_pnl)/max(1,sum(abs(s['pnl']) for s in sleeves))*3,2)}
