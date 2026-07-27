"""
api/routers/admin_tenants.py

Tenant Admin Router

REST endpoints under /api/v1/admin/tenants for tenant CRUD: list, get,
create, rename, activate, deactivate. Wraps
modules.admin.tenant_service.TenantService -- no business logic lives
here.

Every endpoint requires the "admin.tenants" permission -- the
purpose-built permission for exactly this, distinct from the broader
"admin.system" (used by api/routers/admin_api_keys.py) and from a
tenant's own "admin.api_keys" (which cannot reach this router at all).
In development mode the dev bypass grants is_super_admin=True, which
satisfies every permission check automatically, so this requires no
setup to keep testing locally.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.exceptions import BadRequest, NotFound
from api.responses import ResponseBuilder

from api.dependencies import get_db

from api.schemas.tenants import TenantCreateRequest, TenantUpdateRequest, ModuleEntitlementUpdateRequest


router = APIRouter(
    prefix="/api/v1/admin/tenants",
    tags=["Tenant Admin"],
)


@router.get("")
async def list_tenants(
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """Every tenant on the platform, alphabetical by name."""

    from modules.admin.tenant_service import TenantService

    tenants = TenantService(db).list_tenants()

    return ResponseBuilder.success(
        request=request,
        data={"tenant_count": len(tenants), "tenants": tenants},
    )


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """Single tenant by id."""

    from modules.admin.tenant_service import TenantService

    tenant = TenantService(db).get_tenant(tenant_id)

    if tenant is None:
        raise NotFound("Tenant not found.")

    return ResponseBuilder.success(request=request, data=tenant)


@router.post("", status_code=201)
async def create_tenant(
    payload: TenantCreateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """
    Create a new tenant. platform_api_access_enabled defaults to False
    -- see api.schemas.tenants.TenantCreateRequest.
    """

    from modules.admin.tenant_service import TenantService

    service = TenantService(db)

    tenant_id = service.create_tenant(
        payload.name,
        platform_api_access_enabled=payload.platform_api_access_enabled,
    )

    if tenant_id is None:
        raise BadRequest("Unable to create tenant due to a database error.")

    tenant = service.get_tenant(tenant_id)

    return ResponseBuilder.created(request=request, data=tenant)


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """Rename a tenant."""

    from modules.admin.tenant_service import TenantService

    service = TenantService(db)

    ok = service.update_tenant(tenant_id, payload.name)

    if not ok:
        raise NotFound("Tenant not found.")

    return ResponseBuilder.success(request=request, data=service.get_tenant(tenant_id))


@router.post("/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """Activate a tenant (is_active=True)."""

    from modules.admin.tenant_service import TenantService

    service = TenantService(db)

    ok = service.activate_tenant(tenant_id)

    if not ok:
        raise NotFound("Tenant not found.")

    return ResponseBuilder.success(request=request, data=service.get_tenant(tenant_id))


@router.post("/{tenant_id}/deactivate")
async def deactivate_tenant(
    tenant_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """
    Deactivate a tenant (is_active=False). Note: unlike the platform
    API access gate (which immediately blocks authentication for
    existing keys), this flag isn't currently checked anywhere in the
    authentication path -- it only affects what shows in tenant
    listings/UI today. A deactivated tenant's existing sessions and API
    keys keep working unless platform_api_access_enabled is also
    turned off (see modules.admin.tenant_service.
    set_platform_api_access) -- worth knowing if you're using this as
    a real "cut this tenant off" action rather than just a status flag.
    """

    from modules.admin.tenant_service import TenantService

    service = TenantService(db)

    ok = service.deactivate_tenant(tenant_id)

    if not ok:
        raise NotFound("Tenant not found.")

    return ResponseBuilder.success(request=request, data=service.get_tenant(tenant_id))


@router.get("/{tenant_id}/modules")
async def get_tenant_modules(
    tenant_id: str,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """
    Which asset-class modules (stocks/options/forex/crypto) this
    tenant is licensed for -- the same values surfaced in a mobile/API
    login response's "modules" block (api/routers/auth.py) and
    enforced server-side on GET /api/v1/executive/mobile-dashboard.
    """

    from modules.admin.tenant_service import TenantService

    modules = TenantService(db).get_module_entitlements(tenant_id)

    if modules is None:
        raise NotFound("Tenant not found.")

    return ResponseBuilder.success(request=request, data=modules)


@router.put("/{tenant_id}/modules/{module}")
async def set_tenant_module(
    tenant_id: str,
    module: str,
    payload: ModuleEntitlementUpdateRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthenticatedUser = Depends(
        require_permission("admin.tenants"),
    ),
):
    """
    Grant or revoke one asset-class module for a tenant. module must
    be one of "stocks", "options", "forex", "crypto". Takes effect
    immediately -- the next login, token refresh, or GET /me for any
    user on this tenant reflects the change, and GET /api/v1/executive/
    mobile-dashboard starts returning {"available": false, "reason":
    "module_not_licensed"} for that section right away rather than
    needing a fresh login.
    """

    from modules.admin.tenant_service import TenantService

    service = TenantService(db)

    if module not in service.MODULE_COLUMNS:
        raise BadRequest(
            f"Unknown module '{module}'. Must be one of: {', '.join(service.MODULE_COLUMNS)}."
        )

    ok = service.set_module_entitlement(tenant_id, module, payload.enabled)

    if not ok:
        raise NotFound("Tenant not found.")

    return ResponseBuilder.success(request=request, data=service.get_module_entitlements(tenant_id))