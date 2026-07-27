"""
api/routers/admin_api_keys.py

API Key Management Router (Super Admin)

REST endpoints under /api/v1/admin/api-keys for platform-level control
over API keys across every tenant/company on the platform -- creating a
key on a tenant's behalf, auditing every key that exists, or revoking
access for any tenant regardless of who created the key.

This is the same underlying api.auth.api_keys.APIKeyService as the
tenant self-service routes (api/routers/api_keys.py); the only
difference is tenant_id scoping is turned off here (every call passes
tenant_id=None to the service, or an explicit target tenant_id for
create), and the permission bar is higher: "admin.system" rather than
"admin.api_keys". A key that only has "admin.api_keys" (a normal
tenant's own admin) cannot reach these routes -- only a real platform
super admin (is_super_admin=True, which auto-satisfies every
permission check) or an API key explicitly granted "admin.system" can.

In development mode the dev bypass grants is_super_admin=True, so these
routes work with no setup while testing locally, exactly like every
other endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.exceptions import BadRequest, NotFound
from api.responses import ResponseBuilder

from api.dependencies import get_db

from api.schemas.api_keys import AdminAPIKeyCreateRequest, APIKeyUpdateRequest
from api.serializers.api_keys import serialize_api_key, serialize_api_keys


router = APIRouter(
    prefix="/api/v1/admin/api-keys",
    tags=["API Keys (Admin)"],
)


@router.post("", status_code=201)
async def admin_create_api_key(
    payload: AdminAPIKeyCreateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.system"),
    ),
):
    """
    Create a new API key on behalf of any tenant -- e.g. onboarding a
    new external partner/company. Unlike the self-service create
    endpoint, tenant_id is a required field in the request body here,
    not implied by the caller's own identity.

    The raw key is returned exactly once, under "raw_key".
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
        tenant_id=payload.tenant_id,
        name=payload.name,
        permissions=payload.permissions,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        expires_at=payload.expires_at,
        created_by_user_id=current_user.user_id,
    )

    if record is None:
        raise BadRequest(error_reason or "Unable to create API key.")

    data = serialize_api_key(record, include_tenant=True)
    data["raw_key"] = raw_key

    return ResponseBuilder.created(request=request, data=data)


@router.get("")
async def admin_list_api_keys(
    request: Request,
    tenant_id: str | None = None,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.system"),
    ),
):
    """
    Every API key on the platform, across every tenant -- or, with
    ?tenant_id=, every key for one specific tenant (the admin
    equivalent of the self-service list, for looking at a company's
    keys without impersonating them).
    """

    from api.auth.api_keys import api_key_service

    records = api_key_service.list_keys(db, tenant_id=tenant_id)

    return ResponseBuilder.success(
        request=request,
        data={
            "tenant_id": tenant_id,
            "key_count": len(records),
            "keys": serialize_api_keys(records, include_tenant=True),
        },
    )


@router.get("/{key_id}")
async def admin_get_api_key(
    key_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.system"),
    ),
):
    """Single API key by id, regardless of which tenant owns it."""

    from api.auth.api_keys import api_key_service

    record = api_key_service.get_key(db, key_id=key_id, tenant_id=None)

    if record is None:
        raise NotFound("API key not found.")

    return ResponseBuilder.success(
        request=request, data=serialize_api_key(record, include_tenant=True)
    )


@router.patch("/{key_id}")
async def admin_update_api_key(
    key_id: str,
    payload: APIKeyUpdateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.system"),
    ),
):
    """
    Update any key's name, permissions, rate limit, or expiration,
    regardless of which tenant owns it. Cannot change the key's actual
    secret value -- use /rotate for that.
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
        tenant_id=None,
        name=payload.name,
        permissions=payload.permissions,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        expires_at=payload.expires_at,
        clear_expiration=payload.clear_expiration,
    )

    if record is None:
        raise NotFound("API key not found.")

    return ResponseBuilder.success(
        request=request, data=serialize_api_key(record, include_tenant=True)
    )


@router.post("/{key_id}/rotate")
async def admin_rotate_api_key(
    key_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.system"),
    ),
):
    """
    Issue a new secret for any tenant's key, regardless of who created
    it. The new raw key is returned exactly once, under "raw_key".
    """

    from api.auth.api_keys import api_key_service

    raw_key, record = api_key_service.rotate_key(db, key_id=key_id, tenant_id=None)

    if record is None:
        raise NotFound("API key not found, or already revoked.")

    data = serialize_api_key(record, include_tenant=True)
    data["raw_key"] = raw_key

    return ResponseBuilder.success(request=request, data=data)


@router.delete("/{key_id}")
async def admin_revoke_api_key(
    key_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.system"),
    ),
):
    """
    Revoke any tenant's API key -- e.g. offboarding a partner, or
    responding to a compromised credential regardless of who owns it.
    Immediate and permanent.
    """

    from api.auth.api_keys import api_key_service

    ok = api_key_service.revoke_key(db, key_id=key_id, tenant_id=None)

    if not ok:
        raise NotFound("API key not found, or already revoked.")

    return ResponseBuilder.success(
        request=request,
        data={"id": key_id, "revoked": True},
    )