"""
api/routers/ipo.py

IPO Router

REST endpoints under /api/v1/ipo: calendar list, single-event detail.
No business logic lives here -- see api.services.ipo_api_service and
modules.ipo.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.exceptions import NotFound
from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1/ipo",
    tags=["IPO"],
)


@router.get("/calendar")
async def get_ipo_calendar(
    request: Request,
    status: str | None = None,
    search: str | None = None,
    limit: int = 500,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ipo.read")),
):
    """
    IPO events for the authenticated caller's tenant, optionally
    filtered by status (upcoming/priced/withdrawn) and/or free-text
    search across company name, symbol, sector, and industry.
    """
    service = registry.ipo()

    data = service.list_calendar(
        tenant_id=current_user.tenant_id,
        status=status,
        search=search,
        limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/{event_id}")
async def get_ipo_event(
    event_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ipo.read")),
):
    """Single IPO event by id, including its full description and raw source payload."""

    service = registry.ipo()

    event = service.get_event(
        tenant_id=current_user.tenant_id,
        event_id=event_id,
    )

    if event is None:
        raise NotFound("IPO event not found.")

    return ResponseBuilder.success(request=request, data=event)