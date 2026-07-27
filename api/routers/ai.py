"""
api/routers/ai.py

AI Router

REST endpoints under /api/v1/ai. No business logic lives here -- see
api.services.ai_dashboard_api_service and its module docstring for
exactly which real, existing module backs each section.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission

from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)


@router.get("/dashboard")
async def get_ai_dashboard(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """Every AI section (market regime, risk, opportunities, portfolio, execution) in one response."""

    service = registry.ai_dashboard()

    data = service.get_dashboard(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        is_super_admin=current_user.is_super_admin,
        roles=current_user.roles,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/portfolio")
async def get_ai_portfolio(
    request: Request,
    max_positions: int = 20,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """
    An AI-ranked, weighted portfolio built from this tenant's
    analytics-snapshot universe -- the same real ranking pipeline and
    portfolio construction logic backing the desktop app's "AI
    Rankings" and "AI Portfolio" pages. Reports {"available": false,
    "reason": ...} if no analytics snapshots exist yet for this
    tenant, rather than fabricating positions.
    """
    service = registry.ai_dashboard()

    data = service.get_portfolio(tenant_id=current_user.tenant_id, max_positions=max_positions)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/risk")
async def get_ai_risk(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """Portfolio risk metrics (market risk, volatility, liquidity, concentration)."""

    service = registry.ai_dashboard()

    data = service.get_risk(
        tenant_id=current_user.tenant_id,
        is_super_admin=current_user.is_super_admin,
        roles=current_user.roles,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/execution")
async def get_ai_execution(
    request: Request,
    lookback_days: int = 7,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """
    Real order/fill activity for this tenant over the lookback
    window -- order count, fill count, fill rate, and a status
    breakdown, from actual trade_orders/trade_fills records.
    """
    service = registry.ai_dashboard()

    data = service.get_execution(tenant_id=current_user.tenant_id, lookback_days=lookback_days)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/opportunities")
async def get_ai_opportunities(
    request: Request,
    limit: int = 10,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """Top-ranked opportunities by composite AI score, from stored analytics snapshots."""

    service = registry.ai_dashboard()

    data = service.get_opportunities(
        tenant_id=current_user.tenant_id,
        is_super_admin=current_user.is_super_admin,
        roles=current_user.roles,
        limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.get("/market-regime")
async def get_ai_market_regime(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """
    Current market regime (bull/bear/panic/range_bound/neutral/
    momentum_volatility), classified from real, computed statistics
    (30d/90d returns, 30d annualized volatility, 90d drawdown) on
    stored SPY price history -- not from a placeholder or hardcoded
    reading. Reports {"available": false, "reason": ...} if there
    isn't enough stored price history yet, rather than a fabricated
    regime.
    """
    service = registry.ai_dashboard()

    data = service.get_market_regime()

    return ResponseBuilder.success(request=request, data=data)


@router.get("/daily-briefing")
async def get_ai_daily_briefing(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("ai.read")),
):
    """
    A plain-language summary of market regime, risk, and top
    opportunities -- template-composed from real numbers, not
    generative-AI-written text (no LLM call is made here).
    """
    service = registry.ai_dashboard()

    data = service.get_daily_briefing(
        tenant_id=current_user.tenant_id,
        is_super_admin=current_user.is_super_admin,
        roles=current_user.roles,
    )

    return ResponseBuilder.success(request=request, data=data)