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


class ForexRuntimeProfiler:
    """Profiles runtime tick behavior and throughput."""

    def profile_tick(self, max_jobs: int = 100) -> Dict[str, Any]:
        started = time.perf_counter()
        before = _snapshot().get("summary", {})
        tick_started = time.perf_counter()
        tick_result = _tick(max_jobs=max_jobs)
        tick_ms = round((time.perf_counter() - tick_started) * 1000, 3)
        after = _snapshot().get("summary", {})
        succeeded_delta = max(0, int(after.get("succeeded_jobs", 0) or 0) - int(before.get("succeeded_jobs", 0) or 0))
        failed_delta = max(0, int(after.get("failed_jobs", 0) or 0) - int(before.get("failed_jobs", 0) or 0))
        processed = succeeded_delta + failed_delta
        jobs_per_second = round(processed / max(tick_ms / 1000, 0.001), 3)
        status = "pass" if tick_result.get("status") not in {"failed", "unavailable"} else "fail"
        return _result(
            "runtime_tick_profile",
            status,
            started,
            requested_max_jobs=max_jobs,
            processed_jobs=processed,
            succeeded_delta=succeeded_delta,
            failed_delta=failed_delta,
            tick_ms=tick_ms,
            jobs_per_second=jobs_per_second,
            tick_result=tick_result,
        )

    def profile_until_drained(self, max_jobs_per_tick: int = 100, max_ticks: int = 100) -> Dict[str, Any]:
        started = time.perf_counter()
        ticks: List[Dict[str, Any]] = []
        for _ in range(max(1, int(max_ticks))):
            snap = _snapshot().get("summary", {})
            if int(snap.get("open_jobs", 0) or 0) <= 0:
                break
            ticks.append(self.profile_tick(max_jobs=max_jobs_per_tick))
        final_summary = _snapshot().get("summary", {})
        status = "pass" if int(final_summary.get("open_jobs", 0) or 0) == 0 else "warn"
        total_processed = sum(int(t.get("processed_jobs", 0) or 0) for t in ticks)
        return _result("runtime_drain_profile", status, started, ticks=len(ticks), processed_jobs=total_processed, final_summary=final_summary, tick_results=ticks)
