"""
api/routers/options.py

Options Router

REST endpoints under /api/v1/options for order submission, order
lookup/history, reconciliation, and positions. No business logic lives
here -- see api.services.options_orders_api_service,
modules.options.options_trading_service.OptionsTradingService, and
modules.options.options_models.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth.models import AuthenticatedUser
from api.auth.permissions import require_permission
from api.auth.module_entitlements import require_module

from api.exceptions import NotFound
from api.responses import ResponseBuilder

from api.services.module_registry import get_module_registry

from api.schemas.options_orders import OptionsOrderCreateRequest


router = APIRouter(
    prefix="/api/v1/options",
    tags=["Options"],
)


@router.post("/orders", status_code=201)
async def create_options_order(
    payload: OptionsOrderCreateRequest,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.write")),
    _module_check: AuthenticatedUser = Depends(require_module("options")),
):
    """
    Submit a new options order. The response is an execution result,
    not a bare order record -- check its "success" field for whether
    the order actually executed; a rejected order (broker error,
    invalid contract, etc.) is still a 201, since a valid request was
    processed and produced a real outcome.

    Unlike stock orders, this often stays "submitted" rather than
    resolving immediately -- Alpaca options limit orders can sit open
    for a while. Use POST /options/orders/reconcile to pick up fills
    that happen after this call returns.
    """
    service = registry.options_orders()

    result = service.create_order(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        option_symbol=payload.option_symbol,
        qty=payload.qty,
        side=payload.side,
        position_intent=payload.position_intent,
        order_type=payload.order_type,
        tif=payload.tif,
        limit_price=payload.limit_price,
    )

    return ResponseBuilder.created(request=request, data=result)


@router.get("/orders/{order_id}")
async def get_options_order(
    order_id: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.read")),
):
    """Single options order by id, scoped to the caller's tenant."""

    service = registry.options_orders()

    order = service.get_order(
        tenant_id=current_user.tenant_id,
        order_id=order_id,
    )

    if order is None:
        raise NotFound("Options order not found.")

    return ResponseBuilder.success(request=request, data=order)


@router.get("/orders")
async def get_options_order_history(
    request: Request,
    limit: int = 50,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.read")),
):
    """Most recent options orders for the caller's tenant."""

    service = registry.options_orders()

    data = service.get_order_history(
        tenant_id=current_user.tenant_id,
        limit=limit,
    )

    return ResponseBuilder.success(request=request, data=data)


@router.post("/orders/reconcile")
async def reconcile_options_orders(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.write")),
):
    """
    Poll the broker for status on locally-open options orders and
    persist any fills that happened after submission returned. Options
    limit orders commonly don't fill synchronously -- call this
    periodically to catch fills submit_order's own response missed.
    """
    service = registry.options_orders()

    data = service.reconcile(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/positions")
async def get_options_positions(
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.read")),
):
    """
    Current options positions for the caller's tenant -- the persisted
    snapshot, refreshed from the broker's authoritative account state
    on every fill (via reconcile or a fast-filling submit_order).
    """
    service = registry.options_orders()

    data = service.get_positions(tenant_id=current_user.tenant_id)

    return ResponseBuilder.success(request=request, data=data)


# ==========================================================
# MARKET DATA (chains / Greeks)
# ==========================================================
# Not tenant-scoped -- options chain and Greeks data is public market
# data, the same as /quotes and /history. See
# api.services.options_market_data_api_service.

@router.get("/chains/{symbol}")
async def get_options_chain(
    symbol: str,
    request: Request,
    expiration: str | None = None,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.read")),
):
    """
    Full options chain for an underlying, grouped by expiration.
    Optionally filter to a single expiration (YYYY-MM-DD).
    available=False (not an error) if no provider could return chain
    data for this symbol.
    """
    service = registry.options_market_data()

    data = service.get_chain(symbol=symbol, expiration=expiration)

    return ResponseBuilder.success(request=request, data=data)


@router.get("/greeks/{option_symbol}")
async def get_options_greeks(
    option_symbol: str,
    request: Request,
    registry=Depends(get_module_registry),
    current_user: AuthenticatedUser = Depends(require_permission("options.read")),
):
    """
    Spot, implied volatility, and Greeks for a single option contract
    (OCC symbol format, e.g. AAPL250117C00150000) -- both whatever the
    data provider supplied directly and an independently-computed
    Black-Scholes-Merton calculation via QuantLib, so you can see
    whether they agree. available=False (not an error) if the contract
    can't be found or Greeks can't be computed for it.
    """
    service = registry.options_market_data()

    data = service.get_greeks(option_symbol=option_symbol)

    return ResponseBuilder.success(request=request, data=data)