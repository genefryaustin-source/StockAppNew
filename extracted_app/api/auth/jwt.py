"""
JWT Service

Responsible for:

    • Creating JWT access tokens
    • Validating JWT access tokens
    • Decoding JWT claims
    • Token expiration checking
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from jose import JWTError
from jose import jwt

from api.auth.models import AuthenticatedUser
from api.auth.models import JWTClaims
from api.config import settings
from api.exceptions import InternalServerError

# Secret values that must never be trusted outside development -- either
# the literal placeholder this app ships with, or other extremely common
# "forgot to change it" defaults seen across other projects/tutorials.
_INSECURE_SECRETS = {
    "",
    "change_me",
    "changeme",
    "secret",
    "your-secret-key",
    "jwt_secret",
    "default",
}

# HS256 signatures are only as strong as the secret's entropy -- a short
# secret is brute-forceable regardless of how "random" it looks.
_MIN_SECRET_LENGTH = 32


def _ensure_secret_is_safe_to_use(secret: str) -> None:
    """
    Refuses to let the app create or trust a JWT signed with a
    default/weak secret once it's not running in development mode.

    Checked at the point of use (not just once at import time), the
    same way the development bypass in api.auth.dependencies re-reads
    settings.environment live on every call -- so flipping environment
    at runtime (e.g. in a test, or a config reload) is respected
    immediately rather than only taking effect on the next process
    restart.

    Anyone who reads this codebase (or its dependencies) knows the
    default secret. A JWT signed with it is forgeable by anyone, for
    any tenant_id, any permissions, any user -- there is no meaningful
    difference between "no authentication" and "authentication with
    the default secret" once that's true.
    """

    if settings.environment.lower() == "development":
        return

    if (
        not secret
        or secret.strip().lower() in _INSECURE_SECRETS
        or len(secret) < _MIN_SECRET_LENGTH
    ):
        raise InternalServerError(
            "JWT_SECRET is not configured securely for this environment.",
            details={
                "environment": settings.environment,
                "reason": (
                    "JWT_SECRET is missing, is one of a small set of known "
                    "placeholder values, or is shorter than "
                    f"{_MIN_SECRET_LENGTH} characters. Set a real, random "
                    "secret via the JWT_SECRET environment variable before "
                    "running outside development mode -- a weak or default "
                    "secret lets anyone forge a valid token for any tenant."
                ),
            },
        )


class JWTService:
    """
    JSON Web Token helper.
    """

    def __init__(self):

        self.secret = settings.jwt_secret

        self.algorithm = settings.jwt_algorithm

        self.expiration_minutes = (
            settings.jwt_expiration_minutes
        )

    # --------------------------------------------------
    # Create Token
    # --------------------------------------------------

    def create_access_token(
        self,
        claims: JWTClaims,
    ) -> str:

        _ensure_secret_is_safe_to_use(self.secret)

        now = datetime.now(timezone.utc)

        expire = (
            now +
            timedelta(
                minutes=self.expiration_minutes
            )
        )

        payload = claims.model_dump()

        payload["iat"] = int(now.timestamp())

        payload["exp"] = int(expire.timestamp())

        return jwt.encode(
            payload,
            self.secret,
            algorithm=self.algorithm,
        )

    # --------------------------------------------------
    # Decode
    # --------------------------------------------------

    def decode(
        self,
        token: str,
    ) -> dict[str, Any]:

        _ensure_secret_is_safe_to_use(self.secret)

        return jwt.decode(
            token,
            self.secret,
            algorithms=[
                self.algorithm,
            ],
        )

    # --------------------------------------------------
    # Validate
    # --------------------------------------------------

    def validate(
        self,
        token: str,
    ) -> JWTClaims:

        payload = self.decode(token)

        return JWTClaims(**payload)

    # --------------------------------------------------
    # Current User
    # --------------------------------------------------

    def get_authenticated_user(
        self,
        token: str,
    ) -> AuthenticatedUser:

        claims = self.validate(token)

        return AuthenticatedUser(

            authenticated=True,

            user_id=claims.sub,

            tenant_id=claims.tenant_id,

            portfolio_id=claims.portfolio_id,

            account_id=claims.account_id,

            roles=claims.roles,

            permissions=claims.permissions,

            is_super_admin=claims.is_super_admin,

            jti=claims.jti,

            issued_at=(
                datetime.fromtimestamp(
                    claims.iat,
                    tz=timezone.utc,
                )
                if claims.iat
                else None
            ),

            expires_at=(
                datetime.fromtimestamp(
                    claims.exp,
                    tz=timezone.utc,
                )
                if claims.exp
                else None
            ),
        )


# ------------------------------------------------------
# Singleton
# ------------------------------------------------------

jwt_service = JWTService()