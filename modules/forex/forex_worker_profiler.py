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


class ForexWorkerProfiler:
    """Profiles effective worker capacity by running controlled runtime ticks."""

    def profile_workers(self, worker_counts: Optional[List[int]] = None, jobs_per_worker: int = 10) -> Dict[str, Any]:
        started = time.perf_counter()
        worker_counts = worker_counts or [1, 2, 5, 10]
        results: List[Dict[str, Any]] = []
        for workers in worker_counts:
            requested = max(1, int(workers)) * max(1, int(jobs_per_worker))
            _schedule_jobs(job_count=requested)
            tick_result = ForexRuntimeProfiler().profile_tick(max_jobs=requested)
            results.append({
                "workers": workers,
                "requested_jobs": requested,
                "processed_jobs": tick_result.get("processed_jobs", 0),
                "jobs_per_second": tick_result.get("jobs_per_second", 0),
                "tick_ms": tick_result.get("tick_ms", 0),
                "status": tick_result.get("status"),
            })
        passed = all(r.get("processed_jobs", 0) >= 0 and r.get("status") in {"pass", "warn"} for r in results)
        return _result("worker_capacity_profile", "pass" if passed else "fail", started, profiles=results)

# local import placed after class dependencies are defined above by runtime module load
try:
    from modules.forex.forex_runtime_profiler import ForexRuntimeProfiler  # type: ignore
except Exception:
    ForexRuntimeProfiler = None  # type: ignore
