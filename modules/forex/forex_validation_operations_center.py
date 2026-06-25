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

class ForexValidationOperationsCenter:
    """Operational snapshot center for validation jobs, runs, notifications, health, and release readiness."""

    def snapshot(self) -> Dict[str, Any]:
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")

        persistence = Persistence()
        data = persistence.snapshot()
        latest = persistence.latest_run()

        try:
            status = Center().status()
        except Exception as exc:
            status = {"status": "unavailable", "error": str(exc), "checked_at": _utc_now()}

        runs = data.get("runs", [])
        failed_runs = [r for r in runs if not _is_success(r)]
        passed_runs = [r for r in runs if _is_success(r)]

        return {
            "status": "healthy" if status.get("status") == "healthy" and not failed_runs else "degraded" if failed_runs else status.get("status", "unknown"),
            "summary": {
                "scheduled_jobs": len(data.get("jobs", [])),
                "validation_runs": len(runs),
                "passed_runs": len(passed_runs),
                "failed_runs": len(failed_runs),
                "notifications": len(data.get("notifications", [])),
            },
            "latest_run": latest,
            "health": status,
            "jobs": data.get("jobs", []),
            "runs": runs,
            "notifications": data.get("notifications", []),
            "checked_at": _utc_now(),
        }

    def latest_result(self) -> Dict[str, Any]:
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        return Persistence().latest_run()

    def clear_validation_state(self) -> Dict[str, Any]:
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        return Persistence().clear()
