"""
modules/forex/forex_master_workspace.py
"""

from __future__ import annotations

import streamlit as st

from modules.forex.forex_system_manager import (
    get_forex_system_manager,
)


class ForexMasterWorkspace:

    def __init__(
        self,
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.manager = get_forex_system_manager(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    def render(self):
        self.manager.initialize()

        status = self.manager.system_status()

        st.sidebar.success("Forex System Online")

        with st.sidebar.expander("Forex Runtime", expanded=False):
            st.json(
                {
                    "runtime": status.get("runtime"),
                    "generated_at": status.get("generated_at"),
                }
            )

        self.manager.render()


_WORKSPACE = None


def get_forex_master_workspace(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _WORKSPACE

    if (
        _WORKSPACE is None
        or _WORKSPACE.db is not db
        or _WORKSPACE.tenant_id != tenant_id
        or _WORKSPACE.user_id != user_id
        or _WORKSPACE.portfolio_id != portfolio_id
    ):

        _WORKSPACE = ForexMasterWorkspace(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _WORKSPACE


def render_forex_master_workspace(*args, **kwargs):

    db = kwargs.get("db")
    tenant_id = kwargs.get("tenant_id")
    user_id = kwargs.get("user_id")
    portfolio_id = kwargs.get("portfolio_id")

    if db is None and len(args) > 0:
        db = args[0]

    #
    # App.py passes (db, user)
    #
    if len(args) > 1 and isinstance(args[1], dict):

        user = args[1]

        if tenant_id is None:
            tenant_id = user.get("tenant_id")

        if user_id is None:
            user_id = (
                    user.get("user_id")
                    or user.get("id")
            )

        if portfolio_id is None:
            portfolio_id = (
                    user.get("portfolio_id")
                    or user.get("active_portfolio_id")
            )

        print("=" * 80)
        print("FOREX MASTER ENTRY")
        print("USER OBJECT :", user)
        print("TENANT      :", tenant_id)
        print("USER ID     :", user_id)
        print("PORTFOLIO   :", portfolio_id)
        print("=" * 80)

    if tenant_id is None and len(args) > 2:
        tenant_id = args[2]

    if user_id is None and len(args) > 3:
        user_id = args[3]

    if portfolio_id is None and len(args) > 4:
        portfolio_id = args[4]

    return get_forex_master_workspace(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).render()