from datetime import datetime, timezone

from modules.forex.forex_master_controller import get_forex_master_controller
from modules.forex.forex_operations_center import get_forex_operations_center

class ForexEnterpriseWorkspace:
    def __init__(self, db=None):
        self.controller=get_forex_master_controller(db=db)
        self.operations=get_forex_operations_center(db=db)

    def initialize(self):
        return self.controller.initialize()

    def workspace_snapshot(self):
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "system":self.controller.system_snapshot(),
            "operations":self.operations.dashboard(),
        }

    def refresh(self):
        return self.operations.refresh()

    def render(self):
        return self.controller.render()

_WORKSPACE=None

def get_forex_enterprise_workspace(db=None):
    global _WORKSPACE
    if _WORKSPACE is None:
        _WORKSPACE=ForexEnterpriseWorkspace(db=db)
    return _WORKSPACE
