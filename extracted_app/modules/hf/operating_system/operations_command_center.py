from __future__ import annotations
from typing import Any
import streamlit as st


def render_operations_command_center(packet: dict[str, Any]) -> None:
    st.subheader('⚙ Operations Command Center')
    st.json(packet.get('organization', {}))
