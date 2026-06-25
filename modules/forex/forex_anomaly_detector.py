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

class ForexAnomalyDetector:
    """Detects basic anomalies in operations snapshots and validation results."""

    def detect_snapshot_anomalies(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        anomalies: List[Dict[str, Any]] = []
        if snapshot is None:
            try:
                Center = _safe_import("modules.forex.forex_operations_center", "ForexOperationsCenter")
                snapshot = Center().snapshot()
            except Exception as exc:
                return _fail("snapshot_anomaly_detection", str(exc))

        summary = snapshot.get("summary", {})
        total = int(summary.get("total_jobs", 0) or 0)
        open_jobs = int(summary.get("open_jobs", 0) or 0)
        succeeded = int(summary.get("succeeded_jobs", 0) or 0)
        failed = int(summary.get("failed_jobs", 0) or 0)

        if failed > 0:
            anomalies.append({"type": "failed_jobs", "severity": "high", "count": failed})
        if open_jobs > total:
            anomalies.append({"type": "open_exceeds_total", "severity": "critical", "open_jobs": open_jobs, "total_jobs": total})
        if succeeded + failed > total:
            anomalies.append({"type": "terminal_exceeds_total", "severity": "critical", "succeeded": succeeded, "failed": failed, "total": total})
        if total > 0 and open_jobs == total:
            anomalies.append({"type": "no_progress_detected", "severity": "medium", "open_jobs": open_jobs, "total": total})

        return {
            "status": "clear" if not anomalies else "anomalies_detected",
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "summary": summary,
            "checked_at": _utc_now(),
        }

    def detect_result_anomalies(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        failures = [r for r in results if not r.get("passed", r.get("status") in ("pass", "success", "healthy"))]
        return {
            "status": "clear" if not failures else "failures_detected",
            "failure_count": len(failures),
            "failures": failures,
            "checked_at": _utc_now(),
        }


def run_anomaly_detection() -> Dict[str, Any]:
    return ForexAnomalyDetector().detect_snapshot_anomalies()
