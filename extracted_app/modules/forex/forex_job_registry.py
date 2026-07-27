from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

try:
    from .forex_common import ForexJob, ForexPriority, ForexStateStore, ForexStatus, default_pairs, iso_now, summarize_jobs
except Exception:
    from forex_common import ForexJob, ForexPriority, ForexStateStore, ForexStatus, default_pairs, iso_now, summarize_jobs


class ForexJobRegistry:
    """Registry of Forex analytics, execution, refresh, and runtime jobs."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()

    def register_job(
        self,
        job_type: str,
        pair: str = "",
        priority: str = ForexPriority.NORMAL.value,
        tenant_id: str = "default",
        payload: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = ForexJob.create(job_type, pair, priority, tenant_id, payload, scheduled_for)
        job.status = ForexStatus.PENDING.value
        data = self.store.upsert_job(job)
        self.store.record_event("job_registered", f"Registered {job_type} for {pair or 'global'}", payload=data)
        return data

    def register_bulk_pairs(
        self,
        job_type: str,
        pairs: Optional[Iterable[str]] = None,
        priority: str = ForexPriority.NORMAL.value,
        tenant_id: str = "default",
        payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        pairs = list(pairs or default_pairs())
        return [self.register_job(job_type, p, priority, tenant_id, payload) for p in pairs]

    def list_jobs(self, status: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        return self.store.list_jobs(status=status, limit=limit)

    def get_summary(self, limit: int = 1000) -> Dict[str, Any]:
        return summarize_jobs(self.store.list_jobs(limit=limit))

    def cancel_job(self, job_id: str, reason: str = "Cancelled by operator") -> Optional[Dict[str, Any]]:
        return self.store.update_job_status(job_id, ForexStatus.CANCELLED.value, error=reason)


def get_forex_job_registry() -> ForexJobRegistry:
    return ForexJobRegistry()
