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

class ForexSelfHealingValidator:
    """Validates that self-healing and recovery components are present and callable."""

    def validate_self_healing_engine(self) -> Dict[str, Any]:
        try:
            Engine = _safe_import("modules.forex.forex_self_healing_engine", "ForexSelfHealingEngine")
            engine = Engine()
            method = None
            for candidate in ("heal", "run", "self_heal", "repair"):
                if hasattr(engine, candidate):
                    method = candidate
                    break
            details = {"engine_class": engine.__class__.__name__, "available_method": method}
            if method:
                try:
                    details["result"] = getattr(engine, method)()
                except TypeError:
                    details["result"] = getattr(engine, method)(None)
            return _ok("self_healing_engine", details)
        except Exception as exc:
            return _fail("self_healing_engine", str(exc))

    def validate_recovery_path(self) -> Dict[str, Any]:
        try:
            Recovery = _safe_import("modules.forex.forex_recovery_validator", "ForexRecoveryValidator")
            result = Recovery().run_all()
            return _ok("recovery_path", result) if result.get("status") == "pass" else _fail("recovery_path", "recovery checks failed", result)
        except Exception as exc:
            return _fail("recovery_path", str(exc))

    def validate_watchdog_path(self) -> Dict[str, Any]:
        try:
            Watchdog = _safe_import("modules.forex.forex_runtime_watchdog", "ForexRuntimeWatchdog")
            result = Watchdog().check_runtime_stall()
            return result
        except Exception as exc:
            return _fail("watchdog_path", str(exc))

    def run_all(self) -> Dict[str, Any]:
        checks = [
            self.validate_self_healing_engine(),
            self.validate_recovery_path(),
            self.validate_watchdog_path(),
        ]
        passed = sum(1 for c in checks if c.get("passed"))
        return {
            "status": "pass" if passed == len(checks) else "fail",
            "passed": passed,
            "failed": len(checks) - passed,
            "checks": checks,
            "completed_at": _utc_now(),
        }


def run_self_healing_validation() -> Dict[str, Any]:
    return ForexSelfHealingValidator().run_all()
