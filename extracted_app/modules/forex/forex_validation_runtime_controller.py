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

class ForexValidationRuntimeController:
    """Runtime controller for executing validation jobs and continuous validation ticks."""

    def tick(self, max_jobs: int = 5) -> Dict[str, Any]:
        Orchestrator = _safe_import("modules.forex.forex_validation_orchestrator", "ForexValidationOrchestrator")
        return Orchestrator().run_pending(max_jobs=max_jobs)

    def run_once(self, include_stress: bool = False, stress_jobs: int = 100) -> Dict[str, Any]:
        Orchestrator = _safe_import("modules.forex.forex_validation_orchestrator", "ForexValidationOrchestrator")
        return Orchestrator().run_now(include_stress=include_stress, stress_jobs=stress_jobs)

    def run_continuous_cycle(self, include_stress: bool = False) -> Dict[str, Any]:
        Engine = _safe_import("modules.forex.forex_continuous_validation_engine", "ForexContinuousValidationEngine")
        return Engine().run_cycle(include_stress=include_stress)

    def release_tick(self) -> Dict[str, Any]:
        Orchestrator = _safe_import("modules.forex.forex_validation_orchestrator", "ForexValidationOrchestrator")
        return Orchestrator().release_check()
