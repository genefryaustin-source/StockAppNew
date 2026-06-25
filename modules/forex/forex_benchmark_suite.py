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


class ForexBenchmarkSuite:
    """Runs repeatable benchmark tiers against the Forex operations runtime."""

    def run_benchmark(self, job_count: int = 100, max_jobs_per_tick: int = 100) -> Dict[str, Any]:
        started = time.perf_counter()
        schedule_started = time.perf_counter()
        scheduled = _schedule_jobs(job_count=job_count)
        schedule_ms = round((time.perf_counter() - schedule_started) * 1000, 3)
        runtime_cls = _safe_import("modules.forex.forex_runtime_profiler", "ForexRuntimeProfiler")
        if runtime_cls is None:
            return _result("benchmark", "fail", started, error="ForexRuntimeProfiler unavailable")
        drain = runtime_cls().profile_until_drained(max_jobs_per_tick=max_jobs_per_tick, max_ticks=math.ceil(job_count / max(1, max_jobs_per_tick)) + 5)
        total_ms = round((time.perf_counter() - started) * 1000, 3)
        processed = int(drain.get("processed_jobs", 0) or 0)
        throughput = round(processed / max(total_ms / 1000, 0.001), 3)
        status = "pass" if processed > 0 and drain.get("status") in {"pass", "warn"} else "fail"
        return _result("benchmark", status, started, requested_jobs=job_count, scheduled=scheduled, schedule_ms=schedule_ms, drain=drain, total_ms=total_ms, throughput_jobs_per_second=throughput, final_summary=_snapshot().get("summary", {}))

    def run_standard_benchmarks(self) -> Dict[str, Any]:
        started = time.perf_counter()
        tiers = [100, 500, 1000]
        results = [self.run_benchmark(job_count=tier, max_jobs_per_tick=min(250, tier)) for tier in tiers]
        passed = sum(1 for r in results if r.get("status") == "pass")
        return _result("standard_benchmark_suite", "pass" if passed == len(results) else "warn", started, tiers=tiers, passed=passed, total=len(results), results=results)
