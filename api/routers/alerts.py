"""
api/routers/alerts.py

Alerts Router

REST endpoints under /api/v1/alerts: create, list, acknowledge. No
business logic lives here -- see api.services.alerts_api_service and
modules.alerts.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.exceptions import BadRequest, NotFound
from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry

from api.schemas.alerts import AlertCreateRequest


router = APIRouter(
    prefix="/api/v1/alerts",
    tags=["Alerts"],
)


@router.post("", status_code=201)
async def create_alert(
    payload: AlertCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(
        require_permission("alerts.write"),
    ),
):
    """Create a single alert for the authenticated caller's tenant."""

    service = registry.alerts()

    result = service.create_alert(
        tenant_id=current_user.tenant_id,
        symbol=payload.symbol,
        title=payload.title,
        alert_type=payload.alert_type,
        message=payload.message,
    )

    if result is None:
        raise BadRequest("Unable to create alert due to a database error.")

    return ResponseBuilder.created(request=request, data=result)


@router.get("")
async def list_alerts(
    request: Request,
    symbol: str | None = None,
    only_unacknowledged: bool = False,
    limit: int = 200,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(
        require_permission("alerts.read"),
    ),
):
    """
    Alerts for the authenticated caller's tenant, optionally filtered
    by symbol and/or unacknowledged-only.
    """

    service = registry.alerts()

    data = service.list_alerts(
        tenant_id=current_user.tenant_id,
        symbol=symbol,
        only_unacknowledged=only_unacknowledged,
        limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(
        require_permission("alerts.write"),
    ),
):
    """
    Acknowledge an alert. Scoped to the caller's own tenant, so one
    tenant can't acknowledge another tenant's alert even by guessing
    its id.
    """

    service = registry.alerts()

    ok = service.acknowledge_alert(
        tenant_id=current_user.tenant_id,
        alert_id=alert_id,
    )

    if not ok:
        raise NotFound("Alert not found.")

    return ResponseBuilder.success(
        request=request,
        data={"id": alert_id, "acknowledged": True},
    )