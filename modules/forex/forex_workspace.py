"""
modules/forex/forex_workspace.py
"""

from __future__ import annotations

import streamlit as st

from modules.forex.forex_app_integration import (
    get_forex_application,
)
from modules.forex.forex_navigation import (
    render_forex_navigation,
)


class ForexWorkspace:
    """
    Primary entry point for the Forex module.

    Responsibilities
    ----------------
    - Initialize Forex services
    - Manage Streamlit session state
    - Maintain portfolio context
    - Route to the institutional Forex workspaces
    """

    def __init__(self):
        self.app = get_forex_application()

    def initialize(self):
        self.app.initialize()

        defaults = {
            "forex_initialized": True,
            "forex_workspace": "Command Center",
            "forex_selected_pair": "EUR/USD",
            "forex_watchlist": [],
            "forex_portfolio_id": None,
            "forex_account_type": "Paper",
        }

        for key, value in defaults.items():
            st.session_state.setdefault(key, value)

    def load_portfolio_context(self):
        return {
            "portfolio_id": st.session_state.get("forex_portfolio_id"),
            "account_type": st.session_state.get("forex_account_type", "Paper"),
            "watchlist": st.session_state.get("forex_watchlist", []),
        }

    def render_header(self):
        st.title("Forex Trading Workspace")
        st.caption(
            "Institutional Forex Command Center • Provider Router • "
            "Currency Strength • Alpha Model • Paper Trading"
        )

    def render(self):
        if not st.session_state.get("forex_initialized"):
            self.initialize()

        self.render_header()

        context = self.load_portfolio_context()

        with st.expander("Workspace Context", expanded=False):
            st.json(context)

        render_forex_navigation()


_WORKSPACE = None


def get_forex_workspace():
    global _WORKSPACE
    if _WORKSPACE is None:
        _WORKSPACE = ForexWorkspace()
    return _WORKSPACE


def initialize_forex_workspace():
    get_forex_workspace().initialize()


def render_forex_workspace():
    get_forex_workspace().render()
