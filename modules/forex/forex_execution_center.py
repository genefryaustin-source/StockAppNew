from datetime import datetime, timezone

from modules.forex.forex_institutional_workspace import get_forex_institutional_workspace
from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine
from modules.forex.forex_order_management_engine import get_forex_order_management_engine
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

class ForexExecutionCenter:
    def __init__(self, db=None):
        self.workspace=get_forex_institutional_workspace(db=db)
        self.execution=get_forex_trade_execution_engine(db=db)
        self.orders=get_forex_order_management_engine(db=db)
        self.portfolio=get_forex_portfolio_manager(db=db)

    def dashboard(self):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace": self.workspace.snapshot(),
            "portfolio": self.portfolio.portfolio_summary(),
            "open_orders": self.orders.open_orders(),
            "filled_orders": self.orders.filled_orders(),
        }

    def submit_order(self, **kwargs):
        return self.execution.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        return self.execution.execute_recommendation(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.orders.cancel(broker_order_id)

    def refresh(self):
        return self.workspace.refresh()

_INSTANCE=None

def get_forex_execution_center(db=None):
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE=ForexExecutionCenter(db=db)
    return _INSTANCE
