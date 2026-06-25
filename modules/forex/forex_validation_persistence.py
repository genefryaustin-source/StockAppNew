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

class ForexValidationPersistence:
    """File-backed persistence adapter for validation jobs, runs, notifications, and API snapshots."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or "data/forex_validation")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_path = self.base_dir / "validation_jobs.jsonl"
        self.runs_path = self.base_dir / "validation_runs.jsonl"
        self.notifications_path = self.base_dir / "validation_notifications.jsonl"

    def _append(self, path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
        return payload

    def _load(self, path: Path, limit: int = 100) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows[-int(limit):]

    def save_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(job)
        payload.setdefault("job_id", _new_id("fx_val_job"))
        payload.setdefault("created_at", _utc_now())
        payload.setdefault("status", "scheduled")
        return self._append(self.jobs_path, payload)

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._load(self.jobs_path, limit=limit)

    def save_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(run)
        payload.setdefault("run_id", _new_id("fx_val_run"))
        payload.setdefault("saved_at", _utc_now())
        return self._append(self.runs_path, payload)

    def list_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._load(self.runs_path, limit=limit)

    def latest_run(self) -> Dict[str, Any]:
        runs = self.list_runs(limit=1)
        return runs[0] if runs else {"status": "empty", "checked_at": _utc_now()}

    def save_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(notification)
        payload.setdefault("notification_id", _new_id("fx_val_note"))
        payload.setdefault("created_at", _utc_now())
        return self._append(self.notifications_path, payload)

    def list_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._load(self.notifications_path, limit=limit)

    def snapshot(self) -> Dict[str, Any]:
        jobs = self.list_jobs(limit=100)
        runs = self.list_runs(limit=100)
        notifications = self.list_notifications(limit=100)
        return {
            "status": "ready",
            "jobs": jobs,
            "runs": runs,
            "notifications": notifications,
            "summary": {
                "jobs": len(jobs),
                "runs": len(runs),
                "notifications": len(notifications),
            },
            "checked_at": _utc_now(),
        }

    def clear(self) -> Dict[str, Any]:
        for path in [self.jobs_path, self.runs_path, self.notifications_path]:
            if path.exists():
                path.unlink()
        return {"status": "cleared", "base_dir": str(self.base_dir), "cleared_at": _utc_now()}
