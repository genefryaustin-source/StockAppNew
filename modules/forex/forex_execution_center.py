"""
modules/forex/forex_execution_center.py

Context-aware Forex execution center.

Sprint 25 Phase 4.5B cleanup:
- Preserves existing execution-center behavior.
- Adds tenant_id/user_id/portfolio_id propagation.
- Keeps backward compatibility with older Forex factories that only accept db.
- Runtime-aware for Sprint 25.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from modules.forex.forex_institutional_workspace import (
    get_forex_institutional_workspace,
)
from modules.forex.forex_trade_execution_engine import (
    get_forex_trade_execution_engine,
)
from modules.forex.forex_order_management_engine import (
    get_forex_order_management_engine,
)
from modules.forex.forex_portfolio_manager import (
    get_forex_portfolio_manager,
)
from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)
from modules.forex.forex_runtime_context import build_forex_runtime_context

def _factory_with_context(
    factory,
    *,
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    """
    Call newer context-aware factories while remaining compatible
    with legacy factories that only accept db.
    """
    try:
        return factory(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
    except TypeError:
        return factory(db=db)


class ForexExecutionCenter:

    def __init__(
        self,
        db: Any = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ):

        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.workspace = _factory_with_context(
            get_forex_institutional_workspace,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        self.execution = _factory_with_context(
            get_forex_trade_execution_engine,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        self.orders = _factory_with_context(
            get_forex_order_management_engine,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        self.portfolio = _factory_with_context(
            get_forex_portfolio_manager,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    @profile_alpha_execution("ForexExecutionCenter.dashboard")
    def dashboard(
        self,
        runtime=None,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        force_refresh: bool = False,
    ):

        resolved_portfolio_id = portfolio_id or self.portfolio_id
        resolved_user_id = user_id or self.user_id
        resolved_tenant_id = tenant_id or self.tenant_id
        if runtime is None:
            runtime = build_forex_runtime_context(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
                force_refresh=force_refresh,
                db=self.db,
            )
            print("=" * 80)
            print("FOREX RUNTIME IDENTITY")
            print("Tenant   :", runtime.tenant_id)
            print("User     :", runtime.user_id)
            print("Portfolio:", runtime.portfolio_id)
            print("Runtime  :", runtime.metadata.get("runtime_id"))
            print("=" * 80)
        #
        # -----------------------------
        # Portfolio
        # -----------------------------
        #
        if runtime is not None and getattr(runtime, "portfolio", None):

            portfolio = runtime.portfolio

        else:

            portfolio = self.portfolio.portfolio_summary(
                portfolio_id=resolved_portfolio_id,
                user_id=resolved_user_id,
                tenant_id=resolved_tenant_id,
                force_refresh=force_refresh,
            )

        #
        # -----------------------------
        # Institutional Workspace
        # -----------------------------
        #
        try:

            workspace = self.workspace.snapshot(
                runtime=runtime,
                force_refresh=force_refresh,
            )

        except TypeError:
            #
            # Older snapshot() implementation.
            #
            workspace = self.workspace.snapshot()

        #
        # -----------------------------
        # Runtime diagnostics
        # -----------------------------
        #
        runtime_summary = {}

        if runtime is not None and hasattr(runtime, "summary"):

            try:
                runtime_summary = runtime.summary()
            except Exception:
                runtime_summary = {}

        return {

            "generated_at": datetime.now(timezone.utc).isoformat(),

            "workspace": workspace,

            "portfolio": portfolio,

            "open_orders": self.orders.open_orders(),

            "filled_orders": self.orders.filled_orders(),

            #
            # Sprint 25 Diagnostics
            #
            "runtime": runtime_summary,

            "runtime_source": (
                "shared"
                if runtime is not None
                else "local"
            ),
        }

    def submit_order(self, **kwargs):

        kwargs.setdefault("portfolio_id", self.portfolio_id)
        kwargs.setdefault("user_id", self.user_id)
        kwargs.setdefault("tenant_id", self.tenant_id)

        return self.execution.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):

        kwargs.setdefault("portfolio_id", self.portfolio_id)
        kwargs.setdefault("user_id", self.user_id)
        kwargs.setdefault("tenant_id", self.tenant_id)

        return self.execution.execute_recommendation(
            recommendation,
            **kwargs,
        )

    def cancel_order(self, broker_order_id):

        return self.orders.cancel(broker_order_id)

    def refresh(self):

        return self.workspace.refresh()


_INSTANCE = None


def get_forex_execution_center(
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
):

    global _INSTANCE

    if (
        _INSTANCE is None
        or getattr(_INSTANCE, "db", None) is not db
        or getattr(_INSTANCE, "tenant_id", None) != tenant_id
        or getattr(_INSTANCE, "user_id", None) != user_id
        or getattr(_INSTANCE, "portfolio_id", None) != portfolio_id
    ):

        _INSTANCE = ForexExecutionCenter(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _INSTANCE