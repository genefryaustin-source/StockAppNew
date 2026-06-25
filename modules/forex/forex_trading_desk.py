from datetime import datetime, timezone

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


class ForexTradingDesk:
    def __init__(self, db=None):
        self.db=db
        self.execution_center=get_forex_execution_center(db=db)
        self.portfolio=get_forex_portfolio_manager(db=db)
        self.orders=get_forex_order_management_engine(db=db)
        self.risk=get_forex_risk_management_engine(db=db)
        self.performance=get_forex_performance_analytics_engine(db=db)
        self.journal=get_forex_trade_journal_engine(db=db)
        self.strategy=get_forex_strategy_lab(db=db)
        self.ai=get_forex_ai_orchestrator(db=db)
        self.health=get_forex_provider_health()
        self.command_center=get_forex_command_center_engine()

    def dashboard(self, portfolio_id=None, user_id=None, tenant_id=None, force_refresh=False):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command_center": self.command_center.build(force_refresh=force_refresh),
            "execution_center": self.execution_center.dashboard(),
            "portfolio": self.portfolio.portfolio_summary(
                portfolio_id=portfolio_id,
                user_id=user_id,
                tenant_id=tenant_id,
                force_refresh=force_refresh,
            ),
            "risk": self.risk.analyze(
                portfolio_id=portfolio_id,
                user_id=user_id,
                tenant_id=tenant_id,
                force_refresh=force_refresh,
            ),
            "performance": self.performance.analyze(
                portfolio_id=portfolio_id,
                user_id=user_id,
                tenant_id=tenant_id,
                force_refresh=force_refresh,
            ),
            "open_orders": self.orders.open_orders(),
            "filled_orders": self.orders.filled_orders(),
            "strategy_lab": self.strategy.run(force_refresh=force_refresh),
            "journal": self.journal.summarize(
                portfolio_id=portfolio_id,
                user_id=user_id,
                tenant_id=tenant_id,
            ),
            "provider_health": self.health.summary(),
        }

    def submit_order(self, **kwargs):
        return self.execution_center.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        return self.execution_center.execute_recommendation(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.execution_center.cancel_order(broker_order_id)

    def autonomous_cycle(self, portfolio_id=None, user_id=None, tenant_id=None):
        return self.ai.autonomous_cycle(
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    def refresh(self):
        return self.execution_center.refresh()

    def emergency_kill_switch(self):
        cancelled=[]
        for order in self.orders.open_orders():
            oid=order.get("broker_order_id")
            if oid:
                cancelled.append(self.orders.cancel(oid))
        return {
            "status":"kill_switch_executed",
            "cancelled_orders":cancelled,
            "timestamp":datetime.now(timezone.utc).isoformat(),
        }


_DESK=None

def get_forex_trading_desk(db=None):
    global _DESK
    if _DESK is None or (db is not None and _DESK.db is None):
        _DESK=ForexTradingDesk(db=db)
    return _DESK
