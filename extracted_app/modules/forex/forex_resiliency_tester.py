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

class ForexResiliencyTester:
    """Combines fault injection, recovery validation, watchdog, and anomaly detection."""

    def run_duplicate_job_resiliency(self) -> Dict[str, Any]:
        Injector = _safe_import("modules.forex.forex_fault_injection_engine", "ForexFaultInjectionEngine")
        Recovery = _safe_import("modules.forex.forex_recovery_validator", "ForexRecoveryValidator")
        injection = Injector().inject_duplicate_jobs(3)
        recovery = Recovery().run_all()
        return {"name": "duplicate_job_resiliency", "status": recovery.get("status"), "injection": injection, "recovery": recovery, "completed_at": _utc_now()}

    def run_worker_failure_resiliency(self) -> Dict[str, Any]:
        Injector = _safe_import("modules.forex.forex_fault_injection_engine", "ForexFaultInjectionEngine")
        Watchdog = _safe_import("modules.forex.forex_runtime_watchdog", "ForexRuntimeWatchdog")
        injection = Injector().inject_worker_failure(1)
        watchdog = Watchdog().check_runtime_stall()
        return {"name": "worker_failure_resiliency", "status": "pass" if watchdog.get("passed") else "fail", "injection": injection, "watchdog": watchdog, "completed_at": _utc_now()}

    def run_queue_pressure_resiliency(self) -> Dict[str, Any]:
        Injector = _safe_import("modules.forex.forex_fault_injection_engine", "ForexFaultInjectionEngine")
        Watchdog = _safe_import("modules.forex.forex_runtime_watchdog", "ForexRuntimeWatchdog")
        injection = Injector().inject_queue_pressure(100)
        drain = Watchdog().drain_check(max_ticks=3, max_jobs=10)
        return {"name": "queue_pressure_resiliency", "status": "pass" if drain.get("passed") else "fail", "injection": injection, "drain": drain, "completed_at": _utc_now()}

    def run_all(self) -> Dict[str, Any]:
        tests = []
        for fn in [self.run_duplicate_job_resiliency, self.run_worker_failure_resiliency, self.run_queue_pressure_resiliency]:
            try:
                tests.append(fn())
            except Exception as exc:
                tests.append({"name": fn.__name__, "status": "fail", "error": str(exc), "completed_at": _utc_now()})
        passed = sum(1 for t in tests if t.get("status") in ("pass", "success", "healthy"))
        return {
            "status": "pass" if passed == len(tests) else "fail",
            "passed": passed,
            "failed": len(tests) - passed,
            "tests": tests,
            "completed_at": _utc_now(),
        }


def run_resiliency_tests() -> Dict[str, Any]:
    return ForexResiliencyTester().run_all()
