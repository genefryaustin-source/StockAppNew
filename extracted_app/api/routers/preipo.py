"""
api/routers/preipo.py

Pre-IPO Router

REST endpoints under /api/v1/preipo: company list. No business logic
lives here -- see api.services.preipo_api_service and
modules.preipo.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1/preipo",
    tags=["Pre-IPO"],
)


@router.get("/companies")
async def get_preipo_companies(
    request: Request,
    search: str | None = None,
    min_score: float | None = None,
    limit: int = 500,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("preipo.read")),
):
    """
    Pre-IPO companies tracked for the authenticated caller's tenant,
    optionally filtered by free-text search (company name, ticker
    hint, sector) and/or a minimum IPO probability score, sorted by
    that score descending.
    """
    service = registry.preipo()

    data = service.list_companies(
        tenant_id=current_user.tenant_id,
        search=search,
        min_score=min_score,
        limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)