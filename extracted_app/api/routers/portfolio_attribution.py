from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request

from api.auth import get_current_user
from api.auth.models import AuthenticatedUser

from api.responses import ResponseBuilder
from api.schemas.common import ApiResponse

from api.services.module_registry import (
    get_module_registry,
)


router = APIRouter(
    prefix="/api/v1/portfolio",
    tags=["Portfolio"],
)


@router.get(
    "/{portfolio_id}/attribution",
    response_model=ApiResponse,
)
async def get_portfolio_attribution(
    portfolio_id: str,
    request: Request,
    registry=Depends(
        get_module_registry,
    ),
    current_user: AuthenticatedUser = Depends(
        get_current_user,
    ),
):
    """
    Portfolio Trade Attribution

    Returns:

    • Summary
    • Recommendation → Trade linkage
    • Signal attribution
    • Sector attribution
    • Conviction band attribution
    • Open recommendation exposure
    """

    service = registry.portfolio_attribution()

    report = service.get_attribution(
        tenant_id=current_user.tenant_id,
        portfolio_id=portfolio_id,
    )

    if report is None:

        return ResponseBuilder.not_found(
            request=request,
            message="Portfolio not found.",
        )

    return ResponseBuilder.success(
        request=request,
        data=report,
    )