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


class ForexLoadGenerator:
    """Generates repeatable Forex runtime workloads for validation, benchmark, and stress tests."""

    def __init__(self, pairs: Optional[List[str]] = None) -> None:
        self.pairs = pairs or _default_pairs()

    def build_job_payloads(self, job_count: int = 100, tenant_id: str = "default") -> List[Dict[str, Any]]:
        job_types = ["spread_scan", "strength_scan", "macro_regime", "sentiment_scan", "carry_scan", "central_bank_scan", "intermarket_scan", "alpha_model"]
        payloads: List[Dict[str, Any]] = []
        for i in range(max(0, int(job_count))):
            payloads.append({
                "job_id": f"fxload_{uuid.uuid4().hex[:16]}",
                "job_type": job_types[i % len(job_types)],
                "pair": self.pairs[i % len(self.pairs)],
                "priority": "normal" if i % 10 else "high",
                "tenant_id": tenant_id,
                "payload": {"sequence": i, "source": "forex_load_generator"},
                "created_at": _utc_now(),
            })
        return payloads

    def schedule_load(self, job_count: int = 100, tenant_id: str = "default") -> Dict[str, Any]:
        started = time.perf_counter()
        scheduled = _schedule_jobs(job_count=job_count, pairs=self.pairs)
        return _result(
            "schedule_load",
            "pass" if scheduled.get("status") == "ok" and scheduled.get("created_count", 0) > 0 else "fail",
            started,
            requested_jobs=job_count,
            created_jobs=scheduled.get("created_count", len(scheduled.get("created", []))),
            details=scheduled,
        )

    def synthetic_load(self, job_count: int = 100) -> Dict[str, Any]:
        started = time.perf_counter()
        payloads = self.build_job_payloads(job_count=job_count)
        return _result("synthetic_load", "pass", started, requested_jobs=job_count, generated_jobs=len(payloads), jobs=payloads)


def generate_forex_load(job_count: int = 100, pairs: Optional[List[str]] = None) -> Dict[str, Any]:
    return ForexLoadGenerator(pairs=pairs).schedule_load(job_count=job_count)
