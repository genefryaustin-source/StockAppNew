from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

try:
    from .forex_common import default_pairs, sample_market_snapshot
    from .forex_workload_balancer import ForexWorkloadBalancer
    from .forex_resource_governor import ForexResourceGovernor
except Exception:
    from forex_common import default_pairs, sample_market_snapshot
    from forex_workload_balancer import ForexWorkloadBalancer
    from forex_resource_governor import ForexResourceGovernor


class ForexExecutionPlanner:
    """Builds actionable execution plans for the Forex runtime."""

    def __init__(self) -> None:
        self.balancer = ForexWorkloadBalancer()
        self.governor = ForexResourceGovernor()

    def build_plan(self, pairs: Optional[Iterable[str]] = None, mode: str = "balanced") -> Dict[str, Any]:
        pairs = list(pairs or default_pairs())
        limits = self.governor.evaluate_limits()
        worker_plan = self.balancer.assign_worker_plan(limits["max_concurrent_jobs"])
        jobs = []
        for pair in pairs:
            snap = sample_market_snapshot(pair)
            priority = "high" if snap["volatility"] > 1.4 or snap["spread"] < 0.0002 else "normal"
            jobs.append({
                "pair": pair,
                "job_types": ["market_snapshot", "spread_scan", "strength_scan", "risk_scan"],
                "priority": priority,
                "expected_cost_units": 4,
                "snapshot": snap,
            })
        return {
            "mode": mode,
            "pair_count": len(pairs),
            "limits": limits,
            "workers": worker_plan,
            "jobs": jobs,
            "estimated_cost_units": sum(j["expected_cost_units"] for j in jobs),
        }
