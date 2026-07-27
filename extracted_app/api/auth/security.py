"""
Security Configuration

Central FastAPI security definitions.

Provides:

    • Bearer Token support

    • API Key support

    • Optional authentication

These definitions automatically appear in
Swagger/OpenAPI.
"""

from __future__ import annotations

from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from fastapi.security import APIKeyHeader

#
# JWT Bearer
#

bearer_scheme = HTTPBearer(

    bearerFormat="JWT",

    auto_error=False,

)

#
# API Key
#

api_key_scheme = APIKeyHeader(

    name="X-API-Key",

    auto_error=False,

)

#
# Optional Security
#

optional_bearer = HTTPBearer(

    auto_error=False,

)

optional_api_key = APIKeyHeader(

    name="X-API-Key",

    auto_error=False,

)

#
# Header Names
#

AUTHORIZATION_HEADER = "Authorization"

API_KEY_HEADER = "X-API-Key"

TOKEN_PREFIX = "Bearer"