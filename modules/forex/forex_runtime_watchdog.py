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

class ForexRuntimeWatchdog:
    """Lightweight watchdog for runtime health and queue drain behavior."""

    def snapshot(self) -> Dict[str, Any]:
        try:
            Center = _safe_import("modules.forex.forex_operations_center", "ForexOperationsCenter")
            snap = Center().snapshot()
            summary = snap.get("summary", {})
            failed = int(summary.get("failed_jobs", 0) or 0)
            open_jobs = int(summary.get("open_jobs", 0) or 0)
            total = int(summary.get("total_jobs", 0) or 0)
            status = "healthy" if failed == 0 else "degraded"
            return {
                "status": status,
                "summary": summary,
                "total_jobs": total,
                "open_jobs": open_jobs,
                "failed_jobs": failed,
                "checked_at": _utc_now(),
            }
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc), "checked_at": _utc_now()}

    def check_runtime_stall(self, open_threshold: int = 1000) -> Dict[str, Any]:
        snap = self.snapshot()
        if snap.get("status") == "unavailable":
            return _fail("runtime_watchdog", snap.get("error", "snapshot unavailable"), snap)
        if snap.get("open_jobs", 0) > open_threshold:
            return _fail("runtime_watchdog", "open job threshold exceeded", snap)
        return _ok("runtime_watchdog", snap)

    def drain_check(self, max_ticks: int = 5, max_jobs: int = 10) -> Dict[str, Any]:
        try:
            Controller = _safe_import("modules.forex.forex_runtime_controller", "ForexRuntimeController")
            before = self.snapshot()
            ticks = []
            for _ in range(max(0, int(max_ticks))):
                ticks.append(Controller().tick(max_jobs=max_jobs))
            after = self.snapshot()
            return _ok("runtime_drain_check", {"before": before, "after": after, "ticks": ticks})
        except Exception as exc:
            return _fail("runtime_drain_check", str(exc))


def run_runtime_watchdog() -> Dict[str, Any]:
    return ForexRuntimeWatchdog().check_runtime_stall()
