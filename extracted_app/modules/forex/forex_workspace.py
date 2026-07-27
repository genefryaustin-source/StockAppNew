"""
modules/forex/forex_workspace.py
"""

import time
from datetime import datetime, timezone

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
        # TIMING DEBUG -- total wall-clock time for
        # this entire render() call, start to finish.
        # Compare against the FOREX ENTRY TIMESTAMP
        # printed in app.py and against the Chrome
        # DevTools Performance trace duration for the
        # same click, to see whether the freeze is
        # real Python execution time or purely client
        # -side (browser) time after Python is done.
        # -----------------------------------------
        _render_start_ts = time.time()
        print("=" * 80)
        print("FOREX WORKSPACE RENDER TIMING | START")
        print("start_wall_clock:", datetime.now(timezone.utc).isoformat())
        print("workspace_instance_id:", id(self))
        print("=" * 80)

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
        _bootstrap_start_ts = time.time()
        bootstrap_result = bootstrap_forex_history_on_workspace_open(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
        )
        _bootstrap_elapsed_ms = (time.time() - _bootstrap_start_ts) * 1000.0
        print("=" * 80)
        print("FOREX HISTORY BOOTSTRAP TIMING")
        print("BOOTSTRAP_ELAPSED_MS:", round(_bootstrap_elapsed_ms, 2))
        print("bootstrap_status:", (bootstrap_result or {}).get("status"))
        print("=" * 80)

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

        _workspace_render_start_ts = time.time()

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

        _workspace_render_elapsed_ms = (time.time() - _workspace_render_start_ts) * 1000.0
        print("=" * 80)
        print("FOREX WORKSPACE TAB RENDER TIMING")
        print("workspace:", workspace)
        print("WORKSPACE_RENDER_ELAPSED_MS:", round(_workspace_render_elapsed_ms, 2))
        print("=" * 80)

        # -----------------------------------------
        # TIMING DEBUG -- end of render(). This is
        # the true total Python wall-clock cost of
        # the entire workspace render, covering every
        # dashboard branch above, not just the named
        # sub-stages instrumented inside each dashboard.
        # -----------------------------------------
        _render_elapsed_ms = (time.time() - _render_start_ts) * 1000.0
        print("=" * 80)
        print("FOREX WORKSPACE RENDER TIMING | END")
        print("end_wall_clock:", datetime.now(timezone.utc).isoformat())
        print("workspace:", workspace)
        print("TOTAL_RENDER_ELAPSED_MS:", round(_render_elapsed_ms, 2))
        print("=" * 80)


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