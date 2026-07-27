"""Phase 12 — Hedge Fund Operating System Dashboard."""
from __future__ import annotations
import pandas as pd
import streamlit as st

from modules.options.options_hedge_fund_operating_system import build_hedge_fund_operating_report
from modules.options.options_hedge_fund_ai import hedge_fund_cio_memo


def _fmt_money(v):
    try: return f"${float(v):,.0f}"
    except Exception: return '—'

def _df(rows):
    return pd.DataFrame(rows or [])


def render_options_hedge_fund_dashboard(ticker: str, paper: bool = True):
    st.subheader('🏛 Hedge Fund Operating System')
    st.caption('CIO dashboard · capital allocation · risk governance · investment committee · execution board · compliance · attribution')
    key=f'hfos_report_{ticker}_{paper}'
    c1,c2=st.columns([1,5])
    with c1:
        if st.button('↺ Refresh HFOS', key=f'hfos_refresh_{ticker}', use_container_width=True):
            st.session_state.pop(key, None)
    if key not in st.session_state:
        with st.spinner(f'Building hedge fund operating report for {ticker}…'):
            st.session_state[key]=build_hedge_fund_operating_report(ticker, paper)
    report=st.session_state[key]
    capital=report.get('capital',{})
    risk=report.get('risk',{})
    committee=report.get('committee',{})
    execution=report.get('execution',{})
    performance=report.get('performance',{})
    m1,m2,m3,m4,m5=st.columns(5)
    m1.metric('Portfolio Value', _fmt_money(capital.get('portfolio_value')))
    m2.metric('Capital Utilization', f"{capital.get('capital_utilization_pct','—')}%")
    m3.metric('Risk Score', f"{risk.get('risk_score','—')}/100", risk.get('status',''))
    m4.metric('Committee', committee.get('decision','Pending'))
    m5.metric('Total P&L', _fmt_money(performance.get('total_pnl')))
    tabs=st.tabs(['🏦 Capital', '🛡 Risk Governor', '📘 Strategy Book', '🗳 Investment Committee', '🚀 Execution Board', '✅ Compliance', '📊 Attribution', '🤖 CIO Memo'])
    with tabs[0]:
        st.markdown('#### Capital Allocation Sleeves')
        st.dataframe(_df(capital.get('sleeves')), use_container_width=True, hide_index=True)
        st.markdown('#### Rebalance Recommendations')
        rec=_df(report.get('rebalance'))
        st.dataframe(rec, use_container_width=True, hide_index=True) if not rec.empty else st.info('No sleeve rebalance required.')
    with tabs[1]:
        st.markdown('#### Hedge Fund Risk Governance')
        st.json({'status':risk.get('status'), 'risk_score':risk.get('risk_score'), 'limits':risk.get('limits')})
        alerts=_df(risk.get('alerts'))
        st.dataframe(alerts, use_container_width=True, hide_index=True) if not alerts.empty else st.success('No active risk-governor breaches.')
    with tabs[2]:
        st.markdown('#### Strategy Book Recommendations')
        st.dataframe(_df(report.get('strategy_recommendations')), use_container_width=True, hide_index=True)
        with st.expander('Full Strategy Book'):
            st.dataframe(_df(report.get('strategy_book')), use_container_width=True, hide_index=True)
    with tabs[3]:
        st.markdown('#### Investment Committee')
        c1,c2,c3=st.columns(3)
        c1.metric('Decision', committee.get('decision','Pending'))
        c2.metric('Approvals', committee.get('approval_votes',0))
        c3.metric('Confidence', f"{committee.get('committee_confidence','—')}%")
        st.dataframe(_df(committee.get('votes')), use_container_width=True, hide_index=True)
    with tabs[4]:
        st.markdown('#### Execution Board')
        c1,c2=st.columns(2)
        c1.metric('Approved / Ready', execution.get('approved_count',0))
        c2.metric('Review Required', execution.get('review_count',0))
        st.dataframe(_df(execution.get('trade_queue')), use_container_width=True, hide_index=True)
    with tabs[5]:
        st.markdown('#### Compliance Review')
        comp=report.get('compliance',{})
        st.success('Approved') if comp.get('approved') else st.error('Blocked')
        st.dataframe(_df(comp.get('checks')), use_container_width=True, hide_index=True)
    with tabs[6]:
        st.markdown('#### Performance Attribution')
        st.dataframe(_df(performance.get('sleeves')), use_container_width=True, hide_index=True)
        st.json({k:v for k,v in performance.items() if k!='sleeves'})
    with tabs[7]:
        st.markdown('#### CIO Memo')
        if st.button('Generate CIO Operating Memo', key=f'hfos_cio_memo_{ticker}', type='primary'):
            st.session_state[f'hfos_memo_{ticker}']=hedge_fund_cio_memo(report)
        memo=st.session_state.get(f'hfos_memo_{ticker}') or hedge_fund_cio_memo(report)
        st.markdown(memo)
