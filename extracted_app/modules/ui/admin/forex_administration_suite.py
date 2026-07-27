"""
ui/admin/forex_administration_suite.py

Top-level administration suite for the Forex platform.
"""

from __future__ import annotations

try:
    import streamlit as st
except Exception:
    st=None

from ui.admin.forex_admin_workspace import render_forex_admin_workspace
from ui.admin.forex_operations_control_center import render_forex_operations_control_center
from ui.admin.forex_health_dashboard import render_forex_health_dashboard
from ui.admin.forex_validation_center import render_forex_validation_center


class ForexAdministrationSuite:

    def __init__(self, db=None):
        self.db=db

    def render(self):
        if st is None:
            return {"status":"streamlit_unavailable"}

        st.title("🌍 Forex Administration Suite")

        section=st.radio(
            "Administration Workspace",
            [
                "Admin Workspace",
                "Operations",
                "Health",
                "Validation",
            ],
            horizontal=True,
        )

        if section=="Admin Workspace":
            render_forex_admin_workspace(db=self.db)
        elif section=="Operations":
            render_forex_operations_control_center(db=self.db)
        elif section=="Health":
            render_forex_health_dashboard(db=self.db)
        else:
            render_forex_validation_center(db=self.db)


_INSTANCE=None

def get_forex_administration_suite(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexAdministrationSuite(db=db)
    return _INSTANCE

def render_forex_administration_suite(db=None):
    return get_forex_administration_suite(db=db).render()
