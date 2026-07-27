"""
api/routers/market_data.py

Market Data Router

REST endpoints under /api/v1 for quotes, historical bars, watchlists,
and the analytics-based screener. No business logic lives here -- see
api.services.quotes_api_service, market_history_api_service,
watchlist_api_service, and screener_api_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.permissions import require_permission
from api.auth.models import AuthenticatedUser

from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1",
    tags=["Market Data"],
)


@router.get("/quotes/{symbol}")
async def get_quote(
    symbol: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Latest price and day-over-day change for a symbol. Not tenant-
    scoped -- market data is shared, not per-tenant. available=False
    (not an error) if no live price can be fetched.
    """
    service = registry.quotes()

    data = service.get_quote(symbol=symbol)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    request: Request,
    period: str = "1y",
    interval: str = "1d",
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Historical OHLCV bars for a symbol. Not tenant-scoped.
    available=False (not an error) if no history can be fetched.
    """
    service = registry.market_history()

    data = service.get_history(symbol=symbol, period=period, interval=interval)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/watchlists")
async def list_watchlists(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """Every watchlist for the authenticated user's tenant, with symbols."""
    service = registry.watchlists()

    data = service.list_watchlists(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/screener")
async def run_screener(
    request: Request,
    sector: str | None = None,
    min_composite: float | None = None,
    min_confidence: float | None = None,
    min_quality: float | None = None,
    min_growth: float | None = None,
    min_value: float | None = None,
    min_momentum: float | None = None,
    max_risk: float | None = None,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("analytics.read")),
):
    """
    Symbols matching the given filters against their latest analytics
    scores, scoped to the authenticated user's tenant.
    """
    service = registry.screener()

    data = service.run_screen(
        tenant_id=current_user.tenant_id,
        sector=sector,
        min_composite=min_composite,
        min_confidence=min_confidence,
        min_quality=min_quality,
        min_growth=min_growth,
        min_value=min_value,
        min_momentum=min_momentum,
        max_risk=max_risk,
    )

    return ResponseBuilder.success(request=request, data=data)