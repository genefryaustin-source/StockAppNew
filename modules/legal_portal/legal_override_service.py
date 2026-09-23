from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .legal_audit import emit_legal_event
from .legal_escalation_models import (
    LegalAccessOverride,
    LegalOverrideReason,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


class InMemoryLegalOverrideRepository:
    def __init__(self) -> None:
        self._records: dict[str, LegalAccessOverride] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        user_id: str,
        tenant_id: str | None,
        acknowledgement_id: str | None,
        document_key: str | None,
        reason: LegalOverrideReason,
        justification: str,
        created_by: str,
        expires_at: str | None,
    ) -> LegalAccessOverride:
        with self._lock:
            record = LegalAccessOverride(
                id=str(uuid4()),
                user_id=user_id,
                tenant_id=tenant_id,
                acknowledgement_id=acknowledgement_id,
                document_key=document_key,
                reason=reason,
                justification=justification,
                created_by=created_by,
                created_at=utc_now_iso(),
                expires_at=expires_at,
            )
            self._records[record.id] = record
            return record

    def list(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[LegalAccessOverride]:
        with self._lock:
            records = list(self._records.values())

            if user_id:
                records = [item for item in records if item.user_id == user_id]
            if tenant_id:
                records = [item for item in records if item.tenant_id == tenant_id]

            return sorted(records, key=lambda item: item.created_at, reverse=True)

    def revoke(
        self,
        override_id: str,
        *,
        revoked_by: str,
    ) -> LegalAccessOverride:
        with self._lock:
            current = self._records.get(override_id)

            if current is None:
                raise KeyError(f"Unknown legal override: {override_id}")

            updated = replace(
                current,
                revoked_at=utc_now_iso(),
                revoked_by=revoked_by,
            )
            self._records[override_id] = updated
            return updated


def is_override_active(
    override: LegalAccessOverride,
    *,
    now: datetime | None = None,
) -> bool:
    if override.revoked_at:
        return False

    expiry = _parse_datetime(override.expires_at)

    if expiry is None:
        return True

    return expiry > (now or datetime.now(timezone.utc))


class LegalOverrideService:
    def __init__(
        self,
        repository: InMemoryLegalOverrideRepository,
        audit_sink=None,
    ) -> None:
        self.repository = repository
        self.audit_sink = audit_sink

    def create_override(
        self,
        *,
        user_id: str,
        tenant_id: str | None,
        acknowledgement_id: str | None,
        document_key: str | None,
        reason: LegalOverrideReason,
        justification: str,
        created_by: str,
        expires_at: str | None,
    ) -> LegalAccessOverride:
        if not justification.strip():
            raise ValueError("Override justification is required.")

        record = self.repository.create(
            user_id=user_id,
            tenant_id=tenant_id,
            acknowledgement_id=acknowledgement_id,
            document_key=document_key,
            reason=reason,
            justification=justification.strip(),
            created_by=created_by,
            expires_at=expires_at,
        )

        emit_legal_event(
            "LEGAL_ACCESS_OVERRIDE_CREATED",
            document_key=document_key,
            user_id=created_by,
            tenant_id=tenant_id,
            metadata={
                "override_id": record.id,
                "target_user_id": user_id,
                "reason": reason.value,
                "expires_at": expires_at,
            },
            sink=self.audit_sink,
        )

        return record

    def revoke_override(
        self,
        *,
        override_id: str,
        revoked_by: str,
        tenant_id: str | None,
    ) -> LegalAccessOverride:
        record = self.repository.revoke(
            override_id,
            revoked_by=revoked_by,
        )

        emit_legal_event(
            "LEGAL_ACCESS_OVERRIDE_REVOKED",
            document_key=record.document_key,
            user_id=revoked_by,
            tenant_id=tenant_id,
            metadata={"override_id": record.id},
            sink=self.audit_sink,
        )

        return record

    def active_for_user(
        self,
        *,
        user_id: str,
        tenant_id: str | None,
    ) -> list[LegalAccessOverride]:
        return [
            item
            for item in self.repository.list(
                user_id=user_id,
                tenant_id=tenant_id,
            )
            if is_override_active(item)
        ]


_OVERRIDE_REPOSITORY = InMemoryLegalOverrideRepository()
_OVERRIDE_SERVICE = LegalOverrideService(_OVERRIDE_REPOSITORY)


def get_legal_override_service() -> LegalOverrideService:
    return _OVERRIDE_SERVICE
