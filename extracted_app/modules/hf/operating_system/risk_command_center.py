from __future__ import annotations
from typing import Any
import streamlit as st


def render_risk_command_center(packet: dict[str, Any]) -> None:
    st.subheader('⚠ Risk Command Center')
    st.json(packet.get('hf5', {}).get('risk', {}))
    st.dataframe(packet.get('alerts', []), use_container_width=True, hide_index=True)
