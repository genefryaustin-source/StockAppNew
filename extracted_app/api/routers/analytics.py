"""
api/routers/analytics.py

Analytics Router

REST endpoints under /api/v1 for tenant-wide (not portfolio-scoped)
recommendations, analytics, and risk. For the portfolio-scoped
equivalents, see api/routers/portfolio.py.

GET /api/v1/research is deliberately not included here. The backing
modules/research/ engines (analyst consensus, market regime, catalyst
tracking, earnings intelligence, sector rotation, and others) don't
call any real market data, fundamentals, or analyst source -- they
generate deterministic pseudo-random scores seeded from a hash of the
ticker symbol (see modules/research/research_utils.py:_stable_score).
AAPL gets the same "analyst consensus" and "catalysts" every time,
forever, regardless of what's actually happening with Apple. Wiring
that up behind a real-looking REST endpoint would present fabricated
data as legitimate research, which isn't something to ship silently --
flagging this for a decision on how to proceed rather than building it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.permissions import require_permission
from api.auth.models import AuthenticatedUser

from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1",
    tags=["Analytics"],
)


@router.get("/recommendations")
async def get_recommendations(
    request: Request,
    status: str | None = None,
    limit: int = 50,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("recommendations.read")),
):
    """
    Tenant-wide recommendation feed across every portfolio. For a
    single portfolio's recommendations, use
    /api/v1/portfolio/{portfolio_id}/recommendations instead.
    """
    service = registry.recommendations_feed()

    data = service.get_recommendations(
        tenant_id=current_user.tenant_id,
        status=status,
        limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/analytics")
async def get_analytics(
    request: Request,
    symbol: str,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Latest analytics snapshot (composite/quality/growth/value/momentum/
    risk scores) for a single symbol, scoped to the authenticated
    user's tenant. available=False (not an error) if no snapshot
    exists for this symbol yet.
    """
    service = registry.analytics_feed()

    data = service.get_analytics(
        tenant_id=current_user.tenant_id,
        symbol=symbol,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/risk")
async def get_risk(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Tenant-wide risk snapshot across every active portfolio. For a
    single portfolio's risk, use /api/v1/portfolio/{portfolio_id}/risk
    or /api/v1/portfolio/{portfolio_id}/health instead.
    """
    service = registry.risk_feed()

    data = service.get_risk(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)