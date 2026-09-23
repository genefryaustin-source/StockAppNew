from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional


class LegalDocumentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    RETIRED = "retired"


class LegalReviewDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class AcknowledgementStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


@dataclass(frozen=True)
class LegalDocumentVersion:
    id: str
    document_key: str
    version: str
    status: LegalDocumentStatus
    effective_date: str
    summary: str
    created_at: str
    created_by: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    published_at: Optional[str] = None
    retired_at: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegalReviewRecord:
    id: str
    document_version_id: str
    reviewer_user_id: str
    decision: LegalReviewDecision
    comments: str
    created_at: str


@dataclass(frozen=True)
class LegalAcknowledgement:
    id: str
    document_key: str
    document_version: str
    user_id: str
    tenant_id: Optional[str]
    status: AcknowledgementStatus
    requested_at: str
    due_at: Optional[str] = None
    responded_at: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegalWorkflowSummary:
    total_versions: int
    drafts: int
    in_review: int
    approved: int
    published: int
    retired: int
    pending_acknowledgements: int
    accepted_acknowledgements: int
    declined_acknowledgements: int
