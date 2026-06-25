from datetime import datetime, timezone

from modules.forex.forex_terminal_api import get_forex_terminal_api

class ForexTerminalDashboardService:
    def __init__(self, db=None):
        self.api=get_forex_terminal_api(db=db)

    def dashboard_data(self, **kwargs):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "terminal": self.api.get_terminal_snapshot(**kwargs),
            "portfolio": self.api.portfolio_summary(**kwargs),
            "provider_health": self.api.provider_health(),
        }

    def refresh(self):
        return self.api.refresh_terminal()

    def execute(self, recommendation, **kwargs):
        return self.api.execute_recommendation(recommendation, **kwargs)

    def submit_order(self, **kwargs):
        return self.api.submit_order(**kwargs)

    def cancel_order(self, broker_order_id):
        return self.api.cancel_order(broker_order_id)

    def emergency_stop(self):
        return self.api.emergency_stop()

_SERVICE=None

def get_forex_terminal_dashboard_service(db=None):
    global _SERVICE
    if _SERVICE is None:
        _SERVICE=ForexTerminalDashboardService(db=db)
    return _SERVICE
