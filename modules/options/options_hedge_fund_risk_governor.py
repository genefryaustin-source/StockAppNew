"""Phase 12 — Portfolio risk governor and hedge fund limits."""
from __future__ import annotations
from typing import Any


def _num(v: Any, default: float = 0.0) -> float:
    try: return float(v if v is not None else default)
    except Exception: return default

DEFAULT_LIMITS = {
    'max_single_position_risk_pct': 4.0,
    'max_strategy_sleeve_pct': 25.0,
    'max_net_delta': 250.0,
    'max_net_vega': 500.0,
    'max_daily_loss_pct': 3.0,
    'max_weekly_loss_pct': 6.0,
    'max_earnings_exposure_pct': 12.0,
    'min_liquidity_score': 20.0,
}


def evaluate_risk_governance(portfolio: dict[str, Any] | None = None, limits: dict[str, Any] | None = None) -> dict[str, Any]:
    portfolio=portfolio or {}
    limits={**DEFAULT_LIMITS, **(limits or {})}
    greeks=portfolio.get('greeks') or {}
    metrics=portfolio.get('metrics') or {}
    alerts=[]
    delta=abs(_num(greeks.get('delta')))
    vega=abs(_num(greeks.get('vega')))
    daily_loss=abs(_num(metrics.get('daily_loss_pct')))
    earnings=_num(metrics.get('earnings_exposure_pct'))
    liquidity=_num(metrics.get('liquidity_score'),50)
    if delta > limits['max_net_delta']:
        alerts.append({'severity':'High','rule':'Delta Limit','message':f'Net delta {delta:.1f} exceeds limit {limits["max_net_delta"]:.1f}','action':'Add hedge or reduce directional exposure'})
    if vega > limits['max_net_vega']:
        alerts.append({'severity':'Medium','rule':'Vega Limit','message':f'Net vega {vega:.1f} exceeds limit {limits["max_net_vega"]:.1f}','action':'Reduce long volatility concentration'})
    if daily_loss > limits['max_daily_loss_pct']:
        alerts.append({'severity':'Critical','rule':'Daily Loss','message':f'Daily loss {daily_loss:.1f}% exceeds limit {limits["max_daily_loss_pct"]:.1f}%','action':'Freeze new risk and review open trades'})
    if earnings > limits['max_earnings_exposure_pct']:
        alerts.append({'severity':'High','rule':'Earnings Exposure','message':f'Earnings exposure {earnings:.1f}% exceeds limit','action':'Cap event trades or hedge implied move risk'})
    if liquidity < limits['min_liquidity_score']:
        alerts.append({'severity':'Medium','rule':'Liquidity','message':'Liquidity score below floor','action':'Increase cash / reduce illiquid options'})
    score=max(0,100-len([a for a in alerts if a['severity'] in ('High','Critical')])*22-len(alerts)*6)
    return {'risk_score':round(score,1),'status':'Approved' if score>=75 else 'Review Required' if score>=50 else 'Risk Lockdown','alerts':alerts,'limits':limits}
