"""In-memory/session-safe execution audit helpers for Streamlit UI."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import uuid


def audit_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "audit_id": str(uuid.uuid4()),
        "event_type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def append_audit_log(log: list[dict[str, Any]], event_type: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    log = list(log or [])
    log.append(audit_event(event_type, payload))
    return log[-250:]
