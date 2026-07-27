"""
api/routers/market.py

Market Router

REST endpoints under /api/v1/market for macro, bond, commodity, and
mover data. No business logic lives here -- see
api.services.market_api_service and its module docstring for exactly
which real, existing module backs each section.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1/market",
    tags=["Market"],
)


@router.get("/macro-dashboard")
async def get_macro_dashboard(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Full macro snapshot: Treasury yield curve, credit spreads (HY/IG
    option-adjusted spreads), inflation breakevens, Fed funds rate,
    VIX term structure, and market proxies -- real FRED (Federal
    Reserve) + Yahoo Finance data.
    """
    service = registry.market()

    data = service.get_macro_dashboard()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/bond-market")
async def get_bond_market(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Bond-market-specific slice of the same macro data: Treasury yield
    curve, credit spreads, and bond ETF proxies (IEF 7-10Y Treasury,
    TIP inflation-protected, TLT 20+Y Treasury).
    """
    service = registry.market()

    data = service.get_bond_market()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/commodities")
async def get_commodities(
    request: Request,
    category: str | None = None,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Real Yahoo Finance futures prices across five sectors: precious
    metals, energy, industrial metals, agriculture, and livestock (20
    contracts total). Optionally scope to one sector via ?category=
    (e.g. "Energy") -- an unscoped response's "categories" field lists
    valid names.
    """
    service = registry.market()

    data = service.get_commodities(category=category)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/movers")
async def get_market_movers(
    request: Request,
    universe_id: str | None = None,
    limit: int = 20,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Top gainers/losers for this tenant's universe -- the same data
    the live "Market Overview" page's movers table uses. Defaults to
    the tenant's first configured universe if universe_id is omitted.
    """
    service = registry.market()

    data = service.get_market_movers(
        tenant_id=current_user.tenant_id, universe_id=universe_id, limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/status")
async def get_market_status(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """Current NYSE session status and local times for New York, London, Tokyo, and Hong Kong."""

    service = registry.market()

    data = service.get_market_status()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/indices")
async def get_major_indices(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """Real Yahoo Finance data for major US and global indices, with 5-day sparklines."""

    service = registry.market()

    data = service.get_major_indices()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/sectors")
async def get_sector_performance(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Real sector-level 1-day performance for this tenant's own tracked
    universe, with the top movers driving each sector's move.
    """
    service = registry.market()

    data = service.get_sector_performance(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/breadth-sentiment")
async def get_breadth_sentiment(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    VIX, Treasury yields, and market breadth (this tenant's own
    tracked universe). No put/call ratio -- no data source for this
    exists in this codebase; this section is honest about that gap
    rather than fabricating a number.
    """
    service = registry.market()

    data = service.get_breadth_sentiment(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/calendar")
async def get_economic_calendar(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """Real, live US macro release calendar (CPI, GDP, employment, retail sales, PPI) from FRED."""

    service = registry.market()

    data = service.get_economic_calendar()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/watchlist-highlights")
async def get_watchlist_highlights(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """This tenant's watchlists, each symbol enriched with current price and 1-day % change."""

    service = registry.market()

    data = service.get_watchlist_highlights(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/search")
async def search_symbols(
    request: Request,
    query: str,
    limit: int = 10,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Prefix-match search against this tenant's own tracked universe
    symbols -- not a general, market-wide ticker search (no such
    database is wired into this codebase).
    """
    service = registry.market()

    data = service.search_symbols(tenant_id=current_user.tenant_id, query=query, limit=limit)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/dashboard")
async def get_market_dashboard(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("market.read")),
):
    """
    Every Market tab section in one response: market status, major
    indices, breadth/sentiment, movers, sector performance, watchlist
    highlights, and the economic calendar. Each section fails
    independently.
    """
    service = registry.market()

    data = service.get_market_dashboard(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)