"""
modules/forex/forex_navigation.py
"""

from __future__ import annotations

import streamlit as st

from modules.forex.forex_command_center_dashboard import render_forex_command_center

PAGES=[
    "Command Center",
    "Currency Strength",
    "Alpha Model",
    "Institutional Flow",
    "Carry Trades",
    "Central Banks",
    "Macro Regime",
    "Sentiment",
    "Portfolio",
    "Paper Trading",
    "Validation",
    "Operations",
]

def render_forex_navigation():
    if "forex_workspace" not in st.session_state:
        st.session_state.forex_workspace="Command Center"

    workspace=st.sidebar.radio(
        "Forex Workspace",
        options=PAGES,
        index=PAGES.index(st.session_state.forex_workspace) if st.session_state.forex_workspace in PAGES else 0,
        key="forex_workspace_radio",
    )
    st.session_state.forex_workspace=workspace

    if workspace=="Command Center":
        render_forex_command_center()
        return

    st.title(f"Forex • {workspace}")
    st.info(
        f"{workspace} is connected to the institutional Forex engines. "
        "This workspace can be expanded into a dedicated dashboard while "
        "continuing to share the common Provider Router, Price Service, "
        "Currency Strength Engine, Alpha Model, and Command Center."
    )

def render():
    render_forex_navigation()
