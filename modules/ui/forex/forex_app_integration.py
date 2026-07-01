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

    def __init__(
        self,
        db: Optional[Any] = None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        self.db = db

        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.module = get_forex_module(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

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


def get_forex_app_integration(
    db: Optional[Any] = None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _INSTANCE

    if _INSTANCE is None or (db is not None and _INSTANCE.db is None):
        _INSTANCE = ForexAppIntegration(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _INSTANCE


def initialize_forex(
    db: Optional[Any] = None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    return get_forex_app_integration(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).initialize_forex()


def render_forex(self):

    tenant_id = self.tenant_id
    user_id = self.user_id
    portfolio_id = self.portfolio_id

    #
    # Recover identity from the authenticated session
    #
    if st is not None:

        user = (
            st.session_state.get("user")
            or st.session_state.get("current_user")
            or {}
        )

        print("=" * 80)
        print("SESSION USER OBJECT")
        print(user)
        print("=" * 80)

        if tenant_id is None:
            tenant_id = (
                user.get("tenant_id")
                or user.get("tenant")
            )

        if user_id is None:
            user_id = (
                user.get("id")
                or user.get("user_id")
            )

        if portfolio_id is None:
            portfolio_id = st.session_state.get(
                "portfolio_id"
            )

    print("=" * 80)
    print("FOREX UI ENTRY")
    print("tenant   :", tenant_id)
    print("user     :", user_id)
    print("portfolio:", portfolio_id)
    print("=" * 80)

    return render_forex_workspace(
        db=self.db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )


def refresh_forex(
    db: Optional[Any] = None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    return get_forex_app_integration(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).refresh_forex()


def shutdown_forex(
    db: Optional[Any] = None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    return get_forex_app_integration(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).shutdown_forex()
