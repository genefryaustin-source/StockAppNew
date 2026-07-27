from __future__ import annotations
from typing import Any
import streamlit as st


def render_research_command_center(packet: dict[str, Any]) -> None:
    st.subheader('🏛 Research Command Center')
    st.metric('Research Pipeline', packet.get('kpis', {}).get('research_pipeline', 0))
    st.info('Use HF-1 Investment Committee and HF-2 Multi-Agent Research for full research packet generation.')
