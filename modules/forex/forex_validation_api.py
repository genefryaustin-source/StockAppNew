from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _is_success(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    return bool(payload.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed",
        "certified", "ready", "saved", "exported", "scheduled"
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

class ForexValidationAPI:
    """Thin application-facing API facade for Forex validation automation and dashboards."""

    def status(self) -> Dict[str, Any]:
        Ops = _safe_import("modules.forex.forex_validation_operations_center", "ForexValidationOperationsCenter")
        return Ops().snapshot()

    def schedule(self, validation_type: str = "full", include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
        Scheduler = _safe_import("modules.forex.forex_validation_scheduler", "ForexValidationScheduler")
        return Scheduler().schedule_validation(
            validation_type=validation_type,
            include_stress=include_stress,
            stress_jobs=stress_jobs,
        )

    def run(self, include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
        Runtime = _safe_import("modules.forex.forex_validation_runtime_controller", "ForexValidationRuntimeController")
        return Runtime().run_once(include_stress=include_stress, stress_jobs=stress_jobs)

    def tick(self, max_jobs: int = 5) -> Dict[str, Any]:
        Runtime = _safe_import("modules.forex.forex_validation_runtime_controller", "ForexValidationRuntimeController")
        return Runtime().tick(max_jobs=max_jobs)

    def release_check(self) -> Dict[str, Any]:
        Runtime = _safe_import("modules.forex.forex_validation_runtime_controller", "ForexValidationRuntimeController")
        return Runtime().release_tick()

    def latest(self) -> Dict[str, Any]:
        Ops = _safe_import("modules.forex.forex_validation_operations_center", "ForexValidationOperationsCenter")
        return Ops().latest_result()

    def reports(self) -> Dict[str, Any]:
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
        payload = Center().run_full_validation()
        return Center().generate_reports(payload)

    def notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        Notifications = _safe_import("modules.forex.forex_validation_notification_engine", "ForexValidationNotificationEngine")
        return Notifications().list_notifications(limit=limit)


def forex_validation_status() -> Dict[str, Any]:
    return ForexValidationAPI().status()


def run_forex_validation(include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
    return ForexValidationAPI().run(include_stress=include_stress, stress_jobs=stress_jobs)
