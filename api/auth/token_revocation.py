"""
api/auth/token_revocation.py

Token Revocation

JWTs are stateless by design -- valid purely by signature and expiry,
with no server-side record of having been issued. That means a logout
endpoint can't do anything meaningful on its own; there's nothing to
invalidate. This module is what makes logout real: a small denylist of
revoked token ids (JWTClaims.jti), checked on every JWT-authenticated
request.

Deliberately NOT hooked into API key authentication -- platform API
keys (api.auth.api_keys.PlatformAPIKey) already have their own
is_active/revoked_at fields and revoke_key() method; this is JWT-only.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


def revoke_token(
    db,
    *,
    jti: str,
    tenant_id: str | None,
    user_id: str | None,
    expires_at: datetime | None,
) -> bool:
    """
    Marks a token's jti as revoked. expires_at should be the token's
    own exp (as a naive UTC datetime) -- used only so this row can be
    safely purged once that time has passed, since the token is
    already rejected by JWT expiry validation at that point regardless
    of this table. Falls back to a 24-hour window if the token had no
    exp for some reason, so a revocation entry is never accidentally
    unbounded. Returns True on success, False (not an exception) on any
    database error -- a failed revocation should surface as a clear
    error to the caller, not crash the request.
    """

    from modules.db.models import RevokedToken

    try:
        db.rollback()
    except Exception:
        pass

    try:
        existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).one_or_none()

        if existing is not None:
            return True

        safe_expires_at = expires_at
        if safe_expires_at is not None and safe_expires_at.tzinfo is not None:
            safe_expires_at = safe_expires_at.replace(tzinfo=None)

        if safe_expires_at is None:
            from datetime import timedelta
            safe_expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=24)

        db.add(RevokedToken(
            jti=jti,
            tenant_id=tenant_id,
            user_id=user_id,
            expires_at=safe_expires_at,
        ))
        db.commit()

        _purge_expired(db)

        return True

    except Exception:
        logger.exception("Failed to revoke token | jti=%s", jti)
        try:
            db.rollback()
        except Exception:
            pass
        return False


def is_token_revoked(db, *, jti: str | None) -> bool:
    """
    Whether a token's jti has been revoked. Fails open to "not
    revoked" on a database error -- a database hiccup here shouldn't
    lock every authenticated user out of the API; the same tradeoff
    api.auth.api_keys.APIKeyService.validate_key makes for its own
    lookups. A jti of None (an older token issued before this field
    existed, or a malformed one) is treated as never revoked, since
    there's nothing to look up.
    """

    if not jti:
        return False

    from modules.db.models import RevokedToken

    try:
        db.rollback()
    except Exception:
        pass

    try:
        return db.query(RevokedToken).filter(RevokedToken.jti == jti).one_or_none() is not None
    except Exception:
        logger.exception("Failed to check token revocation | jti=%s", jti)
        try:
            db.rollback()
        except Exception:
            pass
        return False


def _purge_expired(db) -> None:
    """
    Deletes revocation entries whose original token has already
    expired on its own -- opportunistic cleanup run inline with each
    new revocation, rather than a separate scheduled job, since this
    table is expected to stay small (only actively logged-out tokens
    within their own lifetime end up here at all).
    """

    from modules.db.models import RevokedToken

    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete(synchronize_session=False)
        db.commit()
    except Exception:
        logger.exception("Failed to purge expired revoked tokens.")
        try:
            db.rollback()
        except Exception:
            pass