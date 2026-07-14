from datetime import datetime, timezone

from modules.forex.forex_control_plane import get_forex_control_plane
from modules.forex.forex_ai_orchestrator import get_forex_ai_orchestrator
from modules.forex.forex_job_registry import get_forex_job_registry

class ForexOperationsCenter:
    def __init__(self, db=None):
        self.control=get_forex_control_plane(db=db)
        self.ai=get_forex_ai_orchestrator(db=db)
        self.jobs=get_forex_job_registry()

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

    def snapshot(self, limit: int = 100):
        """
        Aggregated view used by the governor/operations/optimizer/runtime/
        scheduler dashboards, which all call center.snapshot() expecting
        {"summary": {...}, "jobs": [...], "events": [...]}. The pieces
        already existed (ForexJobRegistry.get_summary()/.list_jobs() and
        ForexStateStore.recent_events()) but nothing tied them together
        under this name, so every dashboard that called it raised
        AttributeError.
        """
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.jobs.get_summary(limit=limit),
            "jobs": self.jobs.list_jobs(limit=limit),
            "events": self.jobs.store.recent_events(limit=limit),
        }

_CENTER=None

def get_forex_operations_center(db=None):
    global _CENTER
    if _CENTER is None:
        _CENTER=ForexOperationsCenter(db=db)
    return _CENTER
