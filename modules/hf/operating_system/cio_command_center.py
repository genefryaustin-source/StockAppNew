from __future__ import annotations
from typing import Any
import streamlit as st


def render_cio_command_center(packet: dict[str, Any]) -> None:
    k = packet.get('kpis', {})
    st.subheader('🎯 CIO Command Center')
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('AUM', f"${k.get('fund_aum',0):,.0f}")
    c2.metric('YTD Return', f"{k.get('ytd_return',0):.2%}")
    c3.metric('Sharpe', k.get('sharpe',0))
    c4.metric('Fund Health', packet.get('health',{}).get('status'))
    st.dataframe(packet.get('strategic_decisions', []), use_container_width=True, hide_index=True)
