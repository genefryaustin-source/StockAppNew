"""
ui/admin/forex_admin_workspace.py

Unified administrative workspace for the Forex platform.
"""

from __future__ import annotations

try:
    import streamlit as st
except Exception:
    st=None

from ui.admin.forex_health_dashboard import render_forex_health_dashboard
from ui.admin.forex_validation_center import render_forex_validation_center
from ui.admin.forex_operations_control_center import render_forex_operations_control_center


class ForexAdminWorkspace:

    def __init__(self, db=None):
        self.db=db

    def render(self):
        if st is None:
            return {"status":"streamlit_unavailable"}

        st.title("🛠️ Forex Administration")

        workspace=st.radio(
            "Admin Workspace",
            [
                "Operations",
                "Health",
                "Validation",
            ],
            horizontal=True,
        )

        if workspace=="Operations":
            render_forex_operations_control_center(db=self.db)
        elif workspace=="Health":
            render_forex_health_dashboard(db=self.db)
        else:
            render_forex_validation_center(db=self.db)


_INSTANCE=None

def get_forex_admin_workspace(db=None):
    global _INSTANCE
    if _INSTANCE is None or (db is not None and getattr(_INSTANCE,"db",None) is None):
        _INSTANCE=ForexAdminWorkspace(db=db)
    return _INSTANCE

def render_forex_admin_workspace(db=None):
    return get_forex_admin_workspace(db=db).render()
