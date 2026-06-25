"""
modules/forex/forex_master_workspace.py
"""

from __future__ import annotations

import streamlit as st

from modules.forex.forex_system_manager import (
    get_forex_system_manager,
)


class ForexMasterWorkspace:

    def __init__(self):
        self.manager=get_forex_system_manager()

    def render(self):
        self.manager.initialize()

        status=self.manager.system_status()

        st.sidebar.success("Forex System Online")

        with st.sidebar.expander("Forex Runtime",expanded=False):
            st.json({
                "runtime":status.get("runtime"),
                "generated_at":status.get("generated_at"),
            })

        self.manager.render()


_WORKSPACE=None

def get_forex_master_workspace():
    global _WORKSPACE
    if _WORKSPACE is None:
        _WORKSPACE=ForexMasterWorkspace()
    return _WORKSPACE

def render_forex_master_workspace(*args, **kwargs):
    db = kwargs.get("db")

    if db is None and len(args) > 0:
        db = args[0]

    user = kwargs.get("user")

    if user is None and len(args) > 1:
        user = args[1]
    get_forex_master_workspace().render()
