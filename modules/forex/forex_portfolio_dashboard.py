
"""
modules/forex/forex_portfolio_dashboard.py
"""

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

class ForexPortfolioDashboard:

    def __init__(self, db=None):
        self.manager=get_forex_portfolio_manager(db=db)

    def render(self, **kwargs):
        report=self.manager.portfolio_summary(**kwargs)

        if st is None:
            return report

        st.header("💼 Forex Portfolio")

        s=report.get("summary",{})
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Positions",s.get("open_positions",0))
        c2.metric("Gross Exposure",f"{s.get('gross_exposure',0):,.0f}")
        c3.metric("Unrealized P&L",f"{s.get('unrealized_pnl',0):,.2f}")
        c4.metric("Win Rate",f"{s.get('win_rate',0)}%")

        ws=st.radio(
            "Portfolio Workspace",
            ["Positions","Currency Exposure","Risk"],
            horizontal=True,
        )

        if ws=="Positions":
            st.dataframe(
                pd.DataFrame(report.get("positions",[])) if pd else report.get("positions",[]),
                use_container_width=True,
                hide_index=True,
            )
        elif ws=="Currency Exposure":
            st.json(report.get("currency_exposure",{}))
        else:
            st.json(report.get("risk",{}))

_INSTANCE=None

def get_forex_portfolio_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexPortfolioDashboard(db=db)
    return _INSTANCE

def render_forex_portfolio_dashboard(db=None, **kwargs):
    return get_forex_portfolio_dashboard(db=db).render(**kwargs)
