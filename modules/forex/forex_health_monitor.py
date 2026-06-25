from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ForexHealthMonitor:
    """Lightweight health monitor for Forex runtime state."""

    def __init__(self, db: Any = None, user: Any = None) -> None:
        self.db = db
        self.user = user

    def snapshot(self) -> Dict[str, Any]:
        health: Dict[str, Any] = {
            "status": "healthy",
            "checked_at": _now(),
            "components": [],
            "summary": {},
            "warnings": [],
            "errors": [],
        }
        try:
            from modules.forex.forex_operations_center import ForexOperationsCenter

            snap = ForexOperationsCenter().snapshot()
            summary = snap.get("summary", {}) if isinstance(snap, dict) else {}
            total = int(summary.get("total_jobs", 0) or 0)
            open_jobs = int(summary.get("open_jobs", 0) or 0)
            failed = int(summary.get("failed_jobs", 0) or 0)
            succeeded = int(summary.get("succeeded_jobs", 0) or 0)
            health["summary"] = {
                "total_jobs": total,
                "open_jobs": open_jobs,
                "succeeded_jobs": succeeded,
                "failed_jobs": failed,
                "success_rate": round((succeeded / total) * 100, 2) if total else 100.0,
            }
            health["components"].append({"name": "Operations Center", "status": "healthy"})
            if failed > 0:
                health["warnings"].append(f"{failed} failed jobs detected.")
                health["status"] = "degraded"
            if total > 0 and open_jobs == total:
                health["warnings"].append("All jobs are open; runtime may not have executed yet.")
        except Exception as exc:
            health["status"] = "unhealthy"
            health["errors"].append(f"Operations snapshot failed: {exc}")
            health["components"].append({"name": "Operations Center", "status": "unhealthy", "error": str(exc)})

        for module_path, object_name, name in [
            ("modules.forex.forex_scheduler", "ForexScheduler", "Scheduler"),
            ("modules.forex.forex_runtime_controller", "ForexRuntimeController", "Runtime Controller"),
            ("modules.forex.forex_job_registry", "ForexJobRegistry", "Job Registry"),
            ("modules.forex.forex_execution_queue", "ForexExecutionQueue", "Execution Queue"),
            ("modules.forex.forex_autonomous_optimizer", "ForexAutonomousOptimizer", "Autonomous Optimizer"),
        ]:
            try:
                module = __import__(module_path, fromlist=[object_name])
                getattr(module, object_name)
                health["components"].append({"name": name, "status": "healthy"})
            except Exception as exc:
                health["status"] = "unhealthy"
                health["errors"].append(f"{name} import failed: {exc}")
                health["components"].append({"name": name, "status": "unhealthy", "error": str(exc)})
        return health

    def health_score(self) -> Dict[str, Any]:
        snap = self.snapshot()
        components = snap.get("components", [])
        total = len(components)
        healthy = sum(1 for c in components if c.get("status") == "healthy")
        score = round((healthy / total) * 100, 2) if total else 0.0
        return {"status": snap.get("status"), "score": score, "healthy_components": healthy, "total_components": total, "snapshot": snap}

    def is_healthy(self) -> bool:
        return self.snapshot().get("status") == "healthy"
