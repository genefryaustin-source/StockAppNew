from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _get_user_value(user: Any, key: str, default: Any = None) -> Any:
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(key, default)
    return getattr(user, key, default)

class ForexValidationMultiTenant:
    """Tenant-aware facade for Forex validation operations."""

    def resolve_tenant_id(self, user: Any = None, tenant_id: Optional[str] = None) -> str:
        if tenant_id:
            return str(tenant_id)
        for key in ("tenant_id", "tenant", "org_id", "organization_id"):
            value = _get_user_value(user, key)
            if value:
                return str(value)
        return "default"

    def tenant_context(self, user: Any = None, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        resolved = self.resolve_tenant_id(user=user, tenant_id=tenant_id)
        return {
            "tenant_id": resolved,
            "user_id": _get_user_value(user, "id", _get_user_value(user, "user_id", None)),
            "email": _get_user_value(user, "email", None),
            "role": _get_user_value(user, "role", None),
            "resolved_at": _utc_now(),
        }

    def run_for_tenant(
        self,
        user: Any = None,
        tenant_id: Optional[str] = None,
        include_stress: bool = False,
        stress_jobs: int = 100,
    ) -> Dict[str, Any]:
        context = self.tenant_context(user=user, tenant_id=tenant_id)
        Center = _safe_import(
            "modules.forex.forex_validation_center",
            "ForexValidationCenter",
        )
        result = Center().run_full_validation(
            include_stress=include_stress,
            stress_jobs=stress_jobs,
        )
        result["tenant_context"] = context
        return result

    def schedule_for_tenant(
        self,
        user: Any = None,
        tenant_id: Optional[str] = None,
        validation_type: str = "full",
        include_stress: bool = False,
        stress_jobs: int = 100,
    ) -> Dict[str, Any]:
        context = self.tenant_context(user=user, tenant_id=tenant_id)
        Scheduler = _safe_import(
            "modules.forex.forex_validation_scheduler",
            "ForexValidationScheduler",
        )
        job = Scheduler().schedule_validation(
            validation_type=validation_type,
            include_stress=include_stress,
            stress_jobs=stress_jobs,
        )
        job["tenant_context"] = context
        return job

    def tenant_snapshot(self, user: Any = None, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        context = self.tenant_context(user=user, tenant_id=tenant_id)
        Ops = _safe_import(
            "modules.forex.forex_validation_operations_center",
            "ForexValidationOperationsCenter",
        )
        snapshot = Ops().snapshot()
        snapshot["tenant_context"] = context
        return snapshot

    def list_supported_scopes(self) -> Dict[str, Any]:
        return {
            "status": "completed",
            "scopes": [
                "tenant_validation_run",
                "tenant_validation_schedule",
                "tenant_validation_snapshot",
                "tenant_validation_reports",
            ],
            "generated_at": _utc_now(),
        }
