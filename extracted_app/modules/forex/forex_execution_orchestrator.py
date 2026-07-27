from __future__ import annotations
from typing import Any, Dict, Iterable, Optional

try:
    from .forex_execution_planner import ForexExecutionPlanner
    from .forex_scheduler import ForexScheduler
    from .forex_runtime_controller import ForexRuntimeController
except Exception:
    from forex_execution_planner import ForexExecutionPlanner
    from forex_scheduler import ForexScheduler
    from forex_runtime_controller import ForexRuntimeController


class ForexExecutionOrchestrator:
    """Coordinates planning, scheduling, queuing, and runtime execution."""

    def __init__(self) -> None:
        self.planner = ForexExecutionPlanner()
        self.scheduler = ForexScheduler()
        self.runtime = ForexRuntimeController(self.scheduler.registry.store)

    def orchestrate_cycle(self, pairs: Optional[Iterable[str]] = None, execute_now: bool = True, max_jobs: int = 10) -> Dict[str, Any]:
        plan = self.planner.build_plan(pairs)
        created = self.scheduler.schedule_cycle(pairs=pairs, job_types=["market_snapshot", "strength_scan", "risk_scan"], enqueue=True)
        runtime_result = self.runtime.tick(max_jobs=max_jobs) if execute_now else {"completed": 0, "failed": 0}
        return {"plan": plan, "scheduled_jobs": len(created), "runtime": runtime_result}
