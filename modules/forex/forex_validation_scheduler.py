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

class ForexValidationScheduler:
    """Schedules validation jobs for manual, recurring, predeployment, and release-readiness runs."""

    def schedule_validation(
        self,
        validation_type: str = "full",
        include_stress: bool = False,
        stress_jobs: int = 100,
        frequency: str = "manual",
        run_after_seconds: int = 0,
    ) -> Dict[str, Any]:
        run_after = datetime.now(timezone.utc) + timedelta(seconds=int(run_after_seconds or 0))
        job = {
            "job_id": _new_id("fx_val_job"),
            "validation_type": validation_type,
            "include_stress": bool(include_stress),
            "stress_jobs": int(stress_jobs),
            "frequency": frequency,
            "status": "scheduled",
            "scheduled_at": _utc_now(),
            "run_after": run_after.replace(microsecond=0).isoformat(),
        }
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        return Persistence().save_job(job)

    def schedule_full_validation(self) -> Dict[str, Any]:
        return self.schedule_validation(validation_type="full", include_stress=False)

    def schedule_nightly_validation(self, include_stress: bool = True, stress_jobs: int = 1000) -> Dict[str, Any]:
        return self.schedule_validation(
            validation_type="nightly",
            include_stress=include_stress,
            stress_jobs=stress_jobs,
            frequency="daily",
        )

    def schedule_predeployment_validation(self) -> Dict[str, Any]:
        return self.schedule_validation(
            validation_type="predeployment",
            include_stress=True,
            stress_jobs=1000,
            frequency="manual",
        )

    def schedule_release_validation(self) -> Dict[str, Any]:
        return self.schedule_validation(
            validation_type="release",
            include_stress=True,
            stress_jobs=1000,
            frequency="manual",
        )

    def pending_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        jobs = Persistence().list_jobs(limit=limit)
        now = datetime.now(timezone.utc)
        pending: List[Dict[str, Any]] = []
        for job in jobs:
            if job.get("status") != "scheduled":
                continue
            try:
                run_after = datetime.fromisoformat(str(job.get("run_after")))
                if run_after.tzinfo is None:
                    run_after = run_after.replace(tzinfo=timezone.utc)
            except Exception:
                run_after = now
            if run_after <= now:
                pending.append(job)
        return pending

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        return Persistence().list_jobs(limit=limit)
