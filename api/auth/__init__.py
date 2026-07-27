"""
Authentication Package
"""

from .models import (
    APIClient,
    AuthenticatedUser,
    JWTClaims,
    LoginRequest,
    Permission,
    Role,
    TokenResponse,
)
from .jwt import JWTService
from .jwt import jwt_service
from .api_keys import APIKeyService
from .api_keys import api_key_service
from .current_user import get_current_user


from .security import (
    bearer_scheme,
    api_key_scheme,
    optional_bearer,
    optional_api_key,
)
from .permissions import (
    PERMISSIONS,
    has_permission,
    has_any_permission,
    has_all_permissions,
    require_permission,
    require_any_permission,
    require_all_permissions,
)
from .authentication_manager import (
    AuthenticationManager,
    authentication_manager,
)

from .dependencies import (
    get_current_user,
)


__all__ = [

    "Permission",

    "Role",

    "AuthenticatedUser",

    "APIClient",

    "JWTClaims",

    "LoginRequest",

    "TokenResponse",

    "JWTService",

    "jwt_service",

    "APIKeyService",

    "api_key_service",



]

__all__ += [

    "PERMISSIONS",

    "has_permission",

    "has_any_permission",

    "has_all_permissions",

    "require_permission",

    "require_any_permission",

    "require_all_permissions",

    "get_current_user",

    "bearer_scheme",

    "api_key_scheme",

    "optional_bearer",

    "optional_api_key",

    "AuthenticationManager",

    "authentication_manager",

    "get_current_user",

]
