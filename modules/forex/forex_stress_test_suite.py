from __future__ import annotations
from typing import Any, Dict, List

try:
    from .forex_performance_profiler import ForexPerformanceProfiler
    from .forex_scheduler import ForexScheduler
    from .forex_execution_queue import ForexExecutionQueue
except Exception:
    from forex_performance_profiler import ForexPerformanceProfiler
    from forex_scheduler import ForexScheduler
    from forex_execution_queue import ForexExecutionQueue


class ForexStressTestSuite:
    """Load tests the Forex operations stack."""

    def run(self, pairs: int = 15, jobs_per_pair: int = 4) -> Dict[str, Any]:
        scheduler = ForexScheduler()
        selected_pairs = [f"FX{i:03d}/USD" for i in range(max(1, pairs))]
        job_types = ["market_snapshot", "strength_scan", "risk_scan", "spread_scan"][:max(1, jobs_per_pair)]
        created = scheduler.schedule_cycle(pairs=selected_pairs, job_types=job_types, enqueue=True)
        profile = ForexPerformanceProfiler().run_profile(sample_size=min(50, max(5, len(created) // 4)))
        depth = ForexExecutionQueue(scheduler.registry.store).queue_depth()
        return {"created_jobs": len(created), "pairs": len(selected_pairs), "job_types": job_types, "profile": profile, "queue_depth": depth}
