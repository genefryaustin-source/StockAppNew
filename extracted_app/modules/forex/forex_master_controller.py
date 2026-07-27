from datetime import datetime, timezone

from modules.forex.forex_supervisor import get_forex_supervisor
from modules.forex.forex_service import get_forex_service

class ForexMasterController:
    def __init__(self, db=None):
        self.supervisor=get_forex_supervisor(db=db)
        self.service=get_forex_service()

    def initialize(self):
        return self.service.initialize()

    def shutdown(self):
        return self.service.shutdown()

    def system_snapshot(self):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "supervisor": self.supervisor.supervise(),
            "diagnostics": self.service.diagnostics(),
        }

    def refresh(self):
        return self.service.refresh_market_data()

    def render(self):
        return self.service.render()

_CONTROLLER=None

def get_forex_master_controller(db=None):
    global _CONTROLLER
    if _CONTROLLER is None:
        _CONTROLLER=ForexMasterController(db=db)
    return _CONTROLLER
