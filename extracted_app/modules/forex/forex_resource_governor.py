from __future__ import annotations
from typing import Any, Dict, Optional

try:
    from .forex_common import ForexStateStore, clamp
    from .forex_workload_balancer import ForexWorkloadBalancer
except Exception:
    from forex_common import ForexStateStore, clamp
    from forex_workload_balancer import ForexWorkloadBalancer


class ForexResourceGovernor:
    """Controls safe runtime throughput for provider/API and compute pressure."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()
        self.balancer = ForexWorkloadBalancer(self.store)

    def evaluate_limits(self) -> Dict[str, Any]:
        load = self.balancer.analyze_load()
        pressure = load["weighted_pressure"]
        throttle = clamp(pressure / 2000.0, 0.0, 0.85)
        max_concurrent = int(clamp(12 - (throttle * 8), 2, 12))
        provider_delay_ms = int(clamp(150 + pressure / 10, 150, 1500))
        state = {
            "pressure_score": round(pressure / 100.0, 2),
            "throttle_ratio": round(throttle, 3),
            "max_concurrent_jobs": max_concurrent,
            "provider_delay_ms": provider_delay_ms,
            "allow_new_scans": pressure < 5000,
            "load": load,
        }
        self.store.set_metric("governor_pressure", state["pressure_score"], state)
        return state

    def should_execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        limits = self.evaluate_limits()
        if not limits["allow_new_scans"] and job.get("priority") not in {"high", "critical"}:
            return {"allowed": False, "reason": "Resource governor is throttling non-priority jobs.", "limits": limits}
        return {"allowed": True, "reason": "Allowed", "limits": limits}
