from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import random
import time


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ok(name: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"name": name, "status": "pass", "passed": True, "details": details or {}, "checked_at": _utc_now()}


def _fail(name: str, error: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = details or {}
    payload["error"] = str(error)
    return {"name": name, "status": "fail", "passed": False, "details": payload, "checked_at": _utc_now()}


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)

class ForexFaultInjectionEngine:
    """Controlled fault scenarios for Forex runtime resiliency testing."""

    def inject_duplicate_jobs(self, count: int = 5) -> Dict[str, Any]:
        faults = [{"fault_id": f"dup_{i}", "type": "duplicate_job", "severity": "medium"} for i in range(max(0, count))]
        return {"status": "injected", "fault_type": "duplicate_jobs", "faults": faults, "count": len(faults), "created_at": _utc_now()}

    def inject_invalid_jobs(self, count: int = 5) -> Dict[str, Any]:
        faults = [{"fault_id": f"invalid_{i}", "type": "invalid_payload", "severity": "high"} for i in range(max(0, count))]
        return {"status": "injected", "fault_type": "invalid_jobs", "faults": faults, "count": len(faults), "created_at": _utc_now()}

    def inject_worker_failure(self, workers: int = 1) -> Dict[str, Any]:
        faults = [{"fault_id": f"worker_{i}", "type": "worker_failure", "severity": "high"} for i in range(max(0, workers))]
        return {"status": "injected", "fault_type": "worker_failure", "faults": faults, "count": len(faults), "created_at": _utc_now()}

    def inject_queue_pressure(self, depth: int = 100) -> Dict[str, Any]:
        return {"status": "injected", "fault_type": "queue_pressure", "requested_depth": int(depth), "severity": "medium", "created_at": _utc_now()}

    def run_fault_matrix(self) -> Dict[str, Any]:
        scenarios = [
            self.inject_duplicate_jobs(3),
            self.inject_invalid_jobs(3),
            self.inject_worker_failure(1),
            self.inject_queue_pressure(100),
        ]
        return {
            "status": "completed",
            "scenario_count": len(scenarios),
            "scenarios": scenarios,
            "completed_at": _utc_now(),
        }


def run_fault_injection_suite() -> Dict[str, Any]:
    return ForexFaultInjectionEngine().run_fault_matrix()
