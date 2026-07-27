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


class ForexMemoryProfiler:
    """Lightweight memory profiling using tracemalloc and GC counters."""

    def snapshot_memory(self) -> Dict[str, Any]:
        started = time.perf_counter()
        gc.collect()
        was_tracing = tracemalloc.is_tracing()
        if not was_tracing:
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        counts = gc.get_count()
        return _result(
            "memory_snapshot",
            "pass",
            started,
            current_bytes=current,
            peak_bytes=peak,
            current_mb=round(current / (1024 * 1024), 4),
            peak_mb=round(peak / (1024 * 1024), 4),
            gc_counts={"gen0": counts[0], "gen1": counts[1], "gen2": counts[2]},
            pid=os.getpid(),
        )

    def profile_callable(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
        started = time.perf_counter()
        gc.collect()
        tracemalloc.start()
        before_current, before_peak = tracemalloc.get_traced_memory()
        try:
            result = fn(*args, **kwargs)
            status = "pass"
            error = None
        except Exception as exc:
            result = None
            status = "fail"
            error = str(exc)
        after_current, after_peak = tracemalloc.get_traced_memory()
        return _result(
            "callable_memory_profile",
            status,
            started,
            before_current_bytes=before_current,
            after_current_bytes=after_current,
            delta_current_bytes=after_current - before_current,
            before_peak_bytes=before_peak,
            after_peak_bytes=after_peak,
            result=result,
            error=error,
        )
