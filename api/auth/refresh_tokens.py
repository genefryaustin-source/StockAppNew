"""
api/auth/refresh_tokens.py

Refresh Tokens

Long-lived, opaque tokens (not JWTs) that let a client obtain a new
access token without the user re-entering credentials. Only a SHA-256
hash is ever stored (modules.db.models.RefreshToken.token_hash) -- the
same pattern api.auth.api_keys.PlatformAPIKey uses for its own secret
material -- so a database read never exposes a usable token.

Rotation: every successful use revokes the presented token and issues
a brand new one in the same call. This means a refresh token is
single-use in practice, which is what makes reuse detectable -- if a
stolen token is used by an attacker before the legitimate client's
next refresh, the legitimate client's own next attempt (with the now-
already-rotated-away token) fails, which is a real signal worth acting
on rather than something to smooth over silently.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, UTC

from api.config import settings

logger = logging.getLogger(__name__)


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def issue_refresh_token(
    db,
    *,
    tenant_id: str,
    user_id: str,
    replaced_token_hash: str | None = None,
) -> tuple[str, datetime]:
    """
    Creates and stores a new refresh token, returning (raw_token,
    expires_at). The raw value is only ever returned here -- it is
    never stored or logged; only its hash is persisted.
    """

    from modules.db.models import RefreshToken

    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash(raw_token)

    expires_at = _naive_utc_now() + timedelta(days=settings.refresh_token_expiration_days)

    db.add(RefreshToken(
        token_hash=token_hash,
        tenant_id=tenant_id,
        user_id=user_id,
        expires_at=expires_at,
        replaced_token_hash=replaced_token_hash,
    ))
    db.commit()

    return raw_token, expires_at


def rotate_refresh_token(db, *, raw_token: str) -> dict | None:
    """
    Validates a presented refresh token and, if valid, revokes it and
    issues a new one in its place. Returns None (not an exception) for
    any invalid case (unknown, expired, or already-used/revoked token)
    -- the router turns that into a 401 asking the client to log in
    again, since there is no partial-credit state for a refresh token;
    it either works or the client needs a fresh login.

    On success, returns {tenant_id, user_id, refresh_token,
    refresh_expires_at} -- refresh_token is the newly issued raw token
    the caller should store going forward; the one they presented is
    now revoked and will not work again.
    """

    from modules.db.models import RefreshToken

    try:
        db.rollback()
    except Exception:
        pass

    token_hash = _hash(raw_token)

    try:
        record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).one_or_none()
    except Exception:
        logger.exception("Failed to look up refresh token.")
        try:
            db.rollback()
        except Exception:
            pass
        return None

    if record is None:
        return None

    if record.revoked_at is not None:
        # A refresh token being presented a second time (after it was
        # already rotated away by an earlier, successful refresh) is
        # not just "invalid" the way an unknown token is -- it means
        # this exact token existed and was already used once. That is
        # either the legitimate client retrying stale state, or a
        # stolen token being used after the real client already
        # rotated past it. Logged distinctly from "unknown token" so
        # this is actually visible to look into, rather than blending
        # into ordinary invalid-token noise.
        logger.warning(
            "Revoked refresh token presented again | tenant_id=%s user_id=%s",
            record.tenant_id, record.user_id,
        )
        return None

    if record.expires_at < _naive_utc_now():
        return None

    try:
        record.revoked_at = _naive_utc_now()
        db.commit()

        new_raw, new_expires_at = issue_refresh_token(
            db,
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            replaced_token_hash=token_hash,
        )

    except Exception:
        logger.exception("Failed to rotate refresh token.")
        try:
            db.rollback()
        except Exception:
            pass
        return None

    return {
        "tenant_id": record.tenant_id,
        "user_id": record.user_id,
        "refresh_token": new_raw,
        "refresh_expires_at": new_expires_at,
    }


def revoke_refresh_token(db, *, raw_token: str) -> bool:
    """
    Revokes a refresh token without issuing a replacement -- used on
    logout. Returns True whether the token existed or not (revoking a
    token that doesn't exist, or is already revoked, is not an error;
    the end state the caller wants -- this token doesn't work -- is
    already true).
    """

    from modules.db.models import RefreshToken

    try:
        db.rollback()
    except Exception:
        pass

    token_hash = _hash(raw_token)

    try:
        record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).one_or_none()

        if record is not None and record.revoked_at is None:
            record.revoked_at = _naive_utc_now()
            db.commit()

        return True

    except Exception:
        logger.exception("Failed to revoke refresh token.")
        try:
            db.rollback()
        except Exception:
            pass
        return False