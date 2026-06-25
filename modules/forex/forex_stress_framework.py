from __future__ import annotations

import os
import gc
import time
import uuid
import math
import tracemalloc
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _safe_import(path: str, name: str):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception:
        return None

def _default_pairs() -> List[str]:
    return ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD", "EUR/GBP"]

def _result(name: str, status: str, started: float, **extra: Any) -> Dict[str, Any]:
    elapsed = max(0.0, time.perf_counter() - started)
    payload = {
        "test": name,
        "status": status,
        "duration_ms": round(elapsed * 1000, 3),
        "timestamp": _utc_now(),
    }
    payload.update(extra)
    return payload

def _snapshot() -> Dict[str, Any]:
    cls = _safe_import("modules.forex.forex_operations_center", "ForexOperationsCenter")
    if cls is None:
        return {"summary": {}, "jobs": [], "events": [], "status": "operations_center_unavailable"}
    try:
        return cls().snapshot()
    except Exception as exc:
        return {"summary": {}, "jobs": [], "events": [], "status": "snapshot_failed", "error": str(exc)}

def _schedule_jobs(job_count: int = 100, pairs: Optional[List[str]] = None) -> Dict[str, Any]:
    cls = _safe_import("modules.forex.forex_scheduler", "ForexScheduler")
    if cls is None:
        return {"status": "unavailable", "created": []}
    pairs = pairs or _default_pairs()
    try:
        scheduler = cls()
        if hasattr(scheduler, "schedule_cycle"):
            created: List[Dict[str, Any]] = []
            remaining = int(job_count)
            while remaining > 0:
                subset = pairs[: max(1, min(len(pairs), remaining))]
                batch = scheduler.schedule_cycle(pairs=subset, enqueue=True) or []
                created.extend(batch if isinstance(batch, list) else [batch])
                if len(created) >= job_count or not batch:
                    break
                remaining = job_count - len(created)
            return {"status": "ok", "created": created[:job_count], "created_count": min(len(created), job_count)}
    except Exception as exc:
        return {"status": "failed", "created": [], "error": str(exc)}
    return {"status": "unsupported", "created": []}

def _tick(max_jobs: int = 100) -> Dict[str, Any]:
    cls = _safe_import("modules.forex.forex_runtime_controller", "ForexRuntimeController")
    if cls is None:
        return {"status": "unavailable", "executed": 0}
    try:
        result = cls().tick(max_jobs=max_jobs)
        if isinstance(result, dict):
            return result
        return {"status": "ok", "result": result}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "executed": 0}


class ForexStressFramework:
    """Stress framework for exercising scheduler, queue, registry, and runtime under load."""

    def stress(self, job_count: int = 1000, batch_size: int = 250, drain: bool = True) -> Dict[str, Any]:
        started = time.perf_counter()
        batches: List[Dict[str, Any]] = []
        remaining = max(0, int(job_count))
        while remaining > 0:
            current = min(max(1, int(batch_size)), remaining)
            batch_started = time.perf_counter()
            scheduled = _schedule_jobs(job_count=current)
            batches.append(_result("stress_schedule_batch", "pass" if scheduled.get("status") == "ok" else "fail", batch_started, requested_jobs=current, created_jobs=scheduled.get("created_count", len(scheduled.get("created", [])))))
            remaining -= current
        runtime_result = None
        if drain:
            runtime_cls = _safe_import("modules.forex.forex_runtime_profiler", "ForexRuntimeProfiler")
            if runtime_cls is not None:
                runtime_result = runtime_cls().profile_until_drained(max_jobs_per_tick=max(1, int(batch_size)), max_ticks=math.ceil(job_count / max(1, batch_size)) + 10)
        final_summary = _snapshot().get("summary", {})
        failed_batches = [b for b in batches if b.get("status") == "fail"]
        status = "pass" if not failed_batches and (not drain or (runtime_result or {}).get("status") in {"pass", "warn"}) else "fail"
        return _result("forex_stress_test", status, started, requested_jobs=job_count, batch_size=batch_size, batches=batches, runtime=runtime_result, final_summary=final_summary)

    def stress_100(self) -> Dict[str, Any]:
        return self.stress(job_count=100, batch_size=50)

    def stress_1000(self) -> Dict[str, Any]:
        return self.stress(job_count=1000, batch_size=250)

    def stress_5000(self) -> Dict[str, Any]:
        return self.stress(job_count=5000, batch_size=500)
