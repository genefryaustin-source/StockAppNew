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


class ForexPerformanceProfiler:
    """Coordinates runtime, memory, and scheduler profiling for Forex operations."""

    def profile_scheduler(self, job_count: int = 100) -> Dict[str, Any]:
        started = time.perf_counter()
        result = _schedule_jobs(job_count=job_count)
        created = int(result.get("created_count", len(result.get("created", []))) or 0)
        jobs_per_second = round(created / max(time.perf_counter() - started, 0.001), 3)
        return _result("scheduler_profile", "pass" if created > 0 else "fail", started, requested_jobs=job_count, created_jobs=created, jobs_per_second=jobs_per_second, details=result)

    def profile_runtime(self, max_jobs: int = 100) -> Dict[str, Any]:
        cls = _safe_import("modules.forex.forex_runtime_profiler", "ForexRuntimeProfiler")
        if cls is None:
            return {"test": "runtime_profile", "status": "fail", "error": "ForexRuntimeProfiler unavailable", "timestamp": _utc_now()}
        return cls().profile_tick(max_jobs=max_jobs)

    def profile_memory(self) -> Dict[str, Any]:
        cls = _safe_import("modules.forex.forex_memory_profiler", "ForexMemoryProfiler")
        if cls is None:
            return {"test": "memory_profile", "status": "fail", "error": "ForexMemoryProfiler unavailable", "timestamp": _utc_now()}
        return cls().snapshot_memory()

    def full_profile(self, job_count: int = 100, max_jobs: Optional[int] = None) -> Dict[str, Any]:
        started = time.perf_counter()
        max_jobs = int(max_jobs or job_count)
        scheduler = self.profile_scheduler(job_count=job_count)
        runtime = self.profile_runtime(max_jobs=max_jobs)
        memory = self.profile_memory()
        statuses = [scheduler.get("status"), runtime.get("status"), memory.get("status")]
        status = "pass" if all(s == "pass" for s in statuses) else "warn" if any(s == "pass" for s in statuses) else "fail"
        return _result("full_performance_profile", status, started, scheduler=scheduler, runtime=runtime, memory=memory, summary=_snapshot().get("summary", {}))
