"""
modules/forex/forex_trading_desk.py

Context-aware Forex trading desk.

Sprint 25 Phase 4.5B cleanup:
- Preserves existing dashboard output shape.
- Adds tenant_id/user_id/portfolio_id propagation.
- Keeps backward compatibility with older db-only factories.
- Passes context into execution-center and portfolio-aware analytics calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from modules.forex.forex_execution_center import get_forex_execution_center
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
from modules.forex.forex_order_management_engine import get_forex_order_management_engine
from modules.forex.forex_risk_management_engine import get_forex_risk_management_engine
from modules.forex.forex_performance_analytics_engine import get_forex_performance_analytics_engine
from modules.forex.forex_trade_journal_engine import get_forex_trade_journal_engine
from modules.forex.forex_strategy_lab import get_forex_strategy_lab
from modules.forex.forex_ai_orchestrator import get_forex_ai_orchestrator
from modules.forex.forex_provider_health import get_forex_provider_health
from modules.forex.forex_command_center_engine import get_forex_command_center_engine

from modules.forex.forex_alpha_execution_profiler import (
    profile_alpha_execution,
)
from modules.forex.forex_runtime_context import (
    build_forex_runtime_context,
)
def _factory_with_context(factory, *, db=None, tenant_id=None, user_id=None, portfolio_id=None):
    """Call newer context-aware factories, falling back to legacy db-only factories."""
    try:
        return factory(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
    except TypeError:
        return factory(db=db)


class ForexTradingDesk:
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

        self.execution_center = get_forex_execution_center(
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
        self.orders = _factory_with_context(
            get_forex_order_management_engine,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        self.risk = _factory_with_context(
            get_forex_risk_management_engine,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        self.performance = _factory_with_context(
            get_forex_performance_analytics_engine,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        self.journal = _factory_with_context(
            get_forex_trade_journal_engine,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        self.strategy = _factory_with_context(
            get_forex_strategy_lab,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        self.ai = _factory_with_context(
            get_forex_ai_orchestrator,
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        self.health = get_forex_provider_health()
        self.command_center = get_forex_command_center_engine()

    @profile_alpha_execution("ForexTradingDesk.dashboard")
    def dashboard(
        self,
        portfolio_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        force_refresh: bool = False,
    ):
        resolved_portfolio_id = portfolio_id or self.portfolio_id
        resolved_user_id = user_id or self.user_id
        resolved_tenant_id = tenant_id or self.tenant_id
        #
        # Build shared runtime context once.
        #
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
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command_center": self.command_center.build(
                runtime=runtime,
                force_refresh=force_refresh,
            ),
            "execution_center": self.execution_center.dashboard(
                runtime=runtime,
                portfolio_id=resolved_portfolio_id,
                user_id=resolved_user_id,
                tenant_id=resolved_tenant_id,
                force_refresh=force_refresh,
            ),
            "portfolio": self.portfolio.portfolio_summary(
                portfolio_id=resolved_portfolio_id,
                user_id=resolved_user_id,
                tenant_id=resolved_tenant_id,
                force_refresh=force_refresh,
            ),
            "risk": self.risk.analyze(
                portfolio_id=resolved_portfolio_id,
                user_id=resolved_user_id,
                tenant_id=resolved_tenant_id,
                force_refresh=force_refresh,
            ),
            "performance": self.performance.analyze(
                portfolio_id=resolved_portfolio_id,
                user_id=resolved_user_id,
                tenant_id=resolved_tenant_id,
                force_refresh=force_refresh,
            ),
            "open_orders": self.orders.open_orders(),
            "filled_orders": self.orders.filled_orders(),
            "strategy_lab": self.strategy.run(
                runtime=runtime,
                force_refresh=force_refresh,
            ),
            "journal": self.journal.summarize(
                portfolio_id=resolved_portfolio_id,
                user_id=resolved_user_id,
                tenant_id=resolved_tenant_id,
            ),

            "provider_health": self.health.summary(),

            #
            # Sprint 25 Runtime Diagnostics
            #
            "runtime": runtime.summary(),
            }

    def submit_order(self, **kwargs):
        kwargs.setdefault("portfolio_id", self.portfolio_id)
        kwargs.setdefault("user_id", self.user_id)
        kwargs.setdefault("tenant_id", self.tenant_id)
        return self.execution_center.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        kwargs.setdefault("portfolio_id", self.portfolio_id)
        kwargs.setdefault("user_id", self.user_id)
        kwargs.setdefault("tenant_id", self.tenant_id)
        return self.execution_center.execute_recommendation(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.execution_center.cancel_order(broker_order_id)

    def autonomous_cycle(
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
        return self.ai.autonomous_cycle(
            runtime=runtime,
            portfolio_id=resolved_portfolio_id,
            user_id=resolved_user_id,
            tenant_id=resolved_tenant_id,
            force_refresh=force_refresh,
        )

    def refresh(self):
        return self.execution_center.refresh()

    def emergency_kill_switch(self):
        cancelled = []
        for order in self.orders.open_orders():
            oid = order.get("broker_order_id")
            if oid:
                cancelled.append(self.orders.cancel(oid))
        return {
            "status": "kill_switch_executed",
            "cancelled_orders": cancelled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


_DESK = None


def get_forex_trading_desk(
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
):
    global _DESK

    if (
        _DESK is None
        or getattr(_DESK, "db", None) is not db
        or getattr(_DESK, "tenant_id", None) != tenant_id
        or getattr(_DESK, "user_id", None) != user_id
        or getattr(_DESK, "portfolio_id", None) != portfolio_id
    ):
        _DESK = ForexTradingDesk(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _DESK
