
"""
modules/forex/forex_workspace.py
"""

try:
    import streamlit as st
except Exception:
    st=None

from modules.forex.forex_terminal_dashboard import render_forex_terminal_dashboard
from modules.forex.forex_trading_desk_dashboard import render_forex_trading_desk_dashboard
from modules.forex.forex_execution_dashboard import render_forex_execution_dashboard
from modules.forex.forex_portfolio_dashboard import render_forex_portfolio_dashboard
from modules.forex.forex_order_dashboard import render_forex_order_dashboard
from modules.forex.forex_ai_dashboard import render_forex_ai_dashboard
from modules.forex.forex_quant_research_dashboard import (
    render_forex_quant_research_dashboard,
)
from modules.forex.forex_factor_models_dashboard import (
    render_forex_factor_models_dashboard,
)
from modules.forex.forex_history_validation_dashboard import (
    render_forex_history_validation_dashboard,
)
from modules.forex.forex_history_dashboard import render_forex_history_dashboard
class ForexWorkspace:

    def __init__(
        self,
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
        **kwargs,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.context = kwargs

    def render(self):
        if st is None:
            return {"status": "streamlit_not_available"}

        # -----------------------------------------
        # Sprint 25 Phase 4.5B-3
        # Bootstrap historical market data
        # Runs once per Streamlit session
        # -----------------------------------------
        from modules.forex.forex_runtime_history_integration import (
            bootstrap_forex_history_on_workspace_open,
        )
        print("=" * 80)
        print("FOREX WORKSPACE")
        print("db =", self.db)
        print("tenant =", self.tenant_id)
        print("user =", self.user_id)
        print("portfolio =", self.portfolio_id)
        print("=" * 80)
        bootstrap_forex_history_on_workspace_open(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
        )

        WORKSPACES = [
            "Institutional Terminal",
            "Trading Desk",
            "Execution Center",
            "Portfolio",
            "Orders",
            "AI Command Center",
            "Quant Research",
            "Factor Models",
            "Market Data",
            "History Validation",
        ]

        workspace = st.radio(
            "Workspace",
            WORKSPACES,
            horizontal=True,
        )
        if workspace=="Institutional Terminal":
            render_forex_terminal_dashboard(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )
        elif workspace=="Trading Desk":
            render_forex_trading_desk_dashboard(db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,)
        elif workspace=="Execution Center":
            render_forex_execution_dashboard(db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,)
        elif workspace=="Portfolio":
            render_forex_portfolio_dashboard(db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,)
        elif workspace=="Orders":
            render_forex_order_dashboard(db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,)
        elif workspace == "Quant Research":

            render_forex_quant_research_dashboard(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        elif workspace == "Factor Models":
            render_forex_factor_models_dashboard(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        elif workspace == "Market Data":
            render_forex_history_dashboard(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        elif workspace == "History Validation":
            render_forex_history_validation_dashboard(
                db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )
        else:
            render_forex_ai_dashboard(db=self.db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,)


_WORKSPACE = None


def get_forex_workspace(
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

        _WORKSPACE = ForexWorkspace(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _WORKSPACE

def render_forex_workspace(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    return get_forex_workspace(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).render()


