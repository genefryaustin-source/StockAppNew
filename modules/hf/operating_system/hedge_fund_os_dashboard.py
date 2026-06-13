from __future__ import annotations
from typing import Any
import pandas as pd
import streamlit as st

from modules.hf.operating_system.operating_system_orchestrator import build_hedge_fund_os_packet
from modules.hf.operating_system.cio_command_center import render_cio_command_center
from modules.hf.operating_system.pm_command_center import render_pm_command_center
from modules.hf.operating_system.research_command_center import render_research_command_center
from modules.hf.operating_system.risk_command_center import render_risk_command_center
from modules.hf.operating_system.capital_allocation_center import render_capital_allocation_center
from modules.hf.operating_system.investor_relations_center import render_investor_relations_center
from modules.hf.operating_system.operations_command_center import render_operations_command_center
from modules.hf.operating_system.executive_dashboard import render_os_executive_dashboard
from modules.hf.operating_system.hedge_fund_copilot import explain_hedge_fund_os
from modules.hf.operating_system.hedge_fund_ai_committee import build_ai_committee_view


def render_hedge_fund_os_dashboard(db: Any = None, user: dict | None = None) -> None:
    st.header('🏦 Hedge Fund Operating System')
    st.caption('HF-6 · Executive command platform across research, PM, risk, operations, and investor reporting.')

    refresh = st.button('Refresh Hedge Fund OS Packet', key='hf6_refresh_packet', use_container_width=True)
    if refresh or 'hf6_packet' not in st.session_state:
        st.session_state['hf6_packet'] = build_hedge_fund_os_packet(db=db, user=user)
    packet = st.session_state['hf6_packet']
    k = packet.get('kpis', {})

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric('AUM', f"${k.get('fund_aum',0):,.0f}")
    c2.metric('YTD Return', f"{k.get('ytd_return',0):.2%}")
    c3.metric('Sharpe', k.get('sharpe', 0))
    c4.metric('Risk Utilization', f"{k.get('risk_utilization',0):.1%}")
    c5.metric('Fund Health', packet.get('health',{}).get('status'), f"{packet.get('health',{}).get('score')}/100")

    tabs = st.tabs(['🎯 CIO Command Center','📊 PM Command Center','🏛 Research Command Center','⚠ Risk Command Center','💰 Capital Allocation','🏦 Investor Relations','⚙ Operations','📈 Executive Dashboard','🩺 Fund Health','🤖 Hedge Fund Copilot'])
    with tabs[0]: render_cio_command_center(packet)
    with tabs[1]: render_pm_command_center(packet)
    with tabs[2]: render_research_command_center(packet)
    with tabs[3]: render_risk_command_center(packet)
    with tabs[4]: render_capital_allocation_center(packet)
    with tabs[5]: render_investor_relations_center(packet)
    with tabs[6]: render_operations_command_center(packet)
    with tabs[7]: render_os_executive_dashboard(packet)
    with tabs[8]:
        st.subheader('🩺 Fund Health Monitor')
        st.json(packet.get('health', {}))
        st.dataframe(pd.DataFrame(packet.get('alerts', [])), use_container_width=True, hide_index=True)
    with tabs[9]:
        st.subheader('🤖 Hedge Fund Copilot')
        st.markdown(explain_hedge_fund_os(packet))
        st.markdown('#### AI Committee View')
        st.dataframe(pd.DataFrame(build_ai_committee_view(packet)), use_container_width=True, hide_index=True)
