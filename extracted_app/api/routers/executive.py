"""
api/routers/executive.py

Executive Dashboard Router

REST endpoint under /api/v1/executive for the platform-wide executive
summary. No business logic lives here -- see
api.services.executive_dashboard_api_service and
modules.dashboard.executive_dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1/executive",
    tags=["Executive Dashboard"],
)


@router.get("/summary")
async def get_executive_summary(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("executive.read")),
):
    """
    Platform-wide executive summary: market breadth, research universe
    coverage, AI top pick, platform usage, data-provider health,
    analytics job queue, portfolio/risk rollups, top opportunities,
    sector leadership, earnings intelligence, and smart-money activity
    -- the same data modules.dashboard.executive_dashboard.
    render_executive_dashboard shows in the app's own Executive
    Dashboard page, scoped to the caller's tenant (or platform-wide for
    a super admin). Each section reports {"available": false, "reason":
    ...} independently if it fails, rather than failing the whole
    request.
    """
    service = registry.executive_dashboard()

    data = service.get_summary(
        tenant_id=current_user.tenant_id,
        is_super_admin=current_user.is_super_admin,
        roles=current_user.roles,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/mobile-dashboard")
async def get_executive_mobile_dashboard(
    request: Request,
    sections: str | None = None,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("executive.read")),
):
    """
    A single aggregated payload for mobile clients, combining equities,
    forex, options, crypto, a cross-asset portfolio rollup, analytics
    fabric, provider health, and platform activity -- one request
    instead of one per asset class.

    Optionally scope the response to specific sections with a
    comma-separated list, e.g. ?sections=forex,portfolio -- omit to get
    every section. Unrecognized section names are silently ignored
    rather than rejected, so a client on a slightly older or newer
    section list still gets a valid response for the ones it knows.

    Each section is independent: crypto (no trading exists yet) and any
    section that fails both report {"available": false, "reason": ...}
    in their own place rather than failing the whole request -- render
    whatever sections are present, as intended for a client that may
    not know about every asset class this platform eventually supports.
    """
    service = registry.executive_mobile_dashboard()

    requested_sections = (
        [s.strip() for s in sections.split(",") if s.strip()]
        if sections
        else None
    )

    data = service.get_mobile_dashboard(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        is_super_admin=current_user.is_super_admin,
        roles=current_user.roles,
        sections=requested_sections,
    )

    return ResponseBuilder.success(request=request, data=data)