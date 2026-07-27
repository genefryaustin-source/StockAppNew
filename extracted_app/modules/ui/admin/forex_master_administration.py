"""
ui/admin/forex_master_administration.py

Master administration entry point for the Forex platform.
"""

from __future__ import annotations

try:
    import streamlit as st
except Exception:
    st=None

from ui.admin.forex_administration_suite import render_forex_administration_suite
from ui.admin.forex_operations_control_center import render_forex_operations_control_center
from ui.admin.forex_health_dashboard import render_forex_health_dashboard
from ui.admin.forex_validation_center import render_forex_validation_center

class ForexMasterAdministration:

    def __init__(self, db=None):
        self.db=db

    def render(self):
        if st is None:
            return {"status":"streamlit_unavailable"}

        st.title("🏛️ Forex Master Administration")

        page=st.radio(
            "Administration",
            [
                "Overview",
                "Administration Suite",
                "Operations",
                "Health",
                "Validation",
            ],
            horizontal=True,
        )

        if page=="Overview":
            st.info("Central administration hub for the Forex subsystem.")
        elif page=="Administration Suite":
            render_forex_administration_suite(db=self.db)
        elif page=="Operations":
            render_forex_operations_control_center(db=self.db)
        elif page=="Health":
            render_forex_health_dashboard(db=self.db)
        else:
            render_forex_validation_center(db=self.db)

_INSTANCE=None

def get_forex_master_administration(db=None):
    global _INSTANCE
    if _INSTANCE is None or (db is not None and getattr(_INSTANCE,"db",None) is None):
        _INSTANCE=ForexMasterAdministration(db=db)
    return _INSTANCE

def render_forex_master_administration(db=None):
    return get_forex_master_administration(db=db).render()
