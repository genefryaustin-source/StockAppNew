from __future__ import annotations
from typing import Any
import streamlit as st


def render_investor_relations_center(packet: dict[str, Any]) -> None:
    st.subheader('🏦 Investor Relations Center')
    st.info('Investor reporting is generated from HF-5 Fund Operations.')
