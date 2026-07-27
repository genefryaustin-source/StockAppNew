"""
api/routers/api_keys.py

API Key Management Router (Tenant Self-Service)

REST endpoints under /api/v1/api-keys for the full lifecycle of API
keys that external systems use to authenticate against this platform's
own REST API: create, list, get, update, rotate, revoke.

Every endpoint here is scoped to the authenticated caller's own
tenant_id (never a client-supplied one) -- a tenant can fully manage
its own keys, but never another tenant's. For cross-tenant management
(a platform super admin controlling API access for every company on
the platform), see api/routers/admin_api_keys.py instead, which is the
same underlying service with tenant scoping turned off and a higher
permission bar.

Requires the "admin.api_keys" permission -- in development mode, the
dev bypass grants is_super_admin=True, which satisfies every permission
check automatically (see api.auth.permissions.has_permission), so this
requires no setup to keep testing locally. In any other environment, a
real caller needs a JWT or an existing API key carrying that
permission -- which means the very first key for a tenant has to be
issued another way (a JWT-authenticated admin session, or a super admin
using the /admin/api-keys routes to create it on that tenant's behalf),
since there's no bootstrap path from nothing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.exceptions import BadRequest, Forbidden, NotFound
from api.responses import ResponseBuilder

from api.dependencies import get_db

from api.schemas.api_keys import APIKeyCreateRequest, APIKeyUpdateRequest
from api.serializers.api_keys import serialize_api_key, serialize_api_keys


router = APIRouter(
    prefix="/api/v1/api-keys",
    tags=["API Keys"],
)


@router.post("", status_code=201)
async def create_api_key(
    payload: APIKeyCreateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.api_keys"),
    ),
):
    """
    Create a new API key for the authenticated caller's tenant.

    The raw key is returned exactly once, in this response, under
    "raw_key" -- it is never stored and can never be retrieved again.
    Store it now; if it's lost, use /rotate to issue a new secret for
    the same key record, or revoke this one and create a new key.
    """

    invalid = payload.invalid_permissions()
    if invalid:
        raise BadRequest(
            "Unrecognized permission(s).",
            details={"invalid_permissions": invalid},
        )

    from api.auth.api_keys import api_key_service

    raw_key, record, error_reason = api_key_service.create_key(
        db,
        tenant_id=current_user.tenant_id,
        name=payload.name,
        permissions=payload.permissions,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        expires_at=payload.expires_at,
        created_by_user_id=current_user.user_id,
    )

    if record is None:
        raise Forbidden(error_reason or "Unable to create API key.")

    data = serialize_api_key(record)
    data["raw_key"] = raw_key

    return ResponseBuilder.created(request=request, data=data)


@router.get("")
async def list_api_keys(
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.api_keys"),
    ),
):
    """
    Every API key for the authenticated caller's tenant. Never includes
    the raw key or its hash -- only display metadata (name, masked
    prefix/suffix, permissions, status, timestamps).
    """

    from api.auth.api_keys import api_key_service

    records = api_key_service.list_keys(db, tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(
        request=request,
        data={
            "tenant_id": current_user.tenant_id,
            "key_count": len(records),
            "keys": serialize_api_keys(records),
        },
    )


@router.get("/{key_id}")
async def get_api_key(
    key_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.api_keys"),
    ),
):
    """Single API key by id, scoped to the caller's own tenant."""

    from api.auth.api_keys import api_key_service

    record = api_key_service.get_key(
        db, key_id=key_id, tenant_id=current_user.tenant_id
    )

    if record is None:
        raise NotFound("API key not found.")

    return ResponseBuilder.success(request=request, data=serialize_api_key(record))


@router.patch("/{key_id}")
async def update_api_key(
    key_id: str,
    payload: APIKeyUpdateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.api_keys"),
    ),
):
    """
    Update a key's name, permissions, rate limit, or expiration. Only
    fields present in the request body are changed. Cannot change the
    key's actual secret value -- use /rotate for that.
    """

    invalid = payload.invalid_permissions()
    if invalid:
        raise BadRequest(
            "Unrecognized permission(s).",
            details={"invalid_permissions": invalid},
        )

    from api.auth.api_keys import api_key_service

    record = api_key_service.update_key(
        db,
        key_id=key_id,
        tenant_id=current_user.tenant_id,
        name=payload.name,
        permissions=payload.permissions,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        expires_at=payload.expires_at,
        clear_expiration=payload.clear_expiration,
    )

    if record is None:
        raise NotFound("API key not found.")

    return ResponseBuilder.success(request=request, data=serialize_api_key(record))


@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.api_keys"),
    ),
):
    """
    Issue a new secret for an existing key, keeping its id, name,
    permissions, and rate limit intact -- the old secret stops working
    immediately. Unlike revoke + create, an integration that references
    this key's id doesn't need to change anything but the secret value.

    The new raw key is returned exactly once, under "raw_key", the same
    as at creation.
    """

    from api.auth.api_keys import api_key_service

    raw_key, record = api_key_service.rotate_key(
        db, key_id=key_id, tenant_id=current_user.tenant_id
    )

    if record is None:
        raise NotFound("API key not found, or already revoked.")

    data = serialize_api_key(record)
    data["raw_key"] = raw_key

    return ResponseBuilder.success(request=request, data=data)


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.api_keys"),
    ),
):
    """
    Revoke an API key. Immediate and permanent -- there's no
    un-revoke, only /rotate or creating a new key. Scoped to the
    caller's own tenant, so one tenant can't revoke another tenant's
    key even by guessing its id.
    """

    from api.auth.api_keys import api_key_service

    ok = api_key_service.revoke_key(
        db,
        key_id=key_id,
        tenant_id=current_user.tenant_id,
    )

    if not ok:
        raise NotFound("API key not found, or already revoked.")

    return ResponseBuilder.success(
        request=request,
        data={"id": key_id, "revoked": True},
    )