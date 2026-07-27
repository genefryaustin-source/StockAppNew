from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _status_ok(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    status = str(value.get("status", "")).lower()
    return bool(value.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed",
        "certified", "ready", "approved", "online", "optimized"
    }

class ForexValidationSLAEngine:
    """Service-level agreement evaluator for Forex validation operations."""

    DEFAULT_SLA = {
        "min_score": 95.0,
        "max_failed_checks": 0,
        "max_failed_runs": 0,
        "max_open_validation_jobs": 100,
        "max_notifications_high": 0,
    }

    def __init__(self, sla: Optional[Dict[str, Any]] = None):
        self.sla = dict(self.DEFAULT_SLA)
        if sla:
            self.sla.update(sla)

    def evaluate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        scorecard = payload.get("scorecard", {}) if isinstance(payload, dict) else {}
        score = float(scorecard.get("score", payload.get("score", 0)) or 0)
        failed = int(payload.get("failed", scorecard.get("failed", 0)) or 0)

        checks = [
            {
                "name": "min_score",
                "target": self.sla["min_score"],
                "actual": score,
                "passed": score >= float(self.sla["min_score"]),
            },
            {
                "name": "max_failed_checks",
                "target": self.sla["max_failed_checks"],
                "actual": failed,
                "passed": failed <= int(self.sla["max_failed_checks"]),
            },
        ]

        violations = [c for c in checks if not c["passed"]]
        return {
            "status": "pass" if not violations else "fail",
            "sla": self.sla,
            "score": score,
            "failed_checks": failed,
            "checks": checks,
            "violations": violations,
            "evaluated_at": _utc_now(),
        }

    def evaluate_operations(self) -> Dict[str, Any]:
        Ops = _safe_import(
            "modules.forex.forex_validation_operations_center",
            "ForexValidationOperationsCenter",
        )
        snapshot = Ops().snapshot()
        summary = snapshot.get("summary", {})
        notifications = snapshot.get("notifications", [])

        high_notifications = [
            n for n in notifications
            if str(n.get("severity", "")).lower() in {"high", "critical"}
        ]

        checks = [
            {
                "name": "max_failed_runs",
                "target": self.sla["max_failed_runs"],
                "actual": int(summary.get("failed_runs", 0) or 0),
                "passed": int(summary.get("failed_runs", 0) or 0) <= int(self.sla["max_failed_runs"]),
            },
            {
                "name": "max_open_validation_jobs",
                "target": self.sla["max_open_validation_jobs"],
                "actual": int(summary.get("scheduled_jobs", 0) or 0),
                "passed": int(summary.get("scheduled_jobs", 0) or 0) <= int(self.sla["max_open_validation_jobs"]),
            },
            {
                "name": "max_notifications_high",
                "target": self.sla["max_notifications_high"],
                "actual": len(high_notifications),
                "passed": len(high_notifications) <= int(self.sla["max_notifications_high"]),
            },
        ]

        violations = [c for c in checks if not c["passed"]]
        return {
            "status": "pass" if not violations else "fail",
            "sla": self.sla,
            "checks": checks,
            "violations": violations,
            "snapshot": snapshot,
            "evaluated_at": _utc_now(),
        }

    def evaluate_all(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if payload is None:
            Center = _safe_import(
                "modules.forex.forex_validation_center",
                "ForexValidationCenter",
            )
            payload = Center().run_full_validation()

        payload_result = self.evaluate_payload(payload)
        operations_result = self.evaluate_operations()
        passed = _status_ok(payload_result) and _status_ok(operations_result)

        return {
            "status": "pass" if passed else "fail",
            "payload_sla": payload_result,
            "operations_sla": operations_result,
            "evaluated_at": _utc_now(),
        }


def evaluate_forex_validation_sla(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return ForexValidationSLAEngine().evaluate_all(payload)
