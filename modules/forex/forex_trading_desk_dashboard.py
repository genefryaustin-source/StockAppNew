
"""
modules/forex/forex_trading_desk_dashboard.py
"""

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_trading_desk import get_forex_trading_desk

class ForexTradingDeskDashboard:

    def __init__(self, db=None):
        self.desk=get_forex_trading_desk(db=db)

    def render(self, **kwargs):
        data=self.desk.dashboard(**kwargs)
        if st is None:
            return data

        st.header("Forex Trading Desk")

        c1,c2,c3,c4=st.columns(4)
        pf=data.get("portfolio",{}).get("summary",{})
        c1.metric("Positions",pf.get("open_positions",0))
        c2.metric("Notional",f"{pf.get('total_notional',0):,.0f}")
        c3.metric("Unrealized P&L",f"{pf.get('unrealized_pnl',0):,.2f}")
        c4.metric("Win Rate",f"{pf.get('win_rate',0)}%")

        ws=st.radio(
            "Trading Desk Workspace",
            [
                "Portfolio",
                "Orders",
                "Risk",
                "Performance",
                "Strategy",
                "Journal",
                "Providers",
            ],
            horizontal=True,
        )

        if ws=="Portfolio":
            st.json(data.get("portfolio",{}))
        elif ws=="Orders":
            a,b=st.columns(2)
            with a:
                st.subheader("Open Orders")
                st.dataframe(pd.DataFrame(data.get("open_orders",[])) if pd else data.get("open_orders",[]),use_container_width=True)
            with b:
                st.subheader("Filled Orders")
                st.dataframe(pd.DataFrame(data.get("filled_orders",[])) if pd else data.get("filled_orders",[]),use_container_width=True)
        elif ws=="Risk":
            st.json(data.get("risk",{}))
        elif ws=="Performance":
            st.json(data.get("performance",{}))
        elif ws=="Strategy":
            st.json(data.get("strategy_lab",{}))
        elif ws=="Journal":
            st.json(data.get("journal",{}))
        else:
            st.json(data.get("provider_health",{}))

_INSTANCE=None
def get_forex_trading_desk_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexTradingDeskDashboard(db=db)
    return _INSTANCE

def render_forex_trading_desk_dashboard(db=None, **kwargs):
    return get_forex_trading_desk_dashboard(db=db).render(**kwargs)
