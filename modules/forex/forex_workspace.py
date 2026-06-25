
"""
modules/forex/forex_workspace.py
"""

try:
    import streamlit as st
except Exception:
    st=None

from modules.forex.forex_terminal_dashboard import render_forex_terminal_dashboard
from modules.forex.forex_trading_desk_dashboard import render_forex_trading_desk_dashboard
from modules.forex.forex_execution_dashboard import render_forex_execution_dashboard
from modules.forex.forex_portfolio_dashboard import render_forex_portfolio_dashboard
from modules.forex.forex_order_dashboard import render_forex_order_dashboard
from modules.forex.forex_ai_dashboard import render_forex_ai_dashboard

class ForexWorkspace:

    def __init__(self, db=None):
        self.db=db

    def render(self):
        if st is None:
            return {"status":"streamlit_not_available"}

        workspace=st.radio(
            "Workspace",
            [
                "Institutional Terminal",
                "Trading Desk",
                "Execution Center",
                "Portfolio",
                "Orders",
                "AI Command Center",
            ],
            horizontal=True,
        )

        if workspace=="Institutional Terminal":
            render_forex_terminal_dashboard(db=self.db)
        elif workspace=="Trading Desk":
            render_forex_trading_desk_dashboard(db=self.db)
        elif workspace=="Execution Center":
            render_forex_execution_dashboard(db=self.db)
        elif workspace=="Portfolio":
            render_forex_portfolio_dashboard(db=self.db)
        elif workspace=="Orders":
            render_forex_order_dashboard(db=self.db)
        else:
            render_forex_ai_dashboard(db=self.db)

_WORKSPACE=None

def get_forex_workspace(db=None):
    global _WORKSPACE
    if _WORKSPACE is None:
        _WORKSPACE=ForexWorkspace(db=db)
    return _WORKSPACE

def render_forex_workspace(db=None):
    return get_forex_workspace(db=db).render()
