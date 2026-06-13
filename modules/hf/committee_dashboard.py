from __future__ import annotations
from typing import Any
import pandas as pd
import streamlit as st
from .research_committee import build_research_committee
from .committee_voting_engine import vote_committee
from .consensus_scoring_engine import score_consensus, controversial
from .investment_council import build_investment_council
from .thesis_registry import build_thesis_registry
from .thesis_scorecard import build_thesis_scorecard
from .recommendation_engine import build_recommendation
from .portfolio_candidate_engine import build_portfolio_candidate
from .research_memo_builder import build_research_memo
from .investment_decision_log import log_investment_decision, get_decision_history

def build_hf1_packet(ticker: str, db: Any=None) -> dict[str,Any]:
    opinions=build_research_committee(ticker, db=db); vote=vote_committee(opinions); consensus=score_consensus(vote); council=build_investment_council(ticker,vote,consensus); thesis=build_thesis_registry(ticker,opinions,council); scorecard=build_thesis_scorecard(opinions,vote,consensus,council); rec=build_recommendation(ticker,vote,consensus,council); candidate=build_portfolio_candidate(ticker,rec,scorecard); memo=build_research_memo(ticker,vote,consensus,council,thesis,rec)
    return {'ticker':ticker.upper(),'opinions':opinions,'vote':vote,'consensus':consensus,'council':council,'thesis':thesis,'scorecard':scorecard,'recommendation':rec,'candidate':candidate,'memo':memo}

def render_committee_dashboard(db: Any=None, user: dict|None=None, default_ticker: str='AAPL') -> None:
    st.header('🏛 Investment Committee'); st.caption('Stock HF-1 · Research Committee & Investment Council')
    c1,c2=st.columns([2,1])
    with c1: ticker=st.text_input('Ticker',value=default_ticker,key='hf1_ticker').upper().strip()
    with c2: run=st.button('Run Committee Review',type='primary',key='hf1_run_review',use_container_width=True)
    if not ticker: st.info('Enter a ticker to begin.'); return
    key=f'hf1_packet_{ticker}'
    if run or key not in st.session_state:
        with st.spinner(f'Running investment committee for {ticker}...'): st.session_state[key]=build_hf1_packet(ticker,db=db)
    p=st.session_state[key]; vote=p['vote']; consensus=p['consensus']; council=p['council']; scorecard=p['scorecard']
    m=st.columns(5); m[0].metric('Rating',vote.get('consensus_rating')); m[1].metric('Committee Score',f"{vote.get('consensus_score')}/100"); m[2].metric('Confidence',f"{vote.get('committee_confidence')}/100"); m[3].metric('Conviction',f"{consensus.get('conviction_score')}/100"); m[4].metric('Council Decision',council.get('decision'))
    tabs=st.tabs(['👥 Research Committee','🗳 Committee Voting','⚖ Consensus Engine','🎯 Investment Council','📄 Research Memo','📚 Decision History'])
    with tabs[0]: st.subheader('Research Committee Opinions'); st.dataframe(pd.DataFrame(p['opinions']),use_container_width=True,hide_index=True); cont=controversial(p['opinions']); st.markdown('#### Most Controversial Views'); st.dataframe(pd.DataFrame(cont),use_container_width=True,hide_index=True) if cont else st.info('No controversy detected.')
    with tabs[1]: st.subheader('Committee Voting'); st.dataframe(pd.DataFrame(vote.get('votes',[])),use_container_width=True,hide_index=True)
    with tabs[2]:
        st.subheader('Consensus Engine'); x=st.columns(4); x[0].metric('Agreement',f"{consensus.get('agreement_score')}/100"); x[1].metric('Disagreement',f"{consensus.get('disagreement_score')}/100"); x[2].metric('Dispersion',consensus.get('dispersion')); x[3].metric('Composite Research',f"{scorecard.get('composite_research_score')}/100"); st.json(scorecard)
    with tabs[3]:
        st.subheader('Investment Council'); st.dataframe(pd.DataFrame(council.get('scenarios',[])),use_container_width=True,hide_index=True); st.json(p['recommendation'])
        if st.button('Log Investment Decision',key=f'hf1_log_{ticker}',use_container_width=True):
            u=user or {}; oid=log_investment_decision(db,u.get('tenant_id','default_tenant'),u.get('user_id',''),ticker,p); st.success(f'Decision logged: {oid}' if oid else 'Decision prepared (no database session available).')
    with tabs[4]: st.subheader('Research Memo'); st.markdown(p['memo']); st.download_button('Download Memo',data=p['memo'],file_name=f'{ticker}_investment_committee_memo.md',mime='text/markdown',key=f'hf1_download_{ticker}')
    with tabs[5]:
        st.subheader('Decision History'); hist=get_decision_history(db,ticker=ticker,limit=25); st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True) if hist else st.info('No logged decisions yet.')

