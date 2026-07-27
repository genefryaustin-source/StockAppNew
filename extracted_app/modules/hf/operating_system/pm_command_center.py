from __future__ import annotations
from typing import Any
import streamlit as st


def render_pm_command_center(packet: dict[str, Any]) -> None:
    st.subheader('📊 PM Command Center')
    hf5 = packet.get('hf5', {})
    positions = hf5.get('positions', [])
    st.dataframe(positions, use_container_width=True, hide_index=True)
