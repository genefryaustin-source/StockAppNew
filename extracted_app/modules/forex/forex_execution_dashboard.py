
"""
modules/forex/forex_execution_dashboard.py
"""

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_execution_center import get_forex_execution_center

class ForexExecutionDashboard:

    def __init__(self, db=None):
        self.center=get_forex_execution_center(db=db)

    def render(self, **kwargs):
        data=self.center.dashboard()

        if st is None:
            return data

        st.header("⚡ Forex Execution Center")

        c1,c2,c3=st.columns(3)
        c1.metric("Open Orders", len(data.get("open_orders",[])))
        c2.metric("Filled Orders", len(data.get("filled_orders",[])))
        c3.metric("Positions", data.get("portfolio",{}).get("summary",{}).get("open_positions",0))

        tab=st.radio(
            "Execution Workspace",
            ["Order Entry","Open Orders","Filled Orders","Portfolio"],
            horizontal=True,
        )

        if tab=="Order Entry":
            with st.form("fx_order"):
                pair=st.text_input("Pair","EUR/USD")
                side=st.selectbox("Side",["BUY","SELL"])
                qty=st.number_input("Units",value=10000.0,min_value=1.0)
                submitted=st.form_submit_button("Submit Paper Order",use_container_width=True)
                if submitted:
                    st.json(self.center.submit_order(pair=pair,side=side,units=qty))

        elif tab=="Open Orders":
            st.dataframe(pd.DataFrame(data.get("open_orders",[])) if pd else data.get("open_orders",[]),use_container_width=True)

        elif tab=="Filled Orders":
            st.dataframe(pd.DataFrame(data.get("filled_orders",[])) if pd else data.get("filled_orders",[]),use_container_width=True)

        else:
            st.json(data.get("portfolio",{}))

_INSTANCE=None

def get_forex_execution_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexExecutionDashboard(db=db)
    return _INSTANCE

def render_forex_execution_dashboard(db=None, **kwargs):
    return get_forex_execution_dashboard(db=db).render(**kwargs)
