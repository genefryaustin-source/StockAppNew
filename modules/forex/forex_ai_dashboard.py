
"""
modules/forex/forex_ai_dashboard.py
"""

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_ai_assistant import get_forex_ai_assistant

class ForexAIDashboard:

    def __init__(self, db=None):
        self.ai=get_forex_ai_assistant(db=db)

    def render(self):
        briefing=self.ai.daily_briefing()

        if st is None:
            return briefing

        st.header("🤖 Forex AI Command Center")

        ws=st.radio(
            "AI Workspace",
            [
                "Morning Briefing",
                "Strategy Lab",
                "Portfolio Plan",
                "Autonomous Trading",
            ],
            horizontal=True,
        )

        if ws=="Morning Briefing":
            st.json(briefing)

        elif ws=="Strategy Lab":
            st.json(briefing.get("strategy_lab",{}))

        elif ws=="Portfolio Plan":
            st.json(briefing.get("portfolio_plan",{}))

        else:
            if st.button("Run Autonomous Cycle",use_container_width=True):
                st.json(self.ai.execute())

_INSTANCE=None

def get_forex_ai_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexAIDashboard(db=db)
    return _INSTANCE

def render_forex_ai_dashboard(db=None):
    return get_forex_ai_dashboard(db=db).render()
