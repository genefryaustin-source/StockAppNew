from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
import uuid


def audit_event(event_type: str, actor: str = 'system', details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {'id': str(uuid.uuid4()), 'event_type': event_type, 'actor': actor, 'details': details or {}, 'created_at': datetime.now(timezone.utc).isoformat()}
