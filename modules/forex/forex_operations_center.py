from datetime import datetime, timezone

from modules.forex.forex_control_plane import get_forex_control_plane
from modules.forex.forex_ai_orchestrator import get_forex_ai_orchestrator

class ForexOperationsCenter:
    def __init__(self, db=None):
        self.control=get_forex_control_plane(db=db)
        self.ai=get_forex_ai_orchestrator(db=db)

    def dashboard(self):
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "system_status":self.control.status(),
            "morning_brief":self.ai.morning_brief(),
        }

    def refresh(self):
        return self.control.refresh()

    def execute(self, command, **kwargs):
        return self.control.execute(command, **kwargs)

_CENTER=None

def get_forex_operations_center(db=None):
    global _CENTER
    if _CENTER is None:
        _CENTER=ForexOperationsCenter(db=db)
    return _CENTER
