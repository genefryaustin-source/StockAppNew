from __future__ import annotations
from typing import Any, Dict, List, Optional

try:
    from .forex_common import ForexStateStore, ForexStatus, PRIORITY_WEIGHT, default_pairs
except Exception:
    from forex_common import ForexStateStore, ForexStatus, PRIORITY_WEIGHT, default_pairs


class ForexWorkloadBalancer:
    """Calculates worker allocation and pair scheduling pressure."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()

    def analyze_load(self) -> Dict[str, Any]:
        jobs = self.store.list_jobs(limit=5000)
        open_jobs = [j for j in jobs if j["status"] in {ForexStatus.PENDING.value, ForexStatus.QUEUED.value, ForexStatus.RUNNING.value}]
        by_pair: Dict[str, int] = {}
        weighted_pressure = 0
        for job in open_jobs:
            pair = job.get("pair") or "GLOBAL"
            by_pair[pair] = by_pair.get(pair, 0) + 1
            weighted_pressure += PRIORITY_WEIGHT.get(job.get("priority"), 50)
        suggested_workers = max(1, min(16, round(len(open_jobs) / 10) + (1 if weighted_pressure > 500 else 0)))
        return {
            "open_jobs": len(open_jobs),
            "weighted_pressure": weighted_pressure,
            "suggested_workers": suggested_workers,
            "by_pair": dict(sorted(by_pair.items(), key=lambda x: x[1], reverse=True)),
            "hot_pairs": [p for p, c in by_pair.items() if c >= 5],
        }

    def assign_worker_plan(self, available_workers: int = 4) -> List[Dict[str, Any]]:
        load = self.analyze_load()
        pairs = list(load["by_pair"].keys()) or default_pairs()
        plan = []
        for idx in range(max(1, available_workers)):
            assigned = pairs[idx::max(1, available_workers)]
            plan.append({"worker_id": f"fx-worker-{idx+1}", "assigned_pairs": assigned, "capacity": max(1, len(assigned) * 3)})
        return plan
