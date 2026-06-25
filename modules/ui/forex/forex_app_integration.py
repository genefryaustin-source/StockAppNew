"""
ui/forex/forex_app_integration.py

Application integration layer for the Forex subsystem.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import streamlit as st
except Exception:
    st = None

from modules.forex.forex_workspace import render_forex_workspace
from modules.forex.forex_module import get_forex_module


class ForexAppIntegration:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self.module = get_forex_module(db=db)

    def initialize_forex(self):
        return self.module.initialize()

    def render_forex(self):
        return render_forex_workspace(db=self.db)

    def refresh_forex(self):
        return self.module.refresh()

    def shutdown_forex(self):
        return self.module.shutdown()

    def health(self):
        return self.module.health()


_INSTANCE = None


def get_forex_app_integration(db: Optional[Any] = None):
    global _INSTANCE
    if _INSTANCE is None or (db is not None and _INSTANCE.db is None):
        _INSTANCE = ForexAppIntegration(db=db)
    return _INSTANCE


def initialize_forex(db: Optional[Any] = None):
    return get_forex_app_integration(db=db).initialize_forex()


def render_forex(db: Optional[Any] = None):
    if st is not None:
        return get_forex_app_integration(db=db).render_forex()
    return get_forex_app_integration(db=db).health()


def refresh_forex(db: Optional[Any] = None):
    return get_forex_app_integration(db=db).refresh_forex()


def shutdown_forex(db: Optional[Any] = None):
    return get_forex_app_integration(db=db).shutdown_forex()
