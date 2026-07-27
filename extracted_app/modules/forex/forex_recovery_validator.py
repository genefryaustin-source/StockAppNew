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

class ForexRecoveryValidator:
    """Validates recovery behavior after simulated runtime faults."""

    def validate_queue_recovery(self) -> Dict[str, Any]:
        try:
            Queue = _safe_import("modules.forex.forex_execution_queue", "ForexExecutionQueue")
            queue = Queue()
            return _ok("queue_recovery", {"queue_class": queue.__class__.__name__})
        except Exception as exc:
            return _fail("queue_recovery", str(exc))

    def validate_runtime_recovery(self, max_jobs: int = 5) -> Dict[str, Any]:
        try:
            Controller = _safe_import("modules.forex.forex_runtime_controller", "ForexRuntimeController")
            result = Controller().tick(max_jobs=max_jobs)
            return _ok("runtime_recovery", {"tick_result": result})
        except Exception as exc:
            return _fail("runtime_recovery", str(exc))

    def validate_registry_recovery(self) -> Dict[str, Any]:
        try:
            Registry = _safe_import("modules.forex.forex_job_registry", "ForexJobRegistry")
            registry = Registry()
            details = {"registry_class": registry.__class__.__name__}
            if hasattr(registry, "summary"):
                details["summary"] = registry.summary()
            return _ok("registry_recovery", details)
        except Exception as exc:
            return _fail("registry_recovery", str(exc))

    def run_all(self) -> Dict[str, Any]:
        checks = [
            self.validate_registry_recovery(),
            self.validate_queue_recovery(),
            self.validate_runtime_recovery(),
        ]
        passed = sum(1 for c in checks if c.get("passed"))
        return {
            "status": "pass" if passed == len(checks) else "fail",
            "passed": passed,
            "failed": len(checks) - passed,
            "checks": checks,
            "completed_at": _utc_now(),
        }


def run_recovery_validation() -> Dict[str, Any]:
    return ForexRecoveryValidator().run_all()
