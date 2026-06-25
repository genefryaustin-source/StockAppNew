from __future__ import annotations
from typing import Any, Dict, Optional

try:
    from .forex_common import ForexStateStore, ForexStatus
except Exception:
    from forex_common import ForexStateStore, ForexStatus


class ForexSelfHealingEngine:
    """Recovers stale/rerunnable jobs and records repair actions."""

    def __init__(self, store: Optional[ForexStateStore] = None) -> None:
        self.store = store or ForexStateStore()

    def heal(self, max_jobs: int = 100) -> Dict[str, Any]:
        repaired = []
        failed = self.store.list_jobs(status=ForexStatus.FAILED.value, limit=max_jobs)
        running = self.store.list_jobs(status=ForexStatus.RUNNING.value, limit=max_jobs)
        for job in failed:
            if int(job.get("attempts") or 0) < int(job.get("max_attempts") or 3):
                job["status"] = ForexStatus.QUEUED.value
                job["error"] = "Recovered from failed state"
                self.store.upsert_job(job)
                repaired.append(job["job_id"])
        for job in running:
            job["status"] = ForexStatus.QUEUED.value
            job["worker_id"] = None
            job["error"] = "Recovered stale running job"
            self.store.upsert_job(job)
            repaired.append(job["job_id"])
        self.store.record_event("self_healing", f"Recovered {len(repaired)} job(s)", payload={"repaired": repaired})
        return {"repaired_count": len(repaired), "repaired_job_ids": repaired}
