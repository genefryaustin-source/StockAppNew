"""
ui/admin/forex_operations_control_center.py

Administrative dashboard for the Forex Operations Control Center.
"""

from __future__ import annotations

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_operations_control_center import get_forex_operations_control_center


class ForexOperationsControlCenterUI:
    def __init__(self, db=None):
        self.center=get_forex_operations_control_center(db=db)

    def render(self):
        report=self.center.dashboard()

        if st is None:
            return report

        st.title("⚙️ Forex Operations Control Center")

        runtime=report.get("runtime",{})
        deployment=report.get("deployment",{})

        c1,c2=st.columns(2)
        c1.metric("Runtime",runtime.get("status","UNKNOWN"))
        c2.metric("Deployment",deployment.get("status","UNKNOWN"))

        workspace=st.radio(
            "Operations Workspace",
            [
                "Overview",
                "Runtime",
                "Deployment",
                "Actions",
            ],
            horizontal=True,
        )

        if workspace=="Overview":
            st.json(report)

        elif workspace=="Runtime":
            st.json(runtime)

        elif workspace=="Deployment":
            latest=deployment.get("latest")
            if latest:
                st.json(latest)
            hist=deployment.get("history",[])
            if hist and pd:
                st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)

        else:
            a,b,c,d=st.columns(4)
            with a:
                if st.button("Startup",use_container_width=True):
                    st.json(self.center.startup())
            with b:
                if st.button("Deploy Staging",use_container_width=True):
                    st.json(self.center.deploy_staging())
            with c:
                if st.button("Deploy Production",use_container_width=True):
                    st.json(self.center.deploy_production())
            with d:
                if st.button("Shutdown",use_container_width=True):
                    st.json(self.center.shutdown())


_INSTANCE=None

def get_forex_operations_control_center_ui(db=None):
    global _INSTANCE
    if _INSTANCE is None or (db is not None and getattr(_INSTANCE,"center",None) is None):
        _INSTANCE=ForexOperationsControlCenterUI(db=db)
    return _INSTANCE

def render_forex_operations_control_center(db=None):
    return get_forex_operations_control_center_ui(db=db).render()
