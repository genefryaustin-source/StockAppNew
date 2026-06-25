from __future__ import annotations
from typing import Any, Dict

try:
    from .forex_control_plane import ForexControlPlane
    from .forex_common import ForexStateStore, summarize_jobs
except Exception:
    from forex_control_plane import ForexControlPlane
    from forex_common import ForexStateStore, summarize_jobs


class ForexOperationsCenter:
    """Aggregates command, runtime, health, events, and metrics for admin UI."""

    def __init__(self) -> None:
        self.store = ForexStateStore()
        self.control = ForexControlPlane()

    def snapshot(self) -> Dict[str, Any]:
        jobs = self.store.list_jobs(limit=1000)
        return {
            "summary": summarize_jobs(jobs),
            "metrics": self.store.metrics(),
            "events": self.store.recent_events(limit=50),
            "jobs": jobs[:250],
        }

    def run_action(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        return self.control.command(action, **kwargs)
