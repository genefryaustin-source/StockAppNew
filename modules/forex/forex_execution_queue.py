from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

try:
    from .forex_common import ForexStateStore, ForexStatus, iso_now
except Exception:
    from forex_common import ForexStateStore, ForexStatus, iso_now


class ForexExecutionQueue:
    """Queue adapter backed by the ForexStateStore."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()

    def enqueue(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.store.update_job_status(job_id, ForexStatus.QUEUED.value)
        if job:
            self.store.record_event("job_enqueued", f"Queued {job_id}", payload={"job_id": job_id})
        return job

    def enqueue_many(self, job_ids: Iterable[str]) -> List[Dict[str, Any]]:
        out = []
        for job_id in job_ids:
            job = self.enqueue(job_id)
            if job:
                out.append(job)
        return out

    def claim(self, worker_id: str, job_types: Optional[Iterable[str]] = None) -> Optional[Dict[str, Any]]:
        return self.store.claim_next_job(worker_id, limit_to_types=job_types)

    def complete(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return self.store.update_job_status(job_id, ForexStatus.SUCCEEDED.value, payload=result or {})

    def fail(self, job_id: str, error: str, requeue_if_possible: bool = True) -> Optional[Dict[str, Any]]:
        job = self.store.get_job(job_id)
        if not job:
            return None
        if requeue_if_possible and int(job.get("attempts") or 0) < int(job.get("max_attempts") or 3):
            job["status"] = ForexStatus.QUEUED.value
            job["error"] = error
            job["updated_at"] = iso_now()
            self.store.upsert_job(job)
            self.store.record_event("job_requeued", f"Requeued {job_id} after failure", "warning", {"error": error})
            return job
        return self.store.update_job_status(job_id, ForexStatus.FAILED.value, error=error)

    def queue_depth(self) -> Dict[str, int]:
        jobs = self.store.list_jobs(limit=5000)
        return {
            "pending": sum(1 for j in jobs if j["status"] == ForexStatus.PENDING.value),
            "queued": sum(1 for j in jobs if j["status"] == ForexStatus.QUEUED.value),
            "running": sum(1 for j in jobs if j["status"] == ForexStatus.RUNNING.value),
            "failed": sum(1 for j in jobs if j["status"] == ForexStatus.FAILED.value),
        }
