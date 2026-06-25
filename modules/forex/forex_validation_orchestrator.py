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

class ForexValidationOrchestrator:
    """Coordinates scheduled validation, release checks, reporting, notifications, and persistence."""

    def run_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
        Notifications = _safe_import("modules.forex.forex_validation_notification_engine", "ForexValidationNotificationEngine")
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")

        validation_type = str(job.get("validation_type", "full"))
        include_stress = bool(job.get("include_stress", False))
        stress_jobs = int(job.get("stress_jobs", 100) or 100)

        if validation_type == "predeployment":
            Validator = _safe_import("modules.forex.forex_predeployment_validator", "ForexPredeploymentValidator")
            result = Validator().run()
        elif validation_type == "release":
            Validator = _safe_import("modules.forex.forex_release_validator", "ForexReleaseValidator")
            result = Validator().validate()
        else:
            result = Center().run_full_validation(
                include_stress=include_stress,
                stress_jobs=stress_jobs,
            )

        run = {
            "run_id": _new_id("fx_val_run"),
            "job": job,
            "status": result.get("status", "completed"),
            "passed": _is_success(result),
            "result": result,
            "completed_at": _utc_now(),
        }

        Persistence().save_run(run)
        Notifications().notify_from_validation(result if isinstance(result, dict) else run)

        return run

    def run_pending(self, max_jobs: int = 5) -> Dict[str, Any]:
        Scheduler = _safe_import("modules.forex.forex_validation_scheduler", "ForexValidationScheduler")
        jobs = Scheduler().pending_jobs(limit=100)
        executed: List[Dict[str, Any]] = []
        for job in jobs[: int(max_jobs)]:
            executed.append(self.run_job(job))
        return {
            "status": "completed",
            "requested": int(max_jobs),
            "available": len(jobs),
            "executed": len(executed),
            "runs": executed,
            "completed_at": _utc_now(),
        }

    def run_now(self, include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
        job = {
            "job_id": _new_id("fx_val_job"),
            "validation_type": "full",
            "include_stress": include_stress,
            "stress_jobs": stress_jobs,
            "frequency": "manual",
            "status": "scheduled",
            "scheduled_at": _utc_now(),
            "run_after": _utc_now(),
        }
        return self.run_job(job)

    def release_check(self) -> Dict[str, Any]:
        job = {
            "job_id": _new_id("fx_val_job"),
            "validation_type": "release",
            "include_stress": True,
            "stress_jobs": 1000,
            "frequency": "manual",
            "status": "scheduled",
            "scheduled_at": _utc_now(),
            "run_after": _utc_now(),
        }
        return self.run_job(job)
