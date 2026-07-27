
"""
modules/forex/forex_order_dashboard.py
"""

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_order_management_engine import get_forex_order_management_engine

class ForexOrderDashboard:

    def __init__(self, db=None):
        self.engine=get_forex_order_management_engine(db=db)

    def render(self):
        open_orders=self.engine.open_orders()
        filled_orders=self.engine.filled_orders()

        if st is None:
            return {
                "open_orders":open_orders,
                "filled_orders":filled_orders,
            }

        st.header("📋 Forex Order Management")

        c1,c2=st.columns(2)
        c1.metric("Open Orders",len(open_orders))
        c2.metric("Filled Orders",len(filled_orders))

        ws=st.radio(
            "Order Workspace",
            ["Open Orders","Filled Orders","Lookup"],
            horizontal=True,
        )

        if ws=="Open Orders":
            st.dataframe(
                pd.DataFrame(open_orders) if pd else open_orders,
                use_container_width=True,
                hide_index=True,
            )

        elif ws=="Filled Orders":
            st.dataframe(
                pd.DataFrame(filled_orders) if pd else filled_orders,
                use_container_width=True,
                hide_index=True,
            )

        else:
            oid=st.text_input("Broker Order ID")
            if st.button("Lookup",use_container_width=True):
                st.json(self.engine.order_status(oid))

_INSTANCE=None

def get_forex_order_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexOrderDashboard(db=db)
    return _INSTANCE

def render_forex_order_dashboard(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
    **kwargs,
):
    return get_forex_order_dashboard(db=db).render()
