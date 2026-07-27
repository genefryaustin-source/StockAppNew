"""
modules/forex/forex_app_router.py

Final app.py-facing router for the Forex subsystem.
Use this from app.py:

    from modules.forex.forex_app_router import render_forex_app

    ...
    elif selected_module == "Forex":
        render_forex_app(db=db)

This keeps app.py clean and isolates Forex initialization/rendering.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import streamlit as st
except Exception:
    st = None

from modules.forex.forex_application import get_forex_application
from modules.forex.forex_terminal_api import get_forex_terminal_api
from modules.forex.forex_provider_health import get_forex_provider_health


class ForexAppRouter:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self.application = get_forex_application(db=db)
        self.terminal_api = get_forex_terminal_api(db=db)
        self.health = get_forex_provider_health()

    def initialize(self):
        try:
            return {
                "status": "initialized",
                "provider_health": self.health.summary(),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    def render(self):
        if st is None:
            return self.terminal_api.get_terminal_snapshot()

        init = self.initialize()
        if init.get("status") == "error":
            st.error(f"Forex failed to initialize: {init.get('error')}")
            return

        try:
            self.application.run()
        except Exception as exc:
            st.error(f"Forex workspace failed: {exc}")

            with st.expander("Forex Provider Health", expanded=False):
                try:
                    st.json(self.health.summary())
                except Exception:
                    st.write("Provider health unavailable.")

    def snapshot(self):
        return self.terminal_api.get_terminal_snapshot()

    def refresh(self):
        return self.terminal_api.refresh_terminal()

    def emergency_stop(self):
        return self.terminal_api.emergency_stop()


_ROUTER = None

def get_forex_app_router(db: Optional[Any] = None) -> ForexAppRouter:
    global _ROUTER
    if _ROUTER is None or (db is not None and _ROUTER.db is None):
        _ROUTER = ForexAppRouter(db=db)
    return _ROUTER


def render_forex_app(db: Optional[Any] = None):
    return get_forex_app_router(db=db).render()


def get_forex_app_snapshot(db: Optional[Any] = None):
    return get_forex_app_router(db=db).snapshot()
