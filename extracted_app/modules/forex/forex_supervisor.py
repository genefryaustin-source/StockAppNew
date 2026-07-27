from datetime import datetime, timezone

from modules.forex.forex_operations_center import get_forex_operations_center
from modules.forex.forex_runtime_manager import get_forex_runtime_manager

class ForexSupervisor:
    def __init__(self, db=None):
        self.ops=get_forex_operations_center(db=db)
        self.runtime=get_forex_runtime_manager()

    def supervise(self):
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "runtime":self.runtime.status(),
            "operations":self.ops.dashboard(),
        }

    def heartbeat(self):
        return self.runtime.status()

    def refresh(self):
        return self.ops.refresh()

_SUPERVISOR=None

def get_forex_supervisor(db=None):
    global _SUPERVISOR
    if _SUPERVISOR is None:
        _SUPERVISOR=ForexSupervisor(db=db)
    return _SUPERVISOR
