from __future__ import annotations
from typing import Any
import streamlit as st


def render_capital_allocation_center(packet: dict[str, Any]) -> None:
    st.subheader('💰 Capital Allocation Center')
    k = packet.get('kpis', {})
    st.metric('Capital Deployment', f"{k.get('capital_deployment',0):.1%}")
    st.metric('Risk Utilization', f"{k.get('risk_utilization',0):.1%}")
