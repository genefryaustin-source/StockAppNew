"""
Authentication Manager

Central authentication orchestrator.

All authentication mechanisms are coordinated here.

Supported:

    • JWT

    • API Keys

Future:

    • OAuth

    • OpenID Connect

    • Azure AD

    • Google

    • GitHub

    • Service Accounts

    • mTLS
"""

from __future__ import annotations

from fastapi.security import HTTPAuthorizationCredentials

from api.auth.api_keys import api_key_service
from api.auth.jwt import jwt_service
from api.auth.models import AuthenticatedUser
from api.exceptions import Unauthorized


class AuthenticationManager:

    """
    Central authentication coordinator.
    """

    def authenticate(

        self,

        bearer: HTTPAuthorizationCredentials | None,

        api_key: str | None,

        db=None,

    ) -> AuthenticatedUser:

        #
        # JWT
        #

        if bearer:

            try:

                user = jwt_service.get_authenticated_user(
                    bearer.credentials,
                )

            except Exception as exc:

                raise Unauthorized(
                    "Invalid authentication token.",
                    details={
                        "reason": str(exc),
                    },
                ) from exc

            if db is not None:
                from api.auth.token_revocation import is_token_revoked

                if is_token_revoked(db, jti=user.jti):
                    raise Unauthorized(
                        "This token has been logged out. Please log in again.",
                    )

            return user

        #
        # API Key
        #

        if api_key:

            client = api_key_service.validate_key(
                db,
                api_key,
            )

            if client is None:

                raise Unauthorized(
                    "Invalid API key.",
                )

            return AuthenticatedUser(

                authenticated=True,

                user_id=client.client_id,

                username=client.client_name,

                tenant_id=client.tenant_id,

                permissions=client.permissions,

                token_type="API Key",

            )

        #
        # Anonymous
        #

        raise Unauthorized(
            "Authentication required.",
        )


authentication_manager = AuthenticationManager()