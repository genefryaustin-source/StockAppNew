from datetime import datetime, timezone

from modules.forex.forex_terminal_dashboard_service import get_forex_terminal_dashboard_service

class ForexTerminalController:
    def __init__(self, db=None):
        self.service=get_forex_terminal_dashboard_service(db=db)

    def initialize(self):
        return {"status":"initialized","timestamp":datetime.now(timezone.utc).isoformat()}

    def dashboard(self, **kwargs):
        return self.service.dashboard_data(**kwargs)

    def refresh(self):
        return self.service.refresh()

    def submit_order(self, **kwargs):
        return self.service.submit_order(**kwargs)

    def execute_recommendation(self, recommendation, **kwargs):
        return self.service.execute(recommendation, **kwargs)

    def cancel_order(self, broker_order_id):
        return self.service.cancel_order(broker_order_id)

    def emergency_stop(self):
        return self.service.emergency_stop()

_CONTROLLER=None

def get_forex_terminal_controller(db=None):
    global _CONTROLLER
    if _CONTROLLER is None:
        _CONTROLLER=ForexTerminalController(db=db)
    return _CONTROLLER
