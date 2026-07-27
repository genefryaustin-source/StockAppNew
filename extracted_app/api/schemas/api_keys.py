"""
api/schemas/api_keys.py

API Key Request/Response Schemas
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from api.auth.permissions import PERMISSIONS


class APIKeyCreateRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=120)

    permissions: list[str] = Field(default_factory=list)

    rate_limit_per_minute: int = Field(default=100, gt=0, le=10000)

    expires_at: datetime | None = None

    def invalid_permissions(self) -> list[str]:
        """
        Returns any requested permission that isn't in the recognized
        PERMISSIONS catalog. Called explicitly by the router, which
        rejects the request with a 400 listing these rather than
        silently dropping them -- a typo'd permission name should never
        produce a key that silently has less access than the caller
        thinks it does.
        """
        return [p for p in self.permissions if p not in PERMISSIONS]


class AdminAPIKeyCreateRequest(APIKeyCreateRequest):
    """
    Same as APIKeyCreateRequest, plus an explicit target tenant_id --
    only used on the super-admin routes (api/routers/admin_api_keys.py),
    where the caller is creating a key on behalf of a tenant that isn't
    necessarily their own. The tenant self-service routes never accept
    a client-supplied tenant_id; they always use the caller's own.
    """

    tenant_id: str = Field(..., min_length=1)


class APIKeyUpdateRequest(BaseModel):
    """
    Partial update -- every field is optional, only fields explicitly
    provided are changed. Cannot change the key's actual secret value;
    see the /rotate endpoint for that.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)

    permissions: list[str] | None = None

    rate_limit_per_minute: int | None = Field(default=None, gt=0, le=10000)

    expires_at: datetime | None = None

    clear_expiration: bool = False

    def invalid_permissions(self) -> list[str]:
        if self.permissions is None:
            return []
        return [p for p in self.permissions if p not in PERMISSIONS]