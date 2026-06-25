from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

try:
    from .forex_common import ForexPriority, default_pairs, iso_now, utc_now
    from .forex_job_registry import ForexJobRegistry
    from .forex_execution_queue import ForexExecutionQueue
except Exception:
    from forex_common import ForexPriority, default_pairs, iso_now, utc_now
    from forex_job_registry import ForexJobRegistry
    from forex_execution_queue import ForexExecutionQueue


class ForexScheduler:
    """Creates scheduled Forex jobs for recurring platform workflows."""

    DEFAULT_JOB_TYPES = [
        "market_snapshot", "spread_scan", "strength_scan", "macro_regime",
        "sentiment_scan", "central_bank_scan", "carry_scan", "intermarket_scan",
    ]

    def __init__(self, registry: Optional[ForexJobRegistry] = None, queue: Optional[ForexExecutionQueue] = None) -> None:
        self.registry = registry or ForexJobRegistry()
        self.queue = queue or ForexExecutionQueue(self.registry.store)

    def schedule_cycle(
        self,
        pairs: Optional[Iterable[str]] = None,
        job_types: Optional[Iterable[str]] = None,
        tenant_id: str = "default",
        enqueue: bool = True,
    ) -> List[Dict[str, Any]]:
        pairs = list(pairs or default_pairs())
        job_types = list(job_types or self.DEFAULT_JOB_TYPES)
        created = []
        for job_type in job_types:
            priority = ForexPriority.HIGH.value if job_type in {"market_snapshot", "risk_scan"} else ForexPriority.NORMAL.value
            for pair in pairs:
                created.append(self.registry.register_job(job_type, pair, priority, tenant_id))
        if enqueue:
            self.queue.enqueue_many([j["job_id"] for j in created])
        return created

    def schedule_staggered_cycle(self, interval_seconds: int = 30, pairs: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
        created = []
        base = utc_now()
        for idx, pair in enumerate(list(pairs or default_pairs())):
            scheduled_for = (base + timedelta(seconds=idx * interval_seconds)).isoformat()
            created.append(self.registry.register_job("market_snapshot", pair, scheduled_for=scheduled_for))
        return created
