from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class LegalEscalationLevel(str, Enum):
    REMINDER = "reminder"
    MANAGER = "manager"
    TENANT_ADMIN = "tenant_admin"
    SUPER_ADMIN = "super_admin"


class LegalOverrideReason(str, Enum):
    ACCESSIBILITY = "accessibility"
    LEGAL_HOLD = "legal_hold"
    SUPPORT_EXCEPTION = "support_exception"
    SYSTEM_ERROR = "system_error"
    COUNSEL_DIRECTION = "counsel_direction"
    EMERGENCY = "emergency"
    OTHER = "other"


@dataclass(frozen=True)
class LegalEscalationRecord:
    id: str
    acknowledgement_id: str
    level: LegalEscalationLevel
    recipient_user_id: Optional[str]
    recipient_email: Optional[str]
    created_at: str
    notification_key: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegalAccessOverride:
    id: str
    user_id: str
    tenant_id: Optional[str]
    acknowledgement_id: Optional[str]
    document_key: Optional[str]
    reason: LegalOverrideReason
    justification: str
    created_by: str
    created_at: str
    expires_at: Optional[str]
    revoked_at: Optional[str] = None
    revoked_by: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegalEvidencePackage:
    generated_at: str
    generated_by: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    document_key: Optional[str]
    payload: Mapping[str, Any]
