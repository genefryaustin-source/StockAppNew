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

class ForexValidationNotificationEngine:
    """Creates validation notifications for failures, regressions, and release blockers."""

    def build_notification(
        self,
        event_type: str,
        severity: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "notification_id": _new_id("fx_val_note"),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "payload": payload or {},
            "created_at": _utc_now(),
            "status": "created",
        }

    def notify_from_validation(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        failed = int(validation.get("failed", 0) or 0)
        scorecard = validation.get("scorecard", {}) if isinstance(validation, dict) else {}
        score = float(scorecard.get("score", 0) or 0)

        if failed > 0:
            note = self.build_notification(
                "validation_failure",
                "high",
                f"Forex validation failed with {failed} failed checks.",
                validation,
            )
        elif score and score < 95:
            note = self.build_notification(
                "validation_score_warning",
                "medium",
                f"Forex validation score below certification threshold: {score}%.",
                validation,
            )
        else:
            note = self.build_notification(
                "validation_success",
                "info",
                "Forex validation completed successfully.",
                validation,
            )

        try:
            Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
            Persistence().save_notification(note)
        except Exception:
            pass

        return note

    def notify_regression(self, regression: Dict[str, Any]) -> Dict[str, Any]:
        score_delta = float(regression.get("score_delta", 0) or 0)
        failed_delta = int(regression.get("failed_delta", 0) or 0)
        severity = "high" if failed_delta > 0 or score_delta < -5 else "medium" if score_delta < 0 else "info"
        message = "Forex validation regression detected." if severity != "info" else "No Forex validation regression detected."
        note = self.build_notification("validation_regression", severity, message, regression)
        try:
            Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
            Persistence().save_notification(note)
        except Exception:
            pass
        return note

    def list_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        Persistence = _safe_import("modules.forex.forex_validation_persistence", "ForexValidationPersistence")
        return Persistence().list_notifications(limit=limit)
