"""
ui/admin/forex_health_dashboard.py

Administrative health dashboard for the Forex subsystem.
"""

from __future__ import annotations

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st=None
    pd=None

from modules.forex.forex_provider_health import get_forex_provider_health
from modules.forex.forex_runtime_manager import get_forex_runtime_manager
from modules.forex.forex_registry import get_forex_registry

class ForexHealthDashboard:

    def __init__(self, db=None):
        self.db=db
        self.providers=get_forex_provider_health()
        self.runtime=get_forex_runtime_manager()
        self.registry=get_forex_registry()

    def render(self):
        health=self.providers.summary()
        runtime=self.runtime.status()
        registry=self.registry.summary()

        if st is None:
            return {
                "provider_health":health,
                "runtime":runtime,
                "registry":registry,
            }

        st.title("🩺 Forex Health Dashboard")

        c1,c2,c3=st.columns(3)
        c1.metric("Provider Status",health.get("status","UNKNOWN"))
        c2.metric("Runtime",runtime.get("status","UNKNOWN"))
        c3.metric("Registry",registry.get("status","UNKNOWN"))

        ws=st.radio(
            "Health Workspace",
            ["Overview","Providers","Runtime","Registry"],
            horizontal=True,
        )

        if ws=="Overview":
            st.json({
                "provider_health":health,
                "runtime":runtime,
                "registry":registry,
            })
        elif ws=="Providers":
            st.json(health)
        elif ws=="Runtime":
            st.json(runtime)
        else:
            st.json(registry)

_INSTANCE=None

def get_forex_health_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexHealthDashboard(db=db)
    return _INSTANCE

def render_forex_health_dashboard(db=None):
    return get_forex_health_dashboard(db=db).render()
