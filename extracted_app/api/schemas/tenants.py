"""
api/schemas/tenants.py

Tenant Admin Request Schemas

Pydantic request bodies for POST /api/v1/admin/tenants and
PUT /api/v1/admin/tenants/{id}.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenantCreateRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=200)

    platform_api_access_enabled: bool = Field(
        default=False,
        description=(
            "Whether this tenant can create/use external API keys "
            "(api.auth.api_keys.PlatformAPIKey) from day one. Off by "
            "default -- a new tenant has no external API access until "
            "explicitly granted. Can be changed later via "
            "modules.admin.tenant_service.set_platform_api_access "
            "(currently only exposed through the admin Streamlit UI, "
            "not yet its own REST endpoint)."
        ),
    )


class TenantUpdateRequest(BaseModel):
    """Rename only -- TenantService.update_tenant doesn't touch anything else."""

    name: str = Field(..., min_length=1, max_length=200)


class ModuleEntitlementUpdateRequest(BaseModel):

    enabled: bool