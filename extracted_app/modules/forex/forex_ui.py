"""
modules/forex/forex_ui.py
"""

from __future__ import annotations

import streamlit as st

from modules.forex.forex_command_center_dashboard import render_forex_command_center


def render_forex_workspace():
    st.sidebar.radio(
        "Forex Workspace",
        [
            "Command Center",
            "Currency Strength",
            "Alpha Model",
            "Institutional Flow",
            "Carry Trades",
            "Central Banks",
            "Macro Regime",
            "Sentiment",
        ],
        key="forex_workspace",
    )

    workspace=st.session_state.get("forex_workspace","Command Center")

    if workspace=="Command Center":
        render_forex_command_center()
    else:
        st.info(f"{workspace} is available through the Command Center engine and can be expanded into a dedicated workspace.")


def render():
    render_forex_workspace()
