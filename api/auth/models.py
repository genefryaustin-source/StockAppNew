"""
Authentication Models

Shared authentication and authorization models used
throughout the StockApp Platform API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


# ---------------------------------------------------------
# Permission
# ---------------------------------------------------------

class Permission(BaseModel):
    """
    Individual permission.
    """

    name: str

    description: Optional[str] = None


# ---------------------------------------------------------
# Role
# ---------------------------------------------------------

class Role(BaseModel):
    """
    User role.
    """

    name: str

    permissions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------
# Authenticated User
# ---------------------------------------------------------

class AuthenticatedUser(BaseModel):
    """
    Represents an authenticated platform user.
    """

    authenticated: bool = False

    user_id: Optional[str] = None

    username: Optional[str] = None

    email: Optional[str] = None

    tenant_id: Optional[str] = None

    portfolio_id: Optional[str] = None

    account_id: Optional[str] = None

    roles: list[str] = Field(default_factory=list)

    permissions: list[str] = Field(default_factory=list)

    is_super_admin: bool = False

    token_type: str = "Bearer"

    jti: Optional[str] = None

    issued_at: Optional[datetime] = None

    expires_at: Optional[datetime] = None


# ---------------------------------------------------------
# API Client
# ---------------------------------------------------------

class APIClient(BaseModel):
    """
    External API client.
    """

    client_id: str

    client_name: str

    tenant_id: Optional[str] = None

    active: bool = True

    permissions: list[str] = Field(default_factory=list)

    rate_limit_per_minute: int = 100

    expires_at: Optional[datetime] = None


# ---------------------------------------------------------
# JWT Claims
# ---------------------------------------------------------

class JWTClaims(BaseModel):
    """
    JWT payload.
    """

    sub: str

    tenant_id: Optional[str] = None

    portfolio_id: Optional[str] = None

    account_id: Optional[str] = None

    roles: list[str] = Field(default_factory=list)

    permissions: list[str] = Field(default_factory=list)

    is_super_admin: bool = False

    # Unique per issued token -- this is what a logout revokes. JWTs are
    # otherwise stateless (valid purely by signature + expiry, with no
    # server-side record), so without a per-token identity there would
    # be nothing for a logout endpoint to actually invalidate; it could
    # only ever be a client-side no-op ("please discard this token"),
    # not a real, enforced logout.
    jti: str = Field(default_factory=lambda: str(uuid.uuid4()))

    exp: Optional[int] = None

    iat: Optional[int] = None


# ---------------------------------------------------------
# Login Request
# ---------------------------------------------------------

class LoginRequest(BaseModel):

    username: str

    password: str


class RefreshRequest(BaseModel):

    refresh_token: str


class LogoutRequest(BaseModel):

    # Optional: if the mobile app also sends the refresh token it was
    # issued at login, logout revokes that too, so the session can't
    # be silently extended via POST /auth/refresh after logging out.
    # The access token itself is always revoked regardless (it's the
    # one authenticating this very request).
    refresh_token: str | None = None


class PreferencesUpdateRequest(BaseModel):

    theme: str | None = None

    default_workspace: str | None = None

    notifications: bool | None = None


# ---------------------------------------------------------
# Token Response
# ---------------------------------------------------------

class TokenResponse(BaseModel):

    access_token: str

    refresh_token: str

    token_type: str = "Bearer"

    expires_in: int

    refresh_expires_in: int

    user: dict

    tenant: dict

    platform: dict

    capabilities: dict

    preferences: dict