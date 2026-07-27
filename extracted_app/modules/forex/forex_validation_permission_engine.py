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

class ForexValidationPermissionEngine:
    """Permission checks for Forex validation actions."""

    DEFAULT_ROLE_PERMISSIONS = {
        "admin": {
            "view", "run", "schedule", "stress", "release", "reports", "history", "audit", "clear"
        },
        "owner": {
            "view", "run", "schedule", "stress", "release", "reports", "history", "audit", "clear"
        },
        "manager": {
            "view", "run", "schedule", "reports", "history", "audit"
        },
        "analyst": {
            "view", "run", "reports"
        },
        "viewer": {
            "view"
        },
        "user": {
            "view", "run"
        },
    }

    def role_for_user(self, user: Any = None) -> str:
        role = _get_user_value(user, "role", None)
        if not role:
            role = _get_user_value(user, "user_role", None)
        return str(role or "viewer").lower()

    def permissions_for_role(self, role: str) -> List[str]:
        return sorted(self.DEFAULT_ROLE_PERMISSIONS.get(str(role).lower(), {"view"}))

    def can(self, user: Any = None, action: str = "view") -> bool:
        role = self.role_for_user(user)
        permissions = self.DEFAULT_ROLE_PERMISSIONS.get(role, {"view"})
        return str(action).lower() in permissions

    def require(self, user: Any = None, action: str = "view") -> Dict[str, Any]:
        allowed = self.can(user=user, action=action)
        return {
            "status": "allowed" if allowed else "denied",
            "allowed": allowed,
            "action": action,
            "role": self.role_for_user(user),
            "permissions": self.permissions_for_role(self.role_for_user(user)),
            "checked_at": _utc_now(),
        }

    def guard(self, user: Any = None, action: str = "view") -> None:
        result = self.require(user=user, action=action)
        if not result["allowed"]:
            raise PermissionError(
                f"Forex validation permission denied for action={action}, role={result['role']}"
            )

    def permission_matrix(self) -> Dict[str, Any]:
        return {
            "status": "completed",
            "matrix": {
                role: sorted(list(perms))
                for role, perms in self.DEFAULT_ROLE_PERMISSIONS.items()
            },
            "generated_at": _utc_now(),
        }


def can_run_forex_validation(user: Any = None) -> bool:
    return ForexValidationPermissionEngine().can(user=user, action="run")
