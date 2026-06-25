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

try:
    import streamlit as st
except Exception:
    st = None

try:
    import pandas as pd
except Exception:
    pd = None


class ForexValidationAuditLog:
    """Simple file-backed audit log for validation UI and command events."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or "data/forex_validation/audit_events.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        event_type: str,
        action: str,
        user: Any = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = {
            "audit_id": _new_id("fx_val_audit"),
            "event_type": event_type,
            "action": action,
            "user_id": _get_user_value(user, "id", _get_user_value(user, "user_id", None)),
            "email": _get_user_value(user, "email", None),
            "role": _get_user_value(user, "role", None),
            "payload": payload or {},
            "created_at": _utc_now(),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
        return event

    def load(self, limit: int = 250) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows[-int(limit):]

    def summary(self) -> Dict[str, Any]:
        rows = self.load(limit=1000)
        by_type: Dict[str, int] = {}
        by_action: Dict[str, int] = {}
        for row in rows:
            by_type[row.get("event_type", "unknown")] = by_type.get(row.get("event_type", "unknown"), 0) + 1
            by_action[row.get("action", "unknown")] = by_action.get(row.get("action", "unknown"), 0) + 1
        return {
            "status": "completed",
            "total_events": len(rows),
            "by_type": by_type,
            "by_action": by_action,
            "checked_at": _utc_now(),
        }

    def clear(self) -> Dict[str, Any]:
        if self.path.exists():
            self.path.unlink()
        return {"status": "cleared", "path": str(self.path), "cleared_at": _utc_now()}


def render_forex_validation_audit_dashboard(db=None, user=None) -> None:
    if st is None:
        return

    st.title("Forex Validation Audit Dashboard")
    st.caption("Audit trail for validation access, commands, release checks, reports, and administrative actions.")

    Audit = ForexValidationAuditLog()
    Permissions = _safe_import(
        "modules.forex.forex_validation_permission_engine",
        "ForexValidationPermissionEngine",
    )
    permission_engine = Permissions()

    permission = permission_engine.require(user=user, action="audit")
    if not permission.get("allowed"):
        st.warning("You do not have permission to view Forex validation audit events.")
        st.json(permission)
        return

    Audit.record(
        event_type="dashboard_access",
        action="view_audit_dashboard",
        user=user,
        payload={"permission": permission},
    )

    summary = Audit.summary()
    c1, c2, c3 = st.columns(3)
    c1.metric("Audit Events", summary.get("total_events", 0))
    c2.metric("Role", permission.get("role", "unknown"))
    c3.metric("Permission", permission.get("status", "unknown").upper())

    st.subheader("Audit Summary")
    st.json({
        "by_type": summary.get("by_type", {}),
        "by_action": summary.get("by_action", {}),
    })

    col1, col2, col3 = st.columns(3)

    if col1.button("Record Test Audit Event", key="fx_val_audit_test"):
        event = Audit.record(
            event_type="manual_test",
            action="record_test_event",
            user=user,
            payload={"source": "audit_dashboard"},
        )
        st.json(event)

    if col2.button("Refresh Audit Events", key="fx_val_audit_refresh"):
        st.rerun()

    if col3.button("Clear Audit Log", key="fx_val_audit_clear"):
        clear_perm = permission_engine.require(user=user, action="clear")
        if clear_perm.get("allowed"):
            st.json(Audit.clear())
        else:
            st.warning("You do not have permission to clear the audit log.")
            st.json(clear_perm)

    rows = Audit.load(limit=250)
    st.subheader("Recent Audit Events")
    if rows:
        if pd is not None:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.json(rows)
    else:
        st.info("No audit events recorded yet.")
