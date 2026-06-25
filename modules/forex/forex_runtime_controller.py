from __future__ import annotations
from typing import Any, Dict, Optional
import time

try:
    from .forex_common import ForexStateStore, ForexStatus, sample_market_snapshot
    from .forex_execution_queue import ForexExecutionQueue
    from .forex_resource_governor import ForexResourceGovernor
except Exception:
    from forex_common import ForexStateStore, ForexStatus, sample_market_snapshot
    from forex_execution_queue import ForexExecutionQueue
    from forex_resource_governor import ForexResourceGovernor


class ForexRuntimeController:
    """Executes queued Forex jobs one tick at a time."""

    def __init__(self, store: Optional[ForexStateStore] = None, worker_id: str = "fx-runtime-controller") -> None:
        self.store = store or ForexStateStore()
        self.queue = ForexExecutionQueue(self.store)
        self.governor = ForexResourceGovernor(self.store)
        self.worker_id = worker_id

    def execute_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        gate = self.governor.should_execute(job)
        if not gate["allowed"]:
            return {"status": ForexStatus.SKIPPED.value, "reason": gate["reason"], "job_id": job["job_id"]}

        job_type = job.get("job_type", "")
        pair = job.get("pair") or ""
        result: Dict[str, Any] = {"job_id": job["job_id"], "job_type": job_type, "pair": pair}

        if job_type in {"market_snapshot", "price_refresh", "spread_scan"}:
            result["snapshot"] = sample_market_snapshot(pair)
        elif job_type in {"strength_scan", "currency_strength"}:
            result["strength"] = self._mock_strength(pair)
        elif job_type in {"risk_scan", "portfolio_risk"}:
            result["risk"] = {"risk_score": 35, "max_pair_exposure": 0.12, "status": "within_limits"}
        elif job_type in {"macro_regime", "sentiment_scan", "central_bank_scan", "carry_scan", "intermarket_scan"}:
            result["signal"] = {"bias": "neutral", "confidence": 0.62, "note": "Runtime placeholder completed."}
        else:
            result["message"] = f"Completed generic Forex job type: {job_type}"

        time.sleep(float(job.get("payload", {}).get("sleep_seconds", 0)))
        return result

    def tick(self, max_jobs: int = 5) -> Dict[str, Any]:
        completed = []
        failed = []
        for _ in range(max(1, int(max_jobs))):
            job = self.queue.claim(self.worker_id)
            if not job:
                break
            try:
                result = self.execute_job(job)
                if result.get("status") == ForexStatus.SKIPPED.value:
                    self.store.update_job_status(job["job_id"], ForexStatus.SKIPPED.value, error=result.get("reason"))
                else:
                    self.queue.complete(job["job_id"], result)
                completed.append(result)
            except Exception as exc:
                failed_job = self.queue.fail(job["job_id"], str(exc))
                failed.append({"job_id": job["job_id"], "error": str(exc), "job": failed_job})
        summary = {"completed": len(completed), "failed": len(failed), "completed_jobs": completed, "failed_jobs": failed}
        self.store.record_event("runtime_tick", f"Runtime tick completed {len(completed)} job(s), {len(failed)} failure(s)", payload=summary)
        return summary

    def _mock_strength(self, pair: str) -> Dict[str, Any]:
        base = pair[:3] if pair else "USD"
        quote = pair[-3:] if pair else "EUR"
        return {"base": base, "quote": quote, "base_strength": 61.5, "quote_strength": 48.0, "edge": 13.5}
