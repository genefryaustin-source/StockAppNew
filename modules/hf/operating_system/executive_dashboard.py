from __future__ import annotations
from typing import Any
import streamlit as st


def render_os_executive_dashboard(packet: dict[str, Any]) -> None:
    st.subheader('📈 Executive Dashboard')
    st.json(packet.get('kpis', {}))
