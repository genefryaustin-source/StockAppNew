"""
API Key Authentication

Provides API key generation and validation for:

    • Third-party applications
    • Enterprise integrations
    • AI agents
    • Partner platforms
    • Internal services

Database-backed via modules.db.models.PlatformAPIKey. The raw key is
never stored -- only a SHA-256 hash of it, plus a short prefix/suffix
for display purposes (e.g. "sk_live_...a1B2"). A high-entropy random
token like this doesn't need a slow password-hashing KDF (bcrypt,
scrypt, argon2) the way a human-chosen password would; a fast one-way
hash is the correct, standard choice here (the same approach GitHub,
Stripe, and most API platforms use for API keys specifically, as
opposed to passwords).

Not to be confused with modules.admin.tenant_api_keys, which manages
each tenant's own outbound credentials for third-party providers
(Polygon, Anthropic, etc.). This module is the inbound direction:
credentials external callers present to authenticate against this
app's own REST API.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, UTC
from typing import Optional

from api.auth.models import APIClient

logger = logging.getLogger(__name__)


class APIKeyService:
    """
    API key generation, validation, and lifecycle management.
    Database-backed -- every method that reads or writes a key takes a
    db session.
    """

    # ---------------------------------------------------------
    # Generate Key
    # ---------------------------------------------------------

    def generate_key(
        self,
        prefix: str = "sk_live",
    ) -> str:
        """
        Generate a cryptographically secure API key. The full raw key
        is only ever available at creation time (see create_key) --
        it's never persisted and can't be recovered afterward, only
        revoked and replaced with a new one.
        """

        token = secrets.token_urlsafe(32)

        return f"{prefix}_{token}"

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _suffix(raw_key: str, length: int = 4) -> str:
        return raw_key[-length:] if len(raw_key) >= length else raw_key

    def has_platform_api_access(self, db, tenant_id: str) -> bool:
        """
        Public entry point for "would create_key/validate_key currently
        let this tenant through" -- accounts for the development-mode
        exemption, unlike reading Tenant.platform_api_access_enabled
        directly (which is the raw configured value a super admin sets,
        useful on its own for the tenant-management screen, but
        misleading for a "can this tenant create keys right now"
        warning banner in dev mode).
        """
        return self._tenant_has_api_access(db, tenant_id)

    @staticmethod
    def _tenant_has_api_access(db, tenant_id: str) -> bool:
        """
        Whether tenant_id is allowed to use the external platform API at
        all -- the super-admin-controlled gate on modules.db.models.
        Tenant.platform_api_access_enabled (see
        modules.admin.tenant_service.set_platform_api_access). Defaults
        closed: a tenant that doesn't exist, or exists but was never
        explicitly granted access, has no access. Never raises --
        returns False on any lookup failure, since "can't tell" should
        fail closed here, not open.

        Exempt in development mode, the same as every other auth/access
        check in this app (see api.auth.dependencies.get_current_user
        and api.auth.jwt._ensure_secret_is_safe_to_use) -- otherwise the
        dev bypass's hardcoded tenant_default, which has no gate enabled
        by default, would be blocked from creating or using API keys
        even though is_super_admin=True satisfies every permission
        check. This gate is a separate, tenant-level mechanism from
        permissions, so the super-admin bypass doesn't cover it on its
        own; this exemption is what does.
        """
        from api.config import settings

        if settings.environment.lower() == "development":
            return True

        try:
            from modules.db.models import Tenant

            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
            return tenant is not None and bool(tenant.platform_api_access_enabled)
        except Exception:
            logger.exception("Tenant API access check failed | tenant_id=%s", tenant_id)
            try:
                db.rollback()
            except Exception:
                pass
            return False

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_key(
        self,
        db,
        *,
        tenant_id: str,
        name: str,
        permissions: list[str] | None = None,
        rate_limit_per_minute: int = 100,
        expires_at: datetime | None = None,
        created_by_user_id: str | None = None,
        prefix: str = "sk_live",
    ):
        """
        Generate and persist a new API key. Returns
        (raw_key, record, error_reason) -- raw_key is shown to the
        caller exactly once, here, and never again; only its hash is
        stored. On failure, raw_key and record are both None and
        error_reason explains why: either the tenant hasn't been
        granted platform API access (a super admin needs to turn that
        on first -- see modules.admin.tenant_service.
        set_platform_api_access), or a database error occurred. Never
        raises.
        """

        if not self._tenant_has_api_access(db, tenant_id):
            return None, None, (
                "This tenant does not have external platform API access "
                "enabled. A super admin needs to turn this on for the "
                "tenant before any API keys can be created."
            )

        from modules.db.models import PlatformAPIKey

        raw_key = self.generate_key(prefix=prefix)

        record = PlatformAPIKey(
            tenant_id=tenant_id,
            name=name,
            key_prefix=prefix,
            key_hash=self._hash_key(raw_key),
            key_suffix=self._suffix(raw_key),
            permissions=json.dumps(permissions or []),
            rate_limit_per_minute=rate_limit_per_minute,
            is_active=True,
            created_by_user_id=created_by_user_id,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )

        try:
            db.add(record)
            db.commit()
        except Exception:
            logger.exception("Failed to create API key | tenant_id=%s", tenant_id)
            try:
                db.rollback()
            except Exception:
                pass
            return None, None, "Unable to create API key due to a database error."

        return raw_key, record, None

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    def validate_key(
        self,
        db,
        api_key: str,
    ) -> Optional[APIClient]:
        """
        Validate a presented API key against the database. Checks
        active status, expiration, AND the tenant's current platform
        API access gate -- unlike the creation-time check, this runs
        on every single authentication, so a super admin revoking a
        tenant's access takes effect immediately for every existing
        key that tenant has, not just future key creation. Updates
        last_used_at on success. Never raises -- returns None on any
        failure (not found, inactive, expired, tenant access revoked,
        or a database error), which the caller (AuthenticationManager)
        turns into a 401. Deliberately doesn't distinguish which of
        these it was in the response -- an anonymous caller doesn't
        need to know their tenant was gated versus their key being
        simply wrong.
        """

        if not api_key or db is None:
            return None

        from modules.db.models import PlatformAPIKey

        key_hash = self._hash_key(api_key)

        try:
            record = (
                db.query(PlatformAPIKey)
                .filter(PlatformAPIKey.key_hash == key_hash)
                .one_or_none()
            )
        except Exception:
            logger.exception("API key lookup failed.")
            try:
                db.rollback()
            except Exception:
                pass
            return None

        if record is None:
            return None

        if not record.is_active or record.revoked_at is not None:
            return None

        if record.expires_at is not None:
            now_naive = datetime.now(UTC).replace(tzinfo=None)
            expires_naive = record.expires_at.replace(tzinfo=None)
            if expires_naive < now_naive:
                return None

        if not self._tenant_has_api_access(db, record.tenant_id):
            return None

        try:
            record.last_used_at = datetime.now(UTC)
            db.commit()
        except Exception:
            logger.exception("Failed to update API key last_used_at.")
            try:
                db.rollback()
            except Exception:
                pass

        try:
            permissions = json.loads(record.permissions or "[]")
        except (TypeError, ValueError):
            permissions = []

        return APIClient(
            client_id=record.id,
            client_name=record.name,
            tenant_id=record.tenant_id,
            active=record.is_active,
            permissions=permissions,
            rate_limit_per_minute=record.rate_limit_per_minute,
            expires_at=record.expires_at,
        )

    def exists(
        self,
        db,
        api_key: str,
    ) -> bool:

        return self.validate_key(db, api_key) is not None

    # ---------------------------------------------------------
    # List / Get / Update / Revoke / Rotate
    # ---------------------------------------------------------
    #
    # Every method below takes an optional tenant_id: pass the caller's
    # own tenant_id for tenant self-service (the key must belong to
    # that tenant or the operation fails), or None for super-admin use
    # (operates across every tenant). Routers, not this service, decide
    # which mode applies based on the caller's permissions -- this
    # service just enforces whatever scope it's given.

    def list_keys(self, db, *, tenant_id: Optional[str] = None):
        """
        API keys, metadata only -- never the raw key or even its hash.
        Scoped to tenant_id if given, otherwise every tenant's keys
        (super-admin use). Never raises; returns [] on failure.
        """

        from modules.db.models import PlatformAPIKey

        try:
            query = db.query(PlatformAPIKey)

            if tenant_id is not None:
                query = query.filter(PlatformAPIKey.tenant_id == tenant_id)

            return query.order_by(PlatformAPIKey.created_at.desc()).all()

        except Exception:
            logger.exception("Failed to list API keys | tenant_id=%s", tenant_id)
            try:
                db.rollback()
            except Exception:
                pass
            return []

    def get_key(self, db, *, key_id: str, tenant_id: Optional[str] = None):
        """
        Single key by id. Scoped to tenant_id if given (returns None if
        the key exists but belongs to a different tenant -- same
        externally-observable result as not existing, so a self-service
        caller can't distinguish "not mine" from "doesn't exist").
        Never raises.
        """

        from modules.db.models import PlatformAPIKey

        try:
            query = db.query(PlatformAPIKey).filter(PlatformAPIKey.id == key_id)

            if tenant_id is not None:
                query = query.filter(PlatformAPIKey.tenant_id == tenant_id)

            return query.one_or_none()

        except Exception:
            logger.exception("Failed to fetch API key | key_id=%s", key_id)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def update_key(
        self,
        db,
        *,
        key_id: str,
        tenant_id: Optional[str] = None,
        name: str | None = None,
        permissions: list[str] | None = None,
        rate_limit_per_minute: int | None = None,
        expires_at: datetime | None = None,
        clear_expiration: bool = False,
    ):
        """
        Partial update of a key's metadata. Only fields explicitly
        passed (not None) are changed -- except expires_at, which needs
        clear_expiration=True to remove an existing expiration, since
        expires_at=None is also the default "don't change this" value
        and the two need to be distinguishable.

        Does not, and cannot, change the key's actual secret value --
        see rotate_key for that. Returns None (not an exception) if the
        key doesn't exist or doesn't belong to tenant_id.
        """

        record = self.get_key(db, key_id=key_id, tenant_id=tenant_id)

        if record is None:
            return None

        try:
            if name is not None:
                record.name = name

            if permissions is not None:
                record.permissions = json.dumps(permissions)

            if rate_limit_per_minute is not None:
                record.rate_limit_per_minute = rate_limit_per_minute

            if clear_expiration:
                record.expires_at = None
            elif expires_at is not None:
                record.expires_at = expires_at

            db.commit()
            return record

        except Exception:
            logger.exception("Failed to update API key | key_id=%s", key_id)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def revoke_key(self, db, *, key_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        Revoke a key. Immediate and permanent -- there's no un-revoke,
        only rotate_key or create_key for a replacement. Scoped to
        tenant_id if given, so a tenant can't revoke another tenant's
        key by guessing its id. Returns False (not an exception) if the
        key doesn't exist, doesn't belong to tenant_id, or is already
        revoked.
        """

        record = self.get_key(db, key_id=key_id, tenant_id=tenant_id)

        if record is None or record.revoked_at is not None:
            return False

        try:
            record.is_active = False
            record.revoked_at = datetime.now(UTC)
            db.commit()
            return True

        except Exception:
            logger.exception("Failed to revoke API key | key_id=%s", key_id)
            try:
                db.rollback()
            except Exception:
                pass
            return False

    def rotate_key(self, db, *, key_id: str, tenant_id: Optional[str] = None):
        """
        Issue a new secret value for an existing key record, keeping
        its id/name/permissions/tenant/rate limit intact -- unlike
        revoke + create_key, an integration referencing this key's id
        (for audit/config purposes) doesn't need to change anything but
        the secret itself. The old secret stops working the instant
        this succeeds. Returns (raw_key, record), or (None, None) if
        the key doesn't exist, doesn't belong to tenant_id, or is
        already revoked (a revoked key can't be rotated back to life --
        create a new one instead).
        """

        record = self.get_key(db, key_id=key_id, tenant_id=tenant_id)

        if record is None or record.revoked_at is not None or not record.is_active:
            return None, None

        raw_key = self.generate_key(prefix=record.key_prefix)

        try:
            record.key_hash = self._hash_key(raw_key)
            record.key_suffix = self._suffix(raw_key)
            record.last_used_at = None
            db.commit()
            return raw_key, record

        except Exception:
            logger.exception("Failed to rotate API key | key_id=%s", key_id)
            try:
                db.rollback()
            except Exception:
                pass
            return None, None


# ---------------------------------------------------------
# Singleton
# ---------------------------------------------------------

api_key_service = APIKeyService()