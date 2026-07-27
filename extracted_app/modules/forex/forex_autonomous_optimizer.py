from __future__ import annotations
from typing import Any, Dict, Optional

try:
    from .forex_common import ForexStateStore
    from .forex_workload_balancer import ForexWorkloadBalancer
    from .forex_resource_governor import ForexResourceGovernor
except Exception:
    from forex_common import ForexStateStore
    from forex_workload_balancer import ForexWorkloadBalancer
    from forex_resource_governor import ForexResourceGovernor


class ForexAutonomousOptimizer:
    """Optimizes runtime settings based on current pressure and recent failures."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()
        self.balancer = ForexWorkloadBalancer(self.store)
        self.governor = ForexResourceGovernor(self.store)

    def optimize(self) -> Dict[str, Any]:
        load = self.balancer.analyze_load()
        limits = self.governor.evaluate_limits()
        failed = load.get("open_jobs", 0) == 0 and self.store.list_jobs(status="failed", limit=50)
        recommendations = []
        if limits["throttle_ratio"] > 0.5:
            recommendations.append("Reduce scan breadth or increase provider pacing.")
        if load["open_jobs"] > 100:
            recommendations.append("Increase worker count or enable staggered scheduling.")
        if failed:
            recommendations.append("Run self-healing to recover failed jobs.")
        if not recommendations:
            recommendations.append("Runtime is healthy. Keep current settings.")
        score = max(0, 100 - int(limits["pressure_score"] * 2) - (10 if failed else 0))
        self.store.set_metric("optimizer_score", score, {"recommendations": recommendations})
        return {"optimizer_score": score, "recommendations": recommendations, "load": load, "limits": limits}
