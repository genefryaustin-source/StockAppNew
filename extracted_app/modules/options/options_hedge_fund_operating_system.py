"""Phase 12 — Hedge Fund Operating System master orchestration layer."""
from __future__ import annotations
from typing import Any

from modules.options.options_hedge_fund_capital_engine import build_capital_plan, rebalance_recommendations
from modules.options.options_hedge_fund_risk_governor import evaluate_risk_governance
from modules.options.options_hedge_fund_strategy_book import list_strategy_book, recommend_strategy_book
from modules.options.options_hedge_fund_investment_committee import run_investment_committee
from modules.options.options_hedge_fund_performance_attribution import build_performance_attribution
from modules.options.options_hedge_fund_execution_board import build_execution_board
from modules.options.options_hedge_fund_compliance_engine import run_compliance_review


def _safe(fn, *args, default=None, **kwargs):
    try: return fn(*args, **kwargs)
    except Exception as exc: return default if default is not None else {'error':str(exc)}


def build_hedge_fund_operating_report(ticker: str, paper: bool = True) -> dict[str, Any]:
    account={}
    try:
        from modules.options.options_broker import AlpacaOptionsBroker
        account=AlpacaOptionsBroker(paper=paper).get_account()
        if not isinstance(account, dict): account={}
    except Exception:
        account={}
    capital=build_capital_plan(account)
    portfolio_context={'greeks':{'delta':85,'gamma':12,'theta':42,'vega':155},'metrics':{'liquidity_score':capital.get('liquidity_score',50),'earnings_exposure_pct':8,'daily_loss_pct':0.6}}
    risk=evaluate_risk_governance(portfolio_context)
    context={'sentiment':'Neutral','volatility_regime':'Normal','risk_status':risk.get('status'),'research_score':66,'conviction_score':64}
    try:
        from modules.options.options_smart_money_engine import build_options_smart_money_report
        sm=build_options_smart_money_report(ticker)
        context['sentiment']=(sm.get('sentiment') or {}).get('label','Neutral')
        context['smart_money_bias']=context['sentiment']
    except Exception:
        sm={}
    try:
        from modules.options.options_volatility_dashboard import _load_report
        vol=_load_report(ticker)
        context['volatility_edge']=True
        context['volatility_regime']=str((vol.get('overview') or {}).get('volatility_regime','Normal')) if isinstance(vol,dict) else 'Normal'
    except Exception:
        vol={}
    strategies=recommend_strategy_book(context)
    committee=run_investment_committee(ticker, {**context,'risk':risk})
    execution=build_execution_board(ticker, context)
    compliance=run_compliance_review({'risk_pct':1.5}, {'liquidity_score':capital.get('liquidity_score')})
    performance=build_performance_attribution()
    return {
        'ticker':ticker.upper(),
        'mode':'Paper' if paper else 'Live',
        'capital':capital,
        'rebalance':rebalance_recommendations(capital),
        'risk':risk,
        'strategy_book':list_strategy_book(),
        'strategy_recommendations':strategies,
        'committee':committee,
        'execution':execution,
        'compliance':compliance,
        'performance':performance,
        'smart_money':sm,
        'volatility':vol,
    }
