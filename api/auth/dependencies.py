"""
Authentication Dependencies
"""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from api.auth.authentication_manager import (
    authentication_manager,
)



from api.auth.security import (
    bearer_scheme,
    api_key_scheme,
)
from api.config import settings
from api.auth.models import AuthenticatedUser
from api.dependencies import get_db

def get_current_user(
    bearer: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme,
    ),
    api_key: str | None = Depends(
        api_key_scheme,
    ),
    db=Depends(get_db),
) -> AuthenticatedUser:

    #
    # Development bypass
    #
    if settings.environment.lower() == "development":

        return AuthenticatedUser(
            authenticated=True,
            user_id="development",
            username="developer",
            tenant_id="tenant_default",
            email="developer@localhost",
            roles=["super_admin"],
            is_super_admin=True,
            token_type="Development",
        )

    return authentication_manager.authenticate(
        bearer,
        api_key,
        db,
    )